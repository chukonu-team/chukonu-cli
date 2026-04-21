"""doctor：自检各项。"""
from __future__ import annotations

import json as json_mod
import os
import time

import httpx
import typer

from chukonu_cli import credentials as creds_mod
from chukonu_cli.client import Client
from chukonu_cli.config import load as load_cfg
from chukonu_cli.paths import config_file as _config_file, credentials_file as _creds_file


def _check_config() -> tuple[bool, str]:
    try:
        load_cfg()
    except Exception as e:  # noqa: BLE001
        return False, f"config parse error: {e}"
    return True, str(_config_file())


def _check_credentials_file() -> tuple[bool, str]:
    p = _creds_file()
    if not p.exists():
        return False, f"not found: {p} (run: chukonu-cli auth login)"
    mode = os.stat(p).st_mode & 0o777
    if mode != 0o600:
        return False, f"bad permissions {oct(mode)}, expected 0o600 ({p})"
    return True, f"{p} (0o600)"


def _check_gateway(cfg) -> tuple[bool, str]:
    try:
        with httpx.Client(verify=cfg.verify_tls, timeout=10.0) as h:
            r = h.get(f"{cfg.gateway_base_url}/healthz")
        if r.status_code != 200:
            return False, f"/healthz returned {r.status_code}"
        return True, f"/healthz 200 @ {cfg.gateway_base_url}"
    except httpx.HTTPError as e:
        return False, f"transport: {e}"


def _check_token_present() -> tuple[bool, str, creds_mod.ProviderCreds | None]:
    c = creds_mod.load()
    if not c.current or c.current not in c.providers:
        return False, "no token (run: chukonu-cli auth login)", None
    pc = c.providers[c.current]
    return True, f"provider={c.current}", pc


def _check_token_local(pc: creds_mod.ProviderCreds) -> tuple[bool, str]:
    remaining = pc.expires_at - int(time.time())
    if remaining <= 60:
        return False, f"expired or expiring in {remaining}s"
    return True, f"expires in {remaining}s"


def _check_token_refresh(cfg, pc: creds_mod.ProviderCreds, provider: str) -> tuple[bool, str]:
    if not pc.refresh_token:
        return False, "no refresh_token"
    try:
        with httpx.Client(verify=cfg.verify_tls, timeout=10.0) as h:
            r = h.post(f"{cfg.gateway_base_url}/auth/refresh", json={"refresh_token": pc.refresh_token})
        if r.status_code != 200:
            return False, f"/auth/refresh {r.status_code}: {r.text[:120]}"
        new_pc = creds_mod.ProviderCreds.from_token_response(r.json(), user=pc.user)
        creds_mod.upsert_provider(provider, new_pc)
        return True, "refresh ok, token rotated"
    except httpx.HTTPError as e:
        return False, f"transport: {e}"


def _check_upstream(cfg, client: Client, path: str, label: str) -> tuple[bool, str]:
    try:
        r = client.request("GET", path)
        if 200 <= r.status_code < 300:
            return True, f"{label} {r.status_code}"
        return False, f"{label} {r.status_code}: {r.text[:100]}"
    except Exception as e:  # noqa: BLE001
        return False, f"{label} error: {e}"


app = typer.Typer(invoke_without_command=True)


@app.callback(invoke_without_command=True)
def doctor(json_out: bool = typer.Option(False, "--json")) -> None:
    """运行 8 项健康检查。"""
    cfg = load_cfg()
    results: list[dict] = []

    def record(name: str, ok: bool, msg: str) -> None:
        results.append({"name": name, "status": "pass" if ok else "fail", "message": msg})

    ok, msg = _check_config()
    record("config_file", ok, msg)

    ok, msg = _check_credentials_file()
    record("credentials_file", ok, msg)

    ok, msg = _check_gateway(cfg)
    record("gateway_reachable", ok, msg)

    ok, msg, pc = _check_token_present()
    record("token_present", ok, msg)

    if pc is not None:
        ok, msg = _check_token_local(pc)
        record("token_local_valid", ok, msg)
        provider = creds_mod.load().current or ""
        ok, msg = _check_token_refresh(cfg, pc, provider)
        record("token_refresh_works", ok, msg)
        with Client(cfg) as client:
            ok, msg = _check_upstream(cfg, client, "/se4ai/api/health", "GET /se4ai/api/health")
            record("upstream_se4ai", ok, msg)
            ok, msg = _check_upstream(cfg, client, "/patent/api/health", "GET /patent/api/health")
            record("upstream_patent", ok, msg)

    must_pass = {"config_file", "gateway_reachable", "token_present", "token_local_valid", "token_refresh_works", "credentials_file"}
    critical_fail = any(r["status"] == "fail" and r["name"] in must_pass for r in results)

    if json_out:
        typer.echo(json_mod.dumps({"ok": not critical_fail, "checks": results}, ensure_ascii=False, indent=2))
    else:
        for r in results:
            mark = "✓" if r["status"] == "pass" else "✗"
            typer.echo(f"{mark} {r['name']:22s} {r['message']}")

    if critical_fail:
        raise typer.Exit(code=1)
