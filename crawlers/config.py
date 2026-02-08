"""Configuration constants for moltbook crawlers."""

BASE_URL = "https://www.moltbook.com"
API_BASE = f"{BASE_URL}/api/v1"

# Rate limiting
MAX_CONCURRENT_REQUESTS = 5
REQUEST_DELAY = 0.5  # seconds between batch requests
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # exponential backoff base (seconds)

# Default batch sizes
DEFAULT_BATCH_SIZE = 50

# Output
DATA_DIR = "data"

# HTTP
HEADERS = {
    "User-Agent": "MoltbookCrawler/1.0 (Academic Research; Agent Social Network Analysis)",
    "Accept": "application/json",
}

# Request timeout (seconds)
REQUEST_TIMEOUT = 30
