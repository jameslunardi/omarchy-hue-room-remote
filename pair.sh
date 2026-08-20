#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/omarchy/settings"
STATE_FILE="$STATE_DIR/hue.json"
CACERT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/hue_bridge_cacert.pem"
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

fetch_bridge_id() {
  local ip="$1" bridge_id
  bridge_id=$(python3 - "
import json, ssl, sys, urllib.request
ctx = ssl.create_default_context(cafile=\"$CACERT\")
ctx.check_hostname = False
try:
    with urllib.request.urlopen(\"https://$ip/api/config\", timeout=5, context=ctx) as r:
        d = json.load(r)
        bid = d.get(\"bridgeid\", \"\")
        print(bid.lower() if bid else \"\")
except Exception:
    pass
" 2>/dev/null || true)
  printf '%s\n' "$bridge_id"
}

pair() {
  local ip="$1" bridge_id="$2" response username
  response=$(curl -fsS --max-time 8 --cacert "$CACERT" \
    --resolve "${bridge_id}:443:${ip}" \
    -X POST -H "Content-Type: application/json" \
    -d "{\"devicetype\":\"$DEVICETYPE\"}" "https://${bridge_id}/api" 2>/dev/null || true)
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

info "Fetching bridge ID..."
bridge_id=$(fetch_bridge_id "$local_ip")
if [[ -z "$bridge_id" ]]; then
  err "Could not fetch bridge ID. Aborting."
  exit 1
fi
ok "Bridge ID: ${bridge_id:0:8}***"

info "Requesting access from the bridge..."
username=$(pair "$local_ip" "$bridge_id") || true
if [[ -z "$username" ]]; then
  err "Pairing failed. The link button was likely not pressed within 30 seconds. Try again."
  exit 1
fi
ok "Got username: ${username:0:4}***"

mkdir -p "$STATE_DIR"
if [[ -f "$STATE_FILE" ]]; then
  current_perms=$(stat -c '%a' "$STATE_FILE" 2>/dev/null || echo "000")
  if [[ "$current_perms" != "600" ]]; then
    chmod 600 "$STATE_FILE"
  fi
fi
umask 077
cat > "$STATE_FILE" <<EOF
{
  "bridgeIp": "$local_ip",
  "bridgeId": "$bridge_id",
  "username": "$username"
}
EOF
chmod 600 "$STATE_FILE"
ok "Saved config to $STATE_FILE"

if [[ ! -f "$CACERT" ]]; then
  err "CA cert not found at $CACERT. Cannot verify bridge connection."
  exit 1
fi

info "Verifying access..."
light_count=$(curl -fsS --max-time 5 --cacert "$CACERT" \
  --resolve "${bridge_id}:443:${local_ip}" \
  "https://${bridge_id}/api/${username}/lights" 2>/dev/null \
  | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || true)
if [[ -n "$light_count" ]]; then
  ok "Connected. Found $light_count light(s)."
else
  err "Wrote config but couldn't list lights yet. The panel will retry automatically."
fi
