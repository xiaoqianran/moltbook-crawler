#!/usr/bin/env bash
# 刷新内置 proxy-hunter 代理池（~18s）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PH="$ROOT/proxy-hunter/source_tests"

if [[ ! -d "$PH" ]]; then
  echo "缺少 proxy-hunter 子模块，请执行:"
  echo "  git submodule update --init --recursive"
  exit 1
fi

cd "$PH"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
elif command -v python3 &>/dev/null; then
  PY=python3
else
  PY=python
fi

echo "=== 运行 proxy-hunter source_tests (~18s) ==="
"$PY" run_all.py
echo "=== 完成，结果: proxy-hunter/source_tests/results/ ==="