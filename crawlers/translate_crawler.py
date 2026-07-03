"""Translate pending posts to Simplified Chinese."""

import asyncio

import aiohttp
from tqdm import tqdm

from .base_crawler import AsyncCrawler
from .post_db import PostDB
from .translate import PostTranslator, is_mostly_chinese


class TranslateCrawler(AsyncCrawler):
    async def crawl(self):
        db = PostDB(self.data_dir)
        try:
            stats = db.stats()
            self._logger.info("post_db total=%s pending=%s translated=%s", stats["total"], stats["pending"], stats["translated"])

            pending = db.get_pending_translation(self.limit)
            if not pending:
                self._logger.info("no pending posts to translate")
                return

            translator = PostTranslator()
            if not translator.available:
                self._logger.error("translate API key missing — set MOLTBOOK_TRANSLATE_API_KEY")
                raise RuntimeError("MOLTBOOK_TRANSLATE_API_KEY not set")

            self._logger.info("translating %s posts model=%s", len(pending), translator.model)
            pbar = tqdm(total=len(pending), desc="Translate", unit="post")

            async with aiohttp.ClientSession() as session:
                for i in range(0, len(pending), self.max_concurrent):
                    if self._shutdown:
                        break
                    batch = pending[i : i + self.max_concurrent]
                    await asyncio.gather(*[
                        self._translate_one(db, translator, session, row, pbar)
                        for row in batch
                    ])
                    await asyncio.sleep(self.delay)

            db.export_jsonl()
            s = db.stats()
            self._logger.info("translate done translated=%s pending=%s failed=%s", s["translated"], s["pending"], s["failed"])
            if self._report:
                self._report.extra = s
        finally:
            db.close()

    async def _translate_one(self, db: PostDB, translator: PostTranslator, session: aiohttp.ClientSession, row: dict, pbar: tqdm) -> None:
        pid = row["id"]
        title = row["title"] or ""
        content = row["content"] or ""
        try:
            if is_mostly_chinese(f"{title}{content}"):
                db.save_translation(pid, title_zh=title, content_zh=content, lang_detected="zh")
            else:
                result = await translator.translate_post(title, content, session)
                db.save_translation(
                    pid,
                    title_zh=result["title_zh"],
                    content_zh=result["content_zh"],
                    lang_detected=result.get("lang_detected"),
                )
        except Exception as e:
            self._logger.warning("translate failed id=%s err=%s", pid, e)
            db.mark_translate_failed(pid, str(e))
        finally:
            pbar.update(1)