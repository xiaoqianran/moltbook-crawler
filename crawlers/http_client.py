"""HTTP client with rate limiting, retries, proxy rotation, and failure logging."""

from __future__ import annotations

import asyncio
import time
from typing import Callable, Literal
from urllib.parse import urlencode

import aiohttp

from . import config
from .failure_log import FailureLog
from .proxy_pool import ProxyPool

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
        failure_log: FailureLog | None = None,
    ):
        self.session = session
        self.max_concurrent = max_concurrent
        self.delay = delay
        self.proxy_pool = proxy_pool
        self.proxy_mode = proxy_mode
        self._shutdown_check = shutdown_check or (lambda: False)
        self.failure_log = failure_log
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.request_count = 0
        self.error_count = 0
        self.proxy_rotations = 0
        self.direct_hits = 0
        self.proxy_hits = 0

    def _url_label(self, url: str, params: dict | None) -> str:
        if not params:
            return url
        return f"{url}?{urlencode(params)}"

    async def _log_failure(
        self,
        url: str,
        params: dict | None,
        *,
        status: int | None = None,
        error: str | None = None,
        proxy: str | None = None,
        attempts: int = 1,
    ) -> None:
        if not self.failure_log:
            return
        await self.failure_log.record(
            url=url,
            params=params,
            status=status,
            error=error,
            proxy=proxy,
            proxy_mode=self.proxy_mode,
            attempts=attempts,
        )

    async def get_json(self, url: str, params: dict | None = None) -> dict | None:
        if self._shutdown_check():
            return None

        async with self.semaphore:
            if self.proxy_mode == "always" and self.proxy_pool:
                return await self._request_with_proxy(url, params)

            if self.proxy_mode == "fallback":
                data, status, err, proxy = await self._request_once(
                    url, params, proxy=None, return_meta=True,
                )
                if data is not None:
                    self.direct_hits += 1
                    if self.delay > 0:
                        await asyncio.sleep(self.delay)
                    return data
                if status == 429 or err:
                    await self._log_failure(
                        url, params, status=status, error=err or "direct failed",
                        proxy=None, attempts=config.MAX_RETRIES,
                    )
                if self.proxy_pool:
                    out = await self._request_with_proxy(url, params)
                    if out is not None:
                        return out
                    await self._log_failure(
                        url, params, error="fallback proxy also failed",
                        proxy=self.proxy_pool.acquire(),
                        attempts=config.MAX_RETRIES * 2,
                    )
                if self.delay > 0:
                    await asyncio.sleep(self.delay)
                return None

            data, status, err, _ = await self._request_once(
                url, params, proxy=None, return_meta=True,
            )
            if data is not None:
                if self.delay > 0:
                    await asyncio.sleep(self.delay)
                return data
            await self._log_failure(
                url, params, status=status, error=err or "request failed",
                attempts=config.MAX_RETRIES,
            )
            if self.delay > 0:
                await asyncio.sleep(self.delay)
            return None

    async def _request_with_proxy(self, url: str, params: dict | None) -> dict | None:
        proxy = self.proxy_pool.acquire() if self.proxy_pool else None
        status: int | None = None
        err: str | None = None
        for attempt in range(config.MAX_RETRIES):
            data, status, err, used = await self._request_once(
                url, params, proxy=proxy, return_meta=True,
            )
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

        await self._log_failure(
            url, params, status=status, error=err or "proxy exhausted retries",
            proxy=proxy, attempts=config.MAX_RETRIES,
        )
        return None

    async def _request_once(
        self,
        url: str,
        params: dict | None,
        proxy: str | None,
        return_meta: bool = False,
    ) -> dict | None | tuple[dict | None, int | None, str | None, str | None]:
        last_status: int | None = None
        last_err: str | None = None

        for attempt in range(config.MAX_RETRIES):
            try:
                async with self.session.get(url, params=params, proxy=proxy) as resp:
                    self.request_count += 1
                    last_status = resp.status
                    if resp.status == 200:
                        data = await resp.json()
                        if return_meta:
                            return data, resp.status, None, proxy
                        return data
                    if resp.status == 429:
                        if return_meta and attempt == config.MAX_RETRIES - 1:
                            return None, 429, "rate limited", proxy
                        retry_after = resp.headers.get("Retry-After")
                        wait = float(retry_after) if retry_after else config.RETRY_BACKOFF_BASE ** (attempt + 1)
                        await asyncio.sleep(wait)
                        continue
                    if resp.status >= 500:
                        last_err = f"HTTP {resp.status}"
                        await asyncio.sleep(config.RETRY_BACKOFF_BASE ** attempt)
                        continue
                    self.error_count += 1
                    last_err = f"HTTP {resp.status}"
                    if return_meta:
                        return None, resp.status, last_err, proxy
                    return None
            except asyncio.TimeoutError:
                self.error_count += 1
                last_err = "timeout"
                if attempt < config.MAX_RETRIES - 1:
                    await asyncio.sleep(config.RETRY_BACKOFF_BASE ** attempt)
            except aiohttp.ClientError as e:
                self.error_count += 1
                last_err = str(e)[:200]
                if attempt < config.MAX_RETRIES - 1:
                    await asyncio.sleep(config.RETRY_BACKOFF_BASE ** attempt)

        if return_meta:
            return None, last_status, last_err, proxy
        return None

    def elapsed_rps(self, start: float) -> float:
        elapsed = time.time() - start
        return self.request_count / elapsed if elapsed > 0 else 0.0