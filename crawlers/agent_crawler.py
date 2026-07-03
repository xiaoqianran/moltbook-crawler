"""Crawler for moltbook.com agent profiles."""

import json

from tqdm import tqdm

from . import config
from .base_crawler import AsyncCrawler


class AgentCrawler(AsyncCrawler):
    """Collect agent profiles via multi-source seeds + snowball + search."""

    AGENTS_FILE = "agents.jsonl"
    TOP_HUMANS_FILE = "top_humans.jsonl"
    DISCOVER_FILE = "agent_discover.jsonl"
    SEARCH_FILE = "search_hits.jsonl"

    async def crawl(self):
        seen_names: set[str] = set()
        profile_queue: list[str] = []

        def add_name(name: str | None):
            if name and name not in seen_names:
                seen_names.add(name)
                profile_queue.append(name)

        # Step 1: top humans
        print("[*] Step 1: Fetching top humans...")
        top_humans = await self._fetch_top_humans()
        if top_humans:
            await self.save_records(self.TOP_HUMANS_FILE, top_humans)
            print(f"    Saved {len(top_humans)} top humans")
            for h in top_humans:
                add_name(h.get("bot_name"))

        # Step 2: recent agents
        print("[*] Step 2: Fetching recent agents...")
        for agent in await self._fetch_recent_agents():
            add_name(agent.get("name"))

        # Step 3: homepage
        print("[*] Step 3: Fetching homepage agents...")
        homepage = await self.fetch_json(f"{config.API_BASE}/homepage", params={"shuffle": "1"})
        if homepage and homepage.get("success"):
            for agent in homepage.get("agents", []):
                add_name(agent.get("name"))
            for post in homepage.get("posts", []):
                add_name(post.get("author", {}).get("name"))

        # Step 4: post authors
        authors = self.store.load_lines_as_set("post_authors.txt")
        if authors:
            print(f"[*] Step 4: Loaded {len(authors)} post authors")
            for name in authors:
                add_name(name)
        else:
            print("[*] Step 4: No post_authors.txt (run posts/search first for more seeds)")

        # Step 5: search hits
        search_names = self._load_search_agent_names()
        if search_names:
            print(f"[*] Step 5: Loaded {len(search_names)} agents from search_hits.jsonl")
            for name in search_names:
                add_name(name)

        # Step 6: live search queries (if search file empty)
        if not search_names:
            print("[*] Step 5b: Running inline search seeds...")
            for q in config.SEARCH_SEED_QUERIES[:4]:
                data = await self.fetch_json(
                    f"{config.API_BASE}/search",
                    params={"q": q, "type": "agents", "limit": 50},
                )
                if data and data.get("success"):
                    for item in data.get("results", data.get("agents", [])):
                        add_name(item.get("name"))

        already_crawled = self.store.load_seen(self.AGENTS_FILE, "name")
        if already_crawled:
            print(f"    Resume: skipping {len(already_crawled)} already-crawled agents")

        print(f"[*] Total seed names: {len(profile_queue)}")
        if not profile_queue:
            print("[!] No agent names collected.")
            return

        # Step 7: snowball profiles + discover
        print("[*] Step 7: Fetching profiles (snowball)...")
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
            if name in processed or name in already_crawled:
                continue
            processed.add(name)

            profile = await self._fetch_profile(name)
            if profile:
                await self.save_record(self.AGENTS_FILE, profile)
                saved_count += 1
                pbar.update(1)

            discover = await self._fetch_discover(name)
            if discover:
                await self.save_record(self.DISCOVER_FILE, {
                    "agent_name": name,
                    "similar_agents": discover.get("similarAgents", []),
                    "series": discover.get("series", []),
                })
                for similar in discover.get("similarAgents", []):
                    add_name(similar.get("name"))

                if self.limit:
                    pbar.total = min(len(profile_queue) - len(already_crawled), self.limit)
                else:
                    pbar.total = len(profile_queue) - len(already_crawled)
                pbar.refresh()

        pbar.close()
        print(f"[*] Done. {saved_count} new profiles (processed {len(processed)} names).")

    def _load_search_agent_names(self) -> list[str]:
        names: list[str] = []
        path = self.store.path(self.SEARCH_FILE)
        if not __import__("os").path.exists(path):
            return names
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("type") != "agents":
                        continue
                    item = rec.get("item", {})
                    if item.get("name"):
                        names.append(item["name"])
                except json.JSONDecodeError:
                    continue
        return names

    async def _fetch_top_humans(self) -> list[dict]:
        data = await self.fetch_json(f"{config.API_BASE}/agents/top-humans", params={"limit": 100})
        return data.get("humans", []) if data and data.get("success") else []

    async def _fetch_recent_agents(self) -> list[dict]:
        data = await self.fetch_json(
            f"{config.API_BASE}/agents/recent",
            params={"limit": 50, "sort": "newest"},
        )
        return data.get("agents", []) if data and data.get("success") else []

    async def _fetch_profile(self, name: str) -> dict | None:
        data = await self.fetch_json(f"{config.API_BASE}/agents/profile", params={"name": name})
        if data and data.get("success"):
            agent = data.get("agent", {})
            agent["_recent_posts"] = data.get("recentPosts", [])
            agent["_recent_comments"] = data.get("recentComments", [])
            return agent
        return None

    async def _fetch_discover(self, name: str) -> dict | None:
        data = await self.fetch_json(f"{config.API_BASE}/agents/{name}/discover")
        return data if data and data.get("success") else None