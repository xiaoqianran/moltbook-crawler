"""Central logging setup: console + rotating file under data/logs/."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_CONFIGURED = False
LOG_DIR_NAME = "logs"
DEFAULT_LOG_FILE = "crawler.log"


def setup_logging(
    *,
    level: str = "INFO",
    log_dir: str | Path | None = None,
    log_file: str = DEFAULT_LOG_FILE,
    also_console: bool = True,
) -> Path | None:
    """Configure root 'moltbook' logger once. Returns log file path if file handler added."""
    global _CONFIGURED
    root = logging.getLogger("moltbook")
    if _CONFIGURED:
        root.setLevel(getattr(logging, level.upper(), logging.INFO))
        return None

    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if also_console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(getattr(logging, level.upper(), logging.INFO))
        ch.setFormatter(fmt)
        root.addHandler(ch)

    file_path: Path | None = None
    if log_dir is not None:
        log_path = Path(log_dir) / LOG_DIR_NAME
        log_path.mkdir(parents=True, exist_ok=True)
        file_path = log_path / log_file
        fh = logging.FileHandler(file_path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        root.addHandler(fh)

    _CONFIGURED = True
    root.debug("logging initialized level=%s file=%s", level, file_path)
    return file_path


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"moltbook.{name}")