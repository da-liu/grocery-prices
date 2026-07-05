#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/extract_server"
export PYTHONPATH="$ROOT"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
.venv/bin/python -c "import server" || exit 1
exec .venv/bin/python server.py
