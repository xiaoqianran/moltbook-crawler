"""Cursor/offset pagination helpers."""

from __future__ import annotations

from typing import Any, Callable, Awaitable

FetchPage = Callable[[dict[str, Any]], Awaitable[dict | None]]


async def crawl_cursor_pages(
    fetch_page: FetchPage,
    *,
    params: dict[str, Any],
    items_key: str,
    cursor_param: str = "cursor",
    limit: int | None = None,
    shutdown: Callable[[], bool] | None = None,
    on_page: Callable[[list[dict], dict], Awaitable[None]] | None = None,
) -> int:
    """Paginate API with next_cursor. Returns total new items processed."""
    total = 0
    cursor: str | None = params.get(cursor_param)

    while True:
        if shutdown and shutdown():
            break

        page_params = {**params}
        if cursor:
            page_params[cursor_param] = cursor
        else:
            page_params.pop(cursor_param, None)

        data = await fetch_page(page_params)
        if not data or not data.get("success", True):
            break

        items = data.get(items_key) or []
        if not items:
            break

        if limit and total + len(items) > limit:
            items = items[: limit - total]

        if on_page:
            await on_page(items, data)

        total += len(items)
        if limit and total >= limit:
            break
        if not data.get("has_more"):
            break

        cursor = data.get("next_cursor")
        if not cursor:
            break

    return total