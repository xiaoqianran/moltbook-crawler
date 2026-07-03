"""
Moltbook Crawler — academic research on AI agent social networks.

Usage:
    uv run python main.py all
    uv run python main.py all --proxy --limit 100
    uv run python main.py search --proxy
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys


def crawler_kwargs(args) -> dict:
    return {
        "limit": args.limit,
        "data_dir": args.output_dir,
        "use_proxy": args.proxy,
        "proxy_results_dir": args.proxy_results,
        "proxy_mode": args.proxy_mode if args.proxy else "off",
    }


async def run_agents(args):
    from crawlers.agent_crawler import AgentCrawler

    print("=" * 60)
    print("  AGENT CRAWLER")
    print("=" * 60)
    await AgentCrawler(**crawler_kwargs(args)).run()


async def run_posts(args):
    from crawlers.post_crawler import PostCrawler

    print("=" * 60)
    print("  POST & COMMENT CRAWLER")
    print("=" * 60)
    await PostCrawler(skip_comments=args.skip_comments, **crawler_kwargs(args)).run()


async def run_submolts(args):
    from crawlers.submolt_crawler import SubmoltCrawler

    print("=" * 60)
    print("  SUBMOLT CRAWLER")
    print("=" * 60)
    await SubmoltCrawler(**crawler_kwargs(args)).run()


async def run_social(args):
    from crawlers.social_graph import SocialGraphCrawler

    print("=" * 60)
    print("  SOCIAL GRAPH CRAWLER")
    print("=" * 60)
    await SocialGraphCrawler(**crawler_kwargs(args)).run()


async def run_search(args):
    from crawlers.search_crawler import SearchCrawler

    print("=" * 60)
    print("  SEARCH CRAWLER")
    print("=" * 60)
    await SearchCrawler(**crawler_kwargs(args)).run()


async def run_all(args):
    # search first → more seeds for agents
    await run_search(args)
    print()
    await run_agents(args)
    print()
    await run_posts(args)
    print()
    await run_submolts(args)
    print("\nRunning social graph crawler...\n")
    await run_social(args)


def print_summary(data_dir: str):
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
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
    parser = argparse.ArgumentParser(
        description="Moltbook Crawler — AI agent social network research",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=["all", "agents", "posts", "submolts", "social", "search"],
        help="Which crawler to run",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max items (testing)")
    parser.add_argument("--output-dir", default="data", help="Output directory")
    parser.add_argument("--skip-comments", action="store_true", help="Skip comment phase")
    parser.add_argument(
        "--proxy",
        action="store_true",
        help="Enable proxy-hunter pool (default mode: fallback on 429)",
    )
    parser.add_argument(
        "--proxy-mode",
        choices=["fallback", "always"],
        default="fallback",
        help="fallback=direct first; always=every request via proxy",
    )
    parser.add_argument(
        "--proxy-results",
        default=None,
        help="Path to proxy-hunter source_tests/results (default: ../proxy-hunter/...)",
    )
    args = parser.parse_args()

    if args.proxy_results is None:
        from crawlers import config
        args.proxy_results = config.PROXY_RESULTS_DIR

    os.makedirs(args.output_dir, exist_ok=True)

    runners = {
        "agents": lambda: run_agents(args),
        "posts": lambda: run_posts(args),
        "submolts": lambda: run_submolts(args),
        "social": lambda: run_social(args),
        "search": lambda: run_search(args),
        "all": lambda: run_all(args),
    }

    if args.proxy:
        print(f"[*] Proxy mode ON → {args.proxy_results}\n")

    try:
        asyncio.run(runners[args.command]())
    except KeyboardInterrupt:
        print("\n[!] Interrupted.")
        sys.exit(1)
    except ImportError as e:
        print(f"[!] {e}")
        print("    Install deps: uv sync")
        sys.exit(1)

    print_summary(args.output_dir)


if __name__ == "__main__":
    main()