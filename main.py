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


async def run_search(args):
    from crawlers.search_crawler import SearchCrawler
    print("=" * 60, "\n  SEARCH CRAWLER\n", "=" * 60, sep="")
    await SearchCrawler(**crawler_kwargs(args)).run()


async def run_submolts(args):
    from crawlers.submolt_crawler import SubmoltCrawler
    print("=" * 60, "\n  SUBMOLT CRAWLER\n", "=" * 60, sep="")
    await SubmoltCrawler(**crawler_kwargs(args)).run()


async def run_feeds(args):
    from crawlers.feed_crawler import FeedCrawler
    print("=" * 60, "\n  SUBMOLT FEED CRAWLER\n", "=" * 60, sep="")
    await FeedCrawler(**crawler_kwargs(args)).run()


async def run_posts(args):
    from crawlers.post_crawler import PostCrawler
    print("=" * 60, "\n  POST CRAWLER\n", "=" * 60, sep="")
    await PostCrawler(**crawler_kwargs(args)).run()


async def run_comments(args):
    from crawlers.comments_crawler import CommentsCrawler
    print("=" * 60, "\n  COMMENTS CRAWLER\n", "=" * 60, sep="")
    await CommentsCrawler(**crawler_kwargs(args)).run()


async def run_agents(args):
    from crawlers.agent_crawler import AgentCrawler
    print("=" * 60, "\n  AGENT CRAWLER\n", "=" * 60, sep="")
    await AgentCrawler(**crawler_kwargs(args)).run()


async def run_social(args):
    from crawlers.social_graph import SocialGraphCrawler
    print("=" * 60, "\n  SOCIAL GRAPH CRAWLER\n", "=" * 60, sep="")
    await SocialGraphCrawler(**crawler_kwargs(args)).run()


async def run_discover(args):
    """Fast discovery pass: search + submolts + feeds + posts + agents."""
    await run_search(args)
    print()
    await run_submolts(args)
    print()
    await run_feeds(args)
    print()
    await run_posts(args)
    print()
    await run_agents(args)


async def run_all(args):
    await run_discover(args)
    if not args.skip_comments:
        print()
        await run_comments(args)
    print("\n  SOCIAL GRAPH\n")
    await run_social(args)


def print_summary(data_dir: str):
    print("\n" + "=" * 60, "\n  SUMMARY\n", "=" * 60, sep="")
    if not os.path.isdir(data_dir):
        return
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
            print(f"  {fname:<30s} {lines:>10,} records  ({size / 1024 / 1024:.1f} MB)")
        else:
            print(f"  {fname:<30s} ({size / 1024:.1f} KB)")


def main():
    parser = argparse.ArgumentParser(description="Moltbook Crawler v0.3")
    parser.add_argument(
        "command",
        choices=["all", "discover", "search", "submolts", "feeds", "posts", "comments", "agents", "social"],
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output-dir", default="data")
    parser.add_argument("--skip-comments", action="store_true")
    parser.add_argument("--proxy", action="store_true")
    parser.add_argument("--proxy-mode", choices=["fallback", "always"], default="fallback")
    parser.add_argument("--proxy-results", default=None)
    parser.add_argument("--concurrency", type=int, default=None)
    parser.add_argument("--delay", type=float, default=None)
    args = parser.parse_args()

    if args.proxy_results is None:
        from crawlers.config import PROXY_RESULTS_DIR
        args.proxy_results = PROXY_RESULTS_DIR

    os.makedirs(args.output_dir, exist_ok=True)

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
    }

    if args.proxy:
        print(f"[*] Proxy fallback ON → {args.proxy_results}\n")

    try:
        asyncio.run(runners[args.command]())
    except KeyboardInterrupt:
        print("\n[!] Interrupted.")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"[!] {e}")
        sys.exit(1)

    print_summary(args.output_dir)


if __name__ == "__main__":
    main()