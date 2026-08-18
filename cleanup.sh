#!/usr/bin/env bash
set -euo pipefail

STATE_FILE="${XDG_STATE_HOME:-$HOME/.local/state}/omarchy/settings/hue.json"

if [[ -f "$STATE_FILE" ]]; then
  rm "$STATE_FILE"
  echo "Removed $STATE_FILE"
else
  echo "No Hue config found at $STATE_FILE"
fi
