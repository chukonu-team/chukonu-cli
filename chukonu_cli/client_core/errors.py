"""client_core 异常类型。"""
from __future__ import annotations

from typing import Any


class ApiError(Exception):
    def __init__(self, status: int, body: Any):
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body}")


class AuthRequired(Exception):
    """没有可用凭据 / refresh 失败,调用方需引导用户重新登录。"""
