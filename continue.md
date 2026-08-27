# Continue here

Status as of 2026-08-27 end of session: the Room View / Room List redesign is
done and confirmed working well by the user ("I think this is perfect!").
This file is the task list and context for the next session.

## Project layout

- Dev copy (this repo): `~/Projects/Hue`
- Live installed copy (what Omarchy actually runs): `~/.config/omarchy/plugins/omarchy-philips-hue`
- Both are separate git repos with identical history — every change gets
  copied to both and committed in both. See "Git / publishing" below for why
  this is about to change.
- `TESTING.md` documents the test suite (`tests/run.sh`) and the live-debug
  procedure (`quickshell log -f` + `~/.cache/omarchy-hue-debug.log`) used to
  chase down bugs this session.

## What happened this session (brief)

- Identified the installed plugin was a customized fork of
  `sethchev/omarchy-philips-hue` with a hardcoded single-room filter.
- Fixed several real bugs: action-queue coalescing, a self-cancelling
  `refresh()` race that was the actual cause of "Couldn't reach the bridge",
  a missing settings directory, `pair.sh`'s octal IP-parsing bug.
- Added a real test suite (`tests/`, stdlib `unittest` + Node's `node:test`,
  no new deps) and moved live-debugging notes from session memory into
  `TESTING.md`.
- Full interface redesign: replaced the single-room filter with two views —
  **Room List** (rooms with lights only, tap to open, star to favorite) and
  **Room View** (name, on/off, room-brightness slider via group action,
  scene list, tap a scene to apply). No more per-light controls or the
  theme-sync toggle (the underlying `theme-sync/45-hue.sh` hook is
  unaffected — it reads `hue-theme.json` independently).
- Fixed several redesign bugs: a `Loader` height-retention bug that left
  dead space under the room list, brightness slider resetting because the
  bridge's group `action.bri` isn't reliable, room toggle now re-applies the
  last-used scene instead of a flat on, brightness now derived from real
  per-light `state.bri` fetched on-demand for just the active room.
- Dropped the theme name from the header ("Hue Lights (nord)" → "Hue Lights").

## Task list for next session

1. **Debug logging: keep or strip?** Still undecided. `Panel.qml` has 18
   `dlog()` calls, `hue-api.py` has 4 `_log()` calls, writing to
   `~/.cache/omarchy-hue-debug.log`. Useful during this session's debugging;
   ask the user whether to remove it now that things are stable, or leave it
   a while longer.

2. **Rename the plugin.** User wants a new name (not yet chosen — ask).
   Touches: `manifest.json` (`id`, `name`), the plugin directory name under
   `~/.config/omarchy/plugins/`, possibly the repo name on GitHub. Note
   `manifest.id` is what's registered in the bar layout config
   (`~/.config/omarchy/shell.json`) — check whether renaming the id requires
   updating that reference too, or whether `omarchy plugin`/`omarchy bar`
   tooling has a rename path.

3. **GitHub fork setup.** User wants to be walked through this. Currently
   `origin` on both copies points at `sethchev/omarchy-philips-hue` (the
   original author's repo — no push access, and it's not a fork of the
   user's). Needs: create a GitHub repo under the user's account (possibly
   via `gh repo fork` or `gh repo create`, decide with the user), point one
   canonical copy's `origin` at it, push. Decide whether to keep both the
   dev copy and installed copy as separate git repos long-term, or
   restructure so the installed plugin dir is not its own separate git repo
   (e.g. symlink, or a deploy step) — worth raising with the user, this
   dual-repo-mirroring approach was a pragmatic choice for this session, not
   necessarily the best long-term setup.

4. **Update README.md.** Currently describes the old per-light/per-room
   design entirely (per-light sliders, color wheel, theme sync toggle) —
   none of that matches the current interface. Rewrite to describe Room
   View / Room List / favorites / scenes. Also add credit to the original
   author (sethchev, https://github.com/sethchev/omarchy-philips-hue) per
   user's request, and update the install command once the repo has moved.

5. **New preview.png.** Current screenshot is of the old interface. Needs a
   fresh screenshot of the new Room List / Room View once naming/branding
   is settled.

6. **Publish to omarchyplugins.com.** Not yet investigated what this
   requires (a submission process, a manifest field, a listing PR — unknown,
   look into it next session).

7. **Minor cleanup, low priority:**
   - `manifest.json` version is still `1.1.0` despite the rewrite — bump it.
   - `write-theme-config` in `hue-api.py` is dead code now that the
     theme-sync UI toggle is gone (nothing calls it). Harmless as-is;
     remove only if confident a settings UI for it won't come back.

## Prompt for starting the next session

```
Continuing work on the omarchy-philips-hue plugin redesign. Read
~/Projects/Hue/continue.md for full context and the task list — start with
item 1 (decide on debug logging) unless I say otherwise. Remember: changes
need to be copied to and committed in both ~/Projects/Hue (dev) and
~/.config/omarchy/plugins/omarchy-philips-hue (live install, what Omarchy
actually runs), and Panel.qml changes need `omarchy-restart-shell` to take
effect — see TESTING.md for the live-debugging procedure if something needs
tracing. Run tests/run.sh before committing anything touching
hue-api.py/HueApi.js/pair.sh.
```
