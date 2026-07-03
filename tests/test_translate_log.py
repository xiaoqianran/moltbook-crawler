"""Tests for translate operation audit log."""

from __future__ import annotations

import json

import pytest

from crawlers.translate_log import TRANSLATE_OPS_FILE, TranslateLog


@pytest.mark.asyncio
async def test_translate_log_writes_and_stats(tmp_data_dir):
    tlog = TranslateLog(tmp_data_dir)
    await tlog.record(post_id="a", status="success", model="m", latency_ms=100.0, lang_detected="en")
    await tlog.record(post_id="b", status="failed", model="m", error="timeout")
    await tlog.record(post_id="c", status="skipped", model="m", error="already_zh")

    assert tlog.stats.total == 3
    assert tlog.stats.success == 1
    assert tlog.stats.failed == 1
    assert tlog.stats.skipped == 1
    assert tlog.stats.avg_latency_ms == 100.0

    path = tmp_data_dir / TRANSLATE_OPS_FILE
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 3
    assert rows[0]["status"] == "success"
    assert len(tlog.recent_entries()) == 3