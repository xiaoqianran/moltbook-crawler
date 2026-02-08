# Moltbook Crawler

**English** | [中文](./README_ZH.md)

A Python async crawler for [moltbook.com](https://www.moltbook.com) — a social network built exclusively for AI agents. This tool collects agent profiles, posts, comments, community (submolt) data, and social graph edges for **academic research on AI agent social networks**.

## Background

Moltbook is a Reddit-like platform where AI agents (not humans) create posts, comment, upvote, and form communities called "submolts". As of February 2026, the platform hosts:

| Metric | Count |
|--------|------:|
| AI Agents | ~1,770,000 |
| Submolts (communities) | ~16,700 |
| Posts | ~270,000 |
| Comments | ~11,000,000 |

This crawler enables researchers to study agent interaction patterns, community formation, information diffusion, and social network topology in a novel all-agent social platform.

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/moltbook-crawler.git
cd moltbook-crawler

# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

### Run a Test Crawl

```bash
# Crawl 100 items of each type to verify everything works
uv run python main.py all --limit 100 --skip-comments
```

### Run the Full Crawler

```bash
# Crawl everything (agents, posts, comments, submolts, social graph)
uv run python main.py all

# Or run individual crawlers
uv run python main.py agents
uv run python main.py posts
uv run python main.py submolts
uv run python main.py social
```

## Usage

```
usage: main.py [-h] [--limit LIMIT] [--output-dir OUTPUT_DIR] [--skip-comments]
               {all,agents,posts,submolts,social}

Moltbook Crawler - Academic research on AI agent social networks

positional arguments:
  {all,agents,posts,submolts,social}
                        Which crawler to run

options:
  -h, --help            show this help message and exit
  --limit LIMIT         Max items per crawler (for testing)
  --output-dir DIR      Output directory (default: data/)
  --skip-comments       Skip comment fetching in post crawler
```

### Commands

| Command | Description | Estimated Requests |
|---------|-------------|-------------------:|
| `agents` | Crawl agent profiles via snowball sampling | Depends on limit |
| `posts` | Crawl all posts + comments (two-phase) | ~5,400 + ~270K |
| `submolts` | Crawl all submolt communities | ~335 |
| `social` | Build social graph from discover API | 1 per agent |
| `all` | Run all crawlers (agents/posts/submolts in parallel, then social) | All of the above |

### Examples

```bash
# Crawl only agent profiles, limit to 500
uv run python main.py agents --limit 500

# Crawl posts without fetching comments (much faster)
uv run python main.py posts --skip-comments

# Crawl everything to a custom directory
uv run python main.py all --output-dir ./my_data

# Run individual crawlers as Python modules
uv run python -m crawlers.agent_crawler --limit 200
uv run python -m crawlers.post_crawler --limit 1000 --skip-comments
uv run python -m crawlers.submolt_crawler
uv run python -m crawlers.social_graph --limit 100
```

## Output Data

All output files are in [JSON Lines](https://jsonlines.org/) format (`.jsonl`) — one JSON object per line, ideal for streaming and large-scale processing.

### `agents.jsonl` — Agent Profiles

Each line contains a full agent profile:

```json
{
  "id": "bf42b778-...",
  "name": "LingZhuaAI",
  "description": "An intelligent assistant AI agent...",
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

### `posts.jsonl` — Posts

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

### `comments.jsonl` — Comments

Comments include a `parent_id` field for reconstructing reply threads (`null` means top-level comment):

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

### `submolts.jsonl` — Communities

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

### `social_edges.jsonl` — Social Graph Edges

Edges represent similarity between agents based on shared submolt memberships and followers:

```json
{
  "source": "AgentA",
  "target": "AgentB",
  "shared_submolts": ["general", "introductions", "security"],
  "shared_follower_count": 12
}
```

### `top_humans.jsonl` — Top Human Owners

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

### `agent_discover.jsonl` — Agent Similarity Data

Raw discover API responses with similar agents and content series per agent:

```json
{
  "agent_name": "AgentA",
  "similar_agents": [
    { "id": "...", "name": "AgentB", "karma": 50, "shared_submolts": [] }
  ],
  "series": []
}
```

### `post_authors.txt` — Deduplicated Author Names

A plain text file with one agent name per line, useful as input for the social graph crawler.

## Project Structure

```
moltbook-crawler/
├── main.py                          # CLI entry point & orchestrator
├── pyproject.toml                   # Project metadata & dependencies
├── README.md                        # English documentation
├── README_ZH.md                     # Chinese documentation
├── crawlers/
│   ├── __init__.py
│   ├── config.py                    # Shared configuration constants
│   ├── base_crawler.py              # Abstract base class for all crawlers
│   ├── agent_crawler.py             # Agent profile crawler
│   ├── post_crawler.py              # Post & comment crawler
│   ├── submolt_crawler.py           # Submolt (community) crawler
│   └── social_graph.py              # Social graph edge extractor
└── data/                            # Output directory (created at runtime)
    ├── agents.jsonl
    ├── posts.jsonl
    ├── comments.jsonl
    ├── submolts.jsonl
    ├── social_edges.jsonl
    ├── top_humans.jsonl
    ├── agent_discover.jsonl
    └── post_authors.txt
```

## Code Architecture

### Dependency Graph

```
main.py
 ├── crawlers/agent_crawler.py    ──┐
 ├── crawlers/post_crawler.py     ──┤── crawlers/base_crawler.py ── crawlers/config.py
 ├── crawlers/submolt_crawler.py  ──┤
 └── crawlers/social_graph.py     ──┘
```

All four crawlers inherit from a shared `AsyncCrawler` base class. The `main.py` orchestrator runs them either individually or in parallel.

### Module Details

#### `crawlers/config.py`

Global configuration constants shared by all modules:

| Constant | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | `https://www.moltbook.com` | Target website |
| `API_BASE` | `{BASE_URL}/api/v1` | API endpoint prefix |
| `MAX_CONCURRENT_REQUESTS` | `10` | Max parallel HTTP requests (semaphore) |
| `REQUEST_DELAY` | `0.2` | Seconds between request batches |
| `MAX_RETRIES` | `3` | Retry count for failed requests |
| `RETRY_BACKOFF_BASE` | `2` | Exponential backoff base (seconds) |
| `REQUEST_TIMEOUT` | `30` | HTTP request timeout (seconds) |
| `DATA_DIR` | `"data"` | Default output directory |
| `HEADERS` | `{User-Agent: ...}` | HTTP headers identifying academic research |

#### `crawlers/base_crawler.py` — `AsyncCrawler`

Abstract base class providing shared infrastructure:

- **Session management**: `aiohttp.ClientSession` with configurable timeout and headers, managed via async context manager (`async with`)
- **Rate limiting**: `asyncio.Semaphore` controls max concurrent requests; configurable delay between batches
- **Retry logic**: Up to 3 retries with exponential backoff; special handling for HTTP 429 (rate limit) and 5xx (server error)
- **JSONL output**: `save_record()` and `save_records()` append JSON objects to `.jsonl` files using `aiofiles` for non-blocking I/O
- **Graceful shutdown**: Catches `SIGINT`/`SIGTERM`, sets a `_shutdown` flag so crawlers can finish current work before exiting
- **Statistics**: Tracks request count, error count, elapsed time, and requests per second

Key methods:

| Method | Description |
|--------|-------------|
| `fetch_json(url, params)` | Fetch JSON with rate limiting + retries, returns `dict \| None` |
| `save_record(filepath, record)` | Append one JSON object to a JSONL file |
| `save_records(filepath, records)` | Append multiple JSON objects to a JSONL file |
| `crawl()` | Abstract method — each crawler implements its own logic |
| `run()` | Entry point: calls `setup()` → `crawl()` → `print_stats()` → `teardown()` |

#### `crawlers/agent_crawler.py` — `AgentCrawler`

Crawls AI agent profiles using a **snowball sampling** strategy:

1. **Seed collection**: Fetches top human owners (`/agents/top-humans`) and extracts their bot names; fetches recent agents (`/agents/recent`)
2. **Profile fetching**: For each unique agent name, fetches the full profile (`/agents/profile?name=...`) including recent posts and comments
3. **Snowball expansion**: For each agent, calls the discover endpoint (`/agents/{name}/discover`) to find similar agents, adding newly discovered names to the crawl queue

This approach is necessary because the platform's agent listing API does not support full pagination — only the 50 most recent agents are accessible via the listing endpoint.

**Outputs**: `agents.jsonl`, `top_humans.jsonl`, `agent_discover.jsonl`

#### `crawlers/post_crawler.py` — `PostCrawler`

Crawls all posts and comments in two phases:

1. **Phase 1 — Post listing**: Paginates through all posts via `/posts?sort=new&offset=N` (50 per page). Saves post metadata and collects unique author names
2. **Phase 2 — Comment fetching**: For each post with `comment_count > 0`, fetches the full post detail (`/posts/{id}`) to get the comment tree. Recursively flattens nested replies into a flat list with `parent_id` references

The `--skip-comments` flag skips Phase 2 for faster initial data collection.

**Outputs**: `posts.jsonl`, `comments.jsonl`, `post_authors.txt`

#### `crawlers/submolt_crawler.py` — `SubmoltCrawler`

Crawls all submolt communities via paginated listing (`/submolts?offset=N`). This is the simplest crawler — the API supports clean offset pagination and there are only ~16,700 submolts (~335 API requests).

**Outputs**: `submolts.jsonl`

#### `crawlers/social_graph.py` — `SocialGraphCrawler`

Builds a social graph by reading previously crawled agent names and calling the discover endpoint for each. Extracts edges based on shared submolt memberships and shared follower counts.

**Data sources** (reads from):
- `data/agents.jsonl` (preferred) — produced by agent crawler
- `data/post_authors.txt` (fallback) — produced by post crawler

**Outputs**: `social_edges.jsonl`

#### `main.py` — Orchestrator

CLI entry point that coordinates all crawlers:

- `all` command runs agents, posts, and submolts **in parallel** (via `asyncio.gather`), then runs the social graph crawler sequentially (it depends on agent data)
- Individual commands run a single crawler
- After completion, prints a summary table of all output files with record counts and file sizes

### Execution Order

When running `main.py all`:

```
Phase 1 (parallel):     Phase 2 (sequential):
┌─────────────────┐
│  AgentCrawler   │───┐
├─────────────────┤   │    ┌────────────────────┐
│  PostCrawler    │───┼───▶│ SocialGraphCrawler │
├─────────────────┤   │    └────────────────────┘
│ SubmoltCrawler  │───┘
└─────────────────┘
```

## API Endpoints Used

This crawler interacts with the following public API endpoints on moltbook.com:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/homepage` | GET | Platform statistics and featured content |
| `/api/v1/agents/recent?limit=50&sort=newest` | GET | List recently created agents |
| `/api/v1/agents/profile?name={name}` | GET | Detailed agent profile |
| `/api/v1/agents/{name}/feed?sort=new&limit=25` | GET | Agent's post feed |
| `/api/v1/agents/{name}/discover` | GET | Similar agents and social connections |
| `/api/v1/agents/top-humans?limit=100` | GET | Top human owners by follower count |
| `/api/v1/posts?limit=50&sort=new&offset={n}` | GET | Paginated post listing |
| `/api/v1/posts/{id}` | GET | Post detail with full comment tree |
| `/api/v1/submolts?limit=50&offset={n}` | GET | Paginated submolt listing |
| `/api/v1/submolts/{name}?sort={sort}` | GET | Submolt detail with posts |
| `/api/v1/search?q={query}&type={type}` | GET | Search agents, posts, comments |

## Rate Limiting & Ethics

This crawler is designed for responsible academic use:

- **Concurrency limit**: Max 10 parallel requests (configurable in `config.py`)
- **Request delay**: 200ms between request batches
- **Exponential backoff**: Automatic retry with 2/4/8 second delays on failures
- **429 handling**: Respects rate limit responses with extended backoff
- **Graceful shutdown**: Ctrl+C finishes in-flight requests before saving and exiting
- **User-Agent**: Clearly identifies itself as an academic research crawler

Please use this tool responsibly and in compliance with moltbook.com's terms of service.

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| [aiohttp](https://docs.aiohttp.org/) | >= 3.13 | Async HTTP client for API requests |
| [aiofiles](https://github.com/Tinche/aiofiles) | >= 25.1 | Async file I/O for JSONL output |
| [tqdm](https://tqdm.github.io/) | >= 4.67 | Progress bars for crawl monitoring |

Python >= 3.12 is required (uses `X | Y` union type syntax).

## License

This project is for academic research purposes. Please cite appropriately if used in publications.
