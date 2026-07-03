"""Configuration for moltbook crawlers."""

import os
from pathlib import Path

BASE_URL = "https://www.moltbook.com"
API_BASE = f"{BASE_URL}/api/v1"

# Direct (no proxy) — conservative for single IP
MAX_CONCURRENT_REQUESTS = 2
REQUEST_DELAY = 1.0

# With proxy pool — spread load across exit IPs
PROXY_MAX_CONCURRENT = 12
PROXY_REQUEST_DELAY = 0.15

MAX_RETRIES = 5
RETRY_BACKOFF_BASE = 2
DEFAULT_BATCH_SIZE = 50
DATA_DIR = "data"
STATE_DIR = ".state"

HEADERS = {
    "User-Agent": "MoltbookCrawler/2.0 (Academic Research; Agent Social Network Analysis)",
    "Accept": "application/json",
}

REQUEST_TIMEOUT = 30

# proxy-hunter integration
USE_PROXY = os.getenv("MOLTBOOK_USE_PROXY", "").lower() in ("1", "true", "yes")
PROXY_RESULTS_DIR = os.getenv(
    "PROXY_HUNTER_RESULTS",
    str(Path(__file__).resolve().parents[2] / "proxy-hunter" / "source_tests" / "results"),
)
PROXY_TOP_SOURCES = 8
PROXY_MAX_POOL = 150

# Agent discovery search seeds
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