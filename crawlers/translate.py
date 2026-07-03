"""High-quality Simplified Chinese translation via OpenAI-compatible API."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass

import aiohttp

from . import config
from .logging_config import get_logger

logger = get_logger("translate")

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

SYSTEM_PROMPT = """你是专业科技/学术译者。将用户给出的帖子标题和正文翻译成**高质量简体中文**。
要求：
- 准确传达原意，术语一致，语句自然流畅
- 保留代码、URL、@用户名、专有名词（必要时括号注明英文）
- 只输出 JSON：{"title_zh":"...","content_zh":"...","lang_detected":"en|zh|..."}
- 若原文已是简体中文，title_zh/content_zh 可与原文相同，lang_detected 填 zh
"""


@dataclass
class TranslateOutcome:
    title_zh: str
    content_zh: str
    lang_detected: str
    latency_ms: float
    attempts: int
    skipped: bool = False


def is_mostly_chinese(text: str) -> bool:
    if not text.strip():
        return True
    cjk = len(_CJK_RE.findall(text))
    return cjk / max(len(text), 1) > 0.3


def _parse_json_response(text: str) -> dict:
    cleaned = _JSON_FENCE_RE.sub("", text.strip())
    return json.loads(cleaned)


def _mask_key(key: str) -> str:
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


class PostTranslator:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
    ):
        self.api_key = api_key or os.getenv("MOLTBOOK_TRANSLATE_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = (base_url or config.TRANSLATE_API_BASE).rstrip("/")
        self.model = model or config.TRANSLATE_MODEL
        self.timeout = timeout or config.TRANSLATE_TIMEOUT
        self.max_retries = max_retries if max_retries is not None else config.TRANSLATE_MAX_RETRIES

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def config_summary(self) -> dict:
        return {
            "model": self.model,
            "base_url": self.base_url,
            "api_key": _mask_key(self.api_key) if self.api_key else None,
            "timeout_s": self.timeout,
            "max_retries": self.max_retries,
        }

    async def health_check(self, session: aiohttp.ClientSession) -> tuple[bool, str, float]:
        """Single-shot smoke test — returns (ok, detail, latency_ms)."""
        t0 = time.perf_counter()
        try:
            result = await self.translate_post(
                "Health check",
                "Translate this short test sentence to Simplified Chinese.",
                session,
                post_id="health-check",
            )
            ms = round((time.perf_counter() - t0) * 1000, 1)
            if result.title_zh and result.content_zh:
                return True, f"ok lang={result.lang_detected} title_zh={result.title_zh[:40]}", ms
            return False, "empty translation fields", ms
        except Exception as e:
            ms = round((time.perf_counter() - t0) * 1000, 1)
            return False, str(e)[:200], ms

    async def translate_post(
        self,
        title: str,
        content: str,
        session: aiohttp.ClientSession,
        *,
        post_id: str = "",
    ) -> TranslateOutcome:
        if not self.api_key:
            raise RuntimeError(
                "未配置翻译 API。请设置环境变量 MOLTBOOK_TRANSLATE_API_KEY 或 OPENAI_API_KEY"
            )

        combined = f"{title}\n{content}"
        if is_mostly_chinese(combined):
            return TranslateOutcome(
                title_zh=title,
                content_zh=content,
                lang_detected="zh",
                latency_ms=0.0,
                attempts=0,
                skipped=True,
            )

        t0 = time.perf_counter()
        last_err: Exception | None = None
        attempts = 0

        for attempt in range(1, self.max_retries + 1):
            attempts = attempt
            try:
                parsed = await self._call_api(title, content, session)
                ms = round((time.perf_counter() - t0) * 1000, 1)
                logger.debug(
                    "translate api ok post_id=%s attempt=%s latency_ms=%s",
                    post_id or "-",
                    attempt,
                    ms,
                )
                return TranslateOutcome(
                    title_zh=parsed.get("title_zh", title),
                    content_zh=parsed.get("content_zh", content),
                    lang_detected=parsed.get("lang_detected", "en"),
                    latency_ms=ms,
                    attempts=attempt,
                )
            except Exception as e:
                last_err = e
                logger.warning(
                    "translate api retry post_id=%s attempt=%s/%s error=%s",
                    post_id or "-",
                    attempt,
                    self.max_retries,
                    e,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(config.TRANSLATE_RETRY_BACKOFF * attempt)

        ms = round((time.perf_counter() - t0) * 1000, 1)
        raise RuntimeError(f"translate failed after {attempts} attempts: {last_err}") from last_err

    async def _call_api(
        self,
        title: str,
        content: str,
        session: aiohttp.ClientSession,
    ) -> dict:
        user_msg = json.dumps({"title": title, "content": content[:8000]}, ensure_ascii=False)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"

        async with session.post(
            url,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=self.timeout),
        ) as resp:
            body = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status}: {body[:300]}")
            data = json.loads(body)
            text = data["choices"][0]["message"]["content"]
            return _parse_json_response(text)