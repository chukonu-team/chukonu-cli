"""明文 JSON 凭据读写,用 filelock 串行化。

用户明确要求:凭据**明文**保存在 ~/.local/share/chukonu-cli/。
文件权限 0600 + 父目录 0700 是唯一保护。

ProviderCreds 数据类来自 client_core,本文件只提供文件落盘 + 多 provider 管理 +
适配 client_core.CredsProvider Protocol 的 FileCredsProvider。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from filelock import BaseFileLock, FileLock

from chukonu_cli.client_core.credentials import ProviderCreds
from chukonu_cli.paths import creds_lock, credentials_file, refresh_lock

__all__ = [
    "ProviderCreds",
    "CredsFile",
    "load",
    "save",
    "upsert_provider",
    "remove_provider",
    "delete_all",
    "FileCredsProvider",
]


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


def _lock() -> BaseFileLock:
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


def upsert_provider(
    provider: str, pc: ProviderCreds, *, make_current: bool = True
) -> CredsFile:
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


class FileCredsProvider:
    """适配 client_core.CredsProvider:从 ~/.local/share/chukonu-cli/credentials.json
    读写指定 provider 的凭据,refresh 用 per-provider filelock 串行化。
    """

    def __init__(self, provider: str | None = None):
        # provider=None 时延迟到 load() 取 current
        self._explicit = provider
        self._refresh_lock_path = (
            refresh_lock(provider) if provider else None
        )

    def _provider(self) -> str | None:
        if self._explicit:
            return self._explicit
        return load().current

    def load(self) -> ProviderCreds | None:
        p = self._provider()
        if not p:
            return None
        return load().providers.get(p)

    def save(self, pc: ProviderCreds) -> None:
        p = self._provider()
        if not p:
            raise RuntimeError("no provider context to save credentials")
        upsert_provider(p, pc)

    def clear(self) -> None:
        p = self._provider()
        if p:
            remove_provider(p)

    def refresh_lock_path(self) -> str:
        # client_core 的 Client._refresh 通过 CredsProvider 接口不直接拿锁。
        # 这里保留 hook 供 CLI 层的 Client 包装使用。
        p = self._provider() or "default"
        return str(refresh_lock(p))
