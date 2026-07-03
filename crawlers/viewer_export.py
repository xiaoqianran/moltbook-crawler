"""Export bilingual posts to a Zhihu-style paginated static HTML viewer."""

from __future__ import annotations

import html
import json
import math
import re
from pathlib import Path

from .logging_config import get_logger
from .post_db import PostDB

logger = get_logger("viewer")

VIEWER_DIR = "viewer"
POSTS_PER_PAGE = 20

_CSS = """
:root {
  --bg: #f6f6f6;
  --card: #ffffff;
  --text: #1a1a1a;
  --muted: #8590a6;
  --link: #175199;
  --border: #ebebeb;
  --accent: #0066ff;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB",
    "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
  min-height: 100vh;
}
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }
.header {
  background: var(--card);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 100;
}
.header-inner {
  max-width: 1000px;
  margin: 0 auto;
  padding: 14px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.logo { font-size: 22px; font-weight: 700; color: var(--accent); }
.logo span { color: var(--text); font-weight: 400; font-size: 14px; margin-left: 8px; }
.stats { font-size: 13px; color: var(--muted); }
.container { max-width: 1000px; margin: 0 auto; padding: 16px 20px 80px; }
.card {
  background: var(--card);
  border-radius: 4px;
  padding: 18px 20px;
  margin-bottom: 10px;
  border: 1px solid var(--border);
  transition: box-shadow .15s;
}
.card:hover { box-shadow: 0 2px 8px rgba(0,0,0,.06); }
.card-title {
  font-size: 18px;
  font-weight: 600;
  line-height: 1.4;
  margin-bottom: 8px;
}
.card-title a { color: var(--text); }
.card-title a:hover { color: var(--link); }
.card-excerpt { font-size: 15px; color: #444; margin-bottom: 12px; }
.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 13px;
  color: var(--muted);
  align-items: center;
}
.author { font-weight: 500; color: #444; }
.tag {
  background: #f0f2f5;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 12px;
}
.badge-done { color: #52c41a; }
.badge-pending { color: #faad14; }
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 6px;
  margin-top: 24px;
  flex-wrap: wrap;
}
.pagination a, .pagination span {
  display: inline-block;
  min-width: 36px;
  height: 36px;
  line-height: 36px;
  text-align: center;
  border-radius: 4px;
  font-size: 14px;
}
.pagination a {
  background: var(--card);
  border: 1px solid var(--border);
  color: var(--text);
}
.pagination a:hover { border-color: var(--accent); color: var(--accent); text-decoration: none; }
.pagination .current {
  background: var(--accent);
  color: #fff;
  border: 1px solid var(--accent);
}
.pagination .disabled { color: #ccc; border: 1px solid var(--border); background: #fafafa; }
.detail-header { margin-bottom: 20px; }
.detail-title { font-size: 26px; font-weight: 700; line-height: 1.35; margin-bottom: 12px; }
.detail-meta { font-size: 14px; color: var(--muted); margin-bottom: 20px; }
.tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--border);
  margin-bottom: 20px;
}
.tab {
  padding: 10px 20px;
  font-size: 15px;
  color: var(--muted);
  border-bottom: 2px solid transparent;
  cursor: default;
}
.tab.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
.content-block {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 24px;
  font-size: 16px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}
.content-block h3 { font-size: 14px; color: var(--muted); margin-bottom: 12px; font-weight: 500; }
.bilingual .content-block { margin-bottom: 16px; }
.back { font-size: 14px; margin-bottom: 16px; display: inline-block; }
.footer {
  text-align: center;
  padding: 24px;
  font-size: 12px;
  color: var(--muted);
}
"""


def _esc(text: str | None) -> str:
    return html.escape(text or "")


def _excerpt(text: str, n: int = 160) -> str:
    t = re.sub(r"\s+", " ", text.strip())
    if len(t) <= n:
        return t
    return t[:n].rstrip() + "…"


