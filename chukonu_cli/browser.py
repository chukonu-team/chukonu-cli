"""loopback HTTP 服务器：接 ?code=&state=，立刻 POST /auth/token 换 session。"""
from __future__ import annotations

import http.server
import threading
import webbrowser
from dataclasses import dataclass
from importlib import resources
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx

from chukonu_cli import credentials as creds_mod
from chukonu_cli.config import Config
from chukonu_cli.pkce import generate as pkce_generate


class LoginError(Exception):
    pass


@dataclass
class LoginOutcome:
    provider: str
    creds: creds_mod.ProviderCreds


def _login_page() -> bytes:
    return resources.files("chukonu_cli").joinpath("login_page.html").read_bytes()


def _error_page(msg: str) -> bytes:
    return (
        f"<!doctype html><meta charset=utf-8><title>login failed</title>"
        f"<body style='font-family:sans-serif;max-width:520px;margin:4rem auto;padding:2rem'>"
        f"<h1 style='color:#cf222e'>✗ 登录失败</h1><p>{msg}</p>"
        f"<p>请返回终端查看详情并重试。</p></body>"
    ).encode("utf-8")


def run_login(
    cfg: Config,
    provider: str,
    *,
    port: int = 0,
    open_browser: bool = True,
    timeout: float = 300.0,
) -> LoginOutcome:
    verifier, challenge = pkce_generate()
    expected_state = __import__("secrets").token_urlsafe(32)

    result: dict[str, Any] = {}
    done = threading.Event()

    # 容器，handler 可通过 server 拿到这些
    ctx = {
        "verifier": verifier,
        "state": expected_state,
        "cfg": cfg,
        "provider": provider,
        "result": result,
        "done": done,
    }

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return  # 静音

        def _reply(self, status: int, body: bytes, content_type: str = "text/html; charset=utf-8") -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            url = urlsplit(self.path)
            if url.path != "/callback":
                self._reply(404, b"not found", "text/plain; charset=utf-8")
                return
            qs = parse_qs(url.query)
            code = (qs.get("code") or [""])[0]
            state = (qs.get("state") or [""])[0]
            err = (qs.get("error") or [""])[0]
            if err:
                msg = f"provider error: {err}"
                ctx["result"]["error"] = msg
                self._reply(400, _error_page(msg))
                ctx["done"].set()
                return
            if not code or state != ctx["state"]:
                msg = "state mismatch or missing code"
                ctx["result"]["error"] = msg
                self._reply(400, _error_page(msg))
                ctx["done"].set()
                return

            # 换 token
            local_redirect = _local_redirect_for(ctx["server_port"])
            cfg_: Config = ctx["cfg"]
            try:
                with httpx.Client(verify=cfg_.verify_tls, timeout=15.0) as http_:
                    r = http_.post(
                        f"{cfg_.gateway_base_url}/auth/token",
                        json={
                            "grant_type": "authorization_code",
                            "code": code,
                            "code_verifier": ctx["verifier"],
                            "redirect_uri": local_redirect,
                        },
                    )
            except httpx.HTTPError as e:
                msg = f"token exchange transport error: {e}"
                ctx["result"]["error"] = msg
                self._reply(502, _error_page(msg))
                ctx["done"].set()
                return
            if r.status_code != 200:
                msg = f"token endpoint {r.status_code}: {r.text[:300]}"
                ctx["result"]["error"] = msg
                self._reply(r.status_code, _error_page(msg))
                ctx["done"].set()
                return
            data = r.json()
            pc = creds_mod.ProviderCreds.from_token_response(
                data, user={"provider": ctx["provider"]}
            )
            ctx["result"]["creds"] = pc
            self._reply(200, _login_page())
            ctx["done"].set()

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    actual_port = httpd.server_address[1]
    ctx["server_port"] = actual_port
    local_redirect = _local_redirect_for(actual_port)

    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    auth_url = (
        f"{cfg.gateway_base_url}/auth/{provider}/login?"
        + urlencode(
            {
                "redirect_uri": local_redirect,
                "state": expected_state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
    )

    if open_browser:
        try:
            webbrowser.open(auth_url)
        except Exception:
            pass
    hint = {
        "google": "请在浏览器中完成 Google 授权。",
        "wechat": "请在浏览器中用手机微信扫描二维码。",
    }.get(provider, f"请在浏览器中完成 {provider} 授权。")
    print(
        f"请在浏览器打开登录链接：\n  {auth_url}\n本地回调：{local_redirect}\n{hint}",
        flush=True,
    )

    try:
        if not done.wait(timeout=timeout):
            raise LoginError(f"login timed out after {timeout:.0f}s")
    finally:
        httpd.shutdown()
        httpd.server_close()

    if "error" in result:
        raise LoginError(str(result["error"]))
    pc = result.get("creds")
    if pc is None:
        raise LoginError("no credentials obtained")
    return LoginOutcome(provider=provider, creds=pc)


def _local_redirect_for(port: int) -> str:
    return f"http://127.0.0.1:{port}/callback"
