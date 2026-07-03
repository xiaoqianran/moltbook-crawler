"""Crawler for moltbook posts and comments."""

import asyncio
import json
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
    def __init__(self, skip_comments: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.skip_comments = skip_comments
        self.authors: set[str] = set()
        self.posts_with_comments: list[int] = []

    async def crawl(self):
        await self._phase1_list_posts()
        if not self.skip_comments and self.posts_with_comments:
            await self._phase2_fetch_comments()

    async def _phase1_list_posts(self):
        print("[*] Phase 1: Listing posts (sort=new)")
        seen_ids = self.store.load_seen(POSTS_FILE, "id")
        if seen_ids:
            print(f"    Resume: {len(seen_ids)} posts already in {POSTS_FILE}")

        offset = self.store.read_state_int("posts.offset", 0)
        if offset:
            print(f"    Resume offset: {offset}")

        total_estimate = self.limit if self.limit else ESTIMATED_TOTAL_POSTS
        pbar = tqdm(total=total_estimate, unit="post", desc="Posts")
        collected = 0

        while not self._shutdown:
            data = await self.fetch_json(
                f"{config.API_BASE}/posts",
                params={"limit": PAGE_SIZE, "sort": "new", "offset": offset},
            )
            if data is None or not data.get("success"):
                print(f"[!] Failed at offset={offset}")
                break

            posts = data.get("posts", [])
            if not posts:
                break

            new_posts = [p for p in posts if p.get("id") not in seen_ids]
            if self.limit and collected + len(new_posts) > self.limit:
                new_posts = new_posts[: self.limit - collected]

            if new_posts:
                await self.save_records(POSTS_FILE, new_posts)
                for p in new_posts:
                    pid = p.get("id")
                    if pid is not None:
                        seen_ids.add(pid)
                    name = p.get("author", {}).get("name")
                    if name:
                        self.authors.add(name)
                    if (p.get("comment_count") or 0) > 0 and pid is not None:
                        self.posts_with_comments.append(pid)

            collected += len(new_posts)
            pbar.update(len(new_posts))
            offset = data.get("next_offset", offset + PAGE_SIZE)
            self.store.write_state_int("posts.offset", offset)

            if self.limit and collected >= self.limit:
                break
            if not data.get("has_more"):
                break

        pbar.close()
        print(f"[*] Phase 1: {collected} new posts")
        print(f"    Authors: {len(self.authors)}, with comments: {len(self.posts_with_comments)}")

        self.store.write_lines(AUTHORS_FILE, sorted(self.authors))
        print(f"    Saved {AUTHORS_FILE}")

    async def _phase2_fetch_comments(self):
        done_posts = self._posts_with_saved_comments()
        todo = [pid for pid in self.posts_with_comments if pid not in done_posts]
        total = len(todo)
        print(f"\n[*] Phase 2: Comments for {total} posts")
        pbar = tqdm(total=total, unit="post", desc="Comments")

        for i in range(0, total, self.max_concurrent):
            if self._shutdown:
                break
            batch = todo[i : i + self.max_concurrent]
            await asyncio.gather(*[self._fetch_post_comments(pid) for pid in batch])
            pbar.update(len(batch))

        pbar.close()

    async def _fetch_post_comments(self, post_id: int):
        data = await self.fetch_json(f"{config.API_BASE}/posts/{post_id}")
        if not data or not data.get("success"):
            return
        comments = data.get("comments", [])
        flat = self._flatten_comments(post_id, comments)
        if flat:
            await self.save_records(COMMENTS_FILE, flat)

    def _flatten_comments(self, post_id: int, comments: list[dict]) -> list[dict]:
        result = []
        for c in comments:
            replies = c.pop("replies", [])
            c["post_id"] = post_id
            result.append(c)
            if replies:
                result.extend(self._flatten_comments(post_id, replies))
        return result

    def _posts_with_saved_comments(self) -> set[int]:
        done: set[int] = set()
        path = self.store.path(COMMENTS_FILE)
        if not os.path.exists(path):
            return done
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    pid = rec.get("post_id")
                    if pid is not None:
                        done.add(pid)
                except json.JSONDecodeError:
                    continue
        return done