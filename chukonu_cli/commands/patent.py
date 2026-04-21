"""patent 子命令：薄封装 /patent/api/* 。"""
from __future__ import annotations

import json as json_mod
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.json import JSON as RichJSON

from chukonu_cli.client import AuthRequired, Client
from chukonu_cli.config import load as load_cfg

app = typer.Typer(help="专利搜索 (keyword/similar/advanced/get/stats)", no_args_is_help=True)
_console = Console()


def _call(method: str, path: str, body: Any | None, json_out: bool) -> None:
    cfg = load_cfg()
    try:
        with Client(cfg) as client:
            r = client.request(method, path, json_body=body) if body is not None else client.request(method, path)
    except AuthRequired as e:
        typer.echo(f"未登录：{e}", err=True)
        raise typer.Exit(code=2)

    if r.status_code >= 400:
        typer.echo(f"{method} {path} failed ({r.status_code}): {r.text[:300]}", err=True)
        raise typer.Exit(code=1)
    try:
        data = r.json()
    except Exception:
        data = r.text
    if json_out or not isinstance(data, (dict, list)):
        typer.echo(json_mod.dumps(data, ensure_ascii=False))
    else:
        _console.print(RichJSON(json_mod.dumps(data, ensure_ascii=False)))


@app.command()
def keyword(
    query: str = typer.Argument(...),
    patent_type: str | None = typer.Option(None, "--patent-type"),
    year_min: int | None = typer.Option(None, "--year-min"),
    year_max: int | None = typer.Option(None, "--year-max"),
    ipc: str | None = typer.Option(None, "--ipc"),
    size: int = typer.Option(10, "--size"),
    frm: int = typer.Option(0, "--from"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    body: dict[str, Any] = {"query": query, "size": size, "from": frm}
    if patent_type: body["patent_type"] = patent_type
    if year_min is not None: body["year_min"] = year_min
    if year_max is not None: body["year_max"] = year_max
    if ipc: body["ipc_code"] = ipc
    _call("POST", "/patent/api/search/keyword", body, json_out)


@app.command()
def similar(
    application_number: str | None = typer.Option(None, "--application-number"),
    text: str | None = typer.Option(None, "--text"),
    top_k: int = typer.Option(10, "--top-k"),
    threshold: float = typer.Option(0.7, "--threshold"),
    ipc: str | None = typer.Option(None, "--ipc"),
    year_min: int | None = typer.Option(None, "--year-min"),
    year_max: int | None = typer.Option(None, "--year-max"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    if not application_number and not text:
        raise typer.BadParameter("必须提供 --application-number 或 --text")
    body: dict[str, Any] = {"top_k": top_k, "threshold": threshold}
    if application_number: body["application_number"] = application_number
    if text: body["text"] = text
    if ipc: body["ipc_code"] = ipc
    if year_min is not None: body["year_min"] = year_min
    if year_max is not None: body["year_max"] = year_max
    _call("POST", "/patent/api/search/similar", body, json_out)


@app.command()
def advanced(
    json_body: Path = typer.Option(..., "--json-body", help="JSON 请求体文件路径"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    body = json_mod.loads(json_body.read_text(encoding="utf-8"))
    _call("POST", "/patent/api/search/advanced", body, json_out)


@app.command()
def get(
    application_number: str = typer.Argument(...),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    _call("GET", f"/patent/api/patent/{application_number}", None, json_out)


@app.command()
def stats(json_out: bool = typer.Option(False, "--json")) -> None:
    _call("GET", "/patent/api/stats", None, json_out)
