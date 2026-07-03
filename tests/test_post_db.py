"""Tests for PostDB dedup and bilingual fields."""

from __future__ import annotations

import json

from crawlers.post_db import PostDB


def _sample_post(pid: str, title: str = "Hello", content: str = "World") -> dict:
    return {
        "id": pid,
        "title": title,
        "content": content,
        "comment_count": 2,
        "author": {"name": "agent1"},
        "submolt": {"name": "general"},
    }


def test_upsert_dedup_across_sources(tmp_data_dir):
    db = PostDB(tmp_data_dir)
    try:
        assert db.upsert_from_api(_sample_post("p1"), source="posts/new", sort_mode="new") == "new"
        assert db.upsert_from_api(_sample_post("p1"), source="posts/hot", sort_mode="hot") == "duplicate"
        assert db.upsert_from_api(_sample_post("p1"), source="feed/general", submolt="general") == "duplicate"
        assert db.count() == 1

        row = db._conn.execute("SELECT sources, sort_modes FROM posts WHERE id = 'p1'").fetchone()
        sources = json.loads(row["sources"])
        sorts = json.loads(row["sort_modes"])
        assert "posts/new" in sources
        assert "posts/hot" in sources
        assert "feed/general" in sources
        assert "new" in sorts
        assert "hot" in sorts
    finally:
        db.close()


def test_export_bilingual_schema(tmp_data_dir):
    db = PostDB(tmp_data_dir)
    try:
        db.upsert_from_api(_sample_post("p2", "Title EN", "Body EN"), source="posts/new", sort_mode="new")
        db.save_translation("p2", title_zh="标题", content_zh="正文", lang_detected="en")
        out = db.export_jsonl()
        rec = json.loads(out.read_text(encoding="utf-8").strip())
        assert rec["title"] == "Title EN"
        assert rec["content"] == "Body EN"
        assert rec["title_original"] == "Title EN"
        assert rec["content_original"] == "Body EN"
        assert rec["title_zh"] == "标题"
        assert rec["content_zh"] == "正文"
        assert rec["translate_status"] == "done"
        assert "posts/new" in rec["_sources"]
    finally:
        db.close()


def test_import_jsonl_dedup(tmp_data_dir):
    db = PostDB(tmp_data_dir)
    legacy = tmp_data_dir / "posts.jsonl"
    p = _sample_post("p3")
    p["title_zh"] = "已有翻译"
    p["content_zh"] = "已有正文"
    legacy.write_text(json.dumps(p, ensure_ascii=False) + "\n", encoding="utf-8")
    p2 = _sample_post("p4")
    legacy.write_text(
        legacy.read_text(encoding="utf-8") + json.dumps(p2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    try:
        new, dup = db.import_jsonl_file(legacy, source="posts/legacy")
        assert new == 2
        assert dup == 0
        new2, dup2 = db.import_jsonl_file(legacy, source="posts/legacy")
        assert new2 == 0
        assert dup2 == 2
        assert db.count() == 2
        assert db.count_translated() == 1
    finally:
        db.close()