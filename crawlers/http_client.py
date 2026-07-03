"""HTTP client with rate limiting, retries, and proxy rotation."""

from __future__ import annotations

import asyncio
import time
from typing import Callable, Literal

import aiohttp

from . import config

try:
    from proxy_hunter import ProxyPool
except ImportError:
    ProxyPool = None  # type: ignore

ProxyMode = Literal["off", "always", "fallback"]


class HttpClient:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        max_concurrent: int,
        delay: float,
        proxy_pool: ProxyPool | None = None,
        proxy_mode: ProxyMode = "off",
        shutdown_check: Callable[[], bool] | None = None,
    ):
        self.session = session
        self.max_concurrent = max_concurrent
        self.delay = delay
        self.proxy_pool = proxy_pool
        self.proxy_mode = proxy_mode
        self._shutdown_check = shutdown_check or (lambda: False)
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.request_count = 0
        self.error_count = 0
        self.proxy_rotations = 0
        self.direct_hits = 0
        self.proxy_hits = 0

    async def get_json(self, url: str, params: dict | None = None) -> dict | None:
        if self._shutdown_check():
            return None

        async with self.semaphore:
            if self.proxy_mode == "always" and self.proxy_pool:
                return await self._request_with_proxy(url, params, force_proxy=True)

            if self.proxy_mode == "fallback":
                data = await self._request_once(url, params, proxy=None)
                if data is not None:
                    self.direct_hits += 1
                    if self.delay > 0:
                        await asyncio.sleep(self.delay)
                    return data
                if self.proxy_pool:
                    data = await self._request_with_proxy(url, params, force_proxy=True)
                    if data is not None:
                        return data
                if self.delay > 0:
                    await asyncio.sleep(self.delay)
                return None

            # off — direct only
            data = await self._request_once(url, params, proxy=None)
            if data is not None and self.delay > 0:
                await asyncio.sleep(self.delay)
            return data

    async def _request_with_proxy(self, url: str, params: dict | None, force_proxy: bool) -> dict | None:
        proxy = self.proxy_pool.acquire() if self.proxy_pool else None
        for attempt in range(config.MAX_RETRIES):
            data, status = await self._request_once(url, params, proxy=proxy, return_status=True)
            if data is not None:
                if proxy and self.proxy_pool:
                    self.proxy_pool.report(proxy, success=True)
                self.proxy_hits += 1
                if self.delay > 0:
                    await asyncio.sleep(self.delay)
                return data

            if status == 429 and self.proxy_pool:
                if proxy:
                    self.proxy_pool.report(proxy, success=False)
                proxy = self.proxy_pool.acquire()
                self.proxy_rotations += 1
                await asyncio.sleep(0.5)
                continue

            if proxy and self.proxy_pool:
                self.proxy_pool.report(proxy, success=False)
                proxy = self.proxy_pool.acquire()
                self.proxy_rotations += 1
            if attempt < config.MAX_RETRIES - 1:
                await asyncio.sleep(config.RETRY_BACKOFF_BASE ** attempt)
        return None

    async def _request_once(
        self,
        url: str,
        params: dict | None,
        proxy: str | None,
        return_status: bool = False,
    ) -> dict | None | tuple[dict | None, int | None]:
        for attempt in range(config.MAX_RETRIES):
            try:
                async with self.session.get(url, params=params, proxy=proxy) as resp:
                    self.request_count += 1
                    if resp.status == 200:
                        data = await resp.json()
                        return (data, resp.status) if return_status else data
                    if resp.status == 429:
                        if return_status:
                            return (None, 429)
                        retry_after = resp.headers.get("Retry-After")
                        wait = float(retry_after) if retry_after else config.RETRY_BACKOFF_BASE ** (attempt + 1)
                        await asyncio.sleep(wait)
                        continue
                    if resp.status >= 500:
                        await asyncio.sleep(config.RETRY_BACKOFF_BASE ** attempt)
                        continue
                    self.error_count += 1
                    return (None, resp.status) if return_status else None
            except (aiohttp.ClientError, asyncio.TimeoutError):
                self.error_count += 1
                if attempt < config.MAX_RETRIES - 1:
                    await asyncio.sleep(config.RETRY_BACKOFF_BASE ** attempt)
                else:
                    return (None, None) if return_status else None
        return (None, None) if return_status else None

    def elapsed_rps(self, start: float) -> float:
        elapsed = time.time() - start
        return self.request_count / elapsed if elapsed > 0 else 0.0