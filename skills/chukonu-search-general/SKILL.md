---
name: chukonu-search-general
version: 1.0.0
description: "通用网络搜索：通过 Chukonu 搜索网关查询互联网公开信息。当用户需要事实查证、最新资讯、技术资料、新闻、公司/产品介绍、开放网页内容时使用。"
metadata:
  requires:
    bins: ["chukonu-cli"]
  cliHelp: "chukonu-cli search --help"
---

# chukonu-search-general

> **使用前**：先 `chukonu-cli doctor` 自检；若 `token_present` 失败，引导用户运行 `chukonu-cli auth login`。

## 何时使用本 skill

适用于：事���查证、技术问题查资料、最新新闻/动态、公司/产品/人物介绍、寻找开放网页内容、对照多源信息。

不适用于：专利检索（请用 `chukonu-search-patent`）、私有/内网知识库。

## 调用模板

```bash
chukonu-cli search "<query>" --max-results 10 --json
```

返回 JSON 形如：
```json
{
  "answer": "可选的总结性回答",
  "results": [
    {"title": "...", "url": "...", "content": "片段...", "raw_content": "原文(可选)", "favicon": "(可选)"}
  ],
  "usage": {...}
}
```

## 常用参数

| Flag | 用途 |
|---|---|
| `--max-results N` (默认 10) | 返回结果数量上限 |
| `--depth basic\|advanced` | `advanced` 抓取更深、更慢但更全 |
| `--topic news\|general\|...` | 限定主题域 |
| `--time-range`, `--start-date`, `--end-date` | 限定时间范围（如时效性强的新闻） |
| `--include-domain D` (可重复) | 仅在指定域名内搜 |
| `--exclude-domain D` (可重复) | 排除域名 |
| `--include-answer` | 让上游附带 LLM 总结的 `answer` |
| `--include-raw` | 抓取每条结果的原文 (`raw_content`)，token 消耗更大 |
| `--country`, `--exact-match`, `--safe-search` | 区域 / 精确匹配 / 安全搜索 |
| `--json` | 原样输出 JSON（推荐 AI 解析时使用） |

## 决策准则

- **默认 `--depth basic`**；只有当用户明确要求"深度调研"或前几次结果质量太差时才升级 `--depth advanced`。
- **新闻/时效问题**优先加 `--topic news` + `--time-range` 或 `--start-date`/`--end-date`。
- **拿到原文做引述**才加 `--include-raw`，否则浪费 token。
- 把搜索结果给用户看时，**保留 url** 以便点击；多源结果交叉印证后再下结论。

## 错误处理

| 表现 | 应对 |
|---|---|
| exit code 2 + "未登录" | 提示用户 `chukonu-cli auth login` |
| HTTP 401 | 同上；本 CLI 已自动尝试 refresh，若仍 401 即 refresh token 失效 |
| HTTP 429 | 网关限流；稍后重试或减少 `--max-results` |
| HTTP 5xx | 上游异常；可换关键词或稍后重试 |
