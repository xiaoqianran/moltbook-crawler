"""Crawler for moltbook.com agent profiles."""

from tqdm import tqdm

from . import config
from .base_crawler import AsyncCrawler


class AgentCrawler(AsyncCrawler):
    AGENTS_FILE = "agents.jsonl"
    TOP_HUMANS_FILE = "top_humans.jsonl"
    DISCOVER_FILE = "agent_discover.jsonl"

    async def crawl(self):
        seen_names: set[str] = set()
        profile_queue: list[str] = []

        def add_name(name: str | None):
            if name and name not in seen_names:
                seen_names.add(name)
                profile_queue.append(name)

        print("[*] Step 1: Top humans...")
        top = await self._fetch_top_humans()
        if top:
            await self.save_records(self.TOP_HUMANS_FILE, top)
            for h in top:
                add_name(h.get("bot_name"))

        print("[*] Step 2: Recent agents...")
        for agent in await self._fetch_recent_agents():
            add_name(agent.get("name"))

        print("[*] Step 3: Homepage...")
        homepage = await self.fetch_json(f"{config.API_BASE}/homepage", params={"shuffle": "1"})
        if homepage:
            for agent in homepage.get("agents", []):
                add_name(agent.get("name"))
            for post in homepage.get("posts", []):
                add_name(post.get("author", {}).get("name"))

        for src in ("post_authors.txt",):
            for name in self.store.load_lines_as_set(src):
                add_name(name)

        for rec in self.store.load_jsonl_records("search_hits.jsonl"):
            if rec.get("type") == "agents":
                add_name(rec.get("item", {}).get("name"))
            elif rec.get("type") == "posts":
                add_name(rec.get("item", {}).get("author", {}).get("name"))

        for rec in self.store.load_jsonl_records("feed_posts.jsonl"):
            add_name(rec.get("author", {}).get("name"))

        for rec in self.store.load_jsonl_records("posts.jsonl"):
            add_name(rec.get("author", {}).get("name"))

        if len(profile_queue) < 20:
            print("[*] Step 4: Inline search seeds...")
            for q in config.SEARCH_SEED_QUERIES[:6]:
                data = await self.fetch_json(
                    f"{config.API_BASE}/search",
                    params={"q": q, "type": "agents", "limit": 50},
                )
                if data and data.get("success"):
                    for item in data.get("results", []):
                        add_name(item.get("name") or item.get("author", {}).get("name"))

        already = self.store.load_seen(self.AGENTS_FILE, "name")
        if already:
            print(f"    Resume: skip {len(already)} crawled agents")

        print(f"[*] Seed queue: {len(profile_queue)} names")
        if not profile_queue:
            print("[!] No seeds.")
            return

        saved = 0
        processed: set[str] = set()
        idx = 0
        target = min(len(profile_queue), self.limit) if self.limit else len(profile_queue)
        pbar = tqdm(total=target, desc="Profiles")

        while idx < len(profile_queue):
            if self._shutdown or (self.limit and saved >= self.limit):
                break
            name = profile_queue[idx]
            idx += 1
            if name in processed or name in already:
                continue
            processed.add(name)

            profile = await self._fetch_profile(name)
            if profile:
                await self.save_record(self.AGENTS_FILE, profile)
                saved += 1
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
                pbar.total = (
                    min(len(profile_queue) - len(already), self.limit)
                    if self.limit
                    else len(profile_queue) - len(already)
                )
                pbar.refresh()

        pbar.close()
        print(f"[*] {saved} new profiles ({len(processed)} processed)")

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