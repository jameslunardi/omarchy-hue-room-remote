#!/usr/bin/env bash
set -euo pipefail

STATE_FILE="${XDG_STATE_HOME:-$HOME/.local/state}/omarchy/settings/hue.json"
CONFIG_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/settings/hue-theme.json"
HOOK_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/hooks/theme-set.d/45-hue.sh"

removed=0

if [[ -f "$STATE_FILE" ]]; then
  rm "$STATE_FILE"
  echo "Removed $STATE_FILE"
  (( removed++ ))
fi

if [[ -f "$CONFIG_FILE" ]]; then
  rm "$CONFIG_FILE"
  echo "Removed $CONFIG_FILE"
  (( removed++ ))
fi

if [[ -f "$HOOK_FILE" ]]; then
  rm "$HOOK_FILE"
  echo "Removed $HOOK_FILE"
  (( removed++ ))
fi

if [[ $removed -eq 0 ]]; then
  echo "No Hue files found to remove."
fi
