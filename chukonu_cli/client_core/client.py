"""httpx 异步客户端:自动注入 Bearer + 过期自动 refresh + 401 重试一次。

凭据来源由 CredsProvider 注入(CLI 用文件存储, MCP server 可传 None 走 anonymous)。

全异步(M9.1/G1):底层用 httpx.AsyncClient,request/_refresh/_ensure_token 均 async,
经 `async with` 使用。这样网关 MCP tool 在 async 事件循环里调后端不再阻塞单 worker
(解 m9-capacity-scaleout.md §4 的 ~18 rps 钳制)。CredsProvider 的 load/save 仍为同步
文件 I/O(CLI 一次性、I/O 极短,可接受)。
"""
from __future__ import annotations

from typing import Any, Protocol

import httpx

from .config import Config
from .credentials import ProviderCreds
from .errors import ApiError, AuthRequired


class CredsProvider(Protocol):
    """凭据访问接口。CLI 用 filelock+JSON 实现,server 用内存/Redis 实现。

    需保证 load 期间对同一 provider 串行化(避免并发 refresh)。
    """

    def load(self) -> ProviderCreds | None: ...

    def save(self, pc: ProviderCreds) -> None: ...

    def clear(self) -> None: ...


class Client:
    def __init__(
        self,
        cfg: Config,
        creds: CredsProvider | None = None,
        *,
        anonymous: bool = False,
    ):
        """anonymous=True 时不读凭据、不发 Bearer。
        否则需注入 creds(没有则任何带 auth=True 的请求都会抛 AuthRequired)。
        """
        self.cfg = cfg
        self._creds = creds
        self._anonymous = anonymous
        self._http = httpx.AsyncClient(
            verify=cfg.verify_tls, timeout=30.0, follow_redirects=False
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "Client":
        return self

    async def __aexit__(self, *a) -> None:
        await self.aclose()

    # ---- token management ----

    def _load_creds(self) -> ProviderCreds:
        if self._creds is None:
            raise AuthRequired("no credentials configured")
        pc = self._creds.load()
        if pc is None:
            raise AuthRequired("no credentials; please login")
        return pc

    async def _refresh(self) -> ProviderCreds:
        assert self._creds is not None  # _load_creds 已校验
        # 同 provider 串行化由 CredsProvider 实现(filelock 等)
        pc = self._creds.load()
        if pc and pc.is_valid():
            return pc
        if not pc or not pc.refresh_token:
            raise AuthRequired("no refresh_token; please login")
        r = await self._http.post(
            f"{self.cfg.gateway_base_url}/auth/refresh",
            json={"refresh_token": pc.refresh_token},
        )
        if r.status_code != 200:
            if r.status_code == 401:
                self._creds.clear()
            raise AuthRequired(f"refresh failed ({r.status_code}): {r.text[:200]}")
        new_pc = ProviderCreds.from_token_response(r.json(), user=pc.user)
        self._creds.save(new_pc)
        return new_pc

    async def _ensure_token(self) -> ProviderCreds:
        pc = self._load_creds()
        if not pc.is_valid():
            pc = await self._refresh()
        return pc

    # ---- request ----

    async def request(
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
        do_auth = auth and not self._anonymous
        if do_auth:
            pc = await self._ensure_token()
            h["Authorization"] = f"{pc.token_type} {pc.access_token}"

        r = await self._http.request(
            method, url, params=params, json=json_body, headers=h, content=content
        )
        if r.status_code == 401 and do_auth:
            try:
                new_pc = await self._refresh()
                h["Authorization"] = f"{new_pc.token_type} {new_pc.access_token}"
                r = await self._http.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=h,
                    content=content,
                )
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
