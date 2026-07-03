"""Live smoke checks — validate API + proxy results + logs."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import aiohttp

from . import config
from .logging_config import get_logger
from .proxy_pool import DEFAULT_RESULTS_DIR, load_pool_from_results

logger = get_logger("verify")

VERIFY_REPORT = "verify_report.json"


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""
    latency_ms: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerifyReport:
    started_at: str
    finished_at: str = ""
    elapsed_s: float = 0.0
    ok: bool = True
    checks: list[CheckResult] = field(default_factory=list)

    def add(self, check: CheckResult) -> None:
        self.checks.append(check)
        if not check.ok:
            self.ok = False

    def save(self, data_dir: str | Path) -> Path:
        path = Path(data_dir) / VERIFY_REPORT
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        return path


async def _get_json(session: aiohttp.ClientSession, url: str, params: dict | None = None) -> tuple[bool, str, float, dict | None]:
    t0 = time.perf_counter()
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            ms = round((time.perf_counter() - t0) * 1000, 1)
            if resp.status != 200:
                return False, f"HTTP {resp.status}", ms, None
            data = await resp.json()
            return True, "ok", ms, data
    except Exception as e:
        ms = round((time.perf_counter() - t0) * 1000, 1)
        return False, str(e)[:200], ms, None


def _check_proxy_results(results_dir: Path) -> CheckResult:
    try:
        pool = load_pool_from_results(results_dir, top_n_sources=3, max_proxies=10)
        stats = pool.stats()
        return CheckResult(
            name="proxy_results",
            ok=stats["alive"] > 0,
            detail=f"alive={stats['alive']}/{stats['total']} sources={stats['sources']}",
            extra=stats,
        )
    except Exception as e:
        return CheckResult(name="proxy_results", ok=False, detail=str(e)[:200])


def _check_log_file(data_dir: Path) -> CheckResult:
    log_file = data_dir / "logs" / "crawler.log"
    if not log_file.exists():
        return CheckResult(name="log_file", ok=False, detail=f"missing {log_file}")
    size = log_file.stat().st_size
    return CheckResult(name="log_file", ok=size > 0, detail=f"{log_file} ({size} bytes)")


def _check_failures_file(data_dir: Path) -> CheckResult:
    path = data_dir / "crawl_failures.jsonl"
    if not path.exists():
        return CheckResult(name="failure_log", ok=True, detail="no failures file yet (ok)")
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return CheckResult(
        name="failure_log",
        ok=True,
        detail=f"{len(lines)} failure records",
        extra={"count": len(lines)},
    )


async def run_verify(data_dir: str, *, proxy_results_dir: str | None = None) -> VerifyReport:
    started = time.time()
    report = VerifyReport(started_at=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    results_dir = Path(proxy_results_dir or config.PROXY_RESULTS_DIR)

    logger.info("verify started data_dir=%s", data_dir)

    api_checks = [
        ("api_posts", f"{config.API_BASE}/posts", {"limit": 1, "sort": "new"}),
        ("api_search", f"{config.API_BASE}/search", {"q": "agent", "type": "agents", "limit": 1}),
        ("api_homepage", f"{config.API_BASE}/homepage", {"shuffle": "1"}),
        ("api_submolts", f"{config.API_BASE}/submolts", {"limit": 1, "offset": 0}),
        ("api_agents_recent", f"{config.API_BASE}/agents/recent", {"limit": 1}),
    ]

    async with aiohttp.ClientSession(headers=config.HEADERS) as session:
        for name, url, params in api_checks:
            ok, detail, ms, data = await _get_json(session, url, params)
            extra = {}
            if data:
                if "posts" in data:
                    extra["count"] = len(data.get("posts", []))
                elif "results" in data:
                    extra["count"] = len(data.get("results", []))
                elif "agents" in data:
                    extra["count"] = len(data.get("agents", []))
                elif "submolts" in data:
                    extra["count"] = len(data.get("submolts", []))
            check = CheckResult(name=name, ok=ok, detail=detail, latency_ms=ms, extra=extra)
            report.add(check)
            if ok:
                logger.info("verify PASS %s %s (%sms)", name, detail, ms)
            else:
                logger.error("verify FAIL %s %s (%sms)", name, detail, ms)

    for fn in (
        lambda: _check_proxy_results(results_dir),
        lambda: _check_log_file(data_path),
        lambda: _check_failures_file(data_path),
    ):
        c = fn()
        report.add(c)
        (logger.info if c.ok else logger.error)("verify %s %s — %s", "PASS" if c.ok else "FAIL", c.name, c.detail)

    report.elapsed_s = round(time.time() - started, 2)
    report.finished_at = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    path = report.save(data_dir)
    logger.info("verify done ok=%s elapsed=%ss report=%s", report.ok, report.elapsed_s, path)
    return report