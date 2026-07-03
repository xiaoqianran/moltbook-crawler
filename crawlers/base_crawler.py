"""Base async crawler with proxy-hunter integration."""

from __future__ import annotations

import asyncio
import os
import signal
import time
from abc import ABC, abstractmethod
from pathlib import Path

import aiohttp

from . import config
from .failure_log import FailureLog
from .http_client import HttpClient
from .proxy_pool import DEFAULT_RESULTS_DIR, load_pool_from_results
from .storage import JsonlStore


class AsyncCrawler(ABC):
    """Base class for all moltbook crawlers."""

    def __init__(
        self,
        max_concurrent: int | None = None,
        delay: float | None = None,
        data_dir: str = config.DATA_DIR,
        limit: int | None = None,
        use_proxy: bool | None = None,
        proxy_results_dir: str | None = None,
        proxy_mode: str | None = None,
    ):
        self.data_dir = data_dir
        self.limit = limit
        self.use_proxy = config.USE_PROXY if use_proxy is None else use_proxy
        self.proxy_results_dir = proxy_results_dir or str(DEFAULT_RESULTS_DIR)
        self.proxy_mode = proxy_mode or ("fallback" if self.use_proxy else "off")

        if self.use_proxy:
            self.max_concurrent = max_concurrent or config.PROXY_MAX_CONCURRENT
            self.delay = delay if delay is not None else config.PROXY_REQUEST_DELAY
        else:
            self.max_concurrent = max_concurrent or config.MAX_CONCURRENT_REQUESTS
            self.delay = delay if delay is not None else config.REQUEST_DELAY

        self.store = JsonlStore(data_dir)
        self.failure_log = FailureLog(data_dir, crawler=self.__class__.__name__)
        self.session: aiohttp.ClientSession | None = None
        self.http: HttpClient | None = None
        self.proxy_pool = None
        self._shutdown = False
        self._start_time = 0.0

    async def __aenter__(self):
        await self.setup()
        return self

    async def __aexit__(self, *args):
        await self.teardown()

    async def setup(self):
        os.makedirs(self.data_dir, exist_ok=True)
        self._start_time = time.time()

        if self.use_proxy:
            print(f"[*] Proxy mode: {self.proxy_mode}")
            self.proxy_pool = load_pool_from_results(
                self.proxy_results_dir,
                top_n_sources=config.PROXY_TOP_SOURCES,
                max_proxies=config.PROXY_MAX_POOL,
            )
            stats = self.proxy_pool.stats()
            print(
                f"[*] Proxy pool ({self.proxy_mode}): "
                f"{stats['alive']}/{stats['total']} from {stats['sources']} sources"
            )

        timeout = aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT)
        self.session = aiohttp.ClientSession(headers=config.HEADERS, timeout=timeout)
        self.http = HttpClient(
            self.session,
            max_concurrent=self.max_concurrent,
            delay=self.delay,
            proxy_pool=self.proxy_pool,
            proxy_mode=self.proxy_mode,  # type: ignore[arg-type]
            shutdown_check=lambda: self._shutdown,
            failure_log=self.failure_log,
        )

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
            self.http = None

    def _handle_shutdown(self):
        print("\n[!] Shutdown requested, finishing current tasks...")
        self._shutdown = True

    async def fetch_json(self, url: str, params: dict | None = None) -> dict | None:
        if not self.http:
            return None
        return await self.http.get_json(url, params)

    async def save_record(self, filepath: str, record: dict) -> None:
        await self.store.append(filepath, record)

    async def save_records(self, filepath: str, records: list[dict]) -> None:
        await self.store.append_many(filepath, records)

    def print_stats(self):
        if not self.http:
            return
        elapsed = time.time() - self._start_time
        print("\n--- Crawl Stats ---")
        print(f"  Requests:  {self.http.request_count}")
        print(f"  Errors:    {self.http.error_count}")
        print(f"  Time:      {elapsed:.1f}s")
        print(f"  RPS:       {self.http.elapsed_rps(self._start_time):.1f}")
        print(f"  Mode:      {'proxy/' + self.proxy_mode if self.use_proxy else 'direct'}")
        self.failure_log.print_session_summary()
        if self.use_proxy:
            print(f"  Direct OK:   {self.http.direct_hits}")
            print(f"  Via proxy:   {self.http.proxy_hits}")
            if self.http.proxy_rotations:
                print(f"  Proxy rotations: {self.http.proxy_rotations}")

    @abstractmethod
    async def crawl(self):
        ...

    async def run(self):
        async with self:
            await self.crawl()
            self.print_stats()