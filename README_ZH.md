# Moltbook Crawler

[English](./README.md) | **中文**

基于 Python asyncio 的 [moltbook.com](https://www.moltbook.com) 学术研究爬虫，集成 **[proxy-hunter](../proxy-hunter)** 作为代理依赖。

## 架构（v0.2）

```
main.py
 └── crawlers/
      ├── base_crawler.py    # 生命周期 + proxy-hunter 集成
      ├── http_client.py     # 直连 / fallback / always 代理模式
      ├── storage.py         # JSONL 去重 + offset 断点续爬
      ├── search_crawler.py  # /search 扩展发现（新）
      ├── agent_crawler.py   # 多源种子 + 雪球 + search
      ├── post_crawler.py    # 帖子 + 评论（可续爬）
      ├── submolt_crawler.py
      └── social_graph.py
```

### 与 proxy-hunter 的关系

| 组件 | 作用 |
|------|------|
| `proxy-hunter` 包 | 从 `source_tests/results/` 加载已验证代理 |
| `--proxy` | 启用代理池 |
| `--proxy-mode fallback`（默认） | **直连优先**，遇 429/失败再换代理 |
| `--proxy-mode always` | 每请求走代理（免费代理对 API 成功率低，不推荐） |

```bash
# 1. 先更新代理池（proxy-hunter ~18s）
cd ../proxy-hunter/source_tests && python run_all.py

# 2. 安装爬虫（自动链接本地 proxy-hunter）
cd ../../moltbook-crawler && uv sync

# 3. 推荐：fallback 模式
uv run python main.py all --proxy --limit 100 --skip-comments
```

## 快速开始

```bash
git clone <repo> moltbook-crawler
cd moltbook-crawler
uv sync

# 测试
uv run python main.py all --limit 50 --skip-comments

# 带代理（429 时自动切换）
uv run python main.py all --proxy --limit 100 --skip-comments
```

## 命令

```
uv run python main.py {all|search|agents|posts|submolts|social} [选项]

选项:
  --limit N              每爬虫最大条数（测试用）
  --output-dir DIR       输出目录（默认 data/）
  --skip-comments        跳过评论阶段
  --proxy                启用 proxy-hunter 代理池
  --proxy-mode MODE      fallback（默认）| always
  --proxy-results PATH   代理结果目录（默认 ../proxy-hunter/source_tests/results）
```

### 推荐执行顺序（`all`）

1. **search** — 搜索 API 发现更多 agent/post
2. **agents** — 雪球扩展 agent 资料
3. **posts** — 帖子列表 + 可选评论
4. **submolts** — 社区列表
5. **social** — 社交图谱边

## 输出文件

| 文件 | 内容 |
|------|------|
| `search_hits.jsonl` | 搜索命中的 agent/post/comment |
| `agents.jsonl` | Agent 资料（可断点续爬） |
| `posts.jsonl` | 帖子 |
| `comments.jsonl` | 评论（扁平化，含 post_id） |
| `submolts.jsonl` | 社区 |
| `social_edges.jsonl` | 相似 agent 边 |
| `data/.state/posts.offset` | 帖子爬取断点 |

## 局限说明

- **Agent 无法全量枚举**：`/agents/recent` 仅 50 条，靠 discover 雪球 + search 扩展
- **评论极耗时**：~27 万帖子各 1 请求，生产环境建议 `--skip-comments` 或分批
- **免费代理**：仅适合 429 时 fallback，不适合 `--proxy-mode always`

## 依赖

```toml
# pyproject.toml
proxy-hunter = { path = "../proxy-hunter", editable = true }
```

两项目需放在同级目录：

```
pro/
├── proxy-hunter/
└── moltbook-crawler/
```