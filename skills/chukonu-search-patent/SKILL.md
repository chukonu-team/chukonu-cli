---
name: chukonu-search-patent
version: 1.0.0
description: "专利搜索：通过 Chukonu 网关检索专利全文。适用于关键词检索、新颖性比对/查新（向量相似度）、按申请号取详情、IPC/年份/申请人等结构化筛选。"
metadata:
  requires:
    bins: ["chukonu-cli"]
  cliHelp: "chukonu-cli patent --help"
---

# chukonu-search-patent

> **使用前**：先 `chukonu-cli doctor` 自检；若 `token_present` 失败，引导用户 `chukonu-cli auth login`。

## 何时使用本 skill

- 检索特定主题/技术的专利
- 给一段技术方案做**新颖性比对/查新**（找潜在冲突专利）
- 已知申请号取详情
- 按 IPC 分类、年份、申请人/发明人、地域等结构化筛选

不适用于：网页/新闻搜索（请用 `chukonu-search-general`）。

## 子命令

### 1. 关键词检索

```bash
chukonu-cli patent keyword "<query>" --size 10 --json
```

可选过滤：`--patent-type`、`--year-min`、`--year-max`、`--ipc <IPC>`、`--from N` (分页偏移)。

### 2. 新颖性比对 / 相似度搜索（重点）

```bash
chukonu-cli patent similar --text "<技术方案文字>" --top-k 20 --threshold 0.7 --json
# 或
chukonu-cli patent similar --application-number CN1234567A --top-k 20 --json
```

返回项里关注 `score` 与 `risk_level` (`high|medium|low`)：

- `risk_level=high` → **建议人工复核**，可能存在新颖性冲突，输出给用户时**显式高亮警示**。
- `risk_level=medium` → 列出，但提醒并非绝对冲突。
- `risk_level=low` → 仅供参考。

调小 `--threshold` 召回更多；`--top-k` 上调可看更长尾。

### 3. 高级结构化检索

字段太多，用文件传 JSON：
```bash
chukonu-cli patent advanced --json-body /tmp/query.json --json
```
`query.json` 字段示例：`title`, `abstract`, `claims`, `applicant`, `inventor`, `ipc_main`, `year_min`, `year_max`, `patent_type`, `size`, `from`。具体字段以 `/patent/api/search/advanced` 上游 schema 为准。

### 4. 按申请号取详情

```bash
chukonu-cli patent get <application_number> --json
```

### 5. 索引统计

```bash
chukonu-cli patent stats --json
```

## 决策准则

- 用户只给主题词 → `keyword`
- 用户给一段技术描述、问"是否已被申请 / 有没有冲突" → `similar --text`，重点看 `risk_level`
- 用户给申请号 → 先 `get` 取详情；若需找近似 → `similar --application-number`
- 给用户呈现结果时**保留**：申请号、标题、申请人、申请日、IPC、`risk_level`（如有）

## 错误处理

| 表现 | 应对 |
|---|---|
| exit code 2 + "未登录" | 提示 `chukonu-cli auth login` |
| HTTP 401 | 同上 |
| HTTP 4xx 字段错误 | 检查 `--json-body` 字段名是否拼错 |
| HTTP 5xx | 上游异常；稍后重试 |
