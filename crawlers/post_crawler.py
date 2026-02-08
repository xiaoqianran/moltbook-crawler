"""Crawler for moltbook posts and comments."""

import asyncio
import os

from tqdm import tqdm

from . import config
from .base_crawler import AsyncCrawler

POSTS_FILE = "posts.jsonl"
COMMENTS_FILE = "comments.jsonl"
AUTHORS_FILE = "post_authors.txt"

PAGE_SIZE = 50
ESTIMATED_TOTAL_POSTS = 270_000


class PostCrawler(AsyncCrawler):
    """Crawl all posts and their comments from moltbook."""

    def __init__(self, skip_comments: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.skip_comments = skip_comments
        self.authors: set[str] = set()
        self.posts_with_comments: list[int] = []

    async def crawl(self):
        await self._phase1_list_posts()
        if not self.skip_comments and self.posts_with_comments:
            await self._phase2_fetch_comments()

    # -- Phase 1: paginate through all posts ----------------------------------

    async def _phase1_list_posts(self):
        print("[*] Phase 1: Listing all posts (sort=new)")
        total_estimate = self.limit if self.limit else ESTIMATED_TOTAL_POSTS
        pbar = tqdm(total=total_estimate, unit="post", desc="Posts")
        offset = 0
        collected = 0

        while not self._shutdown:
            data = await self.fetch_json(
                f"{config.API_BASE}/posts",
                params={"limit": PAGE_SIZE, "sort": "new", "offset": offset},
            )
            if data is None or not data.get("success"):
                print(f"[!] Failed to fetch posts at offset={offset}, stopping.")
                break

            posts = data.get("posts", [])
            if not posts:
                break

            # If limit is set, trim the batch so we don't exceed it
            if self.limit and collected + len(posts) > self.limit:
                posts = posts[: self.limit - collected]

            await self.save_records(POSTS_FILE, posts)

            for p in posts:
                author = p.get("author", {})
                name = author.get("name")
                if name:
                    self.authors.add(name)
                if (p.get("comment_count") or 0) > 0:
                    self.posts_with_comments.append(p["id"])

            collected += len(posts)
            pbar.update(len(posts))

            if self.limit and collected >= self.limit:
                break
            if not data.get("has_more"):
                break

            offset = data.get("next_offset", offset + PAGE_SIZE)

        pbar.close()
        print(f"[*] Phase 1 complete: {collected} posts saved")
        print(f"    Unique authors: {len(self.authors)}")
        print(f"    Posts with comments: {len(self.posts_with_comments)}")

        # Write deduplicated author names
        authors_path = os.path.join(self.data_dir, AUTHORS_FILE)
        with open(authors_path, "w", encoding="utf-8") as f:
            for name in sorted(self.authors):
                f.write(name + "\n")
        print(f"    Author names saved to {AUTHORS_FILE}")

    # -- Phase 2: fetch comments from post detail -----------------------------

    async def _phase2_fetch_comments(self):
        total = len(self.posts_with_comments)
        print(f"\n[*] Phase 2: Fetching comments for {total} posts")
        pbar = tqdm(total=total, unit="post", desc="Comments")

        for i in range(0, total, config.MAX_CONCURRENT_REQUESTS):
            if self._shutdown:
                break
            batch = self.posts_with_comments[i : i + config.MAX_CONCURRENT_REQUESTS]
            tasks = [self._fetch_post_comments(pid) for pid in batch]
            await asyncio.gather(*tasks)
            pbar.update(len(batch))
            await asyncio.sleep(self.delay)

        pbar.close()
        print("[*] Phase 2 complete")

    async def _fetch_post_comments(self, post_id: int):
        data = await self.fetch_json(f"{config.API_BASE}/posts/{post_id}")
        if data is None or not data.get("success"):
            return

        comments = data.get("comments", [])
        flat = self._flatten_comments(post_id, comments)
        if flat:
            await self.save_records(COMMENTS_FILE, flat)

    def _flatten_comments(self, post_id: int, comments: list[dict]) -> list[dict]:
        """Recursively flatten nested comment tree, adding post_id to each."""
        result = []
        for c in comments:
            replies = c.pop("replies", [])
            c["post_id"] = post_id
            result.append(c)
            if replies:
                result.extend(self._flatten_comments(post_id, replies))
        return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--skip-comments", action="store_true")
    args = parser.parse_args()
    crawler = PostCrawler(limit=args.limit, skip_comments=args.skip_comments)
    asyncio.run(crawler.run())
