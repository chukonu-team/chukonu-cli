"""通用 api 子命令：chukonu-cli api <METHOD> <PATH> [flags]."""
from __future__ import annotations

import json as json_mod
import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.json import JSON as RichJSON

from chukonu_cli.client import ApiError, AuthRequired, Client
from chukonu_cli.config import load as load_cfg

app = typer.Typer(invoke_without_command=True)

_console = Console()


def _parse_kv(pairs: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for kv in pairs or []:
        if "=" not in kv:
            raise typer.BadParameter(f"bad --header value {kv!r}; expect K=V")
        k, v = kv.split("=", 1)
        out[k.strip()] = v
    return out


def _parse_json(s: str | None, label: str) -> Any:
    if s is None:
        return None
    try:
        return json_mod.loads(s)
    except json_mod.JSONDecodeError as e:
        raise typer.BadParameter(f"{label} is not valid JSON: {e}")


@app.callback(invoke_without_command=True)
def api(
    method: str = typer.Argument(..., help="HTTP method: GET/POST/PUT/PATCH/DELETE/HEAD"),
    path: str = typer.Argument(..., help="Path (相对于 gateway_base_url) 或完整 URL"),
    params: str | None = typer.Option(None, "--params", help="JSON 字串，会作为 query string 发出"),
    data: str | None = typer.Option(None, "--data", help="JSON 字串作为请求体"),
    data_file: Path | None = typer.Option(None, "--data-file", help="从文件读取 JSON 请求体"),
    header: list[str] | None = typer.Option(None, "--header", "-H", help="K=V，可重复"),
    no_auth: bool = typer.Option(False, "--no-auth", help="不注入 Bearer"),
    fmt: str = typer.Option("pretty", "--format", help="pretty|json|raw"),
    output: Path | None = typer.Option(None, "--output", "-o", help="把响应体写入文件 (二进制兼容)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="只打印将要发出的请求"),
) -> None:
    cfg = load_cfg()
    params_obj = _parse_json(params, "--params")
    body_obj: Any = None
    if data is not None and data_file is not None:
        raise typer.BadParameter("--data and --data-file are mutually exclusive")
    if data is not None:
        body_obj = _parse_json(data, "--data")
    elif data_file is not None:
        body_obj = json_mod.loads(data_file.read_text(encoding="utf-8"))

    headers = _parse_kv(header)

    if dry_run:
        typer.echo(json_mod.dumps(
            {"method": method.upper(), "path": path, "params": params_obj, "json_body": body_obj, "headers": headers, "auth": not no_auth},
            ensure_ascii=False, indent=2,
        ))
        return

    try:
        with Client(cfg) as client:
            r = client.request(method.upper(), path, params=params_obj, json_body=body_obj, headers=headers, auth=not no_auth)
    except AuthRequired as e:
        typer.echo(f"未登录或凭据失效：{e}", err=True)
        raise typer.Exit(code=2)

    if output is not None:
        output.write_bytes(r.content)
        typer.echo(f"wrote {len(r.content)} bytes to {output}", err=True)
        if not (200 <= r.status_code < 300):
            raise typer.Exit(code=r.status_code // 100)
        return

    ct = r.headers.get("content-type", "")
    try:
        body: Any = r.json() if "json" in ct else r.text
    except Exception:
        body = r.text

    if fmt == "raw":
        sys.stdout.write(r.text)
        if not r.text.endswith("\n"):
            sys.stdout.write("\n")
    elif fmt == "json":
        if isinstance(body, (dict, list)):
            typer.echo(json_mod.dumps(body, ensure_ascii=False))
        else:
            typer.echo(json_mod.dumps({"raw": body}, ensure_ascii=False))
    else:  # pretty
        if isinstance(body, (dict, list)):
            _console.print(RichJSON(json_mod.dumps(body, ensure_ascii=False)))
        else:
            typer.echo(body)

    if not (200 <= r.status_code < 300):
        raise ApiError(r.status_code, body) if False else typer.Exit(code=1)
