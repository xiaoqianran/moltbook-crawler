"""Crawler for per-submolt public feeds — expands post/agent discovery."""

from tqdm import tqdm

from . import config
from .base_crawler import AsyncCrawler
from .paginate import crawl_cursor_pages

FEED_POSTS_FILE = "feed_posts.jsonl"
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
        seen_post_ids = self.store.load_seen(FEED_POSTS_FILE, "id")
        authors: set[str] = set()
        total = 0

        print(f"[*] Feeds for {len(submolts)} submolts")
        for name in tqdm(submolts, desc="Feeds", unit="sub"):
            if self._shutdown:
                break

            async def on_page(items: list[dict], _data: dict) -> None:
                nonlocal total
                new = []
                for p in items:
                    pid = p.get("id")
                    if not pid or pid in seen_post_ids:
                        continue
                    seen_post_ids.add(pid)
                    p["_submolt"] = name
                    new.append(p)
                    author = p.get("author", {}).get("name")
                    if author:
                        authors.add(author)
                if new:
                    await self.save_records(FEED_POSTS_FILE, new)
                    total += len(new)

            async def fetch_page(params: dict) -> dict | None:
                return await self.fetch_json(
                    f"{config.API_BASE}/submolts/{name}/feed",
                    params=params,
                )

            await crawl_cursor_pages(
                fetch_page,
                params={"limit": 25, "sort": "new"},
                items_key="posts",
                limit=100,  # per submolt cap
                shutdown=lambda: self._shutdown,
                on_page=on_page,
            )

        if authors:
            existing = self.store.load_lines_as_set("post_authors.txt")
            self.store.write_lines("post_authors.txt", sorted(existing | authors))

        print(f"[*] Feed posts saved: {total} → {FEED_POSTS_FILE}")

    def _load_submolt_names(self) -> list[str]:
        records = self.store.load_jsonl_records(SUBMOLTS_FILE)
        names = []
        for r in records:
            n = r.get("name") or r.get("slug")
            if n:
                names.append(n)
        if names:
            return names

        return []

    async def _bootstrap_submolt_names(self) -> list[str]:
        data = await self.fetch_json(f"{config.API_BASE}/submolts", params={"limit": 50, "offset": 0})
        if not data or not data.get("success"):
            return []
        return [s["name"] for s in data.get("submolts", []) if s.get("name")]