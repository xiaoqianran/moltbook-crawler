# Moltbook Crawler v0.5

[English](./README.md) | **中文**

moltbook.com 学术研究爬虫。内置 **proxy-hunter** 子模块（git submodule）。

## v0.5 新增：帖子去重 + 双语保留

### 爬取哪些帖子？

| 来源 | API | 说明 |
|------|-----|------|
| **posts** | `GET /api/v1/posts?sort=new\|hot` | 全站帖子列表（按时间 / 热度） |
| **feeds** | `GET /api/v1/submolts/{name}/feed` | 各社区子版块 feed（扩大覆盖面） |
| **search** | `GET /api/v1/search?type=posts` | 搜索命中（发现用，**不写入帖子库**） |

`search` 只产出 `search_hits.jsonl`；真正入库的帖子来自 **posts** 与 **feeds** 两条链路。

### 全局去重（不会重复存同一帖）

所有帖子写入 **`data/posts.db`**（SQLite，`id` 唯一约束）。同一帖子无论从 `posts/new`、`posts/hot` 还是 `feed/general` 爬到，**只保留一条记录**，并在 `_sources` 字段记录发现来源：

```json
{
  "id": "uuid",
  "title": "original English title",
  "content": "original body",
  "title_original": "original English title",
  "content_original": "original body",
  "title_zh": "简体中文标题",
  "content_zh": "简体中文正文",
  "lang_detected": "en",
  "translate_status": "done",
  "_sources": ["posts/new", "posts/hot", "feed/general"],
  "_sort_modes": ["new", "hot"]
}
```

导出文件 **`data/posts.jsonl`** 由数据库生成，供下游分析使用。旧的 `feed_posts.jsonl` 不再单独写入；可用 `merge-legacy` 合并历史数据。

### 高质量简体中文翻译

```bash
# 复制 .env.example → .env，填入 API Key
cp .env.example .env

# 默认：NVIDIA NIM qwen3-next-80b @ newapi-jp2.xiaoqianran.xyz
# MOLTBOOK_TRANSLATE_BASE_URL=https://newapi-jp2.xiaoqianran.xyz/v1
# MOLTBOOK_TRANSLATE_MODEL=qwen/qwen3-next-80b-a3b-instruct
# MOLTBOOK_TRANSLATE_CONCURRENCY=16   # 19 号池，可调到 16~19

# 单独翻译待处理帖子
uv run python main.py translate --limit 50

# 爬取后自动翻译
uv run python main.py discover --limit 100 --translate
```

- 原文保留在 `title` / `content`（及 `title_original` / `content_original`）
- 译文写入 `title_zh` / `content_zh`
- 已是中文的帖子自动 `skipped`，不重复调用 API

### 合并历史 jsonl（一次性迁移）

若你已有 v0.4 的 `posts.jsonl` + `feed_posts.jsonl`：

```bash
uv run python main.py merge-legacy
```

会按 `id` 去重合并进 `posts.db`，再重新导出 `posts.jsonl`。

## 工程化能力（v0.5+）

| 能力 | 说明 |
|------|------|
| **结构化日志** | `data/logs/crawler.log` + 控制台，`--log-level DEBUG` |
| **爬取失败明细** | `data/crawl_failures.jsonl` 每条失败 HTTP 请求 |
| **翻译审计日志** | `data/translate_operations.jsonl` 每条翻译（成功/失败/跳过、耗时、重试次数） |
| **运行报告** | `data/.state/report_*.json` 每爬虫统计（含 translate_session） |
| **统一仪表盘** | `data/dashboard.json` 汇总 crawl + translate + verify + 数据集 |
| **健康检查** | `main.py verify` → `verify_report.json`（含 post_db、translate_api 冒烟） |
| **单元测试** | `pytest` 覆盖 translate/translate_log/verify/post_db 等 |
| **集成测试** | `pytest -m integration` live API |

### 翻译监控与问题定位

```bash
# 1. 健康检查（含翻译 API 冒烟测试，需 .env 配好 Key）
uv run python main.py verify
cat data/verify_report.json | python3 -m json.tool

# 2. 跑翻译并看实时日志
uv run python main.py translate --log-level DEBUG
tail -f data/logs/crawler.log | grep -E 'translate|Translate'

# 3. 审计每条翻译结果
cat data/translate_operations.jsonl | python3 -m json.tool

# 4. 单元测试验证翻译逻辑（mock API，不耗额度）
uv run pytest tests/test_translate.py tests/test_translate_log.py tests/test_verify_translate.py -v

# 5. 统一 metrics 仪表盘
uv run python main.py dashboard
cat data/dashboard.json | python3 -m json.tool
```

`dashboard.json` 结构：`health`（总健康）、`posts`（双语覆盖）、`crawl`（各爬虫报告）、`translate`（翻译耗时/成功率）、`datasets`（jsonl 行数）、`verify`（最近一次检查结果）。

每次爬取/翻译结束后会自动刷新；也可手动 `main.py dashboard`。

`translate_operations.jsonl` 字段：`post_id`、`status`（success/failed/skipped）、`latency_ms`、`attempts`、`error`。

## 快速开始

```bash
git clone --recurse-submodules https://github.com/xiaoqianran/moltbook-crawler.git
cd moltbook-crawler
uv sync --dev

uv run python main.py verify
uv run pytest -m "not integration" -v
uv run python main.py discover --limit 100 --log-level INFO
```

## 命令

```
uv run python main.py {verify|discover|all|search|feeds|posts|comments|agents|submolts|social|translate|merge-legacy}

  --translate                      discover/all 结束后自动翻译
  --log-level DEBUG|INFO|WARNING   日志级别
  --proxy / --proxy-mode fallback  代理（429 时切换）
  --limit N                        测试条数上限
```

## 爬虫模块

| 模块 | 输出 |
|------|------|
| `search` | `search_hits.jsonl` |
| `submolts` | `submolts.jsonl`, `submolt_details.jsonl` |
| `feeds` | → `posts.db` → `posts.jsonl` |
| `posts` | → `posts.db` → `posts.jsonl` |
| `translate` | 更新 `posts.db` 译文 → 导出 `posts.jsonl` |
| `merge-legacy` | 合并旧 jsonl → `posts.db` |
| `comments` | `comments.jsonl` |
| `agents` | `agents.jsonl` |
| `social` | `social_edges.jsonl` |

## 目录结构

```
moltbook-crawler/
├── crawlers/
│   ├── post_db.py           # SQLite 帖子库（去重 + 双语）
│   ├── translate.py         # LLM 翻译
│   ├── translate_crawler.py
│   └── ...
├── tests/
├── proxy-hunter/            # submodule
└── data/
    ├── posts.db             # 唯一帖子库
    ├── posts.jsonl          # 导出（原文 + 简体中文）
    └── logs/crawler.log
```

## CI

推送 `main` 后 GitHub Actions 自动跑单元测试、`main.py verify` 与集成测试。