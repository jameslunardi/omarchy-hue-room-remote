#!/usr/bin/env bash
# Installs the omarchy theme-set hook that syncs Hue lights to the active
# theme, plus a default hue-theme.json config.
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
HOOK_SRC="$HERE/45-hue.sh"
CONFIG_SRC="$HERE/hue-theme.json"
HOOK_DIR="$HOME/.config/omarchy/hooks/theme-set.d"
CONFIG_DIR="$HOME/.config/omarchy/settings"
HOOK_DEST="$HOOK_DIR/45-hue.sh"
CONFIG_DEST="$CONFIG_DIR/hue-theme.json"

[[ -f "$HOOK_SRC" ]] || { echo "error: missing $HOOK_SRC" >&2; exit 1; }

mkdir -p "$HOOK_DIR" "$CONFIG_DIR"

if [[ -f "$HOOK_DEST" ]] && [[ ! -L "$HOOK_DEST" ]]; then
  backup="$HOOK_DEST.bak.$(date +%s)"
  cp -f "$HOOK_DEST" "$backup"
  echo "Backed up existing hook to $backup"
fi

[[ ! -L "$HOOK_DEST" ]] || rm "$HOOK_DEST"
cp -f "$HOOK_SRC" "$HOOK_DEST"
chmod +x "$HOOK_DEST"
echo "Installed $HOOK_DEST"

if [[ -L "$CONFIG_DEST" ]]; then
  rm "$CONFIG_DEST"
  cp "$CONFIG_SRC" "$CONFIG_DEST"
  echo "Installed $CONFIG_DEST"
elif [[ ! -f "$CONFIG_DEST" ]]; then
  cp "$CONFIG_SRC" "$CONFIG_DEST"
  echo "Installed $CONFIG_DEST"
else
  echo "Left $CONFIG_DEST in place (already exists)"
fi

echo
echo "Done. The hook runs automatically on every 'omarchy theme set'."
echo "Test it now with:  bash $HOOK_DEST <theme-slug>"
