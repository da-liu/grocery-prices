#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
.venv/bin/pip install -q -e .
.venv/bin/python -c "import extract_server.main" || exit 1
exec .venv/bin/python -m extract_server.main
