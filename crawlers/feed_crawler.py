"""Crawler for per-submolt public feeds — expands post/agent discovery."""

from tqdm import tqdm

from . import config
from .base_crawler import AsyncCrawler
from .paginate import crawl_cursor_pages
from .post_db import PostDB

SUBMOLTS_FILE = "submolts.jsonl"


class FeedCrawler(AsyncCrawler):
    """Crawl /submolts/{name}/feed for posts across communities."""

    async def crawl(self):
        submolts = self._load_submolt_names()
        if not submolts:
            submolts = await self._bootstrap_submolt_names()
        if not submolts:
            print("[!] No submolts found. Run submolts crawler first.")
            return

        cap = self.limit or config.DEFAULT_SUBMOLT_FEED_LIMIT
        submolts = submolts[:cap]
        authors: set[str] = set()
        total_new = 0
        total_dup = 0

        db = PostDB(self.data_dir)
        try:
            print(f"[*] Feeds for {len(submolts)} submolts → PostDB (no cross-file duplicates)")
            for name in tqdm(submolts, desc="Feeds", unit="sub"):
                if self._shutdown:
                    break

                async def on_page(items: list[dict], _data: dict, *, _name: str = name) -> None:
                    nonlocal total_new, total_dup
                    for p in items:
                        pid = p.get("id")
                        if not pid:
                            continue
                        p["_submolt"] = _name
                        result = db.upsert_from_api(
                            p,
                            source=f"feed/{_name}",
                            submolt=_name,
                        )
                        if result == "new":
                            total_new += 1
                        elif result == "duplicate":
                            total_dup += 1
                        author = p.get("author", {}).get("name")
                        if author:
                            authors.add(author)

                async def fetch_page(params: dict) -> dict | None:
                    return await self.fetch_json(
                        f"{config.API_BASE}/submolts/{name}/feed",
                        params=params,
                    )

                await crawl_cursor_pages(
                    fetch_page,
                    params={"limit": 25, "sort": "new"},
                    items_key="posts",
                    limit=100,
                    shutdown=lambda: self._shutdown,
                    on_page=on_page,
                )

            db.export_jsonl()
            stats = db.stats()
            print(f"[*] Feed crawl: +{total_new} new, {total_dup} duplicate merges")
            print(f"    PostDB total unique: {stats['total']}")
            if authors:
                existing = self.store.load_lines_as_set("post_authors.txt")
                self.store.write_lines("post_authors.txt", sorted(existing | authors))
            if self._report:
                self._report.extra = {"new": total_new, "duplicate": total_dup, **stats}
        finally:
            db.close()

    def _load_submolt_names(self) -> list[str]:
        records = self.store.load_jsonl_records(SUBMOLTS_FILE)
        names = []
        for r in records:
            n = r.get("name") or r.get("slug")
            if n:
                names.append(n)
        return names

    async def _bootstrap_submolt_names(self) -> list[str]:
        data = await self.fetch_json(f"{config.API_BASE}/submolts", params={"limit": 50, "offset": 0})
        if not data or not data.get("success"):
            return []
        return [s["name"] for s in data.get("submolts", []) if s.get("name")]