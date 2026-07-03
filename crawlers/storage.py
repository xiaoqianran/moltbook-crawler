"""JSONL storage with deduplication and resume state."""

from __future__ import annotations

import json
import os
from pathlib import Path

import aiofiles


class JsonlStore:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

    def path(self, filename: str) -> str:
        return os.path.join(self.data_dir, filename)

    def load_seen(self, filename: str, key: str) -> set:
        seen: set = set()
        path = self.path(filename)
        if not os.path.exists(path):
            return seen
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    val = record.get(key)
                    if val is not None:
                        seen.add(val)
                except json.JSONDecodeError:
                    continue
        return seen

    def load_lines_as_set(self, filename: str) -> set[str]:
        out: set[str] = set()
        path = self.path(filename)
        if not os.path.exists(path):
            return out
        with open(path, encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s:
                    out.add(s)
        return out

    async def append(self, filename: str, record: dict) -> None:
        path = self.path(filename)
        async with aiofiles.open(path, "a", encoding="utf-8") as f:
            await f.write(json.dumps(record, ensure_ascii=False) + "\n")

    async def append_many(self, filename: str, records: list[dict]) -> None:
        if not records:
            return
        path = self.path(filename)
        async with aiofiles.open(path, "a", encoding="utf-8") as f:
            for record in records:
                await f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def write_lines(self, filename: str, lines: list[str]) -> None:
        path = self.path(filename)
        with open(path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")

    def state_path(self, name: str) -> Path:
        state = Path(self.data_dir) / ".state"
        state.mkdir(parents=True, exist_ok=True)
        return state / name

    def read_state_int(self, name: str, default: int = 0) -> int:
        path = self.state_path(name)
        if not path.exists():
            return default
        try:
            return int(path.read_text(encoding="utf-8").strip())
        except ValueError:
            return default

    def write_state_int(self, name: str, value: int) -> None:
        self.state_path(name).write_text(str(value), encoding="utf-8")