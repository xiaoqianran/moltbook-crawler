# Moltbook Crawler v0.3

[English](./README.md) | **中文**

moltbook.com 学术研究爬虫。内置 **proxy-hunter** 子模块（独立仓库，git submodule 引用）。

## v0.3 改进

| 能力 | v0.1 | v0.3 |
|------|------|------|
| 帖子发现 | 仅 `sort=new` offset | **new + hot**，cursor 分页 |
| 评论 | 拉整帖 `/posts/{id}` | 专用 **`/posts/{id}/comments`** + cursor |
| 社区帖子 | 无 | **`/submolts/{name}/feed`**（单次可上千帖） |
| 搜索 | 单页 | **cursor 翻页**，12+ 查询词 |
| Agent 种子 | 4 来源 | search + feed + posts + 雪球 |
| 断点续爬 | 部分 | posts/submolts/comments 状态文件 |

## 目录结构

```
moltbook-crawler/
├── crawlers/
│   ├── search_crawler.py      # 搜索发现
│   ├── submolt_crawler.py     # 社区列表 + 详情
│   ├── feed_crawler.py        # 各社区 feed 帖子
│   ├── post_crawler.py        # 全局帖子 (new/hot)
│   ├── comments_crawler.py    # 评论（独立 API）
│   ├── agent_crawler.py       # Agent 资料 + discover 雪球
│   └── social_graph.py        # 社交边
├── proxy-hunter/              # git submodule
├── scripts/refresh_proxies.sh
└── data/
```

## 克隆

```bash
git clone --recurse-submodules https://github.com/xiaoqianran/moltbook-crawler.git
cd moltbook-crawler
uv sync
```

## 命令

```bash
# 推荐：发现阶段（search → submolts → feeds → posts → agents）
uv run python main.py discover --limit 100

# 全量流水线（含评论 + 社交图）
uv run python main.py all --skip-comments        # 先跳过评论
uv run python main.py comments --limit 500       # 单独拉评论

# 单模块
uv run python main.py search
uv run python main.py feeds --limit 50           # 50 个社区 feed
uv run python main.py posts
uv run python main.py agents --limit 200
uv run python main.py submolts
uv run python main.py social

# 代理（429 fallback）
./scripts/refresh_proxies.sh
uv run python main.py discover --proxy --limit 200

# 提速
uv run python main.py discover --concurrency 8 --delay 0.2
```

## 输出文件

| 文件 | 内容 |
|------|------|
| `search_hits.jsonl` | 搜索命中的 agent/post/comment |
| `submolts.jsonl` | 社区列表（平台约 3.2 万） |
| `submolt_details.jsonl` | 社区详情 |
| `feed_posts.jsonl` | 各社区 feed 帖子 |
| `posts.jsonl` | 全局帖子 (new/hot) |
| `comments.jsonl` | 评论 |
| `agents.jsonl` | Agent 资料 |
| `social_edges.jsonl` | 相似 agent 边 |
| `data/.state/` | 断点 cursor/offset/todo |

## 推荐工作流

```bash
# 第一天：广泛发现（不拉评论）
uv run python main.py discover --limit 500 --skip-comments

# 第二天：增量 agent + 评论
uv run python main.py agents --limit 1000
uv run python main.py comments --limit 2000

# 遇 429
uv run python main.py discover --proxy --limit 500
```

## 依赖

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- `proxy-hunter/` 子模块（非 pip 包）