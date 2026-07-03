"""Tests for translation parsing, skip logic, and API client."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crawlers.translate import (
    PostTranslator,
    _parse_json_response,
    is_mostly_chinese,
)


def test_is_mostly_chinese():
    assert is_mostly_chinese("这是一段中文正文")
    assert not is_mostly_chinese("Hello world this is English text only")
    assert is_mostly_chinese("")


def test_parse_json_response_plain():
    raw = '{"title_zh":"标题","content_zh":"正文","lang_detected":"en"}'
    parsed = _parse_json_response(raw)
    assert parsed["title_zh"] == "标题"
    assert parsed["lang_detected"] == "en"


def test_parse_json_response_fenced():
    raw = '```json\n{"title_zh":"A","content_zh":"B","lang_detected":"ja"}\n```'
    parsed = _parse_json_response(raw)
    assert parsed["title_zh"] == "A"
    assert parsed["lang_detected"] == "ja"


def test_config_summary_masks_key(monkeypatch):
    monkeypatch.setenv("MOLTBOOK_TRANSLATE_API_KEY", "sk-abcdefghijklmnop")
    t = PostTranslator()
    assert t.available
    summary = t.config_summary()
    assert "sk-a" in summary["api_key"]
    assert "mnop" in summary["api_key"]
    assert "abcdefghijklmnop" not in summary["api_key"]


@pytest.mark.asyncio
async def test_translate_post_skips_chinese():
    t = PostTranslator(api_key="sk-test")
    session = MagicMock()
    out = await t.translate_post("中文标题", "中文内容", session, post_id="p1")
    assert out.skipped
    assert out.lang_detected == "zh"
    assert out.attempts == 0


@pytest.mark.asyncio
async def test_translate_post_calls_api(monkeypatch):
    t = PostTranslator(api_key="sk-test", max_retries=1)

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.text = AsyncMock(
        return_value=json.dumps({
            "choices": [{
                "message": {
                    "content": '{"title_zh":"你好","content_zh":"世界","lang_detected":"en"}',
                },
            }],
        })
    )
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)

    session = MagicMock()
    session.post = MagicMock(return_value=mock_resp)

    out = await t.translate_post("Hello", "World", session, post_id="p2")
    assert out.title_zh == "你好"
    assert out.content_zh == "世界"
    assert out.attempts == 1
    assert out.latency_ms >= 0


@pytest.mark.asyncio
async def test_translate_post_retries_then_fails(monkeypatch):
    t = PostTranslator(api_key="sk-test", max_retries=2)

    mock_resp = AsyncMock()
    mock_resp.status = 500
    mock_resp.text = AsyncMock(return_value="server error")
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)

    session = MagicMock()
    session.post = MagicMock(return_value=mock_resp)

    with patch("crawlers.translate.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(RuntimeError, match="failed after 2 attempts"):
            await t.translate_post("Hi", "There", session, post_id="p3")