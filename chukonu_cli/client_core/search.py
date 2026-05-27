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
    dataset: str | None = None,
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
    if dataset:
        body["dataset"] = dataset
    return body


def build_patent_detail_path(application_number: str, dataset: str | None = None) -> str:
    """patent_search_engine `/patent/{application_number}` 详情端点路径。

    application_number 由调用方负责 quote;dataset 不为 None 时追加为 query param,
    对应后端 `_resolve_index` 的多数据集路由(cn_abstract / epo_docdb 等)。
    """
    path = f"/patent/{application_number}"
    if dataset:
        path = f"{path}?dataset={dataset}"
    return path


def build_patent_advanced_body(
    *,
    # 文本（支持 OR 布尔，如 "人工智能 OR 深度学习"）
    title: str | None = None,
    abstract_content: str | None = None,
    claim: str | None = None,
    title_abstract_content: str | None = None,
    tiabc: str | None = None,
    full: str | None = None,
    # IPC 五级
    class_ipc: str | None = None,
    class_ipc_main: str | None = None,
    class_ipc_section: str | None = None,
    class_ipc_class: str | None = None,
    class_ipc_subclass: str | None = None,
    class_ipc_group: str | None = None,
    # 主体
    ap: str | None = None,
    first_ap: str | None = None,
    inventor: str | None = None,
    first_in: str | None = None,
    # 类型 & 号
    patent_type: str | None = None,
    an: str | None = None,
    pn: str | None = None,
    # 范围（字符串语法，由后端解析）
    application_date: str | None = None,
    no_ap: str | None = None,
    no_in: str | None = None,
    citation_number_of_times: str | None = None,
    citation_forward_number_of_times: str | None = None,
    # 分页 & 数据集
    size: int = 20,
    frm: int = 0,
    dataset: str = "cn_abstract",
    # 兜底：透传 AdvancedSearchRequest 未在签名暴露的字段
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """patent_search_engine `/search/advanced` 请求体。

    显式 kwargs 覆盖 extra 同名 key;空字符串等价于 None(不进 body)。
    分页字段映射后端契约 `size` / `from`。
    """
    body: dict[str, Any] = {}
    if extra:
        for k, v in extra.items():
            if v is None or v == "":
                continue
            body[k] = v
    explicit: dict[str, Any] = {
        "title": title,
        "abstract_content": abstract_content,
        "claim": claim,
        "title_abstract_content": title_abstract_content,
        "tiabc": tiabc,
        "full": full,
        "class_ipc": class_ipc,
        "class_ipc_main": class_ipc_main,
        "class_ipc_section": class_ipc_section,
        "class_ipc_class": class_ipc_class,
        "class_ipc_subclass": class_ipc_subclass,
        "class_ipc_group": class_ipc_group,
        "ap": ap,
        "first_ap": first_ap,
        "inventor": inventor,
        "first_in": first_in,
        "patent_type": patent_type,
        "an": an,
        "pn": pn,
        "application_date": application_date,
        "no_ap": no_ap,
        "no_in": no_in,
        "citation_number_of_times": citation_number_of_times,
        "citation_forward_number_of_times": citation_forward_number_of_times,
    }
    for k, v in explicit.items():
        if v is None or v == "":
            continue
        body[k] = v
    body["size"] = size
    body["from"] = frm
    body["dataset"] = dataset
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
