---
name: chukonu-search-patent
version: 0.1.0
description: "专利搜索：通过 Chukonu 网关检索专利全文。支持基于标题/摘要/权利要求/全文的布尔查询、IPC 分类、申请人/发明人、地域、专利类型、日期与数值范围等高级结构化检索，并按申请号取详情。"
metadata:
  requires:
    bins: ["chukonu-cli"]
  cliHelp: "chukonu-cli patent --help"
---

# chukonu-search-patent

> **使用前**：先 `chukonu-cli doctor` 自检；若 `token_present` 失败，引导用户 `chukonu-cli auth login`。

## 何时使用本 skill

- 检索特定主题/技术的专利
- 已知申请号取详情
- 按 IPC 分类、年份、申请人/发明人、地域等结构化筛选

不适用于：网页/新闻搜索（请用 `chukonu-search-general`）。

## 子命令

### 1. 高级结构化检索（主力）

> **构造 `--json-body` 前，先执行 `chukonu-cli patent advanced --openapi` 查看完整字段定义、示例与最新约束。** 该命令会输出 `/search/advanced` 的 OpenAPI schema（含 `AdvancedSearchRequest` / `AdvancedSearchResponse` / `AdvancedSearchHit`）。

```bash
chukonu-cli patent advanced --json-body /tmp/query.json --json
# 查看字段权威定义
chukonu-cli patent advanced --openapi
```

所有字段均可选，任意组合即可。文本字段支持 `OR` 布尔，例如 `人工智能 OR 深度学习`。

#### 文本检索字段（均支持 OR 布尔）

| 字段 | 含义 |
|---|---|
| `title` | 标题 |
| `abstract_content` | 摘要 |
| `claim` | 权利要求 |
| `title_abstract_content` | 标题 + 摘要 联合 |
| `tiabc` | 标题 + 摘要 + 权利要求 联合 |
| `full` | 全文（标题/摘要/权利要求） |

#### IPC 分类

- `class_ipc` — IPC 精确匹配，如 `G06T11/60`
- `class_ipc_main` — IPC 主分类号，支持 OR，如 `A61K OR C07H`
- `class_ipc_section` / `class_ipc_cla_ss` / `class_ipc_subclass` / `class_ipc_group` — 部 / 大类 / 小类 / 大组（如 `G` / `G06` / `G06F` / `G06F17`）

#### 申请人 / 权利人 / 发明人

- `ap` 原始申请/专利权人；`first_ap` 第一申请人；`apc` 当前权利人
- `inventor` 发明/设计人；`first_in` 第一发明人
- `ap_type` 申请人类型，逗号分隔多值；`ap_add` 申请人地址

#### 地域（中国申请人）

- `province` / `city` / `county`，如 `河北省` / `保定市` / `徐水区`

#### 号码与类型

- `an` 申请号，精确或前缀匹配，如 `CN202510299981.2`
- `pn` 公开/公告号，精确或前缀匹配
- `patent_type` 专利类型，逗号分隔多值。支持代码或中文：
  - `A` = 发明申请，`B` = 发明授权，`U` = 实用新型,`F` = 外观设计
  - 例：`A,U` 表示「发明申请 + 实用新型」

#### 日期范围（格式 `[YYYYMMDD TO YYYYMMDD]`，`*` 表开放端）

- `application_date` 申请日
- `publication_date` 公开/公告日
- `grant_publication_date` 授权公告日

#### 数值范围（精确值 `X` 或区间 `X TO Y`，`*` 表开放端）

- `apn` 申请人数量；`inn` 发明人数量
- `citation_number_of_times` 引证次数；`citation_forward_number_of_times` 被引证次数

#### 分页

- `size`：1–100，默认 20
- `from`：分页起始偏移，默认 0

#### 示例

**示例 1：主题检索 + 年份 + 类型过滤**
```json
{
  "tiabc": "人工智能 OR 深度学习",
  "patent_type": "A,B",
  "application_date": "[20200101 TO 20231231]",
  "size": 20
}
```

**示例 2：申请人 + IPC 主分类 + 地域**
```json
{
  "first_ap": "华为技术有限公司",
  "class_ipc_main": "G06F OR G06N",
  "province": "广东省",
  "size": 10
}
```

**示例 3：高被引 + 权利要求命中**
```json
{
  "claim": "卷积神经网络",
  "citation_forward_number_of_times": "10 TO *",
  "size": 20
}
```

#### 响应关键字段（AdvancedSearchHit）

向用户呈现结果时建议保留：`application_number`、`patent_name`、`applicant`（或 `first_ap`）、`inventor`、`application_date`、`ipc_main`、`publication_number`、`_score`。完整字段以 `--openapi` 输出为准。

### 2. 按申请号取详情

```bash
chukonu-cli patent get <application_number> --json
```

### 3. 索引统计

```bash
chukonu-cli patent stats --json
```

## 决策准则

- 用户给主题词或一段技术描述 → `advanced`，使用 `tiabc` 或 `full`，必要时叠加 `patent_type` / `application_date` / `class_ipc_main`
- 用户指定申请人/发明人/地域/IPC/日期等结构化条件 → `advanced` 对应字段组合
- 用户给申请号 → 先 `patent get <an>` 取详情；若需找同申请人更多专利，再用 `advanced` 配合 `ap` / `first_ap`
- 给用户呈现结果时保留：申请号、标题、申请人、申请日、IPC、公开号

## 错误处理

| 表现 | 应对 |
|---|---|
| exit code 2 + "未登录" | 提示 `chukonu-cli auth login` |
| HTTP 401 | 同上 |
| HTTP 422 字段校验错误 | 先跑 `chukonu-cli patent advanced --openapi`，对齐字段名/格式（如日期 `[YYYYMMDD TO YYYYMMDD]`、`patent_type` 代码）后重试 |
| HTTP 5xx | 上游异常；稍后重试 |
