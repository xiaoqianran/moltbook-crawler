"""Crawler for moltbook search API with cursor pagination."""

from tqdm import tqdm

from . import config
from .base_crawler import AsyncCrawler
from .paginate import crawl_cursor_pages

SEARCH_FILE = "search_hits.jsonl"


class SearchCrawler(AsyncCrawler):
    """Search across queries and types to discover agents/posts/comments."""

    async def crawl(self):
        queries = list(config.SEARCH_SEED_QUERIES)
        if self.limit:
            queries = queries[: max(1, self.limit // 20)]

        seen: set[str] = set()
        total = 0
        print(f"[*] Search: {len(queries)} queries × {len(config.SEARCH_TYPES)} types")

        for q in tqdm(queries, desc="Queries", unit="q"):
            if self._shutdown:
                break
            for stype in config.SEARCH_TYPES:
                if self._shutdown:
                    break

                async def on_page(items: list[dict], _data: dict) -> None:
                    nonlocal total
                    batch = []
                    for item in items:
                        key = f"{stype}:{item.get('id') or item.get('name') or item.get('title')}"
                        if key in seen:
                            continue
                        seen.add(key)
                        batch.append({"query": q, "type": stype, "item": item})
                    if batch:
                        await self.save_records(SEARCH_FILE, batch)
                        total += len(batch)

                async def fetch_page(params: dict) -> dict | None:
                    return await self.fetch_json(f"{config.API_BASE}/search", params=params)

                per_limit = None
                if self.limit:
                    per_limit = max(1, self.limit - total)
                    if per_limit <= 0:
                        print(f"[*] Search limit reached: {total}")
                        return

                await crawl_cursor_pages(
                    fetch_page,
                    params={"q": q, "type": stype, "limit": 50},
                    items_key="results",
                    limit=per_limit,
                    shutdown=lambda: self._shutdown,
                    on_page=on_page,
                )

        print(f"[*] Saved {total} search hits → {SEARCH_FILE}")