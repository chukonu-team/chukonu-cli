"""chukonu-cli 根 Typer app。

注：单命令 (doctor / api / search) 不通过 add_typer 注册，
否则 Typer 会把它们当 group，positional 参数解析失败。
"""
from __future__ import annotations

import typer

from chukonu_cli.commands import api as api_cmd
from chukonu_cli.commands import auth as auth_cmd
from chukonu_cli.commands import doctor as doctor_cmd
from chukonu_cli.commands import patent as patent_cmd
from chukonu_cli.commands import search as search_cmd

app = typer.Typer(
    name="chukonu-cli",
    help="Chukonu 搜索网关 CLI — OAuth + 通用搜索 + 专利搜索。",
    no_args_is_help=True,
    add_completion=False,
)

# 多命令 group
app.add_typer(auth_cmd.app, name="auth")
app.add_typer(patent_cmd.app, name="patent")

# 单命令直接挂
app.command("doctor", help="运行健康检查 (config/凭据/网关/token/上游)")(doctor_cmd.doctor)
app.command(
    "api",
    help="通用调用网关 API: chukonu-cli api <METHOD> <PATH> [flags]",
    context_settings={"allow_extra_args": False},
)(api_cmd.api)
app.command("search", help="通用搜索 (薄封装 POST /se4ai/api/search)")(search_cmd.search)


if __name__ == "__main__":
    app()
