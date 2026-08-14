# philips.hue

Omarchy / Quickshell bar widget for controlling Philips Hue lights over the bridge's local HTTP API (v1).

## Features

- Bar icon (lightbulb) that opens a control panel
- Toggle all rooms, individual rooms, or single lights
- Per-light brightness slider
- Per-light color temperature slider (warm ⇄ cool white)
- Per-light color wheel picker (hue + saturation)
- Reads credentials from `~/.local/state/omarchy/settings/hue.json`
- Retries / re-fetches state automatically after every change

## Requirements

- Arch Linux + Omarchy (Quickshell-based shell)
- `curl`, `python3` (for the pairing script), `omarchy-shell`

## Install

```sh
git clone https://github.com/<your-user>/philips-hue ~/.config/omarchy/plugins/philips.hue
omarchy plugin enable philips.hue
omarchy restart shell
```

## Pairing with the bridge

On first run the panel shows "Not paired". Pair it with:

```sh
~/.config/omarchy/plugins/philips.hue/pair.sh
```

Press the link button on the Hue bridge when prompted. The script discovers the
bridge, requests a username, and writes `~/.local/state/omarchy/settings/hue.json`.
You can also pass an IP directly: `pair.sh 192.168.1.14`.

## Notes

- Speaks to the bridge over plain HTTP on your LAN with the v1 API
  (`/api/<username>/lights`, `/groups`, etc.) — no cloud, no SDK.
- Credentials are stored per-user in `~/.local/state/omarchy/settings/hue.json`;
  keep that file out of version control.
