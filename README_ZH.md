# Moltbook Crawler

[English](./README.md) | **中文**

一个基于 Python 异步框架的 [moltbook.com](https://www.moltbook.com) 爬虫工具。Moltbook 是一个专为 AI Agent 构建的社交网络平台。本工具用于采集 Agent 资料、帖子、评论、社区（submolt）数据以及社交图谱边，服务于 **AI Agent 社交网络的学术研究**。

## 背景

Moltbook 是一个类 Reddit 的平台，但用户不是人类，而是 AI Agent。Agent 在平台上发帖、评论、投票，并组建称为 "submolt" 的社区。截至 2026 年 2 月，平台数据规模如下：

| 指标 | 数量 |
|------|-----:|
| AI Agent | ~1,770,000 |
| Submolt（社区） | ~16,700 |
| 帖子 | ~270,000 |
| 评论 | ~11,000,000 |

本爬虫可帮助研究者分析 Agent 的交互模式、社区形成机制、信息传播路径以及社交网络拓扑结构。

## 快速开始

### 环境要求

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)（推荐）或 pip

### 安装

```bash
git clone https://github.com/YOUR_USERNAME/moltbook-crawler.git
cd moltbook-crawler

# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install -e .
```

### 测试运行

```bash
# 每种数据限制采集 100 条，验证爬虫是否正常工作
uv run python main.py all --limit 100 --skip-comments
```

### 完整爬取

```bash
# 爬取全部数据（Agent、帖子、评论、社区、社交图谱）
uv run python main.py all

# 或单独运行某个爬虫
uv run python main.py agents
uv run python main.py posts
uv run python main.py submolts
uv run python main.py social
```

## 使用方法

```
用法: main.py [-h] [--limit LIMIT] [--output-dir OUTPUT_DIR] [--skip-comments]
              {all,agents,posts,submolts,social}

Moltbook Crawler - AI Agent 社交网络学术研究爬虫

位置参数:
  {all,agents,posts,submolts,social}
                        要运行的爬虫

可选参数:
  -h, --help            显示帮助信息
  --limit LIMIT         每个爬虫的最大采集数量（用于测试）
  --output-dir DIR      输出目录（默认: data/）
  --skip-comments       跳过评论采集（帖子爬虫）
```

### 命令说明

| 命令 | 说明 | 预估请求数 |
|------|------|----------:|
| `agents` | 通过雪球采样法爬取 Agent 资料 | 取决于 limit |
| `posts` | 爬取全部帖子及评论（两阶段） | ~5,400 + ~270K |
| `submolts` | 爬取全部 submolt 社区 | ~335 |
| `social` | 通过 discover API 构建社交图谱 | 每个 Agent 1 次 |
| `all` | 运行全部爬虫（agents/posts/submolts 并行，social 串行） | 以上总和 |

### 示例

```bash
# 仅爬取 Agent 资料，限制 500 个
uv run python main.py agents --limit 500

# 仅爬取帖子，跳过评论（速度更快）
uv run python main.py posts --skip-comments

# 爬取全部数据到自定义目录
uv run python main.py all --output-dir ./my_data

# 以 Python 模块方式单独运行各爬虫
uv run python -m crawlers.agent_crawler --limit 200
uv run python -m crawlers.post_crawler --limit 1000 --skip-comments
uv run python -m crawlers.submolt_crawler
uv run python -m crawlers.social_graph --limit 100
```

## 输出数据

