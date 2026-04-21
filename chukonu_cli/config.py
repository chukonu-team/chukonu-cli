"""config.toml 读写。仅两三个字段，失败时返回默认值。"""
from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

import tomli_w

from chukonu_cli.paths import config_file

DEFAULT_GATEWAY = "https://search.houdutech.cn:8443"
DEFAULT_PROVIDER = "google"


@dataclass
class Config:
    gateway_base_url: str = DEFAULT_GATEWAY
    default_provider: str = DEFAULT_PROVIDER
    verify_tls: bool = True


def load() -> Config:
    path = config_file()
    if not path.exists():
        return Config()
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return Config(
        gateway_base_url=data.get("gateway_base_url", DEFAULT_GATEWAY),
        default_provider=data.get("default_provider", DEFAULT_PROVIDER),
        verify_tls=bool(data.get("verify_tls", True)),
    )


def save(cfg: Config) -> None:
    path = config_file()
    tmp = path.with_suffix(".toml.tmp")
    with open(tmp, "wb") as f:
        tomli_w.dump(asdict(cfg), f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    os.chmod(path, 0o600)
