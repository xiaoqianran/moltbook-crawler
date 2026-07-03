"""Tests for static HTML viewer export."""

from __future__ import annotations

import json

from crawlers.post_db import PostDB
from crawlers.viewer_export import export_viewer


def test_export_viewer_generates_pages(tmp_data_dir):
    db = PostDB(tmp_data_dir)
    try:
        for i in range(25):
            db.upsert_from_api(
                {
                    "id": f"p{i}",
                    "title": f"Title {i}",
                    "content": f"Content {i}",
                    "author": {"name": f"agent{i}"},
                    "submolt": {"name": "general", "display_name": "General"},
                    "score": i,
                    "comment_count": 0,
                    "created_at": "2026-07-01T00:00:00Z",
                },
                source="test",
            )
            if i % 2 == 0:
                db.save_translation(f"p{i}", title_zh=f"标题{i}", content_zh=f"正文{i}", lang_detected="en")
    finally:
        db.close()

    out = export_viewer(tmp_data_dir, per_page=10)
    assert (out / "index.html").exists()
    assert (out / "page" / "1.html").exists()
    assert (out / "page" / "3.html").exists()
    assert (out / "post" / "p0.html").exists()
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["total_posts"] == 25
    assert meta["pages"] == 3
    page1 = (out / "page" / "1.html").read_text(encoding="utf-8")
    assert "标题0" in page1 or "Title" in page1