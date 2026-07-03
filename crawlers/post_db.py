"""Canonical post store: SQLite dedup + bilingual fields."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

POSTS_JSONL = "posts.jsonl"
DB_NAME = "posts.db"


class PostDB:
    """Single source of truth for posts — UNIQUE id, no cross-source duplicates."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / DB_NAME
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS posts (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                title_zh TEXT,
                content_zh TEXT,
                lang_detected TEXT,
                translate_status TEXT NOT NULL DEFAULT 'pending',
                translate_error TEXT,
                sources TEXT NOT NULL DEFAULT '[]',
                sort_modes TEXT NOT NULL DEFAULT '[]',
                submolt TEXT,
                author_name TEXT,
                comment_count INTEGER DEFAULT 0,
                raw_json TEXT NOT NULL,
                crawled_at TEXT NOT NULL,
                translated_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_posts_translate ON posts(translate_status);
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]

    def count_translated(self) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM posts WHERE translate_status = 'done'"
        ).fetchone()[0]

    def upsert_from_api(self, raw: dict, *, source: str, sort_mode: str | None = None, submolt: str | None = None) -> str:
        """
        Insert new post or merge source tag into existing.
        Returns: 'new' | 'duplicate' | 'skip' (no id)
        """
        pid = raw.get("id")
        if not pid:
            return "skip"

        row = self._conn.execute("SELECT id, sources, sort_modes FROM posts WHERE id = ?", (pid,)).fetchone()
        now = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        author = (raw.get("author") or {}).get("name") or ""
        sm = submolt or raw.get("_submolt") or (raw.get("submolt") or {}).get("name") or ""

        if row:
            sources = json.loads(row["sources"])
            sorts = json.loads(row["sort_modes"])
            changed = False
            if source not in sources:
                sources.append(source)
                changed = True
            if sort_mode and sort_mode not in sorts:
                sorts.append(sort_mode)
                changed = True
            cc = int(raw.get("comment_count") or 0)
            self._conn.execute(
                """
                UPDATE posts SET
                    sources = ?, sort_modes = ?,
                    comment_count = MAX(comment_count, ?)
                WHERE id = ?
                """,
                (json.dumps(sources), json.dumps(sorts), cc, pid),
            )
            self._conn.commit()
            return "duplicate"

        self._conn.execute(
            """
            INSERT INTO posts (
                id, title, content, sources, sort_modes, submolt, author_name,
                comment_count, raw_json, crawled_at, translate_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                pid,
                raw.get("title") or "",
                raw.get("content") or "",
                json.dumps([source]),
                json.dumps([sort_mode] if sort_mode else []),
                sm,
                author,
                int(raw.get("comment_count") or 0),
                json.dumps(raw, ensure_ascii=False),
                now,
            ),
        )
        self._conn.commit()
        return "new"

    def get_pending_translation(self, limit: int | None = None) -> list[dict[str, Any]]:
        sql = "SELECT id, title, content, lang_detected FROM posts WHERE translate_status = 'pending'"
        if limit:
            sql += f" LIMIT {int(limit)}"
        rows = self._conn.execute(sql).fetchall()
        return [dict(r) for r in rows]

    def save_translation(
        self,
        post_id: str,
        *,
        title_zh: str,
        content_zh: str,
        lang_detected: str | None = None,
        backend: str = "",
    ) -> None:
        now = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        self._conn.execute(
            """
            UPDATE posts SET
                title_zh = ?, content_zh = ?, lang_detected = ?,
                translate_status = 'done', translated_at = ?, translate_error = NULL
            WHERE id = ?
            """,
            (title_zh, content_zh, lang_detected, now, post_id),
        )
        self._conn.commit()

    def mark_translate_failed(self, post_id: str, error: str) -> None:
        self._conn.execute(
            "UPDATE posts SET translate_status = 'failed', translate_error = ? WHERE id = ?",
            (error[:500], post_id),
        )
        self._conn.commit()

    def mark_translate_skipped(self, post_id: str, reason: str = "already_zh") -> None:
        self._conn.execute(
            "UPDATE posts SET translate_status = 'skipped', translate_error = ? WHERE id = ?",
            (reason, post_id),
        )
        self._conn.commit()

    def post_ids_with_comments(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT id FROM posts WHERE comment_count > 0"
        ).fetchall()
        return [r[0] for r in rows]

    def export_jsonl(self, path: str | Path | None = None) -> Path:
        """Export bilingual posts to posts.jsonl for downstream tools."""
        out = Path(path) if path else self.data_dir / POSTS_JSONL
        rows = self._conn.execute("SELECT * FROM posts ORDER BY crawled_at").fetchall()
        with open(out, "w", encoding="utf-8") as f:
            for row in rows:
                rec = self._row_to_export(dict(row))
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return out

    def _row_to_export(self, row: dict[str, Any]) -> dict[str, Any]:
        raw = json.loads(row["raw_json"])
        rec = {
            **raw,
            "id": row["id"],
            "title": row["title"],
            "content": row["content"],
            "title_original": row["title"],
            "content_original": row["content"],
            "title_zh": row["title_zh"],
            "content_zh": row["content_zh"],
            "lang_detected": row["lang_detected"],
            "translate_status": row["translate_status"],
            "_sources": json.loads(row["sources"]),
            "_sort_modes": json.loads(row["sort_modes"]),
            "_submolt": row["submolt"] or None,
            "_crawled_at": row["crawled_at"],
            "_translated_at": row["translated_at"],
        }
        return rec

    def import_jsonl_file(self, path: Path, *, source: str) -> tuple[int, int]:
        """Migrate legacy jsonl into DB with dedup. Returns (new, duplicate)."""
        new = dup = 0
        if not path.exists():
            return new, dup
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                raw = {
                    **raw,
                    "title": raw.get("title_original") or raw.get("title") or "",
                    "content": raw.get("content_original") or raw.get("content") or "",
                }
                r = self.upsert_from_api(raw, source=source, submolt=raw.get("_submolt"))
                if r == "new":
                    new += 1
                    pid = raw.get("id")
                    title_zh = raw.get("title_zh")
                    content_zh = raw.get("content_zh")
                    if pid and title_zh and content_zh:
                        self.save_translation(
                            pid,
                            title_zh=title_zh,
                            content_zh=content_zh,
                            lang_detected=raw.get("lang_detected"),
                        )
                elif r == "duplicate":
                    dup += 1
        return new, dup

    def stats(self) -> dict[str, int]:
        total = self.count()
        done = self.count_translated()
        pending = self._conn.execute(
            "SELECT COUNT(*) FROM posts WHERE translate_status = 'pending'"
        ).fetchone()[0]
        failed = self._conn.execute(
            "SELECT COUNT(*) FROM posts WHERE translate_status = 'failed'"
        ).fetchone()[0]
        skipped = self._conn.execute(
            "SELECT COUNT(*) FROM posts WHERE translate_status = 'skipped'"
        ).fetchone()[0]
        return {
            "total": total,
            "translated": done,
            "pending": pending,
            "failed": failed,
            "skipped": skipped,
        }