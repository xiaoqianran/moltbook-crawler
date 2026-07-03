"""High-quality Simplified Chinese translation via OpenAI-compatible API."""

from __future__ import annotations

import json
import os
import re

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


def is_mostly_chinese(text: str) -> bool:
    if not text.strip():
        return True
    cjk = len(_CJK_RE.findall(text))
    return cjk / max(len(text), 1) > 0.3


def _parse_json_response(text: str) -> dict:
    cleaned = _JSON_FENCE_RE.sub("", text.strip())
    return json.loads(cleaned)


class PostTranslator:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ):
        self.api_key = api_key or os.getenv("MOLTBOOK_TRANSLATE_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = (base_url or config.TRANSLATE_API_BASE).rstrip("/")
        self.model = model or config.TRANSLATE_MODEL
        self.timeout = timeout or config.TRANSLATE_TIMEOUT

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    async def translate_post(self, title: str, content: str, session: aiohttp.ClientSession) -> dict[str, str]:
        if not self.api_key:
            raise RuntimeError(
                "未配置翻译 API。请设置环境变量 MOLTBOOK_TRANSLATE_API_KEY 或 OPENAI_API_KEY"
            )

        combined = f"{title}\n{content}"
        if is_mostly_chinese(combined):
            return {
                "title_zh": title,
                "content_zh": content,
                "lang_detected": "zh",
            }

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
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"translate API HTTP {resp.status}: {body[:300]}")
            data = await resp.json()
            text = data["choices"][0]["message"]["content"]
            parsed = _parse_json_response(text)
            return {
                "title_zh": parsed.get("title_zh", title),
                "content_zh": parsed.get("content_zh", content),
                "lang_detected": parsed.get("lang_detected", "en"),
            }