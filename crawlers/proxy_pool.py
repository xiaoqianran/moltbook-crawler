"""Load proxy pool from bundled proxy-hunter results (no pip package)."""

from __future__ import annotations

import json
import random
import threading
from dataclasses import dataclass, field
from pathlib import Path

# moltbook-crawler/proxy-hunter/ — git submodule or vendored copy
PROXY_HUNTER_ROOT = Path(__file__).resolve().parents[1] / "proxy-hunter"
DEFAULT_RESULTS_DIR = PROXY_HUNTER_ROOT / "source_tests" / "results"


@dataclass
class ProxyEntry:
    url: str
    source_id: str
    latency_ms: float | None = None
    https_ok: bool = False
    failures: int = 0
    successes: int = 0

    @property
    def score(self) -> float:
        base = self.latency_ms if self.latency_ms is not None else 500.0
        return base + self.failures * 2000 - self.successes * 50


@dataclass
class ProxyPool:
    entries: list[ProxyEntry]
    max_failures: int = 5
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _cursor: int = 0

    def __len__(self) -> int:
        return len(self.entries)

    def alive(self) -> list[ProxyEntry]:
        return [e for e in self.entries if e.failures < self.max_failures]

    def acquire(self) -> str | None:
        with self._lock:
            alive = self.alive()
            if not alive:
                for e in self.entries:
                    e.failures = 0
                alive = self.entries
            if not alive:
                return None
            alive.sort(key=lambda e: e.score)
            pick = alive[self._cursor % len(alive)]
            self._cursor += 1
            return pick.url

    def report(self, url: str, *, success: bool) -> None:
        with self._lock:
            for e in self.entries:
                if e.url == url:
                    if success:
                        e.successes += 1
                        e.failures = max(0, e.failures - 1)
                    else:
                        e.failures += 1
                    return

    def stats(self) -> dict:
        alive = self.alive()
        return {
            "total": len(self.entries),
            "alive": len(alive),
            "sources": len({e.source_id for e in self.entries}),
        }


def _ranking_source_ids(results_dir: Path, top_n: int = 8) -> list[str]:
    ranking = results_dir / "00_RANKING.json"
    if not ranking.exists():
        return []
    data = json.loads(ranking.read_text(encoding="utf-8"))
    ok = [s for s in data.get("summaries", []) if s.get("fetch_ok") and s.get("working", 0) > 0]
    ok.sort(key=lambda x: (-x.get("success_rate", 0), -(x.get("working", 0))))
    return [s["id"] for s in ok[:top_n]]


def load_pool_from_results(
    results_dir: Path | str | None = None,
    *,
    source_ids: list[str] | None = None,
    top_n_sources: int = 8,
    max_proxies: int = 150,
) -> ProxyPool:
    root = Path(results_dir) if results_dir else DEFAULT_RESULTS_DIR
    if not root.exists():
        raise FileNotFoundError(
            f"未找到代理结果: {root}\n"
            f"请先运行: cd proxy-hunter/source_tests && python run_all.py"
        )

    ids = source_ids or _ranking_source_ids(root, top_n=top_n_sources)
    if not ids:
        raise FileNotFoundError(f"{root} 无排名数据，请先运行 proxy-hunter/source_tests/run_all.py")

    entries: list[ProxyEntry] = []
    seen: set[str] = set()
    for sid in ids:
        path = root / f"{sid}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data.get("working_proxies", []):
            url = item.get("proxy")
            if not url or url in seen:
                continue
            seen.add(url)
            entries.append(
                ProxyEntry(
                    url=url,
                    source_id=sid,
                    latency_ms=item.get("latency_ms"),
                    https_ok=bool(item.get("https_ok")),
                )
            )
            if len(entries) >= max_proxies:
                break
        if len(entries) >= max_proxies:
            break

    if not entries:
        raise RuntimeError(f"未能从 {root} 加载可用代理")

    entries.sort(key=lambda e: (e.latency_ms is None, e.latency_ms or 9999))
    return ProxyPool(entries)