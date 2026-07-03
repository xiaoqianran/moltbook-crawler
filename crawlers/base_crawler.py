"""Base async crawler with logging, reports, and proxy integration."""

from __future__ import annotations

import asyncio
import os
import signal
import time
from abc import ABC, abstractmethod

import aiohttp

from . import config
from .failure_log import FailureLog
from .http_client import HttpClient
from .logging_config import get_logger
from .proxy_pool import DEFAULT_RESULTS_DIR, load_pool_from_results
from .run_report import CrawlReport
from .storage import JsonlStore

logger = get_logger("crawler")


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
        self._logger = get_logger(self.__class__.__name__)

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
        self._report: CrawlReport | None = None

    async def __aenter__(self):
        await self.setup()
        return self

    async def __aexit__(self, *args):
        await self.teardown()

    async def setup(self):
        os.makedirs(self.data_dir, exist_ok=True)
        self._start_time = time.time()
        self._report = CrawlReport(
            crawler=self.__class__.__name__,
            started_at=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            mode=f"proxy/{self.proxy_mode}" if self.use_proxy else "direct",
        )

        if self.use_proxy:
            self._logger.info("proxy mode=%s results=%s", self.proxy_mode, self.proxy_results_dir)
            self.proxy_pool = load_pool_from_results(
                self.proxy_results_dir,
                top_n_sources=config.PROXY_TOP_SOURCES,
                max_proxies=config.PROXY_MAX_POOL,
            )
            stats = self.proxy_pool.stats()
            self._logger.info(
                "proxy pool alive=%s total=%s sources=%s",
                stats["alive"],
                stats["total"],
                stats["sources"],
            )
        else:
            self._logger.info("connection=direct concurrency=%s delay=%s", self.max_concurrent, self.delay)

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
        self._logger.warning("shutdown requested")
        self._shutdown = True

    async def fetch_json(self, url: str, params: dict | None = None) -> dict | None:
        if not self.http:
            return None
        return await self.http.get_json(url, params)

    async def save_record(self, filepath: str, record: dict) -> None:
        await self.store.append(filepath, record)

    async def save_records(self, filepath: str, records: list[dict]) -> None:
        await self.store.append_many(filepath, records)

    def _emit_stats(self) -> CrawlReport | None:
        if not self.http or not self._report:
            return None

        elapsed = time.time() - self._start_time
        r = self._report
        r.elapsed_s = round(elapsed, 2)
        r.requests = self.http.request_count
        r.errors = self.http.error_count
        r.failures = self.failure_log.session_count()
        r.rps = round(self.http.elapsed_rps(self._start_time), 2)
        r.proxy_direct_hits = self.http.direct_hits
        r.proxy_hits = self.http.proxy_hits
        r.proxy_rotations = self.http.proxy_rotations
        r.finish(ok=r.failures == 0 or r.requests > 0)

        self._logger.info(
            "done requests=%s errors=%s failures=%s rps=%s elapsed=%ss mode=%s",
            r.requests,
            r.errors,
            r.failures,
            r.rps,
            r.elapsed_s,
            r.mode,
        )

        if r.failures:
            for e in self.failure_log.recent_entries(3):
                self._logger.warning(
                    "recent failure status=%s url=%s",
                    e.get("status") or e.get("error"),
                    (e.get("url") or "")[:80],
                )

        path = r.save(self.data_dir)
        self._logger.info("report saved %s", path)
        return r

    @abstractmethod
    async def crawl(self):
        ...

    async def run(self):
        self._logger.info("crawl start limit=%s data_dir=%s", self.limit, self.data_dir)
        try:
            async with self:
                await self.crawl()
        except Exception:
            self._logger.exception("crawl failed")
            if self._report:
                self._report.finish(ok=False)
                self._report.save(self.data_dir)
            raise
        self._emit_stats()