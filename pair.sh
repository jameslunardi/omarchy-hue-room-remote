#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/omarchy/settings"
STATE_FILE="$STATE_DIR/hue.json"
CACERT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/hue_bridge_cacert.pem"
MAX_BOOTSTRAP_RESPONSE_BYTES=65536
MAX_CREDS_BYTES=4096
DEVICETYPE="${PHILIPS_HUE_DEVICETYPE:-philips#omarchy-hue}"
DEVICETYPE="${DEVICETYPE//[^a-zA-Z0-9#_-]/}"

BRIDGE_IP="${1:-}"

info() { printf '\033[1;34m::\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m::\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m::\033[0m %s\n' "$*" >&2; }

valid_ip() {
  local parts
  IFS='.' read -ra parts <<< "$1"
  [[ ${#parts[@]} -eq 4 ]] || return 1
  for part in "${parts[@]}"; do
    [[ "$part" =~ ^[0-9]{1,3}$ ]] || return 1
    (( 10#$part >= 0 && 10#$part <= 255 )) || return 1
  done
}

discover_bridge() {
  local response ip
  response=$(curl -fsS --max-time 5 https://discovery.meethue.com/ 2>/dev/null | head -c "$MAX_BOOTSTRAP_RESPONSE_BYTES" || true)
  [[ -z "$response" ]] && return 1
  ip=$(python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    ips = [x.get('internalipaddress', '') for x in d if isinstance(x, dict) and x.get('internalipaddress')]
    print(ips[0] if ips else '')
except Exception:
    pass
" <<<"$response")
  [[ -n "$ip" ]] || return 1
  printf '%s\n' "$ip"
}

fetch_bridge_id() {
  local ip="$1" bridge_id
  bridge_id=$(CACERT="$CACERT" TARGET_IP="$ip" MAX_BYTES="$MAX_BOOTSTRAP_RESPONSE_BYTES" python3 - <<'PY' 2>/dev/null || true
import json, os, ssl, sys, urllib.request
cacert = os.environ["CACERT"]
target = os.environ["TARGET_IP"]
max_bytes = int(os.environ["MAX_BYTES"])
ctx = ssl.create_default_context(cafile=cacert)
ctx.check_hostname = False
try:
    with urllib.request.urlopen("https://%s/api/config" % target, timeout=5, context=ctx) as r:
        raw = r.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError("response too large")
        d = json.loads(raw)
        bid = d.get("bridgeid", "")
        bid = bid.lower() if bid else ""
        if all(c in "0123456789abcdef" for c in bid) and len(bid) == 16:
            print(bid)
except Exception:
    pass
PY
  )
  printf '%s\n' "$bridge_id"
}

write_state() {
  local bridge_ip="$1" bridge_id="$2" username="$3"
  printf '%s\n%s\n%s\n' "$bridge_ip" "$bridge_id" "$username" | python3 -c "
import json, os, sys
bridge_ip, bridge_id, username = sys.stdin.read().splitlines()[:3]
state_file = sys.argv[1]
fd = os.open(state_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as f:
    json.dump({'bridgeIp': bridge_ip, 'bridgeId': bridge_id, 'username': username}, f, indent=2)
    f.write('\n')
" "$STATE_FILE"
}

# Best-effort zero-fill before a re-pair's rm -f unlinks the old config, so
# the superseded username doesn't just sit in unallocated disk sectors.
# Same open/fstat/S_ISREG+owner shape as cleanup.sh's secure_remove, minus
# the removal itself -- the caller does its own remove-and-retry.
shred_file() {
  local f="$1"
  python3 -c "
import os, stat, sys
path = sys.argv[1]
try:
    fd = os.open(path, os.O_WRONLY | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        if stat.S_ISREG(st.st_mode) and st.st_uid == os.getuid() and st.st_size > 0:
            os.write(fd, b'\x00' * st.st_size)
    finally:
        os.close(fd)
except OSError:
    pass
" "$f" 2>/dev/null || true
}

pair() {
  local ip="$1" bridge_id="$2" response username
  response=$(curl -fsS --max-time 8 --cacert "$CACERT" \
    --resolve "${bridge_id}:443:${ip}" \
    -X POST -H "Content-Type: application/json" \
    -d "{\"devicetype\":\"$DEVICETYPE\"}" "https://${bridge_id}/api" 2>/dev/null | head -c "$MAX_BOOTSTRAP_RESPONSE_BYTES" || true)
  username=$(python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    for item in d:
        if isinstance(item, dict) and 'success' in item and 'username' in item['success']:
            u = item['success']['username']
            import re
            if re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', u):
                print(u)
            break
except Exception:
    pass
" <<<"$response")
  [[ -n "$username" ]] || return 1
  printf '%s\n' "$username"
}

if [[ -f "$STATE_FILE" ]] && MAX_BYTES="$MAX_CREDS_BYTES" python3 -c "
import json, os, stat, sys
path = sys.argv[1]
max_bytes = int(os.environ['MAX_BYTES'])
try:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid():
            sys.exit(1)
        data = os.read(fd, max_bytes + 1)
    finally:
        os.close(fd)
    if len(data) > max_bytes:
        sys.exit(1)
    d = json.loads(data)
    sys.exit(0 if d.get('bridgeIp') else 1)
except Exception:
    sys.exit(1)
" "$STATE_FILE" 2>/dev/null; then
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

if [[ -L "$STATE_DIR" ]]; then
  err "$STATE_DIR is a symlink; refusing to use it."
  exit 1
fi
mkdir -p "$STATE_DIR" && chmod 700 "$STATE_DIR"
write_state "$local_ip" "$bridge_id" "$username" 2>/dev/null || {
  shred_file "$STATE_FILE"
  rm -f "$STATE_FILE" 2>/dev/null
  write_state "$local_ip" "$bridge_id" "$username"
}
ok "Saved config to $STATE_FILE"

if [[ ! -f "$CACERT" ]]; then
  err "CA cert not found at $CACERT. Cannot verify bridge connection."
  exit 1
fi

info "Verifying access..."
light_count=$(python3 "$(dirname -- "${BASH_SOURCE[0]}")/hue_api.py" verify 2>/dev/null || true)
if [[ -n "$light_count" ]]; then
  ok "Connected. Found $light_count light(s)."
else
  err "Wrote config but couldn't list lights yet. The panel will retry automatically."
fi
