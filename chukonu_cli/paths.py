"""集中管理 chukonu-cli 的文件路径与目录权限。

- 配置：$XDG_CONFIG_HOME/chukonu-cli/ 或 ~/.chukonu-cli/
- 锁：   <config_dir>/locks/
- 凭据： $XDG_DATA_HOME/chukonu-cli/ 或 ~/.local/share/chukonu-cli/
"""
from __future__ import annotations

import os
from pathlib import Path


def _xdg(env: str, fallback: Path) -> Path:
    v = os.environ.get(env)
    return Path(v).expanduser() if v else fallback


def config_dir() -> Path:
    # 用户要求 ~/.chukonu-cli/，XDG 作为可选覆盖
    override = os.environ.get("CHUKONU_CLI_CONFIG_DIR")
    p = Path(override).expanduser() if override else Path.home() / ".chukonu-cli"
    p.mkdir(mode=0o700, exist_ok=True)
    try:
        os.chmod(p, 0o700)
    except OSError:
        pass
    return p


def data_dir() -> Path:
    override = os.environ.get("CHUKONU_CLI_DATA_DIR")
    if override:
        p = Path(override).expanduser()
    else:
        p = _xdg("XDG_DATA_HOME", Path.home() / ".local" / "share") / "chukonu-cli"
    p.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(p, 0o700)
    except OSError:
        pass
    return p


def locks_dir() -> Path:
    p = config_dir() / "locks"
    p.mkdir(mode=0o700, exist_ok=True)
    return p


def config_file() -> Path:
    return config_dir() / "config.toml"


def credentials_file() -> Path:
    return data_dir() / "credentials.json"


def refresh_lock(provider: str) -> Path:
    safe = "".join(c for c in provider if c.isalnum() or c in "._-")
    return locks_dir() / f"refresh_{safe or 'default'}.lock"


def creds_lock() -> Path:
    return locks_dir() / "creds.lock"
