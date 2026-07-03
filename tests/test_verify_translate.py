"""Tests for verify checks related to posts.db and translate log."""

from __future__ import annotations

import json

import pytest

from crawlers.post_db import PostDB
from crawlers.translate_log import TRANSLATE_OPS_FILE, TranslateLog
from crawlers.verify import _check_post_db, _check_translate_log


def test_check_post_db_empty_ok(tmp_data_dir):
    r = _check_post_db(tmp_data_dir)
    assert r.ok
    assert "no posts.db" in r.detail


def test_check_post_db_with_records(tmp_data_dir):
    db = PostDB(tmp_data_dir)
    try:
        db.upsert_from_api(
            {"id": "x1", "title": "T", "content": "C"},
            source="test",
        )
        db.save_translation("x1", title_zh="标题", content_zh="正文", lang_detected="en")
    finally:
        db.close()
    r = _check_post_db(tmp_data_dir)
    assert r.ok
    assert r.extra["total"] == 1
    assert r.extra["translated"] == 1


@pytest.mark.asyncio
async def test_check_translate_log(tmp_data_dir):
    tlog = TranslateLog(tmp_data_dir)
    await tlog.record(post_id="p1", status="success", model="m", latency_ms=50)

    r = _check_translate_log(tmp_data_dir)
    assert r.ok
    assert r.extra["count"] == 1

    path = tmp_data_dir / TRANSLATE_OPS_FILE
    assert path.exists()
    row = json.loads(path.read_text(encoding="utf-8").strip())
    assert row["post_id"] == "p1"