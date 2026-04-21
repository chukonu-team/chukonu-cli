"""明文 JSON 凭据读写，用 filelock 串行化。

用户明确要求：凭据**明文**保存在 ~/.local/share/chukonu-cli/。
文件权限 0600 + 父目录 0700 是唯一保护。
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

from filelock import FileLock

from chukonu_cli.paths import creds_lock, credentials_file


@dataclass
class ProviderCreds:
    access_token: str
    refresh_token: str
    expires_at: int  # unix 秒
    token_type: str = "Bearer"
    granted_at: int = field(default_factory=lambda: int(time.time()))
    user: dict[str, Any] = field(default_factory=dict)

    def is_valid(self, skew_seconds: int = 60) -> bool:
        return self.expires_at > int(time.time()) + skew_seconds

    @classmethod
    def from_token_response(cls, data: dict[str, Any], user: dict[str, Any] | None = None) -> "ProviderCreds":
        now = int(time.time())
        expires_in = int(data.get("expires_in", 0))
        return cls(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", ""),
            expires_at=now + expires_in if expires_in else now,
            token_type=data.get("token_type", "Bearer"),
            granted_at=now,
            user=user or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "token_type": self.token_type,
            "granted_at": self.granted_at,
            "user": self.user,
        }


@dataclass
class CredsFile:
    current: str | None = None
    providers: dict[str, ProviderCreds] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "current": self.current,
            "providers": {k: v.to_dict() for k, v in self.providers.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CredsFile":
        providers: dict[str, ProviderCreds] = {}
        for k, v in (data.get("providers") or {}).items():
            providers[k] = ProviderCreds(
                access_token=v.get("access_token", ""),
                refresh_token=v.get("refresh_token", ""),
                expires_at=int(v.get("expires_at", 0)),
                token_type=v.get("token_type", "Bearer"),
                granted_at=int(v.get("granted_at", 0)),
                user=v.get("user") or {},
            )
        return cls(current=data.get("current"), providers=providers)


def _lock() -> FileLock:
    return FileLock(str(creds_lock()), timeout=10)


def load() -> CredsFile:
    path = credentials_file()
    if not path.exists():
        return CredsFile()
    with _lock():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    return CredsFile.from_dict(data)


def save(creds: CredsFile) -> None:
    path = credentials_file()
    with _lock():
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(creds.to_dict(), f, ensure_ascii=False, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        os.chmod(path, 0o600)


def upsert_provider(provider: str, pc: ProviderCreds, *, make_current: bool = True) -> CredsFile:
    creds = load()
    creds.providers[provider] = pc
    if make_current or creds.current is None:
        creds.current = provider
    save(creds)
    return creds


def remove_provider(provider: str) -> CredsFile:
    creds = load()
    creds.providers.pop(provider, None)
    if creds.current == provider:
        creds.current = next(iter(creds.providers), None)
    save(creds)
    return creds


def delete_all() -> None:
    path = credentials_file()
    with _lock():
        if path.exists():
            path.unlink()
