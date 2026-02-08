"""Crawler for moltbook.com agent profiles."""

import asyncio
import json
import os

from tqdm import tqdm

from . import config
from .base_crawler import AsyncCrawler


class AgentCrawler(AsyncCrawler):
    """Collects agent profiles from moltbook.com.

    Strategy: gather agent names from multiple sources (recent listing,
    top humans, post authors, homepage, discover endpoint snowballing),
    then fetch full profiles.
    """

    AGENTS_FILE = "agents.jsonl"
    TOP_HUMANS_FILE = "top_humans.jsonl"
    DISCOVER_FILE = "agent_discover.jsonl"

    async def crawl(self):
        seen_names: set[str] = set()
        profile_queue: list[str] = []

        def add_name(name: str):
            if name and name not in seen_names:
                seen_names.add(name)
                profile_queue.append(name)

        # --- Step 1: Fetch top humans ---
        print("[*] Step 1: Fetching top humans...")
        top_humans = await self._fetch_top_humans()
        if top_humans:
            await self.save_records(self.TOP_HUMANS_FILE, top_humans)
            print(f"    Saved {len(top_humans)} top humans")
            for h in top_humans:
                add_name(h.get("bot_name"))

        # --- Step 2: Fetch recent agents ---
        print("[*] Step 2: Fetching recent agents...")
        recent_agents = await self._fetch_recent_agents()
        if recent_agents:
            for agent in recent_agents:
                add_name(agent.get("name"))

        # --- Step 3: Fetch homepage agents ---
        print("[*] Step 3: Fetching homepage agents...")
        homepage = await self.fetch_json(
            f"{config.API_BASE}/homepage", params={"shuffle": "1"}
        )
        if homepage and homepage.get("success"):
            for agent in homepage.get("agents", []):
                add_name(agent.get("name"))
            # Extract author names from homepage posts
            for post in homepage.get("posts", []):
                author = post.get("author", {})
                add_name(author.get("name"))

        # --- Step 4: Load post_authors.txt if available ---
        authors_path = os.path.join(self.data_dir, "post_authors.txt")
        if os.path.exists(authors_path):
            print(f"[*] Step 4: Loading seed names from {authors_path}...")
            with open(authors_path, encoding="utf-8") as f:
                for line in f:
                    add_name(line.strip())
            print(f"    Loaded post authors, {len(profile_queue)} unique names now")
        else:
            print(f"[*] Step 4: No post_authors.txt found (run 'posts' crawler first for more seeds)")

        # --- Step 5: Load existing agents.jsonl to skip already crawled ---
        already_crawled: set[str] = set()
        agents_path = os.path.join(self.data_dir, self.AGENTS_FILE)
        if os.path.exists(agents_path):
            with open(agents_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        name = record.get("name")
                        if name:
                            already_crawled.add(name)
                    except json.JSONDecodeError:
                        continue
            if already_crawled:
                print(f"    Skipping {len(already_crawled)} already-crawled agents (resuming)")

        print(f"[*] Total seed names collected: {len(profile_queue)}")

        if not profile_queue:
            print("[!] No agent names collected, nothing to crawl.")
            return

        # --- Step 6: Fetch profiles + discover (snowball) ---
        print(f"[*] Step 6: Fetching profiles (snowball expansion enabled)...")
        saved_count = 0
        processed: set[str] = set()
        idx = 0
        target = min(len(profile_queue), self.limit) if self.limit else len(profile_queue)
        pbar = tqdm(total=target, desc="Profiles")

        while idx < len(profile_queue):
            if self._shutdown:
                break
            if self.limit and saved_count >= self.limit:
                break

            name = profile_queue[idx]
            idx += 1

            if name in processed:
                continue
            processed.add(name)

            # Skip if already crawled in a previous run
            if name in already_crawled:
                continue

            # Fetch profile
            profile_data = await self._fetch_profile(name)
            if profile_data:
                await self.save_record(self.AGENTS_FILE, profile_data)
                saved_count += 1
                pbar.update(1)

            # Fetch discover for snowball expansion
            discover_data = await self._fetch_discover(name)
            if discover_data:
                await self.save_record(self.DISCOVER_FILE, {
                    "agent_name": name,
                    "similar_agents": discover_data.get("similarAgents", []),
                    "series": discover_data.get("series", []),
                })
                for similar in discover_data.get("similarAgents", []):
                    add_name(similar.get("name"))

                # Update progress bar total
                if self.limit:
                    pbar.total = min(
                        len(profile_queue) - len(already_crawled),
                        self.limit,
                    )
                else:
                    pbar.total = len(profile_queue) - len(already_crawled)
                pbar.refresh()

        pbar.close()
        print(f"[*] Done. Saved {saved_count} new agent profiles (processed {len(processed)} names).")

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------

    async def _fetch_top_humans(self) -> list[dict]:
        url = f"{config.API_BASE}/agents/top-humans"
        data = await self.fetch_json(url, params={"limit": 100})
        if data and data.get("success"):
            return data.get("humans", [])
        return []

    async def _fetch_recent_agents(self) -> list[dict]:
        url = f"{config.API_BASE}/agents/recent"
        data = await self.fetch_json(url, params={"limit": 50, "sort": "newest"})
        if data and data.get("success"):
            return data.get("agents", [])
        return []

    async def _fetch_profile(self, name: str) -> dict | None:
        url = f"{config.API_BASE}/agents/profile"
        data = await self.fetch_json(url, params={"name": name})
        if data and data.get("success"):
            agent = data.get("agent", {})
            agent["_recent_posts"] = data.get("recentPosts", [])
            agent["_recent_comments"] = data.get("recentComments", [])
            return agent
        return None

    async def _fetch_discover(self, name: str) -> dict | None:
        url = f"{config.API_BASE}/agents/{name}/discover"
        data = await self.fetch_json(url)
        if data and data.get("success"):
            return data
        return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Crawl moltbook.com agent profiles")
    parser.add_argument("--limit", type=int, default=None, help="Max agents to crawl")
    args = parser.parse_args()

    crawler = AgentCrawler(limit=args.limit)
    asyncio.run(crawler.run())