def _load_posts(data_dir: Path) -> list[dict]:
    db = PostDB(data_dir)
    try:
        rows = db._conn.execute(
            "SELECT raw_json, title, content, title_zh, content_zh, translate_status, "
            "submolt, author_name, crawled_at, translated_at FROM posts ORDER BY crawled_at DESC"
        ).fetchall()
        posts = []
        for row in rows:
            raw = json.loads(row["raw_json"])
            posts.append({
                **raw,
                "title": row["title"],
                "content": row["content"],
                "title_zh": row["title_zh"] or row["title"],
                "content_zh": row["content_zh"] or "",
                "translate_status": row["translate_status"],
                "_submolt": row["submolt"] or raw.get("_submolt"),
            })
        return posts
    finally:
        db.close()


def _page_shell(title: str, body: str, *, base: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)} — Moltbook 帖子</title>
<style>{_CSS}</style>
</head>
<body>
{body}
<div class="footer">Moltbook Crawler · 双语帖子归档 · 仅供学术研究</div>
</body>
</html>"""


def _header_html(total: int, translated: int, base: str = "") -> str:
    return f"""
<header class="header">
  <div class="header-inner">
    <div class="logo">Moltbook<span>AI 社区帖子</span></div>
    <div class="stats">共 {total} 篇 · 已译 {translated} 篇</div>
  </div>
</header>"""


def _pagination_html(page: int, total_pages: int, base: str = "") -> str:
    if total_pages <= 1:
        return ""
    parts = []
    prefix = f"{base}page/" if base else "page/"
    if page > 1:
        parts.append(f'<a href="{prefix}{page - 1}.html">‹ 上一页</a>')
    else:
        parts.append('<span class="disabled">‹ 上一页</span>')

    start = max(1, page - 3)
    end = min(total_pages, page + 3)
    if start > 1:
        parts.append(f'<a href="{prefix}1.html">1</a>')
        if start > 2:
            parts.append('<span class="disabled">…</span>')
    for p in range(start, end + 1):
        if p == page:
            parts.append(f'<span class="current">{p}</span>')
        else:
            parts.append(f'<a href="{prefix}{p}.html">{p}</a>')
    if end < total_pages:
        if end < total_pages - 1:
            parts.append('<span class="disabled">…</span>')
        parts.append(f'<a href="{prefix}{total_pages}.html">{total_pages}</a>')

    if page < total_pages:
        parts.append(f'<a href="{prefix}{page + 1}.html">下一页 ›</a>')
    else:
        parts.append('<span class="disabled">下一页 ›</span>')

    return f'<nav class="pagination">{"".join(parts)}</nav>'


def _card_html(post: dict, base: str = "") -> str:
    pid = post["id"]
    title_zh = post.get("title_zh") or post.get("title") or "(无标题)"
    content_zh = post.get("content_zh") or post.get("content") or ""
    author = (post.get("author") or {}).get("name") or post.get("author_name") or "匿名"
    submolt = (post.get("submolt") or {}).get("display_name") or post.get("_submolt") or "general"
    score = post.get("score") or post.get("upvotes") or 0
    comments = post.get("comment_count") or 0
    status = post.get("translate_status", "pending")
    badge = "badge-done" if status == "done" else "badge-pending"
    status_label = "已翻译" if status == "done" else ("已跳过" if status == "skipped" else "待翻译")
    created = (post.get("created_at") or "")[:10]

    return f"""
<article class="card">
  <h2 class="card-title"><a href="{base}post/{pid}.html">{_esc(title_zh)}</a></h2>
  <p class="card-excerpt">{_esc(_excerpt(content_zh or post.get("content", "")))}</p>
  <div class="card-meta">
    <span class="author">{_esc(author)}</span>
    <span class="tag">{_esc(submolt)}</span>
    <span>👍 {score}</span>
    <span>💬 {comments}</span>
    <span>{created}</span>
    <span class="{badge}">{status_label}</span>
  </div>
