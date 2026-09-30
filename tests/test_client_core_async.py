"""M9.1/G1: client_core.Client 全异步通路单元测试。

验证:
  - async `request` + 同步纯函数 `json_or_raise` 正常工作;
  - 非 2xx → ApiError(status, body);
  - `aclose` / `async with` 幂等;
  - 关键:多个并发 `request` 不阻塞事件循环(gather N 个慢请求 ≈ 单发耗时,
    而非 N× 串行)——这正是 G1 要解的网关单 worker 钳制(m9-capacity-scaleout.md §4)。

用 httpx transport 注入(替换 Client 内部 AsyncClient),不依赖 pytest-asyncio:
每个 test 用 asyncio.run 驱动。
"""
from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from chukonu_cli.client_core import ApiError, Client, Config


def _client_with_transport(transport: httpx.AsyncBaseTransport) -> Client:
    """构造 anonymous Client 并把内部 AsyncClient 换成带注入 transport 的实例。"""
    c = Client(Config(gateway_base_url="http://test.local"), anonymous=True)
    # 原 __init__ 里的 AsyncClient 未发请求,直接替换(不需 await aclose)。
    c._http = httpx.AsyncClient(transport=transport, base_url="http://test.local")
    return c


def test_async_request_and_json_or_raise() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/search/keyword"
        return httpx.Response(200, json={"results": [], "total": 0})

    async def go() -> None:
        async with _client_with_transport(httpx.MockTransport(handler)) as c:
            r = await c.request("POST", "/search/keyword", json_body={"q": "x"}, auth=False)
            raw = c.json_or_raise(r)
        assert raw == {"results": [], "total": 0}

    asyncio.run(go())


def test_async_api_error_on_non_2xx() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "overloaded", "retry_after": 1})

    async def go() -> None:
        async with _client_with_transport(httpx.MockTransport(handler)) as c:
            r = await c.request("GET", "/x", auth=False)
            with pytest.raises(ApiError) as ei:
                c.json_or_raise(r)
        assert ei.value.status == 503
        assert ei.value.body == {"detail": "overloaded", "retry_after": 1}

    asyncio.run(go())


def test_aclose_idempotent() -> None:
    async def go() -> None:
        c = _client_with_transport(httpx.MockTransport(lambda req: httpx.Response(200)))
        await c.aclose()
        await c.aclose()  # 第二次不应抛

    asyncio.run(go())


def test_event_loop_not_blocked_under_concurrency() -> None:
    """核心验收的本地代理:10 个并发慢请求应并行完成,总耗时 << 10×单发。"""
    delay = 0.2
    n = 10

    class SlowTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            await asyncio.sleep(delay)
            return httpx.Response(200, json={"ok": True})

    async def go() -> float:
        async with _client_with_transport(SlowTransport()) as c:
            t0 = time.perf_counter()
            results = await asyncio.gather(
                *[c.request("GET", f"/x/{i}", auth=False) for i in range(n)]
            )
            elapsed = time.perf_counter() - t0
        assert all(r.status_code == 200 for r in results)
        return elapsed

    elapsed = asyncio.run(go())
    # 串行会是 ~n*delay=2.0s;并发应接近单发 delay。给足裕度防 CI 抖动。
    assert elapsed < delay * 3, f"requests appear serialized: {elapsed:.3f}s for {n}x{delay}s"
