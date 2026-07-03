"""Tests for JsonlStore."""

from __future__ import annotations

import pytest

from crawlers.storage import JsonlStore


@pytest.mark.asyncio
async def test_append_and_load_seen(tmp_data_dir):
    store = JsonlStore(str(tmp_data_dir))
    await store.append("items.jsonl", {"id": "a", "v": 1})
    await store.append_many("items.jsonl", [{"id": "b", "v": 2}, {"id": "c", "v": 3}])
    seen = store.load_seen("items.jsonl", "id")
    assert seen == {"a", "b", "c"}


def test_state_read_write(tmp_data_dir):
    store = JsonlStore(str(tmp_data_dir))
    store.write_state_str("cursor.new", "eyJ0ZXN0In0=")
    assert store.read_state_str("cursor.new") == "eyJ0ZXN0In0="
    store.write_state_int("offset", 150)
    assert store.read_state_int("offset") == 150