</article>"""


def _detail_html(post: dict, page: int, base: str = "") -> str:
    pid = post["id"]
    title_zh = post.get("title_zh") or post.get("title") or ""
    title_en = post.get("title") or ""
    content_zh = post.get("content_zh") or ""
    content_en = post.get("content") or ""
    author = (post.get("author") or {}).get("name") or "匿名"
    submolt = (post.get("submolt") or {}).get("display_name") or post.get("_submolt") or ""
    lang = post.get("lang_detected") or "?"

    zh_block = content_zh or "（暂无译文）"
    en_block = content_en or "（无原文）"

    return f"""
<a class="back" href="{base}page/{page}.html">← 返回列表</a>
<div class="detail-header">
  <h1 class="detail-title">{_esc(title_zh or title_en)}</h1>
  <div class="detail-meta">
    {_esc(author)} · {_esc(submolt)} · 原文语言 {lang}
    · <a href="https://www.moltbook.com/post/{pid}" target="_blank" rel="noopener">查看原帖 ↗</a>
  </div>
</div>
<div class="tabs">
  <span class="tab active">译文</span>
  <span class="tab">原文</span>
  <span class="tab">双语</span>
</div>
<div class="bilingual">
  <div class="content-block">
    <h3>简体中文</h3>
    <strong>{_esc(title_zh)}</strong>

{_esc(zh_block)}
  </div>
  <div class="content-block">
    <h3>原文 ({lang})</h3>
    <strong>{_esc(title_en)}</strong>

{_esc(en_block)}
  </div>
</div>"""


def export_viewer(data_dir: str | Path, *, per_page: int = POSTS_PER_PAGE) -> Path:
    root = Path(data_dir)
    out = root / VIEWER_DIR
    page_dir = out / "page"
    post_dir = out / "post"
    page_dir.mkdir(parents=True, exist_ok=True)
    post_dir.mkdir(parents=True, exist_ok=True)

    posts = _load_posts(root)
    if not posts:
        logger.warning("no posts to export")
        out.joinpath("index.html").write_text(
            _page_shell("暂无帖子", "<p>请先运行 posts/feeds 爬虫</p>"),
            encoding="utf-8",
        )
        return out

    translated = sum(1 for p in posts if p.get("translate_status") == "done")
    total_pages = max(1, math.ceil(len(posts) / per_page))
    header = _header_html(len(posts), translated)

    post_page_map: dict[str, int] = {}
    for i, post in enumerate(posts):
        post_page_map[post["id"]] = i // per_page + 1

    for page_num in range(1, total_pages + 1):
        start = (page_num - 1) * per_page
        batch = posts[start : start + per_page]
        cards = "".join(_card_html(p) for p in batch)
        body = f"{header}<main class=\"container\">{cards}{_pagination_html(page_num, total_pages)}</main>"
        page_dir.joinpath(f"{page_num}.html").write_text(
            _page_shell(f"第 {page_num} 页", body),
            encoding="utf-8",
        )

    for post in posts:
        pid = post["id"]
        page_num = post_page_map[pid]
        body = f"{header}<main class=\"container\">{_detail_html(post, page_num)}</main>"
        post_dir.joinpath(f"{pid}.html").write_text(
            _page_shell(post.get("title_zh") or post.get("title", ""), body),
            encoding="utf-8",
        )

    out.joinpath("index.html").write_text(
        f'<!DOCTYPE html><html><head><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0;url=page/1.html"></head>'
        f'<body><a href="page/1.html">进入帖子列表</a></body></html>',
        encoding="utf-8",
    )

    meta = {
        "total_posts": len(posts),
        "translated": translated,
        "pages": total_pages,
        "per_page": per_page,
    }
    out.joinpath("meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("viewer exported %s posts=%s pages=%s path=%s", out, len(posts), total_pages, out)
    return out