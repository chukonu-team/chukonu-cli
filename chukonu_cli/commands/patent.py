"""patent 子命令：薄封装 /patent/api/* 。"""
from __future__ import annotations

import asyncio
import json as json_mod
from pathlib import Path
from typing import Any
from urllib.parse import quote

import typer
from rich.console import Console
from rich.json import JSON as RichJSON
from rich.table import Table

from chukonu_cli.client import AuthRequired, Client
from chukonu_cli.client_core.search import (
    build_patent_detail_path,
    build_patent_keyword_body,
    build_patent_similar_body,
)
from chukonu_cli.config import load as load_cfg

app = typer.Typer(help="专利搜索 (keyword/similar/advanced/get/stats)", no_args_is_help=True)
_console = Console()

# 后端 `_resolve_index` 支持的数据集。本地校验，拼错不必打到后端才拿 400。
PATENT_DATASETS: tuple[str, ...] = ("epo_docdb", "epo_docdb_family")

# family 命中的成员平行数组（规范 §2.2）：同一下标恒为同一成员。
# 渲染成表格时 null **必须**占位输出，跳过会让整列错位。
_MEMBER_PARALLEL_FIELDS: tuple[str, ...] = (
    "application_number",
    "publication_number",
    "doc_id",
    "patent_name",
    "abstract",
    "title_zh",
    "title_ja",
    "title_ko",
    "abstract_zh",
    "abstract_ja",
    "abstract_ko",
    "first_ap",
    "first_in",
    "patent_type",
    "ipc_main",
    "ipc_main_code",
    "cpc_main",
    "country",
    "title_lang",
    "abstract_lang",
    "date_of_last_exchange",
    "claims",
    "claims_lang",
    "description_text",
)

# 表格列（顺序即列序）。其余平行数组不铺开成列，避免宽表；用 --json 取全量。
_MEMBER_COLUMNS: tuple[tuple[str, str], ...] = (
    ("publication_number", "公开号"),
    ("application_number", "申请号"),
    ("country", "国别"),
    ("patent_type", "类型"),
    ("patent_name", "标题"),
)

_NULL_PLACEHOLDER = "-"


def _validate_dataset(value: str) -> str:
    if value not in PATENT_DATASETS:
        raise typer.BadParameter(
            f"未知 dataset {value!r}；可选 {list(PATENT_DATASETS)}", param_hint="--dataset"
        )
    return value


def _member_row_count(hit: dict[str, Any]) -> int:
    """成员行数：以族级 family_size 为准，缺失时退回最长平行数组。"""
    size = hit.get("family_size")
    if isinstance(size, int) and not isinstance(size, bool) and size > 0:
        return size
    return max(
        (len(hit[f]) for f in _MEMBER_PARALLEL_FIELDS if isinstance(hit.get(f), list)),
        default=0,
    )


def _cell(value: Any) -> str:
    """单元格文本；None / 缺位一律占位符，绝不跳过（跳过会让成员下标错位）。"""
    if value is None:
        return _NULL_PLACEHOLDER
    text = str(value)
    return text if text else _NULL_PLACEHOLDER


def _family_member_table(hit: dict[str, Any]) -> Table:
    """把一个 family 命中按成员下标渲染成表格（规范 §6）。"""
    rows = _member_row_count(hit)
    key = _cell(hit.get("family_key"))
    caption = f"family_size={hit.get('family_size')}" if "family_size" in hit else None

    table = Table(title=f"family_key {key}", caption=caption, title_justify="left")
    table.add_column("#", justify="right", style="dim", no_wrap=True)
    present = [(f, label) for f, label in _MEMBER_COLUMNS if isinstance(hit.get(f), list)]
    for _field, label in present:
        table.add_column(label, overflow="fold")

    for i in range(rows):
        cells = []
        for field, _label in present:
            arr = hit[field]
            cells.append(_cell(arr[i]) if i < len(arr) else _NULL_PLACEHOLDER)
        table.add_row(str(i), *cells)
    return table


