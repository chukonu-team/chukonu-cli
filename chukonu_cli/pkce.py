"""PKCE (RFC 7636) verifier / S256 challenge 生成。"""
from __future__ import annotations

import base64
import hashlib
import secrets


def generate() -> tuple[str, str]:
    """返回 (verifier, challenge)。verifier 64 字节 (~86 字符 urlsafe)。"""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge
