"""Pytest fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def reset_logging():
    import crawlers.logging_config as lc
    lc._CONFIGURED = False
    yield
    lc._CONFIGURED = False


@pytest.fixture
def proxy_results_dir(tmp_path: Path) -> Path:
    """Minimal proxy-hunter results layout."""
    root = tmp_path / "results"
    root.mkdir()
    summaries = [
        {"id": "test_http", "fetch_ok": True, "working": 2, "success_rate": 50.0},
    ]
    (root / "00_RANKING.json").write_text(
        json.dumps({"summaries": summaries}),
        encoding="utf-8",
    )
    (root / "test_http.json").write_text(
        json.dumps({
            "working_proxies": [
                {"proxy": "http://1.2.3.4:8080", "latency_ms": 100, "https_ok": True},
                {"proxy": "http://5.6.7.8:3128", "latency_ms": 200, "https_ok": False},
            ]
        }),
        encoding="utf-8",
    )
    return root


@pytest.fixture
def posts_page_fixture(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "posts_page.json").read_text(encoding="utf-8"))