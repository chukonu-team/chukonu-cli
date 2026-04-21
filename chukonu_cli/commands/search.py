"""search 子命令：薄封装 POST /se4ai/api/search。"""
from __future__ import annotations

import json as json_mod
from typing import Any

import typer
from rich.console import Console
from rich.json import JSON as RichJSON

from chukonu_cli.client import AuthRequired, Client
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
    body: dict[str, Any] = {"query": query, "search_depth": depth, "max_results": max_results}
    if topic is not None: body["topic"] = topic
    if time_range is not None: body["time_range"] = time_range
    if start_date is not None: body["start_date"] = start_date
    if end_date is not None: body["end_date"] = end_date
    if include_domain: body["include_domains"] = include_domain
    if exclude_domain: body["exclude_domains"] = exclude_domain
    if include_answer: body["include_answer"] = True
    if include_raw: body["include_raw_content"] = True
    if include_favicon: body["include_favicon"] = True
    if country is not None: body["country"] = country
    if exact_match: body["exact_match"] = True
    if safe_search: body["safe_search"] = True
    if chunks_per_source is not None: body["chunks_per_source"] = chunks_per_source

    cfg = load_cfg()
    try:
        with Client(cfg) as client:
            r = client.request("POST", "/se4ai/api/search", json_body=body)
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
