"""
Moltbook Crawler - Academic research on AI agent social networks
================================================================

Crawls data from moltbook.com (a social network for AI agents) for
studying agent interaction patterns, community structures, and social graphs.

Usage:
    uv run python main.py all               # Run all crawlers
    uv run python main.py agents            # Crawl agent profiles only
    uv run python main.py posts             # Crawl posts and comments
    uv run python main.py submolts          # Crawl submolts (communities)
    uv run python main.py social            # Build social graph from agent data
    uv run python main.py all --limit 100   # Test run with 100 items max

Output files (in data/):
    agents.jsonl          - Agent profiles (id, name, karma, followers, owner info)
    top_humans.jsonl      - Top human users ranked by follower count
    agent_discover.jsonl  - Agent similarity/discovery data
    posts.jsonl           - All posts with metadata
    comments.jsonl        - All comments with thread structure (parent_id)
    post_authors.txt      - Unique post author names
    submolts.jsonl        - All submolt communities
    social_edges.jsonl    - Social graph edges (shared submolts, followers)
"""

import argparse
import asyncio
import os
import sys


async def run_agents(limit: int | None, data_dir: str):
    from crawlers.agent_crawler import AgentCrawler

    print("=" * 60)
    print("  AGENT CRAWLER")
    print("=" * 60)
    crawler = AgentCrawler(limit=limit, data_dir=data_dir)
    await crawler.run()


async def run_posts(limit: int | None, data_dir: str, skip_comments: bool = False):
    from crawlers.post_crawler import PostCrawler

    print("=" * 60)
    print("  POST & COMMENT CRAWLER")
    print("=" * 60)
    crawler = PostCrawler(limit=limit, data_dir=data_dir, skip_comments=skip_comments)
    await crawler.run()


async def run_submolts(limit: int | None, data_dir: str):
    from crawlers.submolt_crawler import SubmoltCrawler

    print("=" * 60)
    print("  SUBMOLT CRAWLER")
    print("=" * 60)
    crawler = SubmoltCrawler(limit=limit, data_dir=data_dir)
    await crawler.run()


async def run_social(limit: int | None, data_dir: str):
    from crawlers.social_graph import SocialGraphCrawler

    print("=" * 60)
    print("  SOCIAL GRAPH CRAWLER")
    print("=" * 60)
    crawler = SocialGraphCrawler(limit=limit, data_dir=data_dir)
    await crawler.run()


async def run_all(limit: int | None, data_dir: str, skip_comments: bool = False):
    # Run in dependency order:
    # 1. agents + submolts + posts can run in parallel
    # 2. social graph depends on agents data
    print("Running agents, posts, and submolts crawlers...\n")
    await asyncio.gather(
        run_agents(limit, data_dir),
        run_posts(limit, data_dir, skip_comments),
        run_submolts(limit, data_dir),
    )
    print("\nRunning social graph crawler...\n")
    await run_social(limit, data_dir)


def print_summary(data_dir: str):
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    for fname in sorted(os.listdir(data_dir)):
        fpath = os.path.join(data_dir, fname)
        if os.path.isfile(fpath):
            size = os.path.getsize(fpath)
            if fname.endswith(".jsonl"):
                with open(fpath, encoding="utf-8") as f:
                    lines = sum(1 for _ in f)
                print(f"  {fname:<30s} {lines:>10,} records  ({size / 1024 / 1024:.1f} MB)")
            else:
                print(f"  {fname:<30s} ({size / 1024:.1f} KB)")


def main():
    parser = argparse.ArgumentParser(
        description="Moltbook Crawler - Academic research on AI agent social networks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=["all", "agents", "posts", "submolts", "social"],
        help="Which crawler to run",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max items per crawler (for testing)")
    parser.add_argument("--output-dir", default="data", help="Output directory (default: data/)")
    parser.add_argument("--skip-comments", action="store_true", help="Skip comment fetching in post crawler")
    args = parser.parse_args()

    data_dir = args.output_dir
    os.makedirs(data_dir, exist_ok=True)

    runners = {
        "agents": lambda: run_agents(args.limit, data_dir),
        "posts": lambda: run_posts(args.limit, data_dir, args.skip_comments),
        "submolts": lambda: run_submolts(args.limit, data_dir),
        "social": lambda: run_social(args.limit, data_dir),
        "all": lambda: run_all(args.limit, data_dir, args.skip_comments),
    }

    try:
        asyncio.run(runners[args.command]())
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user.")
        sys.exit(1)

    print_summary(data_dir)


if __name__ == "__main__":
    main()
