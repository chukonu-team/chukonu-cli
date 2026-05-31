"""search 子命令：薄封装 POST /se4ai/api/search。"""
from __future__ import annotations

import asyncio
import json as json_mod
from typing import Any

import typer
from rich.console import Console
from rich.json import JSON as RichJSON

from chukonu_cli.client import AuthRequired, Client
from chukonu_cli.client_core.search import build_search_body
from chukonu_cli.config import load as load_cfg

app = typer.Typer(invoke_without_command=True)
_console = Console()


@app.callback(invoke_without_command=True)
def search(
    query: str = typer.Argument(..., help="搜索关键字"),
    depth: str = typer.Option("basic", "--depth", help="basic|advanced"),
    max_results: int = typer.Option(10, "--max-results", "-n"),
    topic: str | None = typer.Option(None, "--topic"),
    time_range: str | None = typer.Option(None, "--time-range"),
    start_date: str | None = typer.Option(None, "--start-date"),
    end_date: str | None = typer.Option(None, "--end-date"),
    include_domain: list[str] | None = typer.Option(None, "--include-domain"),
    exclude_domain: list[str] | None = typer.Option(None, "--exclude-domain"),
    include_answer: bool = typer.Option(False, "--include-answer"),
    include_raw: bool = typer.Option(False, "--include-raw"),
    include_favicon: bool = typer.Option(False, "--include-favicon"),
    country: str | None = typer.Option(None, "--country"),
    exact_match: bool = typer.Option(False, "--exact-match"),
    safe_search: bool = typer.Option(False, "--safe-search"),
    chunks_per_source: int | None = typer.Option(None, "--chunks-per-source"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    body = build_search_body(
        query=query,
        depth=depth,
        max_results=max_results,
        topic=topic,
        time_range=time_range,
        start_date=start_date,
        end_date=end_date,
        include_domains=include_domain,
        exclude_domains=exclude_domain,
        include_answer=include_answer,
        include_raw_content=include_raw,
        include_favicon=include_favicon,
        country=country,
        exact_match=exact_match,
        safe_search=safe_search,
        chunks_per_source=chunks_per_source,
    )

    cfg = load_cfg()
    asyncio.run(_run(cfg, body, json_out))


async def _run(cfg: Any, body: dict[str, Any], json_out: bool) -> None:
    try:
        async with Client(cfg) as client:
            r = await client.request("POST", "/se4ai/api/search", json_body=body)
    except AuthRequired as e:
        typer.echo(f"未登录：{e}", err=True)
        raise typer.Exit(code=2)

    if r.status_code != 200:
        typer.echo(f"search failed ({r.status_code}): {r.text[:300]}", err=True)
        raise typer.Exit(code=1)
    data = r.json()

    if json_out:
        typer.echo(json_mod.dumps(data, ensure_ascii=False))
        return

    answer = data.get("answer")
    results = data.get("results", [])
    if answer:
        _console.print(f"[bold]Answer:[/bold] {answer}\n")
    for i, item in enumerate(results, 1):
        title = item.get("title", "(no title)")
        url = item.get("url", "")
        snippet = item.get("content") or item.get("snippet") or ""
        _console.print(f"[bold cyan]{i}.[/bold cyan] {title}")
        if url:
            _console.print(f"   [dim]{url}[/dim]")
        if snippet:
            short = snippet if len(snippet) < 300 else snippet[:300] + "…"
            _console.print(f"   {short}")
        _console.print()
    if not results:
        _console.print(RichJSON(json_mod.dumps(data, ensure_ascii=False)))
