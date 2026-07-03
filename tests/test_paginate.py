"""Tests for cursor pagination."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crawlers.paginate import crawl_cursor_pages

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_crawl_cursor_pages_two_pages():
    pages = [
        json.loads((FIXTURES / "posts_page.json").read_text()),
        json.loads((FIXTURES / "posts_page2.json").read_text()),
    ]
    calls: list[dict] = []
    collected: list[dict] = []

    async def fetch_page(params: dict) -> dict | None:
        calls.append(dict(params))
        if "cursor" not in params:
            return pages[0]
        if params["cursor"] == "cursor_page_2":
            return pages[1]
        return None

    async def on_page(items: list[dict], _data: dict) -> None:
        collected.extend(items)

    n = await crawl_cursor_pages(
        fetch_page,
        params={"limit": 50, "sort": "new"},
        items_key="posts",
        on_page=on_page,
    )

    assert n == 3
    assert len(collected) == 3
    assert len(calls) == 2
    assert calls[1].get("cursor") == "cursor_page_2"


@pytest.mark.asyncio
async def test_crawl_cursor_respects_limit():
    page = json.loads((FIXTURES / "posts_page.json").read_text())

    async def fetch_page(_params: dict) -> dict:
        return page

    async def on_page(items: list[dict], _data: dict) -> None:
        pass

    n = await crawl_cursor_pages(
        fetch_page,
        params={"limit": 50},
        items_key="posts",
        limit=1,
        on_page=on_page,
    )
    assert n == 1