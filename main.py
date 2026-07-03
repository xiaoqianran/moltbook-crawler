"""
Moltbook Crawler — academic research on AI agent social networks.

Pipeline (all):
  search → submolts → feeds → posts → agents → comments → social
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from crawlers.logging_config import get_logger, setup_logging

logger = get_logger("main")


def crawler_kwargs(args) -> dict:
    kw = {
        "limit": args.limit,
        "data_dir": args.output_dir,
        "use_proxy": args.proxy,
        "proxy_results_dir": args.proxy_results,
        "proxy_mode": args.proxy_mode if args.proxy else "off",
    }
    if args.concurrency:
        kw["max_concurrent"] = args.concurrency
        kw["delay"] = args.delay
    return kw


def _banner(title: str) -> None:
    logger.info("=" * 20 + " %s " + "=" * 20, title)


async def run_search(args):
    from crawlers.search_crawler import SearchCrawler
    _banner("SEARCH")
    await SearchCrawler(**crawler_kwargs(args)).run()


async def run_submolts(args):
    from crawlers.submolt_crawler import SubmoltCrawler
    _banner("SUBMOLTS")
    await SubmoltCrawler(**crawler_kwargs(args)).run()


async def run_feeds(args):
    from crawlers.feed_crawler import FeedCrawler
    _banner("FEEDS")
    await FeedCrawler(**crawler_kwargs(args)).run()


async def run_posts(args):
    from crawlers.post_crawler import PostCrawler
    _banner("POSTS")
    await PostCrawler(**crawler_kwargs(args)).run()


async def run_comments(args):
    from crawlers.comments_crawler import CommentsCrawler
    _banner("COMMENTS")
    await CommentsCrawler(**crawler_kwargs(args)).run()


async def run_agents(args):
    from crawlers.agent_crawler import AgentCrawler
    _banner("AGENTS")
    await AgentCrawler(**crawler_kwargs(args)).run()


async def run_social(args):
    from crawlers.social_graph import SocialGraphCrawler
    _banner("SOCIAL")
    await SocialGraphCrawler(**crawler_kwargs(args)).run()


async def run_discover(args):
    await run_search(args)
    await run_submolts(args)
    await run_feeds(args)
    await run_posts(args)
    await run_agents(args)
    if getattr(args, "translate", False):
        await run_translate(args)


async def run_translate(args):
    from crawlers.translate_crawler import TranslateCrawler
    _banner("TRANSLATE")
    await TranslateCrawler(**crawler_kwargs(args)).run()


async def run_merge_legacy(args):
    from pathlib import Path

    from crawlers.post_db import PostDB, POSTS_JSONL

    _banner("MERGE-LEGACY")
    data = Path(args.output_dir)
    db = PostDB(data)
    try:
        n1, d1 = db.import_jsonl_file(data / POSTS_JSONL, source="posts/legacy")
        n2, d2 = db.import_jsonl_file(data / "feed_posts.jsonl", source="feed/legacy")
        db.export_jsonl()
        stats = db.stats()
        logger.info("merged posts.jsonl      new=%s duplicate=%s", n1, d1)
        logger.info("merged feed_posts.jsonl new=%s duplicate=%s", n2, d2)
        logger.info("post_db stats: %s", stats)
    finally:
        db.close()


async def run_all(args):
    await run_discover(args)
    if getattr(args, "translate", False):
        await run_translate(args)
    if not args.skip_comments:
        await run_comments(args)
    _banner("SOCIAL")
    await run_social(args)


async def run_verify(args):
    from crawlers.verify import run_verify
    _banner("VERIFY")
    report = await run_verify(args.output_dir, proxy_results_dir=args.proxy_results)
    for c in report.checks:
        level = logger.info if c.ok else logger.error
        level("  [%s] %s — %s", "PASS" if c.ok else "FAIL", c.name, c.detail)
    logger.info("verify_report → %s/verify_report.json ok=%s", args.output_dir, report.ok)
    if not report.ok:
        sys.exit(2)


def print_summary(data_dir: str):
    logger.info("=" * 20 + " SUMMARY " + "=" * 20)
    if not os.path.isdir(data_dir):
        return
    db_path = os.path.join(data_dir, "posts.db")
    if os.path.isfile(db_path):
        from crawlers.post_db import PostDB

        db = PostDB(data_dir)
        try:
            s = db.stats()
            logger.info(
                "  %-30s %10d unique posts  (translated=%s pending=%s)",
                "posts.db",
                s["total"],
                s["translated"],
                s["pending"],
            )
        finally:
            db.close()
    for fname in sorted(os.listdir(data_dir)):
        if fname.startswith("."):
            continue
        fpath = os.path.join(data_dir, fname)
        if not os.path.isfile(fpath):
            continue
        size = os.path.getsize(fpath)
        if fname.endswith(".jsonl"):
            with open(fpath, encoding="utf-8") as f:
                lines = sum(1 for _ in f)
            logger.info("  %-30s %10d records  (%.1f MB)", fname, lines, size / 1024 / 1024)
        else:
            logger.info("  %-30s (%.1f KB)", fname, size / 1024)


def _load_dotenv() -> None:
    """Load .env from project root (does not override existing env vars)."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


def main():
    _load_dotenv()
    parser = argparse.ArgumentParser(description="Moltbook Crawler v0.5")
    parser.add_argument(
        "command",
        choices=[
            "all", "discover", "search", "submolts", "feeds", "posts", "comments",
            "agents", "social", "verify", "translate", "merge-legacy",
        ],
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output-dir", default="data")
    parser.add_argument("--skip-comments", action="store_true")
    parser.add_argument("--proxy", action="store_true")
    parser.add_argument("--proxy-mode", choices=["fallback", "always"], default="fallback")
    parser.add_argument("--proxy-results", default=None)
    parser.add_argument("--concurrency", type=int, default=None)
    parser.add_argument("--delay", type=float, default=None)
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--log-file", default=None, help="default: data/logs/crawler.log")
    parser.add_argument(
        "--translate",
        action="store_true",
        help="after discover/all, translate pending posts to 简体中文 (needs API key)",
    )
    args = parser.parse_args()

    if args.proxy_results is None:
        from crawlers.config import PROXY_RESULTS_DIR
        args.proxy_results = PROXY_RESULTS_DIR

    os.makedirs(args.output_dir, exist_ok=True)
    log_path = setup_logging(
        level=args.log_level,
        log_dir=args.output_dir,
        log_file=args.log_file or "crawler.log",
    )
    if log_path:
        logger.info("log file: %s", log_path)

    if args.proxy:
        logger.info("proxy enabled mode=%s dir=%s", args.proxy_mode, args.proxy_results)
    else:
        logger.info("direct connection (use --proxy for 429 fallback)")

    runners = {
        "search": lambda: run_search(args),
        "submolts": lambda: run_submolts(args),
        "feeds": lambda: run_feeds(args),
        "posts": lambda: run_posts(args),
        "comments": lambda: run_comments(args),
        "agents": lambda: run_agents(args),
        "social": lambda: run_social(args),
        "discover": lambda: run_discover(args),
        "all": lambda: run_all(args),
        "verify": lambda: run_verify(args),
        "translate": lambda: run_translate(args),
        "merge-legacy": lambda: run_merge_legacy(args),
    }

    try:
        asyncio.run(runners[args.command]())
    except KeyboardInterrupt:
        logger.warning("interrupted")
        sys.exit(1)
    except FileNotFoundError as e:
        logger.error("%s", e)
        sys.exit(1)

    if args.command != "verify":
        print_summary(args.output_dir)


if __name__ == "__main__":
    main()