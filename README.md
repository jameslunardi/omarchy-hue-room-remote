# omarchy-philips-hue

Omarchy / Quickshell bar widget for controlling Philips Hue lights over the bridge's local HTTP API (v1).

<p align="center">
  <img src="preview.png" alt="omarchy-philips-hue panel screenshot" width="360">
</p>

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
- `curl`, `python3` (for pairing), `omarchy-shell`

## Install

```sh
omarchy plugin add https://github.com/sethchev/omarchy-philips-hue.git --enable
```

## Pairing with the bridge

On first run the bar shows a lightbulb icon. Click it to open the panel, then
click **Pair with bridge**. This opens a terminal — press the link button on
your Hue bridge when prompted. The script discovers the bridge, requests a
username, and writes `~/.local/state/omarchy/settings/hue.json`. The panel
picks up the new credentials automatically within seconds.

You can also pair manually:

```sh
~/.config/omarchy/plugins/omarchy-philips-hue/pair.sh
```

Pass an IP directly to skip auto-discovery: `pair.sh 192.168.1.14`.

## Syncing lights with the omarchy theme

The plugin automatically syncs every room/zone to the active theme's `accent`
color whenever you run `omarchy theme set`. This is built into the QML plugin
itself — no external hooks or scripts required.

The plugin watches `~/.local/state/omarchy/current/theme/colors.toml` and
`~/.local/state/omarchy/current/theme.name` for changes, then sends the accent
color to your Hue bridge groups.

Behavior is configured in `~/.config/omarchy/settings/hue-theme.json`:

```json
{
  "enabled": true,
  "transition": 20,
  "groups": ["all"],
  "bri": null,
  "turnOn": false,
  "themes": {}
}
```

- `enabled` — `false` to disable theme syncing
- `transition` — fade length in tenths of a second (20 = 2 s)
- `groups` — `["all"]`, or a subset of room/zone names to sync
- `bri` — optional forced brightness (1–254); leave `null` to keep each light's current brightness
- `turnOn` — `true` to turn lights on when syncing; `false` leaves on/off state untouched
- `themes` — per-theme hex overrides, e.g. `{ "spacehaven": "#0c8184" }`; themes without an override use their own `accent`

## Remove

```sh
~/.config/omarchy/plugins/omarchy-philips-hue/cleanup.sh
omarchy plugin remove omarchy-philips-hue
```

The cleanup script removes your bridge credentials from
`~/.local/state/omarchy/settings/hue.json`. Run it before removing the
plugin so no auth token is left behind.

## Notes

- Speaks to the bridge over plain HTTP on your LAN with the v1 API
  (`/api/<username>/lights`, `/groups`, etc.) — no cloud, no SDK.
- Credentials are stored per-user in `~/.local/state/omarchy/settings/hue.json`;
  keep that file out of version control.
