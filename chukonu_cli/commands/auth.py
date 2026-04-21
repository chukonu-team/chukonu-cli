"""auth login / logout / status 子命令。"""
from __future__ import annotations

import json as json_mod
import time

import httpx
import typer

from chukonu_cli import credentials as creds_mod
from chukonu_cli.browser import LoginError, run_login
from chukonu_cli.client import AuthRequired, Client
from chukonu_cli.config import load as load_cfg, save as save_cfg

app = typer.Typer(help="OAuth 凭据管理 (login/logout/status)", no_args_is_help=True)


@app.command()
def login(
    provider: str = typer.Option(None, "--provider", "-p", help="OAuth provider；缺省用 config 里的 default_provider"),
    gateway: str | None = typer.Option(None, "--gateway", help="覆盖 gateway_base_url"),
    port: int = typer.Option(0, "--port", help="本地 loopback 端口；0=内核分配"),
    no_browser: bool = typer.Option(False, "--no-browser", help="不自动开浏览器，仅打印 URL"),
    timeout: float = typer.Option(300.0, "--timeout", help="等待回调的秒数"),
    json_out: bool = typer.Option(False, "--json", help="JSON 格式输出结果"),
) -> None:
    """执行 OAuth Authorization Code Flow + PKCE 登录。"""
    cfg = load_cfg()
    if gateway:
        cfg.gateway_base_url = gateway.rstrip("/")
        save_cfg(cfg)
    prov = provider or cfg.default_provider
    try:
        out = run_login(cfg, prov, port=port, open_browser=not no_browser, timeout=timeout)
    except LoginError as e:
        typer.echo(f"login failed: {e}", err=True)
        raise typer.Exit(code=2)
    creds_mod.upsert_provider(out.provider, out.creds, make_current=True)
    if json_out:
        typer.echo(json_mod.dumps({"provider": out.provider, "expires_at": out.creds.expires_at}, ensure_ascii=False))
    else:
        typer.echo(f"已登录 provider={out.provider} (expires in {out.creds.expires_at - int(time.time())}s)")


@app.command()
def logout(
    provider: str | None = typer.Option(None, "--provider", "-p"),
    all_: bool = typer.Option(False, "--all", help="删除所有 provider 的凭据"),
    remote: bool = typer.Option(False, "--remote", help="同时在网关侧撤销 refresh token"),
) -> None:
    """删除本地凭据。"""
    cfg = load_cfg()
    creds = creds_mod.load()
    if all_:
        if remote:
            for prov, pc in creds.providers.items():
                _revoke_remote(cfg.gateway_base_url, pc, verify=cfg.verify_tls, provider=prov)
        creds_mod.delete_all()
        typer.echo("已清除所有凭据")
        return
    target = provider or creds.current
    if not target:
        typer.echo("当前无登录凭据", err=True)
        raise typer.Exit(code=1)
    if remote:
        pc = creds.providers.get(target)
        if pc:
            _revoke_remote(cfg.gateway_base_url, pc, verify=cfg.verify_tls, provider=target)
    creds_mod.remove_provider(target)
    typer.echo(f"已登出 provider={target}")


def _revoke_remote(base_url: str, pc: creds_mod.ProviderCreds, *, verify: bool, provider: str) -> None:
    try:
        with httpx.Client(verify=verify, timeout=10.0) as http_:
            http_.post(
                f"{base_url}/auth/logout",
                headers={"Authorization": f"{pc.token_type} {pc.access_token}"},
            )
    except httpx.HTTPError as e:
        typer.echo(f"remote logout for {provider} failed (ignored): {e}", err=True)


@app.command()
def status(json_out: bool = typer.Option(False, "--json")) -> None:
    """查看当前登录状态。未登录时 exit 1。"""
    cfg = load_cfg()
    creds = creds_mod.load()
    if not creds.current or creds.current not in creds.providers:
        if json_out:
            typer.echo(json_mod.dumps({"logged_in": False}))
        else:
            typer.echo("未登录。请运行：chukonu-cli auth login", err=True)
        raise typer.Exit(code=1)
    pc = creds.providers[creds.current]
    now = int(time.time())
    info = {
        "logged_in": True,
        "provider": creds.current,
        "gateway": cfg.gateway_base_url,
        "expires_at": pc.expires_at,
        "expires_in": pc.expires_at - now,
        "has_refresh_token": bool(pc.refresh_token),
        "granted_at": pc.granted_at,
        "user": pc.user,
    }

    # 从网关查询 user_id 和 quota
    me_err: str | None = None
    try:
        with Client(cfg) as client:
            r = client.request("GET", "/auth/me")
        if r.status_code == 200:
            me = r.json()
            info["user_id"] = me.get("user_id")
            info["quota"] = me.get("quota")
            info["used_today"] = me.get("used_today")
            info["remaining"] = me.get("remaining")
            info["reset_tz"] = me.get("reset_tz")
        else:
            me_err = f"{r.status_code} {r.text[:120]}"
    except AuthRequired as e:
        me_err = f"auth: {e}"
    except Exception as e:  # noqa: BLE001
        me_err = f"network: {e}"

    if json_out:
        if me_err:
            info["me_error"] = me_err
        typer.echo(json_mod.dumps(info, ensure_ascii=False))
    else:
        typer.echo(f"Provider     : {info['provider']}")
        typer.echo(f"Gateway      : {info['gateway']}")
        if "user_id" in info:
            typer.echo(f"User         : {info['provider']}:{info['user_id']}")
            typer.echo(
                f"Quota        : {info['remaining']}/{info['quota']} "
                f"(used {info['used_today']}, reset tz {info.get('reset_tz', 'UTC')})"
            )
        elif me_err:
            typer.echo(f"User/Quota   : (unavailable: {me_err})")
        typer.echo(f"Expires in   : {info['expires_in']}s")
        typer.echo(f"Refresh token: {'yes' if info['has_refresh_token'] else 'no'}")
        typer.echo(f"Granted at   : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(pc.granted_at))}")
