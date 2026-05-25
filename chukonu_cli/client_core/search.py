"""检索请求体构造的纯函数。被 CLI 命令与 MCP tool 共用。"""
from __future__ import annotations

from typing import Any


def build_search_body(
    *,
    query: str,
    depth: str = "basic",
    max_results: int = 10,
    topic: str | None = None,
    time_range: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    include_answer: bool = False,
    include_raw_content: bool = False,
    include_favicon: bool = False,
    country: str | None = None,
    exact_match: bool = False,
    safe_search: bool = False,
    chunks_per_source: int | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "query": query,
        "search_depth": depth,
        "max_results": max_results,
    }
    if topic is not None:
        body["topic"] = topic
    if time_range is not None:
        body["time_range"] = time_range
    if start_date is not None:
        body["start_date"] = start_date
    if end_date is not None:
        body["end_date"] = end_date
    if include_domains:
        body["include_domains"] = include_domains
    if exclude_domains:
        body["exclude_domains"] = exclude_domains
    if include_answer:
        body["include_answer"] = True
    if include_raw_content:
        body["include_raw_content"] = True
    if include_favicon:
        body["include_favicon"] = True
    if country is not None:
        body["country"] = country
    if exact_match:
        body["exact_match"] = True
    if safe_search:
        body["safe_search"] = True
    if chunks_per_source is not None:
        body["chunks_per_source"] = chunks_per_source
    return body


def build_patent_keyword_body(
    *,
    query: str,
    patent_type: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    ipc_code: str | None = None,
    size: int = 10,
    frm: int = 0,
) -> dict[str, Any]:
    body: dict[str, Any] = {"query": query, "size": size, "from": frm}
    if patent_type:
        body["patent_type"] = patent_type
    if year_min is not None:
        body["year_min"] = year_min
    if year_max is not None:
        body["year_max"] = year_max
    if ipc_code:
        body["ipc_code"] = ipc_code
    return body


def build_patent_similar_body(
    *,
    application_number: str | None = None,
    text: str | None = None,
    top_k: int = 10,
    threshold: float = 0.7,
    ipc_code: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
) -> dict[str, Any]:
    if not application_number and not text:
        raise ValueError("application_number 或 text 至少提供一个")
    body: dict[str, Any] = {"top_k": top_k, "threshold": threshold}
    if application_number:
        body["application_number"] = application_number
    if text:
        body["text"] = text
    if ipc_code:
        body["ipc_code"] = ipc_code
    if year_min is not None:
        body["year_min"] = year_min
    if year_max is not None:
        body["year_max"] = year_max
    return body
