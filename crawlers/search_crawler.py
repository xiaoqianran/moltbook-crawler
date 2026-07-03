"""Crawler for moltbook search API — expands agent/post discovery."""

from tqdm import tqdm

from . import config
from .base_crawler import AsyncCrawler

SEARCH_FILE = "search_hits.jsonl"


class SearchCrawler(AsyncCrawler):
    """Run multiple search queries to collect agents and posts not reached by pagination."""

    async def crawl(self):
        queries = config.SEARCH_SEED_QUERIES
        if self.limit:
            queries = queries[: max(1, self.limit // 10)]

        print(f"[*] Search crawler: {len(queries)} queries")
        total_saved = 0
        seen_keys: set[str] = set()

        for q in tqdm(queries, desc="Queries", unit="q"):
            if self._shutdown:
                break

            for search_type in ("posts", "agents", "comments"):
                if self._shutdown:
                    break
                data = await self.fetch_json(
                    f"{config.API_BASE}/search",
                    params={"q": q, "type": search_type, "limit": 50},
                )
                if not data or not data.get("success"):
                    continue

                results = data.get("results") or data.get(search_type) or []
                batch = []
                for item in results:
                    key = f"{search_type}:{item.get('id') or item.get('name')}"
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    batch.append({
                        "query": q,
                        "type": search_type,
                        "item": item,
                    })

                if batch:
                    await self.save_records(SEARCH_FILE, batch)
                    total_saved += len(batch)

                if self.limit and total_saved >= self.limit:
                    print(f"[*] Search limit reached: {total_saved}")
                    return

        print(f"[*] Saved {total_saved} search hits to {SEARCH_FILE}")