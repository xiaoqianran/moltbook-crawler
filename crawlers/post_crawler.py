"""Crawler for moltbook posts (multi-sort, cursor pagination)."""

from tqdm import tqdm

from . import config
from .base_crawler import AsyncCrawler
from .paginate import crawl_cursor_pages
from .post_db import PostDB

AUTHORS_FILE = "post_authors.txt"


class PostCrawler(AsyncCrawler):
    """Crawl posts via /posts with cursor pagination across sort modes."""

    def __init__(self, sorts: tuple[str, ...] | None = None, **kwargs):
        super().__init__(**kwargs)
        self.sorts = sorts or config.POST_SORTS
        self.authors: set[str] = set()
        self.posts_with_comments: list[str] = []

    async def crawl(self):
        db = PostDB(self.data_dir)
        try:
            existing = db.count()
            if existing:
                print(f"[*] PostDB: {existing} posts already stored (global dedup)")

            total_new = 0
            total_dup = 0
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

                async def on_page(items: list[dict], _data: dict, *, _sort: str = sort) -> None:
                    nonlocal total_new, total_dup
                    for p in items:
                        pid = p.get("id")
                        if not pid:
                            continue
                        result = db.upsert_from_api(
                            p,
                            source=f"posts/{_sort}",
                            sort_mode=_sort,
                        )
                        if result == "new":
                            total_new += 1
                            pbar.update(1)
                        elif result == "duplicate":
                            total_dup += 1
                        name = p.get("author", {}).get("name")
                        if name:
                            self.authors.add(name)
                        if (p.get("comment_count") or 0) > 0:
                            self.posts_with_comments.append(pid)

                state_key = f"posts.cursor.{sort}"

                async def fetch_page(params: dict) -> dict | None:
                    return await self.fetch_json(f"{config.API_BASE}/posts", params=params)

                base_params = {"limit": config.PAGE_SIZE, "sort": sort}
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

            db.export_jsonl()
            stats = db.stats()
            print(f"[*] PostDB: +{total_new} new, {total_dup} duplicate merges")
            print(f"    Total unique: {stats['total']}, pending translate: {stats['pending']}")
            print(f"    Authors: {len(self.authors)}, with comments: {len(self.posts_with_comments)}")
            self.store.write_lines(AUTHORS_FILE, sorted(self.authors))
            self._save_comments_todo(db)
            if self._report:
                self._report.extra = {"new": total_new, "duplicate": total_dup, **stats}
        finally:
            db.close()

    def _save_comments_todo(self, db: PostDB) -> None:
        todo_path = self.store.state_path("comments.todo.txt")
        existing: set[str] = set()
        if todo_path.exists():
            existing = {ln.strip() for ln in todo_path.read_text(encoding="utf-8").splitlines() if ln.strip()}
        merged = existing | set(self.posts_with_comments) | set(db.post_ids_with_comments())
        if merged:
            todo_path.write_text("\n".join(sorted(merged)) + "\n", encoding="utf-8")