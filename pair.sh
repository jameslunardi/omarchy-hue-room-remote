#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/omarchy/settings"
STATE_FILE="$STATE_DIR/hue.json"
DEVICETYPE="${PHILIPS_HUE_DEVICETYPE:-philips#omarchy-hue}"
DEVICETYPE="${DEVICETYPE//[^a-zA-Z0-9#_-]/}"

BRIDGE_IP="${1:-}"

info() { printf '\033[1;34m::\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m::\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m::\033[0m %s\n' "$*" >&2; }

valid_ip() {
  local IFS='.' parts=($1)
  [[ ${#parts[@]} -eq 4 ]] || return 1
  for part in "${parts[@]}"; do
    [[ "$part" =~ ^[0-9]{1,3}$ ]] || return 1
    (( part >= 0 && part <= 255 )) || return 1
  done
}

discover_bridge() {
  local response ip
  response=$(curl -fsS --max-time 5 https://discovery.meethue.com/ 2>/dev/null || true)
  [[ -z "$response" ]] && return 1
  ip=$(python3 -c "
import json, sys
d = json.load(sys.stdin)
ips = [x.get('internalipaddress', '') for x in d if x.get('internalipaddress')]
print(ips[0] if ips else '')
" <<<"$response")
  [[ -n "$ip" ]] || return 1
  printf '%s\n' "$ip"
}

pair() {
  local ip="$1" response username
  response=$(curl -sS --max-time 8 -X POST -H "Content-Type: application/json" \
    -d "{\"devicetype\":\"$DEVICETYPE\"}" "http://$ip/api" 2>/dev/null || true)
  username=$(python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    for item in d:
        if isinstance(item, dict) and 'success' in item and 'username' in item['success']:
            print(item['success']['username'])
            break
except Exception:
    pass
" <<<"$response")
  [[ -n "$username" ]] || return 1
  printf '%s\n' "$username"
}

if [[ -f "$STATE_FILE" ]] && python3 -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if d.get('bridgeIp') else 1)" "$STATE_FILE" 2>/dev/null; then
  info "Existing config found at $STATE_FILE."
  info "Re-pairing will replace the current username. The old username will stop working."
fi

read -r -p "Press the link button on the Hue bridge, then press Enter to continue... " </dev/tty

local_ip=""
if [[ -n "$BRIDGE_IP" ]]; then
  local_ip="$BRIDGE_IP"
else
  info "Discovering bridge..."
  local_ip=$(discover_bridge) || true
  if [[ -z "$local_ip" ]]; then
    read -r -p "Couldn't discover the bridge automatically. Enter its IP address: " local_ip </dev/tty
  fi
fi

if [[ -z "$local_ip" ]]; then
  err "No bridge IP. Aborting."
  exit 1
fi

if ! valid_ip "$local_ip"; then
  err "Invalid IP address: $local_ip"
  exit 1
fi

info "Using bridge at $local_ip"

info "Requesting access from the bridge..."
username=$(pair "$local_ip") || true
if [[ -z "$username" ]]; then
  err "Pairing failed. The link button was likely not pressed within 30 seconds. Try again."
  exit 1
fi
ok "Got username: $username"

mkdir -p "$STATE_DIR"
umask 077
cat > "$STATE_FILE" <<EOF
{
  "bridgeIp": "$local_ip",
  "username": "$username"
}
EOF
ok "Saved config to $STATE_FILE"

info "Verifying access..."
light_count=$(curl -fsS --max-time 5 "http://$local_ip/api/$username/lights" 2>/dev/null \
  | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || true)
if [[ -n "$light_count" ]]; then
  ok "Connected. Found $light_count light(s)."
else
  err "Wrote config but couldn't list lights yet. The panel will retry automatically."
fi
