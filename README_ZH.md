# Moltbook Crawler v0.4

[English](./README.md) | **中文**

moltbook.com 学术研究爬虫。内置 **proxy-hunter** 子模块（git submodule）。

## 工程化能力（v0.4）

| 能力 | 说明 |
|------|------|
| **结构化日志** | `data/logs/crawler.log` + 控制台，`--log-level DEBUG` |
| **失败明细** | `data/crawl_failures.jsonl` 每条失败请求 |
| **运行报告** | `data/.state/report_*.json` 每爬虫统计 |
| **健康检查** | `main.py verify` → `verify_report.json` |
| **单元测试** | `pytest` 覆盖 storage/paginate/proxy/log |
| **集成测试** | `pytest -m integration`  live API |

## 快速开始

```bash
git clone --recurse-submodules https://github.com/xiaoqianran/moltbook-crawler.git
cd moltbook-crawler
uv sync --dev

# 1. 健康检查（推荐第一步）
uv run python main.py verify

# 2. 单元测试
uv run pytest -m "not integration" -v

# 3. 集成测试（需网络）
uv run pytest -m integration -v

# 4. 爬取
uv run python main.py discover --limit 100 --log-level INFO
```

## 命令

```
uv run python main.py {verify|discover|all|search|feeds|posts|comments|agents|submolts|social}

  --log-level DEBUG|INFO|WARNING   日志级别
  --log-file NAME                  默认 crawler.log
  --proxy / --proxy-mode fallback  代理（429 时切换）
  --limit N                        测试条数上限
```

## 日志与验证工作流

```bash
# 跑功能
uv run python main.py search --limit 20 --log-level DEBUG

# 看日志
tail -f data/logs/crawler.log

# 看失败
cat data/crawl_failures.jsonl | python3 -m json.tool

# 看最近一次爬虫报告
cat data/.state/report_latest.json | python3 -m json.tool

# 验证 API + 代理池 + 日志文件是否健全
uv run python main.py verify
cat data/verify_report.json
```

### 代理说明

- **默认直连**，日志里 `connection=direct`
- `--proxy` 时 `proxy/fallback`，失败写入 `crawl_failures.jsonl` 含 `proxy` 字段

## 爬虫模块

| 模块 | 输出 |
|------|------|
| `search` | `search_hits.jsonl` |
| `submolts` | `submolts.jsonl`, `submolt_details.jsonl` |
| `feeds` | `feed_posts.jsonl` |
| `posts` | `posts.jsonl` (new+hot) |
| `comments` | `comments.jsonl` |
| `agents` | `agents.jsonl` |
| `social` | `social_edges.jsonl` |

## 目录结构

```
moltbook-crawler/
├── crawlers/
│   ├── logging_config.py    # 日志
│   ├── failure_log.py       # 失败 JSONL
│   ├── run_report.py        # 运行报告
│   ├── verify.py            # 健康检查
│   └── ...
├── tests/                   # pytest
├── proxy-hunter/            # submodule
└── data/
    ├── logs/crawler.log
    ├── crawl_failures.jsonl
    ├── verify_report.json
    └── .state/report_*.json
```

## CI

推送 `main` 后 GitHub Actions 自动跑：
1. 单元测试 `pytest -m "not integration"`
2. `main.py verify` + 集成测试