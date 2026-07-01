#!/usr/bin/env bash
# Add api-g.daliu.ca to the existing Cloudflare tunnel and start the grocery API.
#
# Usage:
#   ./infra/setup-tunnel.sh              # update tunnel config + install launchd API service
#   ./infra/setup-tunnel.sh --reload     # reload cloudflared (shared with trackerV2) + API only
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INFRA_DIR="$REPO_ROOT/infra"
API_HOSTNAME="${API_HOSTNAME:-api-g.daliu.ca}"
API_PORT="${GROCERY_API_PORT:-8765}"
TRACKER_API_PORT="${TRACKER_API_PORT:-7391}"
TRACKER_API_HOSTNAME="${TRACKER_API_HOSTNAME:-api-t.daliu.ca}"
TUNNEL_ID="${TUNNEL_ID:-ed055d32-6cc4-482b-9aad-dac154f99551}"
CLOUDFLARED_DIR="${HOME}/.cloudflared"
CONFIG_FILE="${CLOUDFLARED_DIR}/config.yml"
CRED_FILE="${CLOUDFLARED_DIR}/${TUNNEL_ID}.json"

log() { echo "==> $*" >&2; }
die() { echo "ERROR: $*" >&2; exit 1; }

resolve_cloudflared_bin() {
  if command -v cloudflared >/dev/null 2>&1; then
    echo "$(command -v cloudflared)"
  elif [[ -x /opt/homebrew/bin/cloudflared ]]; then
    echo "/opt/homebrew/bin/cloudflared"
  else
    die "cloudflared not found (brew install cloudflared)"
  fi
}

write_tunnel_config() {
  [[ -f "$CRED_FILE" ]] || die "Missing $CRED_FILE (run: cloudflared tunnel login)"
  mkdir -p "$CLOUDFLARED_DIR"
  cat >"$CONFIG_FILE" <<EOF
tunnel: $TUNNEL_ID
credentials-file: $CRED_FILE

ingress:
  - hostname: $TRACKER_API_HOSTNAME
    service: http://127.0.0.1:$TRACKER_API_PORT
  - hostname: $API_HOSTNAME
    service: http://127.0.0.1:$API_PORT
  - service: http_status:404
EOF
  log "Wrote $CONFIG_FILE (api-t + api-g)"
}

install_api_service() {
  chmod +x "$REPO_ROOT/extract_server/start.sh"
  local agents_dir="$HOME/Library/LaunchAgents"
  mkdir -p "$agents_dir" "$HOME/Library/Logs"
  cp "$INFRA_DIR/launchd/com.daliu.grocery-prices.api.plist" \
    "$agents_dir/com.daliu.grocery-prices.api.plist"
  launchctl bootout "gui/$(id -u)/com.daliu.grocery-prices.api" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$agents_dir/com.daliu.grocery-prices.api.plist"
  launchctl enable "gui/$(id -u)/com.daliu.grocery-prices.api"
  log "API launchd service installed (logs: ~/Library/Logs/grocery-prices-api.log)"
}

reload_cloudflared() {
  launchctl kickstart -k "gui/$(id -u)/com.daliu.trackerV2.cloudflared" 2>/dev/null \
    || log "cloudflared launchd not loaded; run trackerV2 ./infra/setup.sh --services or: cloudflared tunnel --config $CONFIG_FILE run"
}

wait_for_local_health() {
  for _ in $(seq 1 15); do
    if curl -fsS "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  die "API did not become healthy on port $API_PORT"
}

print_dns_instructions() {
  cat <<EOF

--- DNS (required once) ---
Add in Google Domains / Squarespace DNS for daliu.ca:

  Type:  CNAME
  Host:  api-g
  Value: ${TUNNEL_ID}.cfargotunnel.com

Then verify:
  curl -s https://${API_HOSTNAME}/health

EOF
}

main() {
  local reload_only=false
  [[ "${1:-}" == "--reload" ]] && reload_only=true

  if [[ "$reload_only" == false ]]; then
    write_tunnel_config
    install_api_service
  fi

  reload_cloudflared
  wait_for_local_health
  log "Local API healthy at http://127.0.0.1:${API_PORT}/health"
  print_dns_instructions
}

main "$@"
