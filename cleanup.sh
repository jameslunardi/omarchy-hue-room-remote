#!/usr/bin/env bash
set -euo pipefail

STATE_FILE="${XDG_STATE_HOME:-$HOME/.local/state}/omarchy/settings/hue.json"
CONFIG_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/settings/hue-theme.json"
HOOK_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/hooks/theme-set.d/45-hue.sh"

removed=0

secure_remove() {
  local f="$1"
  [[ -f "$f" ]] || return 0
  if [[ -L "$f" ]]; then
    rm "$f"
    return 0
  fi
  local owner
  owner=$(stat -c '%U' "$f" 2>/dev/null || true)
  if [[ "$owner" == "$USER" ]]; then
    local size
    size=$(stat -c%s "$f" 2>/dev/null || echo 0)
    if [[ "$size" -gt 0 ]]; then
      dd if=/dev/zero of="$f" bs=1 count="$size" conv=notrunc 2>/dev/null || true
    fi
  fi
  rm "$f"
}

if [[ -f "$STATE_FILE" ]]; then
  secure_remove "$STATE_FILE"
  echo "Removed $STATE_FILE"
  removed=$((removed + 1))
fi

if [[ -f "$CONFIG_FILE" ]]; then
  rm -f "$CONFIG_FILE"
  echo "Removed $CONFIG_FILE"
  removed=$((removed + 1))
fi

if [[ -f "$HOOK_FILE" ]]; then
  rm -f "$HOOK_FILE"
  echo "Removed $HOOK_FILE"
  removed=$((removed + 1))
fi

if [[ $removed -eq 0 ]]; then
  echo "No Hue files found to remove."
fi