def _family_length_warnings(hit: dict[str, Any]) -> list[str]:
    """平行数组长度必须等于 family_size（规范 §2.1.1）；不等是数据契约破坏，明说而不是静默截断。"""
    size = hit.get("family_size")
    if not isinstance(size, int) or isinstance(size, bool):
        return []
    return [
        f"{f} 长度 {len(hit[f])} != family_size {size}"
        for f in _MEMBER_PARALLEL_FIELDS
        if isinstance(hit.get(f), list) and len(hit[f]) != size
    ]


def _family_hits(data: Any) -> list[dict[str, Any]]:
    """从响应里挑出 family 命中：详情响应本身，或 results[] 里带 family_key 的 hit。"""
    if isinstance(data, dict):
        if data.get("family_key"):
            return [data]
        results = data.get("results")
        if isinstance(results, list):
            return [
                h for h in results if isinstance(h, dict) and h.get("family_key")
            ]
    return []


def _render(data: Any) -> None:
    """family 命中走成员表格，其余沿用原始 JSON dump。"""
    hits = _family_hits(data)
    if not hits:
        _console.print(RichJSON(json_mod.dumps(data, ensure_ascii=False)))
        return

    if isinstance(data, dict) and data.get("total") is not None:
        _console.print(f"[bold]total[/bold] {data['total']} ({data.get('total_unit') or 'families'})")
    for hit in hits:
        _console.print(_family_member_table(hit))
        for warn in _family_length_warnings(hit):
            _console.print(f"[yellow]契约告警[/yellow] {warn}")
        # 非成员字段（族级标量与族事实集合）不进表格，原样补出，避免丢信息。
        rest = {k: v for k, v in hit.items() if k not in _MEMBER_PARALLEL_FIELDS}
        if rest:
            _console.print(RichJSON(json_mod.dumps(rest, ensure_ascii=False)))
    _console.print("[dim]完整数组（含未成列字段）用 --json 取。[/dim]")


async def _call(method: str, path: str, body: Any | None, json_out: bool) -> None:
    cfg = load_cfg()
    try:
        async with Client(cfg) as client:
            r = (
                await client.request(method, path, json_body=body)
                if body is not None
                else await client.request(method, path)
            )
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
        # --json 走原始 dump：显示层可以截断，但不得改变 API 数组（规范 §6）。
        typer.echo(json_mod.dumps(data, ensure_ascii=False))
    else:
        _render(data)


