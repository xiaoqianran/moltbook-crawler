"""Per-post translation audit log — JSONL for monitoring and debugging."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import aiofiles

from .logging_config import get_logger

logger = get_logger("translate_log")

TRANSLATE_OPS_FILE = "translate_operations.jsonl"


@dataclass
class TranslateSessionStats:
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    latencies_ms: list[float] = field(default_factory=list)

    @property
    def avg_latency_ms(self) -> float | None:
        if not self.latencies_ms:
            return None
        return round(sum(self.latencies_ms) / len(self.latencies_ms), 1)

    @property
    def p95_latency_ms(self) -> float | None:
        if not self.latencies_ms:
            return None
        sorted_lat = sorted(self.latencies_ms)
        idx = max(0, int(len(sorted_lat) * 0.95) - 1)
        return round(sorted_lat[idx], 1)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "success": self.success,
            "failed": self.failed,
            "skipped": self.skipped,
            "avg_latency_ms": self.avg_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
        }


class TranslateLog:
    """Append-only JSONL log for each translation attempt."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.stats = TranslateSessionStats()

    @property
    def path(self) -> Path:
        return self.data_dir / TRANSLATE_OPS_FILE

    async def _write(self, entry: dict) -> None:
        async with aiofiles.open(self.path, "a", encoding="utf-8") as f:
            await f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    async def record(
        self,
        *,
        post_id: str,
        status: str,
        model: str = "",
        base_url: str = "",
        latency_ms: float | None = None,
        lang_detected: str | None = None,
        error: str | None = None,
        attempts: int = 1,
        title_len: int = 0,
        content_len: int = 0,
    ) -> None:
        self.stats.total += 1
        if status == "success":
            self.stats.success += 1
            if latency_ms is not None:
                self.stats.latencies_ms.append(latency_ms)
        elif status == "skipped":
            self.stats.skipped += 1
        else:
            self.stats.failed += 1

        entry = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "post_id": post_id,
            "status": status,
            "model": model,
            "base_url": base_url,
            "latency_ms": latency_ms,
            "lang_detected": lang_detected,
            "error": (error or "")[:500] or None,
            "attempts": attempts,
            "title_len": title_len,
            "content_len": content_len,
        }
        await self._write(entry)

        if status == "success":
            logger.info(
                "translate ok post_id=%s latency_ms=%s lang=%s title_len=%s content_len=%s",
                post_id,
                latency_ms,
                lang_detected,
                title_len,
                content_len,
            )
        elif status == "skipped":
            logger.debug("translate skip post_id=%s reason=%s", post_id, error or "already_zh")
        else:
            logger.warning(
                "translate fail post_id=%s attempts=%s error=%s latency_ms=%s",
                post_id,
                attempts,
                error,
                latency_ms,
            )

    def recent_entries(self, max_show: int = 10) -> list[dict]:
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

    def file_count(self) -> int:
        if not self.path.exists():
            return 0
        return sum(1 for ln in self.path.read_text(encoding="utf-8").splitlines() if ln.strip())