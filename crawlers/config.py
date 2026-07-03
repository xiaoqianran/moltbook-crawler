"""Configuration for moltbook crawlers."""

import os
from pathlib import Path

BASE_URL = "https://www.moltbook.com"
API_BASE = f"{BASE_URL}/api/v1"

MAX_CONCURRENT_REQUESTS = 2
REQUEST_DELAY = 1.0
PROXY_MAX_CONCURRENT = 12
PROXY_REQUEST_DELAY = 0.15

MAX_RETRIES = 5
RETRY_BACKOFF_BASE = 2
DEFAULT_BATCH_SIZE = 50
DATA_DIR = "data"

HEADERS = {
    "User-Agent": "MoltbookCrawler/2.0 (Academic Research; Agent Social Network Analysis)",
    "Accept": "application/json",
}

REQUEST_TIMEOUT = 30

# Bundled proxy-hunter (submodule at moltbook-crawler/proxy-hunter/)
PROXY_HUNTER_ROOT = Path(__file__).resolve().parents[1] / "proxy-hunter"
PROXY_RESULTS_DIR = str(PROXY_HUNTER_ROOT / "source_tests" / "results")

USE_PROXY = os.getenv("MOLTBOOK_USE_PROXY", "").lower() in ("1", "true", "yes")
PROXY_TOP_SOURCES = 8
PROXY_MAX_POOL = 150

SEARCH_SEED_QUERIES = [
    "agent",
    "memory",
    "AI safety",
    "moltbook",
    "llm",
    "autonomous",
    "tool use",
    "reasoning",
]