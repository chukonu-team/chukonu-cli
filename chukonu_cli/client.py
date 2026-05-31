"""CLI 侧 Client:复用 client_core.Client,叠加文件凭据 + per-provider refresh 锁。

对外签名保持 `Client(cfg, provider=None)` 不变,命令层无需改动。
"""
from __future__ import annotations

from filelock import FileLock

from chukonu_cli.client_core.client import Client as _CoreClient
from chukonu_cli.client_core.config import Config
from chukonu_cli.client_core.credentials import ProviderCreds
from chukonu_cli.client_core.errors import ApiError, AuthRequired
from chukonu_cli.credentials import FileCredsProvider

__all__ = ["Client", "ApiError", "AuthRequired", "Config", "ProviderCreds"]


class Client(_CoreClient):
    def __init__(self, cfg: Config, provider: str | None = None):
        self._file_creds = FileCredsProvider(provider)
        super().__init__(cfg, creds=self._file_creds)

    async def _refresh(self) -> ProviderCreds:
        # 多进程串行化:同一 provider 的 refresh 互斥,避免并发触发 RT rotation 竞争。
        # FileLock 同步获取(短暂);拿到锁后驱动父类的 async refresh。
        lock = FileLock(self._file_creds.refresh_lock_path(), timeout=30)
        with lock:
            return await super()._refresh()