@app.command()
def keyword(
    query: str = typer.Argument(...),
    dataset: str = typer.Option(
        "epo_docdb", "--dataset", help=f"数据集，可选 {list(PATENT_DATASETS)}"
    ),
    patent_type: str | None = typer.Option(None, "--patent-type"),
    year_min: int | None = typer.Option(None, "--year-min"),
    year_max: int | None = typer.Option(None, "--year-max"),
    ipc: str | None = typer.Option(None, "--ipc"),
    size: int = typer.Option(10, "--size"),
    frm: int = typer.Option(0, "--from"),
    include_claims: bool = typer.Option(False, "--include-claims"),
    include_description: bool = typer.Option(False, "--include-description"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    body = build_patent_keyword_body(
        query=query,
        patent_type=patent_type,
        year_min=year_min,
        year_max=year_max,
        ipc_code=ipc,
        size=size,
        frm=frm,
        dataset=_validate_dataset(dataset),
        include_claims=include_claims,
        include_description=include_description,
    )
    asyncio.run(_call("POST", "/patent/api/search/keyword", body, json_out))


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
    body = build_patent_similar_body(
        application_number=application_number,
        text=text,
        top_k=top_k,
        threshold=threshold,
        ipc_code=ipc,
        year_min=year_min,
        year_max=year_max,
    )
    asyncio.run(_call("POST", "/patent/api/search/similar", body, json_out))


@app.command()
def advanced(
    json_body: Path | None = typer.Option(None, "--json-body", help="JSON 请求体文件路径"),
    dedup: str | None = typer.Option(
        None, "--dedup", help="族去重口径 auto|family|none，覆盖 JSON body 同名键"
    ),
    include_claims: bool | None = typer.Option(
        None, "--include-claims/--no-include-claims", help="覆盖 JSON body 同名键"
    ),
    include_description: bool | None = typer.Option(
        None, "--include-description/--no-include-description", help="覆盖 JSON body 同名键"
    ),
    openapi: bool = typer.Option(False, "--openapi", help="打印 /search/advanced 接口的 OpenAPI schema（含依赖的 components.schemas），便于 AI 按规范构造请求体"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    if openapi:
        asyncio.run(_print_advanced_openapi(json_out))
        return
    if json_body is None:
        raise typer.BadParameter("必须提供 --json-body 或 --openapi")
    body = json_mod.loads(json_body.read_text(encoding="utf-8"))
    # 命令行显式给出时覆盖文件里的同名键；未给（None）则保持文件原值。
    if dedup is not None:
        if dedup not in ("auto", "family", "none"):
            raise typer.BadParameter(
                "dedup 只能是 auto|family|none", param_hint="--dedup"
            )
        # auto 是后端默认：与 builder 一致，不进 body。
        body.pop("dedup", None)
        if dedup != "auto":
            body["dedup"] = dedup
    if include_claims is not None:
        body["include_claims"] = include_claims
    if include_description is not None:
        body["include_description"] = include_description
    asyncio.run(_call("POST", "/patent/api/search/advanced", body, json_out))


@app.command()
def analyze(
    json_body: Path = typer.Option(..., "--json-body", help="JSON 请求体文件路径"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """计量分析（聚合）：过滤字段同 advanced，外加 facets/top_n/applicant_repr/inventor_repr。

    例:{"facets":["top_applicants","by_application_year"],"country":["CN"],
    "applicant_repr":"original","top_n":10}
    """
    body = json_mod.loads(json_body.read_text(encoding="utf-8"))
    asyncio.run(_call("POST", "/patent/api/analytics/facets", body, json_out))



async def _print_advanced_openapi(json_out: bool) -> None:
    cfg = load_cfg()
    try:
        async with Client(cfg) as client:
            r = await client.request("GET", "/patent/api/openapi.json")
    except AuthRequired as e:
        typer.echo(f"未登录：{e}", err=True)
        raise typer.Exit(code=2)
    if r.status_code >= 400:
        typer.echo(f"fetch openapi failed ({r.status_code}): {r.text[:300]}", err=True)
        raise typer.Exit(code=1)
    spec = r.json()

    target = "/search/advanced"
    path_obj = (spec.get("paths") or {}).get(target)
    if path_obj is None:
        typer.echo(f"openapi.json 里未找到 {target} ，返回完整文档以供参考", err=True)
        out = spec
    else:
        all_schemas = ((spec.get("components") or {}).get("schemas") or {})
        needed: dict[str, Any] = {}
        _collect_refs(path_obj, all_schemas, needed)
        out = {
            "openapi": spec.get("openapi"),
            "info": spec.get("info"),
            "paths": {target: path_obj},
            "components": {"schemas": needed} if needed else {},
        }

    payload = json_mod.dumps(out, ensure_ascii=False, indent=2)
    if json_out:
        typer.echo(payload)
    else:
        _console.print(RichJSON(payload))


def _collect_refs(node: Any, all_schemas: dict[str, Any], out: dict[str, Any]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            name = ref.split("/")[-1]
            if name not in out and name in all_schemas:
                out[name] = all_schemas[name]
                _collect_refs(all_schemas[name], all_schemas, out)
        for v in node.values():
            _collect_refs(v, all_schemas, out)
    elif isinstance(node, list):
        for v in node:
            _collect_refs(v, all_schemas, out)


@app.command()
def get(
    key: str = typer.Argument(..., help="文献申请号，或 family 数据集的 family_key"),
    dataset: str = typer.Option(
        "epo_docdb", "--dataset", help=f"数据集，可选 {list(PATENT_DATASETS)}"
    ),
    include_claims: bool = typer.Option(False, "--include-claims"),
    include_description: bool = typer.Option(False, "--include-description"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    backend_path = build_patent_detail_path(
        quote(key, safe=""),
        dataset=_validate_dataset(dataset),
        include_claims=include_claims,
        include_description=include_description,
    )
    path = f"/patent/api{backend_path}"
    asyncio.run(_call("GET", path, None, json_out))


@app.command()
def stats(json_out: bool = typer.Option(False, "--json")) -> None:
    asyncio.run(_call("GET", "/patent/api/stats", None, json_out))
