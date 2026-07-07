#!/usr/bin/env sh
set -e

# Named tunnel: https://api-g.daliu.ca (see setup-tunnel.sh)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/setup-tunnel.sh" "$@"
