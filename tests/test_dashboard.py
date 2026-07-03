"""Tests for unified metrics dashboard."""

from __future__ import annotations

import json

from crawlers.dashboard import DASHBOARD_FILE, build_dashboard, save_dashboard
from crawlers.post_db import PostDB
from crawlers.run_report import CrawlReport
from crawlers.translate_log import TranslateLog


def _write_verify(data_dir, *, ok: bool = True):
    report = {
        "started_at": "2026-01-01 00:00:00 UTC",
        "finished_at": "2026-01-01 00:00:05 UTC",
        "ok": ok,
        "checks": [
            {"name": "api_posts", "ok": ok, "detail": "ok"},
            {"name": "translate_api", "ok": True, "detail": "skipped"},
        ],
    }
    (data_dir / "verify_report.json").write_text(json.dumps(report), encoding="utf-8")


async def _seed_translate_ops(data_dir, *, include_failure: bool = False):
    tlog = TranslateLog(data_dir)
    await tlog.record(post_id="p1", status="success", model="m1", latency_ms=100.0)
    if include_failure:
        await tlog.record(post_id="p2", status="failed", model="m1", error="timeout")


def test_build_dashboard_empty(tmp_data_dir):
    dash = build_dashboard(tmp_data_dir)
    assert dash.posts["total"] == 0
    assert dash.crawl["crawlers"] == []
    assert dash.translate["ops_total"] == 0


def test_build_dashboard_aggregates(tmp_data_dir):
    db = PostDB(tmp_data_dir)
    try:
        db.upsert_from_api({"id": "a1", "title": "T", "content": "C"}, source="test")
        db.save_translation("a1", title_zh="标题", content_zh="正文", lang_detected="en")
    finally:
        db.close()

    state = tmp_data_dir / ".state"
    state.mkdir()
    r = CrawlReport(crawler="PostCrawler", started_at="2026-01-01 00:00:00 UTC")
    r.requests = 10
    r.extra = {"new": 1, "duplicate": 0}
    r.finish()
    r.save(tmp_data_dir)

    import asyncio
    asyncio.run(_seed_translate_ops(tmp_data_dir))
    _write_verify(tmp_data_dir, ok=True)
    (tmp_data_dir / "posts.jsonl").write_text("{}\n", encoding="utf-8")

    dash = build_dashboard(tmp_data_dir)
    assert dash.posts["total"] == 1
    assert dash.posts["translated"] == 1
    assert dash.posts["coverage_pct"] == 100.0
    assert len(dash.crawl["crawlers"]) == 1
    assert dash.crawl["crawlers"][0]["name"] == "PostCrawler"
    assert dash.translate["success"] == 1
    assert dash.translate["failed"] == 0
    assert dash.verify["ok"] is True
    assert dash.health["ok"] is True
    assert "posts.jsonl" in dash.datasets


def test_save_dashboard_writes_files(tmp_data_dir):
    path = save_dashboard(tmp_data_dir)
    assert path == tmp_data_dir / DASHBOARD_FILE
    assert (tmp_data_dir / ".state" / "dashboard_latest.json").exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "generated_at" in data
    assert "health" in data
    assert "crawl" in data
    assert "translate" in data


def test_health_degraded_on_verify_fail(tmp_data_dir):
    _write_verify(tmp_data_dir, ok=False)
    dash = build_dashboard(tmp_data_dir)
    assert dash.health["ok"] is False
    assert dash.verify["checks_failed"] >= 1


def test_health_degraded_on_translate_failure(tmp_data_dir):
    import asyncio

    asyncio.run(_seed_translate_ops(tmp_data_dir, include_failure=True))
    dash = build_dashboard(tmp_data_dir)
    assert dash.translate["failed"] == 1
    assert dash.health["translate_recent_failed"] == 1
    assert dash.health["ok"] is False