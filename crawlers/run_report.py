"""Per-crawler run report persisted as JSON for audit and verify."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CrawlReport:
    crawler: str
    started_at: str
    finished_at: str = ""
    elapsed_s: float = 0.0
    requests: int = 0
    errors: int = 0
    failures: int = 0
    rps: float = 0.0
    mode: str = "direct"
    proxy_direct_hits: int = 0
    proxy_hits: int = 0
    proxy_rotations: int = 0
    ok: bool = True
    notes: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def finish(self, *, ok: bool = True) -> None:
        self.ok = ok
        self.finished_at = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    def save(self, data_dir: str | Path) -> Path:
        state = Path(data_dir) / ".state"
        state.mkdir(parents=True, exist_ok=True)
        safe = self.crawler.replace(" ", "_")
        path = state / f"report_{safe}.json"
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        latest = state / "report_latest.json"
        latest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        return path