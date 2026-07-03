"""Tests for crawl run reports."""

from __future__ import annotations

import json

from crawlers.run_report import CrawlReport


def test_crawl_report_save(tmp_data_dir):
    r = CrawlReport(crawler="SearchCrawler", started_at="2026-01-01 00:00:00 UTC")
    r.requests = 10
    r.failures = 1
    r.finish(ok=False)
    path = r.save(tmp_data_dir)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["requests"] == 10
    assert data["ok"] is False
    assert (tmp_data_dir / ".state" / "report_latest.json").exists()