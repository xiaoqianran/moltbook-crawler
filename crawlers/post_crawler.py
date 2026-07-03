"""Crawler for moltbook posts (multi-sort, cursor pagination)."""

from tqdm import tqdm

from . import config
from .base_crawler import AsyncCrawler
from .paginate import crawl_cursor_pages

POSTS_FILE = "posts.jsonl"
AUTHORS_FILE = "post_authors.txt"


class PostCrawler(AsyncCrawler):
    """Crawl posts via /posts with cursor pagination across sort modes."""

    def __init__(self, sorts: tuple[str, ...] | None = None, **kwargs):
        super().__init__(**kwargs)
        self.sorts = sorts or config.POST_SORTS
        self.authors: set[str] = set()
        self.posts_with_comments: list[str] = []

    async def crawl(self):
        seen_ids = self.store.load_seen(POSTS_FILE, "id")
        if seen_ids:
            print(f"[*] Resume: {len(seen_ids)} posts already in {POSTS_FILE}")

        total_new = 0
        for sort in self.sorts:
            if self._shutdown:
                break
            remaining = None
            if self.limit:
                remaining = max(0, self.limit - total_new)
                if remaining == 0:
                    break

            print(f"[*] Listing posts sort={sort}")
            pbar = tqdm(desc=f"posts/{sort}", unit="post")

            async def on_page(items: list[dict], _data: dict) -> None:
                nonlocal total_new
                new = [p for p in items if p.get("id") not in seen_ids]
                if not new:
                    return
                for p in new:
                    pid = p.get("id")
                    if pid:
                        seen_ids.add(pid)
                    name = p.get("author", {}).get("name")
                    if name:
                        self.authors.add(name)
                    if (p.get("comment_count") or 0) > 0 and pid:
                        self.posts_with_comments.append(pid)
                await self.save_records(POSTS_FILE, new)
                total_new += len(new)
                pbar.update(len(new))

            state_key = f"posts.cursor.{sort}"

            async def fetch_page(params: dict) -> dict | None:
                return await self.fetch_json(f"{config.API_BASE}/posts", params=params)

            base_params = {"limit": config.PAGE_SIZE, "sort": sort}
            # restore cursor if resuming this sort only when no new limit override
            saved = self.store.read_state_str(state_key)
            if saved and not self.limit:
                base_params["cursor"] = saved

            n = await crawl_cursor_pages(
                fetch_page,
                params=base_params,
                items_key="posts",
                limit=remaining,
                shutdown=lambda: self._shutdown,
                on_page=on_page,
            )
            pbar.close()
            print(f"    sort={sort}: {n} posts this run")

        print(f"[*] Total new posts: {total_new}")
        print(f"    Authors: {len(self.authors)}, with comments: {len(self.posts_with_comments)}")
        self.store.write_lines(AUTHORS_FILE, sorted(self.authors))

        # Save post ids needing comments for comments crawler
        if self.posts_with_comments:
            todo_path = self.store.state_path("comments.todo.txt")
            existing: set[str] = set()
            if todo_path.exists():
                existing = {ln.strip() for ln in todo_path.read_text(encoding="utf-8").splitlines() if ln.strip()}
            merged = existing | set(self.posts_with_comments)
            todo_path.write_text("\n".join(sorted(merged)) + "\n", encoding="utf-8")