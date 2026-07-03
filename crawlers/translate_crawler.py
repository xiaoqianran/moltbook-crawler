"""Translate pending posts to Simplified Chinese."""

import asyncio

import aiohttp
from tqdm import tqdm

from . import config
from .base_crawler import AsyncCrawler
from .post_db import PostDB
from .translate import PostTranslator, is_mostly_chinese
from .translate_log import TranslateLog


class TranslateCrawler(AsyncCrawler):
    def __init__(self, **kwargs):
        kwargs.setdefault("max_concurrent", config.TRANSLATE_MAX_CONCURRENT)
        kwargs.setdefault("delay", config.TRANSLATE_DELAY)
        super().__init__(**kwargs)
        self._translate_log: TranslateLog | None = None
        self._processed = 0

    async def crawl(self):
        db = PostDB(self.data_dir)
        tlog = TranslateLog(self.data_dir)
        self._translate_log = tlog
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

            cfg = translator.config_summary()
            self._logger.info(
                "translate start count=%s model=%s base=%s concurrency=%s key=%s",
                len(pending),
                cfg["model"],
                cfg["base_url"],
                self.max_concurrent,
                cfg["api_key"],
            )

            pbar = tqdm(total=len(pending), desc="Translate", unit="post")

            async with aiohttp.ClientSession() as session:
                for i in range(0, len(pending), self.max_concurrent):
                    if self._shutdown:
                        self._logger.warning("translate interrupted at %s/%s", self._processed, len(pending))
                        break
                    batch = pending[i : i + self.max_concurrent]
                    await asyncio.gather(*[
                        self._translate_one(db, translator, session, tlog, row, pbar)
                        for row in batch
                    ])
                    if self.delay:
                        await asyncio.sleep(self.delay)

            db.export_jsonl()
            s = db.stats()
            ts = tlog.stats.to_dict()
            self._logger.info(
                "translate done db_translated=%s pending=%s failed=%s session=%s",
                s["translated"],
                s["pending"],
                s["failed"],
                ts,
            )
            if tlog.stats.failed:
                for e in tlog.recent_entries(3):
                    if e.get("status") != "success":
                        self._logger.warning(
                            "recent translate failure post_id=%s error=%s",
                            e.get("post_id"),
                            e.get("error"),
                        )
            if self._report:
                self._report.extra = {**s, "translate_session": ts}
        finally:
            db.close()

    async def _translate_one(
        self,
        db: PostDB,
        translator: PostTranslator,
        session: aiohttp.ClientSession,
        tlog: TranslateLog,
        row: dict,
        pbar: tqdm,
    ) -> None:
        pid = row["id"]
        title = row["title"] or ""
        content = row["content"] or ""
        cfg = translator.config_summary()
        try:
            if is_mostly_chinese(f"{title}{content}"):
                db.save_translation(pid, title_zh=title, content_zh=content, lang_detected="zh")
                await tlog.record(
                    post_id=pid,
                    status="skipped",
                    model=cfg["model"],
                    base_url=cfg["base_url"],
                    error="already_zh",
                    title_len=len(title),
                    content_len=len(content),
                )
            else:
                outcome = await translator.translate_post(title, content, session, post_id=pid)
                db.save_translation(
                    pid,
                    title_zh=outcome.title_zh,
                    content_zh=outcome.content_zh,
                    lang_detected=outcome.lang_detected,
                )
                await tlog.record(
                    post_id=pid,
                    status="success",
                    model=cfg["model"],
                    base_url=cfg["base_url"],
                    latency_ms=outcome.latency_ms,
                    lang_detected=outcome.lang_detected,
                    attempts=outcome.attempts,
                    title_len=len(title),
                    content_len=len(content),
                )
        except Exception as e:
            self._logger.warning("translate failed id=%s err=%s", pid, e)
            db.mark_translate_failed(pid, str(e))
            await tlog.record(
                post_id=pid,
                status="failed",
                model=cfg["model"],
                base_url=cfg["base_url"],
                error=str(e),
                title_len=len(title),
                content_len=len(content),
            )
        finally:
            self._processed += 1
            pbar.update(1)
            if self._processed % config.TRANSLATE_PROGRESS_EVERY == 0:
                ts = tlog.stats.to_dict()
                self._logger.info(
                    "translate progress %s/%s success=%s failed=%s skipped=%s avg_ms=%s",
                    self._processed,
                    pbar.total,
                    ts["success"],
                    ts["failed"],
                    ts["skipped"],
                    ts["avg_latency_ms"],
                )

    def _emit_stats(self):
        r = super()._emit_stats()
        if self._translate_log and r:
            ts = self._translate_log.stats.to_dict()
            r.extra.setdefault("translate_session", ts)
            r.notes.append(f"translate_ops={self._translate_log.file_count()}")
            r.save(self.data_dir)
            self._logger.info("translate audit log %s", self._translate_log.path)
        return r