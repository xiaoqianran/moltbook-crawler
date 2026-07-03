"""Unified crawl + translate metrics dashboard (JSON)."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .failure_log import FAILURES_FILE
from .logging_config import get_logger
from .translate_log import TRANSLATE_OPS_FILE

logger = get_logger("dashboard")

DASHBOARD_FILE = "dashboard.json"
VERIFY_REPORT = "verify_report.json"


@dataclass
class Dashboard:
    generated_at: str
    data_dir: str
    health: dict[str, Any] = field(default_factory=dict)
    posts: dict[str, Any] = field(default_factory=dict)
    crawl: dict[str, Any] = field(default_factory=dict)
    translate: dict[str, Any] = field(default_factory=dict)
    datasets: dict[str, Any] = field(default_factory=dict)
    verify: dict[str, Any] = field(default_factory=dict)

    def save(self, data_dir: str | Path) -> Path:
        root = Path(data_dir)
        root.mkdir(parents=True, exist_ok=True)
        path = root / DASHBOARD_FILE
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        state = root / ".state"
        state.mkdir(parents=True, exist_ok=True)
        latest = state / "dashboard_latest.json"
        latest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        return path


def _jsonl_stats(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"records": 0, "bytes": 0}
    text = path.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return {"records": len(lines), "bytes": path.stat().st_size}


def _load_crawler_reports(state_dir: Path) -> list[dict[str, Any]]:
    if not state_dir.exists():
        return []
    reports = []
    for p in sorted(state_dir.glob("report_*.json")):
        if p.name == "report_latest.json":
            continue
        try:
            reports.append(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return reports


def _aggregate_translate_ops(path: Path) -> dict[str, Any]:
    base = {
        "ops_total": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "avg_latency_ms": None,
        "p95_latency_ms": None,
        "recent_failed": 0,
    }
    if not path.exists():
        return base

    latencies: list[float] = []
    recent = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            row = json.loads(ln)
        except json.JSONDecodeError:
            continue
        base["ops_total"] += 1
        status = row.get("status")
        if status == "success":
            base["success"] += 1
            if row.get("latency_ms") is not None:
                latencies.append(float(row["latency_ms"]))
        elif status == "failed":
            base["failed"] += 1
        elif status == "skipped":
            base["skipped"] += 1
        recent.append(row)

    for row in recent[-20:]:
        if row.get("status") == "failed":
            base["recent_failed"] += 1

    if latencies:
        latencies.sort()
        base["avg_latency_ms"] = round(sum(latencies) / len(latencies), 1)
        idx = max(0, int(len(latencies) * 0.95) - 1)
        base["p95_latency_ms"] = round(latencies[idx], 1)

    last = recent[-1] if recent else {}
    if last.get("model"):
        base["model"] = last["model"]
    if last.get("base_url"):
        base["base_url"] = last["base_url"]

    return base


def _load_post_db_stats(data_dir: Path) -> dict[str, Any]:
    from .post_db import DB_NAME, PostDB

    db_path = data_dir / DB_NAME
    if not db_path.exists():
        return {"total": 0, "translated": 0, "pending": 0, "failed": 0, "skipped": 0, "coverage_pct": 0.0}

    db = PostDB(data_dir)
    try:
        s = db.stats()
        total = s["total"]
        coverage = round((s["translated"] / total) * 100, 1) if total else 0.0
        return {**s, "coverage_pct": coverage}
    finally:
        db.close()


def _load_verify_summary(data_dir: Path) -> dict[str, Any]:
    path = data_dir / VERIFY_REPORT
    if not path.exists():
        return {"ok": None, "checks_passed": 0, "checks_failed": 0, "last_run": None, "checks": []}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"ok": False, "checks_passed": 0, "checks_failed": 0, "last_run": None, "checks": []}

    checks = raw.get("checks", [])
    passed = sum(1 for c in checks if c.get("ok"))
    failed = len(checks) - passed
    return {
        "ok": raw.get("ok"),
        "checks_passed": passed,
        "checks_failed": failed,
        "last_run": raw.get("finished_at") or raw.get("started_at"),
        "elapsed_s": raw.get("elapsed_s"),
        "checks": [{k: c.get(k) for k in ("name", "ok", "detail", "latency_ms")} for c in checks],
    }


def build_dashboard(data_dir: str | Path) -> Dashboard:
    root = Path(data_dir)
    state_dir = root / ".state"

    posts = _load_post_db_stats(root)
    verify = _load_verify_summary(root)
    crawler_reports = _load_crawler_reports(state_dir)
    translate = _aggregate_translate_ops(root / TRANSLATE_OPS_FILE)
    failure_count = _jsonl_stats(root / FAILURES_FILE)["records"]

    crawl_requests = sum(r.get("requests", 0) for r in crawler_reports)
    crawl_errors = sum(r.get("errors", 0) for r in crawler_reports)
    crawl_failures = sum(r.get("failures", 0) for r in crawler_reports)

    datasets: dict[str, Any] = {}
    if root.is_dir():
        for p in sorted(root.iterdir()):
            if p.is_file() and p.suffix == ".jsonl" and not p.name.startswith("."):
                datasets[p.name] = _jsonl_stats(p)

    health_ok = True
    if verify.get("ok") is False:
        health_ok = False
    if posts.get("failed", 0) > 0:
        health_ok = False
    if translate.get("recent_failed", 0) > 0:
        health_ok = False

    dash = Dashboard(
        generated_at=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        data_dir=str(root),
        health={
            "ok": health_ok,
            "verify_ok": verify.get("ok"),
            "posts_failed": posts.get("failed", 0),
            "translate_recent_failed": translate.get("recent_failed", 0),
        },
        posts=posts,
        crawl={
            "total_requests": crawl_requests,
            "total_errors": crawl_errors,
            "total_failures": crawl_failures,
            "failure_log_count": failure_count,
            "crawlers": [
                {
                    "name": r.get("crawler"),
                    "ok": r.get("ok"),
                    "elapsed_s": r.get("elapsed_s"),
                    "requests": r.get("requests"),
                    "errors": r.get("errors"),
                    "failures": r.get("failures"),
                    "rps": r.get("rps"),
                    "mode": r.get("mode"),
                    "extra": r.get("extra", {}),
                }
                for r in crawler_reports
            ],
        },
        translate=translate,
        datasets=datasets,
        verify=verify,
    )
    return dash


def save_dashboard(data_dir: str | Path) -> Path:
    dash = build_dashboard(data_dir)
    path = dash.save(data_dir)
    logger.info(
        "dashboard saved %s health_ok=%s posts=%s translate_ops=%s crawlers=%s",
        path,
        dash.health.get("ok"),
        dash.posts.get("total"),
        dash.translate.get("ops_total"),
        len(dash.crawl.get("crawlers", [])),
    )
    return path