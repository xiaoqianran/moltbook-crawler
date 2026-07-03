"""Tests for failure logging."""

from __future__ import annotations

import json

import pytest

from crawlers.failure_log import FAILURES_FILE, FailureLog


@pytest.mark.asyncio
async def test_failure_log_writes_jsonl(tmp_data_dir):
    fl = FailureLog(str(tmp_data_dir), crawler="TestCrawler")
    await fl.record(url="https://example.com/api", status=429, error="rate limited")
    assert fl.session_count() == 1
    path = tmp_data_dir / FAILURES_FILE
    assert path.exists()
    row = json.loads(path.read_text(encoding="utf-8").strip())
    assert row["status"] == 429
    assert row["crawler"] == "TestCrawler"
    assert len(fl.recent_entries()) == 1