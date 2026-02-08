"""Crawler for moltbook agent social graph (discover/similar agents)."""

import argparse
import asyncio
import json
import os

from tqdm import tqdm

from . import config
from .base_crawler import AsyncCrawler

EDGES_FILE = "social_edges.jsonl"


class SocialGraphCrawler(AsyncCrawler):
    """Crawl agent discover endpoints to build a social graph."""

    def _load_agent_names(self) -> list[str]:
        """Load agent names from agents.jsonl or fall back to post_authors.txt."""
        agents_path = os.path.join(self.data_dir, "agents.jsonl")
        authors_path = os.path.join(self.data_dir, "post_authors.txt")

        names = []
        if os.path.exists(agents_path):
            print(f"[*] Reading agent names from {agents_path}")
            with open(agents_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        name = record.get("name")
                        if name:
                            names.append(name)
                    except json.JSONDecodeError:
                        continue
        elif os.path.exists(authors_path):
            print(f"[*] Reading agent names from {authors_path}")
            with open(authors_path, encoding="utf-8") as f:
                for line in f:
                    name = line.strip()
                    if name:
                        names.append(name)
        else:
            print("[!] No agent source found. Need data/agents.jsonl or data/post_authors.txt")

        return names

    async def _crawl_agent(self, name: str, pbar: tqdm):
        """Fetch discover endpoint for one agent and save edges."""
        if self._shutdown:
            return

        url = f"{config.API_BASE}/agents/{name}/discover"
        data = await self.fetch_json(url)
        pbar.update(1)

        if not data or not data.get("success"):
            return

        similar = data.get("similarAgents", [])
        edges = []
        for agent in similar:
            target_name = agent.get("name")
            if not target_name:
                continue
            edges.append({
                "source": name,
                "target": target_name,
                "shared_submolts": agent.get("shared_submolts", []),
                "shared_follower_count": agent.get("shared_follower_count", 0),
            })

        if edges:
            await self.save_records(EDGES_FILE, edges)

    async def crawl(self):
        names = self._load_agent_names()
        if not names:
            print("[!] No agents to process.")
            return

        if self.limit:
            names = names[: self.limit]

        print(f"[*] Processing {len(names)} agents for social graph")

        pbar = tqdm(total=len(names), desc="Agents", unit="agent")

        # Process in batches to respect concurrency
        batch_size = self.max_concurrent
        for i in range(0, len(names), batch_size):
            if self._shutdown:
                break
            batch = names[i : i + batch_size]
            tasks = [self._crawl_agent(name, pbar) for name in batch]
            await asyncio.gather(*tasks)

        pbar.close()
        print(f"[*] Social edges saved to {EDGES_FILE}")


async def main():
    parser = argparse.ArgumentParser(description="Crawl moltbook agent social graph")
    parser.add_argument("--limit", type=int, default=None, help="Max agents to process")
    args = parser.parse_args()

    crawler = SocialGraphCrawler(limit=args.limit)
    await crawler.run()


if __name__ == "__main__":
    asyncio.run(main())
