# chukonu-cli

Python CLI for Chukonu 搜索网关 (api-gateway)，基于 [Typer](https://github.com/fastapi/typer)。

## 安装

```bash
python -m venv .venv
.venv/bin/pip install -e .
```

## 命令

| 命令 | 说明 |
|---|---|
| `chukonu-cli auth login [--provider google]` | OAuth Authorization Code Flow + PKCE + loopback 回调 |
| `chukonu-cli auth logout [--provider X] [--all] [--remote]` | 清理凭据，可同时在网关撤销 refresh token |
| `chukonu-cli auth status [--json]` | 查看登录状态；未登录 exit 1 |
| `chukonu-cli doctor [--json]` | 健康检查 (config / 凭据 / 网关 / token / 上游) |
| `chukonu-cli api <METHOD> <PATH> [flags]` | 通用 API 调用，自动注入 Bearer |
| `chukonu-cli search <query> [flags]` | 通用搜索，薄封装 `POST /se4ai/api/search` |
| `chukonu-cli patent {keyword,similar,advanced,get,stats}` | 专利搜索 |

## 文件布局

- 配置：`~/.chukonu-cli/config.toml`
- 文件锁：`~/.chukonu-cli/locks/`
- 明文凭据：`~/.local/share/chukonu-cli/credentials.json` (0600)

## 登录安全模型

CLI ↔ 网关采用 OAuth 2.0 Authorization Code Flow + PKCE (RFC 7636, S256)：

1. CLI 生成高熵 `code_verifier` 与 `code_challenge = BASE64URL(SHA256(verifier))`
2. CLI 启动 `127.0.0.1:<port>` loopback HTTP server 作为 `redirect_uri`
3. 浏览器访问 `{gateway}/auth/google/login?redirect_uri=...&state=...&code_challenge=...&code_challenge_method=S256`
4. 网关重定向到 Google，用户授权后回网关 `/auth/google/callback`
5. 网关仅回 `?code=<一次性码>&state=...` 给 loopback (**access_token 不再进浏览器 URL**)
6. CLI 立刻 `POST /auth/token` 带上 `code` + `code_verifier` + `redirect_uri` 换取 session (access/refresh token)
7. 凭据写入 `credentials.json` (明文，0600)

## Skills

`skills/chukonu-search-general/` 与 `skills/chukonu-search-patent/` 为 AI Agent (例如 Claude Code) 接入搜索能力。

## 作为 Claude Code 插件安装

本仓库本身即是一个 Claude Code 插件 marketplace，内含 `chukonu-cli` 插件（含 `chukonu-search-general` / `chukonu-search-patent` 两个 skill）。

前置：已 `pip install -e .` 或 `pip install chukonu-cli`，并完成 `chukonu-cli auth login`。

```bash
# 在 Claude Code 中
claude plugin marketplace add chukonu-team/chukonu-cli
claude plugin install chukonu-cli@chukonu
```

安装后 skill 会以 `chukonu-cli:chukonu-search-general` 与 `chukonu-cli:chukonu-search-patent` 暴露，Claude 会按需自动调用。

本地开发调试：

```bash
claude plugin marketplace add /absolute/path/to/chukonu-cli
claude plugin install chukonu-cli@chukonu
# 修改 SKILL.md 后
/plugin marketplace update chukonu
```
