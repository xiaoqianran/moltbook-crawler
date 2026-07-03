"""Tests for logging setup."""

from __future__ import annotations

import logging

from crawlers.logging_config import get_logger, setup_logging


def test_setup_logging_creates_file(tmp_data_dir):
    path = setup_logging(level="DEBUG", log_dir=tmp_data_dir)
    assert path is not None
    assert path.exists()
    log = get_logger("test")
    log.info("hello test")
    assert "hello test" in path.read_text(encoding="utf-8")


def test_get_logger_hierarchy():
    setup_logging(level="INFO", log_dir=None, also_console=False)
    log = get_logger("SearchCrawler")
    assert log.name == "moltbook.SearchCrawler"
    assert isinstance(log, logging.Logger)