"""Per-request failure logging to JSONL + structured logger."""

from __future__ import annotations

import json
import time
from pathlib import Path

import aiofiles

from .logging_config import get_logger

logger = get_logger("failure")
FAILURES_FILE = "crawl_failures.jsonl"


class FailureLog:
    def __init__(self, data_dir: str, crawler: str = ""):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.crawler = crawler
        self._session_failures = 0

    @property
    def path(self) -> Path:
        return self.data_dir / FAILURES_FILE

    async def record(
        self,
        *,
        url: str,
        params: dict | None = None,
        status: int | None = None,
        error: str | None = None,
        proxy: str | None = None,
        proxy_mode: str = "off",
        attempts: int = 1,
    ) -> None:
        self._session_failures += 1
        entry = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "crawler": self.crawler,
            "url": url,
            "params": params,
            "status": status,
            "error": error,
            "proxy": proxy,
            "proxy_mode": proxy_mode,
            "attempts": attempts,
        }
        async with aiofiles.open(self.path, "a", encoding="utf-8") as f:
            await f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.warning(
            "request failed crawler=%s status=%s error=%s proxy=%s url=%s params=%s",
            self.crawler,
            status,
            error,
            "yes" if proxy else "no",
            url,
            params,
        )

    def session_count(self) -> int:
        return self._session_failures

    def recent_entries(self, max_show: int = 5) -> list[dict]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").strip().splitlines()
        out = []
        for line in lines[-max_show:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out