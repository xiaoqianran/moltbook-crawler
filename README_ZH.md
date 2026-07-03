# Moltbook Crawler

[English](./README.md) | **中文**

moltbook.com 学术研究爬虫。**内置 [proxy-hunter](https://github.com/xiaoqianran/proxy-hunter) 子模块**（独立项目，仅引用，不合并）。

## 目录结构

```
moltbook-crawler/          ← 本仓库（xiaoqianran/moltbook-crawler）
├── crawlers/              ← 爬虫核心
├── proxy-hunter/          ← git submodule → xiaoqianran/proxy-hunter
│   └── source_tests/      ← 代理测试与 results/
├── scripts/
│   └── refresh_proxies.sh
└── data/                  ← 爬取输出
```

> **proxy-hunter 仍是独立仓库**，此处通过 submodule 引用，不修改其项目形态。

## 克隆（含子模块）

```bash
git clone --recurse-submodules https://github.com/xiaoqianran/moltbook-crawler.git
cd moltbook-crawler
uv sync
```

已克隆但未拉子模块：

```bash
git submodule update --init --recursive
```

## 快速开始

```bash
# 1. 刷新代理池（调用内置 proxy-hunter，~18s）
./scripts/refresh_proxies.sh

# 2. 测试爬取
uv run python main.py all --limit 50 --skip-comments

# 3. 遇 429 时启用代理 fallback
uv run python main.py all --proxy --limit 100 --skip-comments
```

## 命令

```
uv run python main.py {all|search|agents|posts|submolts|social}

  --proxy              启用内置 proxy-hunter 结果（fallback 模式）
  --proxy-mode MODE    fallback（默认）| always
  --limit N            测试条数上限
  --skip-comments      跳过评论
```

## 代理如何工作

| 步骤 | 说明 |
|------|------|
| `proxy-hunter/` | submodule，独立项目 |
| `run_all.py` | 在子模块内跑，产出 `results/*.json` |
| `crawlers/proxy_pool.py` | 读取 results，**不** pip 安装 proxy-hunter |
| `--proxy` | 直连优先，429 时轮换代理 |

## 爬虫模块

| 模块 | 作用 |
|------|------|
| `search_crawler` | `/search` 扩展 agent/post 发现 |
| `agent_crawler` | 多源种子 + discover 雪球 |
| `post_crawler` | 帖子 + 评论（offset 断点续爬） |
| `submolt_crawler` | 社区列表 |
| `social_graph` | 相似 agent 边 |

## 依赖关系

```
moltbook-crawler
    └── proxy-hunter/   (git submodule，非 pip 包)
            └── source_tests/results/  →  proxy_pool.py 读取
```