"""Base async crawler with rate limiting, retries, and JSONL output."""

import asyncio
import json
import os
import signal
import time
from abc import ABC, abstractmethod

import aiofiles
import aiohttp
from tqdm import tqdm

from . import config


class AsyncCrawler(ABC):
    """Base class for all moltbook crawlers."""

    def __init__(
        self,
        max_concurrent: int = config.MAX_CONCURRENT_REQUESTS,
        delay: float = config.REQUEST_DELAY,
        data_dir: str = config.DATA_DIR,
        limit: int | None = None,
    ):
        self.max_concurrent = max_concurrent
        self.delay = delay
        self.data_dir = data_dir
        self.limit = limit
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.session: aiohttp.ClientSession | None = None
        self._shutdown = False
        self._request_count = 0
        self._error_count = 0
        self._start_time = 0.0

    async def __aenter__(self):
        await self.setup()
        return self

    async def __aexit__(self, *args):
        await self.teardown()

    async def setup(self):
        os.makedirs(self.data_dir, exist_ok=True)
        timeout = aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT)
        self.session = aiohttp.ClientSession(
            headers=config.HEADERS,
            timeout=timeout,
        )
        self._start_time = time.time()
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._handle_shutdown)
            except NotImplementedError:
                pass

    async def teardown(self):
        if self.session:
            await self.session.close()
            self.session = None

    def _handle_shutdown(self):
        print("\n[!] Shutdown requested, finishing current tasks...")
        self._shutdown = True

    async def fetch_json(self, url: str, params: dict | None = None) -> dict | None:
        """Fetch JSON from URL with rate limiting and retries."""
        if self._shutdown:
            return None

        async with self.semaphore:
            for attempt in range(config.MAX_RETRIES):
                try:
                    async with self.session.get(url, params=params) as resp:
                        self._request_count += 1
                        if resp.status == 200:
                            return await resp.json()
                        elif resp.status == 429:
                            wait = config.RETRY_BACKOFF_BASE ** (attempt + 1)
                            print(f"[!] Rate limited, waiting {wait}s...")
                            await asyncio.sleep(wait)
                        elif resp.status >= 500:
                            wait = config.RETRY_BACKOFF_BASE ** attempt
                            await asyncio.sleep(wait)
                        else:
                            self._error_count += 1
                            return None
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    self._error_count += 1
                    if attempt < config.MAX_RETRIES - 1:
                        wait = config.RETRY_BACKOFF_BASE ** attempt
                        await asyncio.sleep(wait)
                    else:
                        print(f"[!] Failed after {config.MAX_RETRIES} retries: {e}")
                        return None

            await asyncio.sleep(self.delay)
        return None

    async def save_record(self, filepath: str, record: dict):
        """Append a single JSON record to a JSONL file."""
        path = os.path.join(self.data_dir, filepath)
        async with aiofiles.open(path, "a", encoding="utf-8") as f:
            await f.write(json.dumps(record, ensure_ascii=False) + "\n")

    async def save_records(self, filepath: str, records: list[dict]):
        """Append multiple JSON records to a JSONL file."""
        if not records:
            return
        path = os.path.join(self.data_dir, filepath)
        async with aiofiles.open(path, "a", encoding="utf-8") as f:
            for record in records:
                await f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def print_stats(self):
        elapsed = time.time() - self._start_time
        rps = self._request_count / elapsed if elapsed > 0 else 0
        print(f"\n--- Crawl Stats ---")
        print(f"  Requests: {self._request_count}")
        print(f"  Errors:   {self._error_count}")
        print(f"  Time:     {elapsed:.1f}s")
        print(f"  RPS:      {rps:.1f}")

    @abstractmethod
    async def crawl(self):
        """Implement the crawling logic."""
        ...

    async def run(self):
        """Entry point: setup, crawl, teardown."""
        async with self:
            await self.crawl()
            self.print_stats()
