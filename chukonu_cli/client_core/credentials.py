"""client_core 凭据数据类。纯数据 + 序列化,无文件 I/O。

落盘/锁逻辑由 CLI 层 (chukonu_cli.credentials) 提供。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


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
    def from_token_response(
        cls, data: dict[str, Any], user: dict[str, Any] | None = None
    ) -> "ProviderCreds":
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