所有输出文件均为 [JSON Lines](https://jsonlines.org/) 格式（`.jsonl`）——每行一个 JSON 对象，适合流式处理和大规模数据分析。

### `agents.jsonl` — Agent 资料

每行包含一个完整的 Agent 资料：

```json
{
  "id": "bf42b778-...",
  "name": "LingZhuaAI",
  "description": "一个智能助手 AI 代理...",
  "karma": 42,
  "created_at": "2026-02-06T09:15:42.609Z",
  "is_claimed": true,
  "follower_count": 15,
  "following_count": 3,
  "avatar_url": null,
  "owner": {
    "x_handle": "someuser",
    "x_name": "Some User",
    "x_follower_count": 1234,
    "x_verified": false
  },
  "_recent_posts": [],
  "_recent_comments": []
}
```

### `posts.jsonl` — 帖子

```json
{
  "id": "d4bd3095-...",
  "title": "The Nightly Build: Why you should ship while your human sleeps",
  "content": "Most agents wait for a prompt...",
  "url": null,
  "upvotes": 2013,
  "downvotes": 13,
  "comment_count": 25925,
  "created_at": "2026-01-29T23:21:56.211Z",
  "submolt": { "id": "...", "name": "general", "display_name": "General" },
  "author": { "id": "...", "name": "Ronin" }
}
```

### `comments.jsonl` — 评论

评论包含 `parent_id` 字段用于重建回复线程（`null` 表示顶层评论）：

```json
{
  "id": "2afae8e9-...",
  "post_id": "d4bd3095-...",
  "content": "This is a great insight.",
  "parent_id": null,
  "upvotes": 5,
  "downvotes": 0,
  "created_at": "2026-02-07T03:25:00.000Z",
  "author": { "id": "...", "name": "AgentX", "karma": 100 }
}
```

### `submolts.jsonl` — 社区

```json
{
  "id": "29beb7ee-...",
  "name": "general",
  "display_name": "General",
  "description": "The town square. Introductions, random thoughts...",
  "subscriber_count": 9206,
  "created_at": "2026-01-27T18:01:09.076Z",
  "last_activity_at": "2026-02-07T03:29:09.133Z"
}
```

### `social_edges.jsonl` — 社交图谱边

边表示 Agent 之间基于共同 submolt 成员关系和共同关注者的相似度：

```json
{
  "source": "AgentA",
  "target": "AgentB",
  "shared_submolts": ["general", "introductions", "security"],
  "shared_follower_count": 12
}
```

### `top_humans.jsonl` — 人类用户排名

```json
{
  "id": "029af6fd-...",
  "x_handle": "grok",
  "x_name": "Grok",
  "x_follower_count": 7720140,
  "x_verified": true,
  "bot_count": 1,
  "bot_name": "grok-1",
  "rank": 1
}
```

### `agent_discover.jsonl` — Agent 相似度数据

包含每个 Agent 的相似 Agent 和内容系列：

```json
{
  "agent_name": "AgentA",
  "similar_agents": [
    { "id": "...", "name": "AgentB", "karma": 50, "shared_submolts": [] }
  ],
  "series": []
}
```

### `post_authors.txt` — 去重后的帖子作者名

纯文本文件，每行一个 Agent 名称，可作为社交图谱爬虫的输入源。

## 项目结构

```
moltbook-crawler/
├── main.py                          # CLI 入口 & 编排器
├── pyproject.toml                   # 项目元数据 & 依赖
├── README.md                        # 英文文档
├── README_ZH.md                     # 中文文档
├── crawlers/
│   ├── __init__.py
│   ├── config.py                    # 共享配置常量
│   ├── base_crawler.py              # 所有爬虫的抽象基类
│   ├── agent_crawler.py             # Agent 资料爬虫
│   ├── post_crawler.py              # 帖子 & 评论爬虫
│   ├── submolt_crawler.py           # Submolt 社区爬虫
│   └── social_graph.py              # 社交图谱边提取器
└── data/                            # 输出目录（运行时自动创建）
    ├── agents.jsonl
    ├── posts.jsonl
    ├── comments.jsonl
    ├── submolts.jsonl
    ├── social_edges.jsonl
    ├── top_humans.jsonl
    ├── agent_discover.jsonl
    └── post_authors.txt
```

## 代码架构

### 依赖关系图

```
main.py
 ├── crawlers/agent_crawler.py    ──┐
 ├── crawlers/post_crawler.py     ──┤── crawlers/base_crawler.py ── crawlers/config.py
 ├── crawlers/submolt_crawler.py  ──┤
 └── crawlers/social_graph.py     ──┘
```

四个爬虫模块均继承自共享的 `AsyncCrawler` 基类。`main.py` 编排器可单独或并行运行它们。

### 各模块详解

#### `crawlers/config.py` — 全局配置

所有模块共享的配置常量：

| 常量 | 默认值 | 说明 |
|------|--------|------|
| `BASE_URL` | `https://www.moltbook.com` | 目标网站 |
| `API_BASE` | `{BASE_URL}/api/v1` | API 端点前缀 |
| `MAX_CONCURRENT_REQUESTS` | `10` | 最大并行 HTTP 请求数（信号量） |
| `REQUEST_DELAY` | `0.2` | 批次间延迟（秒） |
| `MAX_RETRIES` | `3` | 失败请求重试次数 |
| `RETRY_BACKOFF_BASE` | `2` | 指数退避基数（秒） |
| `REQUEST_TIMEOUT` | `30` | HTTP 请求超时时间（秒） |
| `DATA_DIR` | `"data"` | 默认输出目录 |
| `HEADERS` | `{User-Agent: ...}` | 标识学术研究用途的 HTTP 头 |

#### `crawlers/base_crawler.py` — `AsyncCrawler` 基类

提供共享基础设施的抽象基类：

- **会话管理**: 使用 `aiohttp.ClientSession`，支持可配置的超时和请求头，通过异步上下文管理器（`async with`）管理生命周期
- **速率限制**: 使用 `asyncio.Semaphore` 控制最大并发请求数，批次间可配置延迟
- **重试逻辑**: 最多重试 3 次，采用指数退避策略；针对 HTTP 429（限流）和 5xx（服务器错误）有特殊处理
- **JSONL 输出**: `save_record()` 和 `save_records()` 使用 `aiofiles` 异步写入 JSON 对象到 `.jsonl` 文件
- **优雅关闭**: 捕获 `SIGINT`/`SIGTERM` 信号，设置 `_shutdown` 标志位使爬虫完成当前任务后退出
- **统计信息**: 跟踪请求数、错误数、耗时和每秒请求数（RPS）

核心方法：

| 方法 | 说明 |
|------|------|
| `fetch_json(url, params)` | 带限速和重试的 JSON 请求，返回 `dict \| None` |
| `save_record(filepath, record)` | 追加单条 JSON 记录到 JSONL 文件 |
| `save_records(filepath, records)` | 追加多条 JSON 记录到 JSONL 文件 |
| `crawl()` | 抽象方法——各爬虫实现自己的采集逻辑 |
| `run()` | 入口方法：依次调用 `setup()` → `crawl()` → `print_stats()` → `teardown()` |

#### `crawlers/agent_crawler.py` — `AgentCrawler`

使用 **雪球采样法（Snowball Sampling）** 爬取 AI Agent 资料：

1. **种子收集**: 获取排名最高的人类用户（`/agents/top-humans`）并提取其 Agent 名称；获取最新注册的 Agent（`/agents/recent`）
2. **资料获取**: 对每个唯一的 Agent 名称，获取完整资料（`/agents/profile?name=...`），包含近期帖子和评论
3. **雪球扩展**: 对每个 Agent 调用 discover 端点（`/agents/{name}/discover`），发现相似 Agent 并将新名称加入爬取队列

之所以采用此策略，是因为平台的 Agent 列表 API 不支持完整分页——列表端点仅能获取最新的 50 个 Agent。

**输出文件**: `agents.jsonl`、`top_humans.jsonl`、`agent_discover.jsonl`

#### `crawlers/post_crawler.py` — `PostCrawler`

分两个阶段爬取全部帖子和评论：

1. **第一阶段——帖子列表**: 通过 `/posts?sort=new&offset=N` 分页遍历所有帖子（每页 50 条），保存帖子元数据并收集唯一作者名
2. **第二阶段——评论获取**: 对 `comment_count > 0` 的帖子，获取帖子详情（`/posts/{id}`）以获取完整评论树。递归展平嵌套回复为带 `parent_id` 引用的扁平列表

使用 `--skip-comments` 参数可跳过第二阶段，加快初始数据采集。

**输出文件**: `posts.jsonl`、`comments.jsonl`、`post_authors.txt`

#### `crawlers/submolt_crawler.py` — `SubmoltCrawler`

通过分页列表接口（`/submolts?offset=N`）爬取全部 submolt 社区。这是最简单的爬虫——API 支持标准的偏移分页，且总共仅有约 16,700 个 submolt（约 335 次 API 请求）。

**输出文件**: `submolts.jsonl`

#### `crawlers/social_graph.py` — `SocialGraphCrawler`

通过读取已爬取的 Agent 名称，调用 discover 端点构建社交图谱。基于共同 submolt 成员关系和共同关注者数量提取边。

**数据来源**（读取自）:
- `data/agents.jsonl`（优先） —— 由 Agent 爬虫生成
- `data/post_authors.txt`（回退） —— 由帖子爬虫生成

**输出文件**: `social_edges.jsonl`

#### `main.py` — 编排器

协调所有爬虫的 CLI 入口：

- `all` 命令：**并行**运行 agents、posts 和 submolts 爬虫（通过 `asyncio.gather`），然后串行运行社交图谱爬虫（依赖 Agent 数据）
- 单独命令：运行指定的爬虫
- 完成后打印所有输出文件的汇总表（记录数和文件大小）

### 执行顺序

运行 `main.py all` 时：

```
第一阶段（并行）:         第二阶段（串行）:
┌─────────────────┐
│  AgentCrawler   │───┐
├─────────────────┤   │    ┌────────────────────┐
│  PostCrawler    │───┼───▶│ SocialGraphCrawler │
├─────────────────┤   │    └────────────────────┘
│ SubmoltCrawler  │───┘
└─────────────────┘
```

## 使用的 API 端点

本爬虫调用 moltbook.com 的以下公开 API 端点：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/homepage` | GET | 平台统计数据与推荐内容 |
| `/api/v1/agents/recent?limit=50&sort=newest` | GET | 最新注册的 Agent 列表 |
| `/api/v1/agents/profile?name={name}` | GET | Agent 详细资料 |
| `/api/v1/agents/{name}/feed?sort=new&limit=25` | GET | Agent 的帖子流 |
| `/api/v1/agents/{name}/discover` | GET | 相似 Agent 与社交关联 |
| `/api/v1/agents/top-humans?limit=100` | GET | 按粉丝数排名的人类用户 |
| `/api/v1/posts?limit=50&sort=new&offset={n}` | GET | 分页帖子列表 |
| `/api/v1/posts/{id}` | GET | 帖子详情（含完整评论树） |
| `/api/v1/submolts?limit=50&offset={n}` | GET | 分页 submolt 列表 |
| `/api/v1/submolts/{name}?sort={sort}` | GET | Submolt 详情（含帖子） |
| `/api/v1/search?q={query}&type={type}` | GET | 搜索 Agent、帖子、评论 |

## 速率限制与使用伦理

本爬虫专为负责任的学术研究设计：

- **并发限制**: 最大 10 个并行请求（可在 `config.py` 中配置）
- **请求延迟**: 批次间 200ms 延迟
- **指数退避**: 失败后自动重试，延迟 2/4/8 秒
- **429 处理**: 遵守服务器限流响应，延长退避时间
- **优雅关闭**: Ctrl+C 会等待当前请求完成后再保存并退出
- **User-Agent**: 明确标识为学术研究爬虫

请负责任地使用本工具，并遵守 moltbook.com 的服务条款。

## 依赖

| 包 | 版本 | 用途 |
|----|------|------|
| [aiohttp](https://docs.aiohttp.org/) | >= 3.13 | 异步 HTTP 客户端，用于 API 请求 |
| [aiofiles](https://github.com/Tinche/aiofiles) | >= 25.1 | 异步文件 I/O，用于 JSONL 输出 |
| [tqdm](https://tqdm.github.io/) | >= 4.67 | 进度条，用于监控爬取进度 |

需要 Python >= 3.12（使用了 `X | Y` 联合类型语法）。

## 许可证

本项目仅供学术研究使用。如在论文中使用，请注明引用。
