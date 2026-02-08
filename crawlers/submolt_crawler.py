"""Crawler for moltbook submolts (communities)."""

import argparse
import asyncio

from tqdm import tqdm

from . import config
from .base_crawler import AsyncCrawler

OUTPUT_FILE = "submolts.jsonl"


class SubmoltCrawler(AsyncCrawler):
    """Crawl all submolts via paginated listing endpoint."""

    async def crawl(self):
        url = f"{config.API_BASE}/submolts"

        # First request to get total count
        data = await self.fetch_json(url, params={"limit": 50, "offset": 0})
        if not data or not data.get("success"):
            print("[!] Failed to fetch initial submolt listing.")
            return

        total = data["count"]
        if self.limit:
            total = min(total, self.limit)

        print(f"[*] Total submolts to crawl: {total}")

        # Save first batch
        submolts = data.get("submolts", [])
        if self.limit:
            submolts = submolts[: self.limit]
        await self.save_records(OUTPUT_FILE, submolts)
        saved = len(submolts)

        pbar = tqdm(total=total, desc="Submolts", unit="sub")
        pbar.update(saved)

        offset = 50
        while saved < total and not self._shutdown:
            batch_data = await self.fetch_json(
                url, params={"limit": 50, "offset": offset}
            )
            if not batch_data or not batch_data.get("success"):
                print(f"[!] Failed at offset {offset}, skipping.")
                offset += 50
                continue

            batch = batch_data.get("submolts", [])
            if not batch:
                break

            remaining = total - saved
            if len(batch) > remaining:
                batch = batch[:remaining]

            await self.save_records(OUTPUT_FILE, batch)
            saved += len(batch)
            pbar.update(len(batch))
            offset += 50

        pbar.close()
        print(f"[*] Saved {saved} submolts to {OUTPUT_FILE}")


async def main():
    parser = argparse.ArgumentParser(description="Crawl moltbook submolts")
    parser.add_argument("--limit", type=int, default=None, help="Max submolts to fetch")
    args = parser.parse_args()

    crawler = SubmoltCrawler(limit=args.limit)
    await crawler.run()


if __name__ == "__main__":
    asyncio.run(main())
