"""httpx 客户端：自动注入 Bearer；过期自动 refresh；401 重试一次。"""
from __future__ import annotations

import time
from typing import Any

import httpx
from filelock import FileLock

from chukonu_cli import credentials as creds_mod
from chukonu_cli.config import Config
from chukonu_cli.paths import refresh_lock


class ApiError(Exception):
    def __init__(self, status: int, body: Any):
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body}")


class AuthRequired(Exception):
    """没有可用凭据 / refresh 失败，需要用户重新 `chukonu-cli auth login`。"""


class Client:
    def __init__(self, cfg: Config, provider: str | None = None):
        self.cfg = cfg
        self._provider_override = provider
        self._http = httpx.Client(verify=cfg.verify_tls, timeout=30.0, follow_redirects=False)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *a) -> None:
        self.close()

    # ---- token management ----

    def _current_provider(self) -> str | None:
        if self._provider_override:
            return self._provider_override
        return creds_mod.load().current

    def _load_creds(self) -> tuple[str, creds_mod.ProviderCreds]:
        provider = self._current_provider()
        if not provider:
            raise AuthRequired("no credentials; run: chukonu-cli auth login")
        c = creds_mod.load()
        pc = c.providers.get(provider)
        if pc is None:
            raise AuthRequired(f"no credentials for provider={provider}; run: chukonu-cli auth login")
        return provider, pc

    def _refresh(self, provider: str) -> creds_mod.ProviderCreds:
        lock = FileLock(str(refresh_lock(provider)), timeout=30)
        with lock:
            # double-check：别的进程可能刚刷过
            c = creds_mod.load()
            pc = c.providers.get(provider)
            if pc and pc.is_valid():
                return pc
            if not pc or not pc.refresh_token:
                raise AuthRequired("no refresh_token; run: chukonu-cli auth login")
            r = self._http.post(
                f"{self.cfg.gateway_base_url}/auth/refresh",
                json={"refresh_token": pc.refresh_token},
            )
            if r.status_code != 200:
                # refresh 永久失败 → 清理本地
                if r.status_code == 401:
                    creds_mod.remove_provider(provider)
                raise AuthRequired(f"refresh failed ({r.status_code}): {r.text[:200]}")
            new_pc = creds_mod.ProviderCreds.from_token_response(r.json(), user=pc.user)
            creds_mod.upsert_provider(provider, new_pc)
            return new_pc

    def _ensure_token(self) -> tuple[str, creds_mod.ProviderCreds]:
        provider, pc = self._load_creds()
        if not pc.is_valid():
            pc = self._refresh(provider)
        return provider, pc

    # ---- request ----

    def request(
        self,
        method: str,
        path_or_url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        headers: dict[str, str] | None = None,
        auth: bool = True,
        content: bytes | None = None,
    ) -> httpx.Response:
        url = path_or_url
        if not (url.startswith("http://") or url.startswith("https://")):
            url = self.cfg.gateway_base_url.rstrip("/") + "/" + url.lstrip("/")

        h = dict(headers or {})
        if auth:
            _, pc = self._ensure_token()
            h["Authorization"] = f"{pc.token_type} {pc.access_token}"

        r = self._http.request(method, url, params=params, json=json_body, headers=h, content=content)
        if r.status_code == 401 and auth:
            # 也许 token 刚被服务端撤；再刷一次重试
            provider = self._current_provider()
            if provider:
                try:
                    new_pc = self._refresh(provider)
                    h["Authorization"] = f"{new_pc.token_type} {new_pc.access_token}"
                    r = self._http.request(method, url, params=params, json=json_body, headers=h, content=content)
                except AuthRequired:
                    raise
        return r

    def json_or_raise(self, r: httpx.Response) -> Any:
        if r.status_code >= 400:
            try:
                body: Any = r.json()
            except Exception:
                body = r.text
            raise ApiError(r.status_code, body)
        if not r.content:
            return None
        ct = r.headers.get("content-type", "")
        if "json" in ct:
            return r.json()
        return r.text
