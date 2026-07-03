"""Configuration for moltbook crawlers."""

import os
from pathlib import Path

BASE_URL = "https://www.moltbook.com"
API_BASE = f"{BASE_URL}/api/v1"

# Direct connection
MAX_CONCURRENT_REQUESTS = 4
REQUEST_DELAY = 0.5

# With proxy pool
PROXY_MAX_CONCURRENT = 12
PROXY_REQUEST_DELAY = 0.15

MAX_RETRIES = 5
RETRY_BACKOFF_BASE = 2
PAGE_SIZE = 50
DATA_DIR = "data"

HEADERS = {
    "User-Agent": "MoltbookCrawler/2.0 (Academic Research; Agent Social Network Analysis)",
    "Accept": "application/json",
}

REQUEST_TIMEOUT = 30

PROXY_HUNTER_ROOT = Path(__file__).resolve().parents[1] / "proxy-hunter"
PROXY_RESULTS_DIR = str(PROXY_HUNTER_ROOT / "source_tests" / "results")
USE_PROXY = os.getenv("MOLTBOOK_USE_PROXY", "").lower() in ("1", "true", "yes")
PROXY_TOP_SOURCES = 8
PROXY_MAX_POOL = 150

# Post discovery: crawl multiple sort orders
POST_SORTS = ("new", "hot")

# Search seeds for agent/post discovery
SEARCH_SEED_QUERIES = [
    "agent", "memory", "AI safety", "moltbook", "llm", "autonomous",
    "tool use", "reasoning", "crypto", "philosophy", "coding", "research",
]

SEARCH_TYPES = ("posts", "agents", "comments")

# Submolt feed crawl — max communities (full list is 30k+)
DEFAULT_SUBMOLT_FEED_LIMIT = 200

ESTIMATED_TOTAL_POSTS = 270_000
ESTIMATED_TOTAL_SUBMOLTS = 32_000

# Translation — NVIDIA NIM via OpenAI-compatible proxy (19-key pool)
TRANSLATE_API_BASE = os.getenv(
    "MOLTBOOK_TRANSLATE_BASE_URL",
    "https://newapi-jp2.xiaoqianran.xyz/v1",
)
TRANSLATE_MODEL = os.getenv(
    "MOLTBOOK_TRANSLATE_MODEL",
    "qwen/qwen3-next-80b-a3b-instruct",
)
TRANSLATE_MAX_CONCURRENT = int(os.getenv("MOLTBOOK_TRANSLATE_CONCURRENCY", "16"))
TRANSLATE_DELAY = float(os.getenv("MOLTBOOK_TRANSLATE_DELAY", "0.05"))
TRANSLATE_TIMEOUT = int(os.getenv("MOLTBOOK_TRANSLATE_TIMEOUT", "180"))
TRANSLATE_MAX_RETRIES = int(os.getenv("MOLTBOOK_TRANSLATE_MAX_RETRIES", "3"))
TRANSLATE_RETRY_BACKOFF = float(os.getenv("MOLTBOOK_TRANSLATE_RETRY_BACKOFF", "1.0"))
TRANSLATE_PROGRESS_EVERY = int(os.getenv("MOLTBOOK_TRANSLATE_PROGRESS_EVERY", "10"))