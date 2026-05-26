"""client_core: 纯 API 调用层，被 CLI、MCP server、未来 web 共用。

不依赖 typer / rich / 文件系统。凭据来源由调用方注入 CredsProvider。
"""
from __future__ import annotations

from .client import Client, CredsProvider
from .config import Config
from .credentials import ProviderCreds
from .errors import ApiError, AuthRequired
from .search import (
    build_patent_detail_path,
    build_patent_keyword_body,
    build_patent_similar_body,
    build_search_body,
)

__all__ = [
    "Client",
    "Config",
    "CredsProvider",
    "ProviderCreds",
    "ApiError",
    "AuthRequired",
    "build_search_body",
    "build_patent_keyword_body",
    "build_patent_detail_path",
    "build_patent_similar_body",
]
