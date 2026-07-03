"""Live integration: requires network. Run with: pytest -m integration"""

from __future__ import annotations

import pytest

from crawlers.logging_config import setup_logging
from crawlers.verify import run_verify


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_verify(tmp_path):
    data = tmp_path / "data"
    setup_logging(level="INFO", log_dir=data)
    report = await run_verify(str(data))
    assert report.checks
    names = {c.name for c in report.checks}
    assert "api_posts" in names
    assert "api_search" in names
    # At least core public APIs should work
    api_checks = [c for c in report.checks if c.name.startswith("api_")]
    passed = sum(1 for c in api_checks if c.ok)
    assert passed >= 3, f"too many API failures: {[(c.name, c.detail) for c in api_checks if not c.ok]}"