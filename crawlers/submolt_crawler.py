"""Crawler for moltbook submolts (communities)."""

from tqdm import tqdm

from . import config
from .base_crawler import AsyncCrawler

OUTPUT_FILE = "submolts.jsonl"
DETAIL_FILE = "submolt_details.jsonl"


class SubmoltCrawler(AsyncCrawler):
    """Crawl submolt listing + optional per-community detail."""

    def __init__(self, fetch_details: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.fetch_details = fetch_details

    async def crawl(self):
        url = f"{config.API_BASE}/submolts"
        seen = self.store.load_seen(OUTPUT_FILE, "name")
        offset = self.store.read_state_int("submolts.offset", 0)

        data = await self.fetch_json(url, params={"limit": config.PAGE_SIZE, "offset": offset})
        if not data or not data.get("success"):
            print("[!] Failed to fetch submolt listing.")
            return

        total_count = data.get("count", config.ESTIMATED_TOTAL_SUBMOLTS)
        target = min(total_count, self.limit) if self.limit else total_count
        print(f"[*] Submolts on platform: {total_count:,}, target: {target:,}")

        saved = len(seen)
        pbar = tqdm(total=target, initial=min(saved, target), desc="Submolts", unit="sub")

        async def save_batch(batch: list[dict]) -> None:
            nonlocal saved
            if saved >= target:
                return
            new = [s for s in batch if s.get("name") and s["name"] not in seen]
            if not new:
                return
            if saved + len(new) > target:
                new = new[: target - saved]
            for s in new:
                seen.add(s["name"])
            await self.save_records(OUTPUT_FILE, new)
            saved += len(new)
            pbar.update(len(new))

        await save_batch(data.get("submolts", []))

        while saved < target and not self._shutdown:
            offset += config.PAGE_SIZE
            batch_data = await self.fetch_json(url, params={"limit": config.PAGE_SIZE, "offset": offset})
            if not batch_data or not batch_data.get("success"):
                print(f"[!] Failed at offset {offset}")
                break
            batch = batch_data.get("submolts", [])
            if not batch:
                break
            if saved + len(batch) > target:
                batch = batch[: target - saved]
            await save_batch(batch)
            self.store.write_state_int("submolts.offset", offset)

        pbar.close()
        print(f"[*] Saved {saved} submolts → {OUTPUT_FILE}")

        if self.fetch_details and not self._shutdown:
            detail_cap = min(len(seen), self.limit or 100)
            await self._fetch_details(list(seen)[:detail_cap])

    async def _fetch_details(self, names: list[str]) -> None:
        done = self.store.load_seen(DETAIL_FILE, "name")
        todo = [n for n in names if n not in done]
        print(f"[*] Submolt details: {len(todo)}")
        for name in tqdm(todo, desc="Details", unit="sub"):
            if self._shutdown:
                break
            data = await self.fetch_json(f"{config.API_BASE}/submolts/{name}")
            if data and data.get("success") and data.get("submolt"):
                rec = data["submolt"]
                rec["name"] = rec.get("name") or name
                await self.save_record(DETAIL_FILE, rec)