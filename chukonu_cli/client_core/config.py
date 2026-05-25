"""client_core 的 Config dataclass。纯数据,无 I/O。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Config:
    gateway_base_url: str
    default_provider: str = "google"
    verify_tls: bool = True
