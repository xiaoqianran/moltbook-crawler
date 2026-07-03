"""Per-request failure logging to JSONL."""

from __future__ import annotations

import json
import time
from pathlib import Path

import aiofiles

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

    def session_count(self) -> int:
        return self._session_failures

    def print_session_summary(self, max_show: int = 5) -> None:
        if self._session_failures == 0:
            print("  Failures:  0")
            return
        print(f"  Failures:  {self._session_failures}  → {FAILURES_FILE}")
        if not self.path.exists():
            return
        lines = self.path.read_text(encoding="utf-8").strip().splitlines()
        recent = lines[-max_show:]
        for line in recent:
            try:
                e = json.loads(line)
                st = e.get("status") or e.get("error") or "?"
                px = "proxy" if e.get("proxy") else "direct"
                print(f"    [{st}] {px} {e.get('url', '')[:70]}")
            except json.JSONDecodeError:
                continue