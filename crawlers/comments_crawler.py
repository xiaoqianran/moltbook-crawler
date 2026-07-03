"""Crawler for post comments via dedicated /posts/{id}/comments API."""

import asyncio

from tqdm import tqdm

from . import config
from .base_crawler import AsyncCrawler
from .paginate import crawl_cursor_pages

COMMENTS_FILE = "comments.jsonl"
POSTS_FILE = "posts.jsonl"


class CommentsCrawler(AsyncCrawler):
    """Fetch comments with cursor pagination (lighter than full post detail)."""

    async def crawl(self):
        todo = self._load_todo_post_ids()
        if not todo:
            print("[!] No posts to fetch comments for. Run posts crawler first.")
            return

        done = self._posts_with_saved_comments()
        todo = [pid for pid in todo if pid not in done]
        if self.limit:
            todo = todo[: self.limit]

        print(f"[*] Comments for {len(todo)} posts")
        pbar = tqdm(total=len(todo), desc="Comments", unit="post")

        for i in range(0, len(todo), self.max_concurrent):
            if self._shutdown:
                break
            batch = todo[i : i + self.max_concurrent]
            await asyncio.gather(*[self._crawl_post_comments(pid, pbar) for pid in batch])

        pbar.close()

    def _load_todo_post_ids(self) -> list[str]:
        todo_path = self.store.state_path("comments.todo.txt")
        if todo_path.exists():
            names = {ln.strip() for ln in todo_path.read_text(encoding="utf-8").splitlines() if ln.strip()}
            if names:
                return sorted(names)

        # fallback: posts.jsonl with comment_count > 0
        ids: list[str] = []
        for rec in self.store.load_jsonl_records(POSTS_FILE):
            if (rec.get("comment_count") or 0) > 0 and rec.get("id"):
                ids.append(rec["id"])
        return ids

    def _posts_with_saved_comments(self) -> set[str]:
        done: set[str] = set()
        for rec in self.store.load_jsonl_records(COMMENTS_FILE):
            pid = rec.get("post_id")
            if pid:
                done.add(pid)
        return done

    async def _crawl_post_comments(self, post_id: str, pbar: tqdm) -> None:
        collected: list[dict] = []

        async def on_page(items: list[dict], _data: dict) -> None:
            for c in items:
                c["post_id"] = post_id
            collected.extend(items)

        async def fetch_page(params: dict) -> dict | None:
            return await self.fetch_json(
                f"{config.API_BASE}/posts/{post_id}/comments",
                params=params,
            )

        await crawl_cursor_pages(
            fetch_page,
            params={"limit": 35, "sort": "new"},
            items_key="comments",
            shutdown=lambda: self._shutdown,
            on_page=on_page,
        )

        if collected:
            await self.save_records(COMMENTS_FILE, collected)
        pbar.update(1)