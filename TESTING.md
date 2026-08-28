# Testing

## Running the suite

```
tests/run.sh
```

Runs all three layers: Python (`hue-api.py`), JS (`HueApi.js`), and bash
(`pair.sh`'s `valid_ip`). Each can also be run standalone:

```
python3 -m unittest tests.test_hue_api -v
node --test tests/hue-api.test.js
bash tests/test_pair_sh.sh
```

No dependencies beyond `python3` and `node` — deliberately using stdlib
`unittest` and the built-in `node:test` runner rather than pulling in
pytest/jest/mocha for a plugin this size.

## What's covered, and what isn't

- **`HueApi.js`** (`tests/hue-api.test.js`): pure functions with no QML
  dependency — `isValidIp`, `isValidId`, `parseConfig`, `parseLights`,
  `parseGroups`, `roomLights`. The file guards its one QML-only call
  (`Qt.resolvedUrl`) so it loads fine under plain Node, and exports its
  functions via `module.exports` only when `module` exists (a no-op under
  QML's JS engine).
- **`hue-api.py`** (`tests/test_hue_api.py`): `_write_favorite`
  (including the settings-directory bug fixed 2026-08-27) and the
  argument-validation regexes in `_dispatch`. Loaded via
  `importlib.util.spec_from_file_location` since the filename has a
  hyphen. `_request`/`_put` (the actual bridge HTTP calls) aren't
  exercised yet — they'd need a mocked HTTPS layer.
- **`pair.sh`** (`tests/test_pair_sh.sh`): only `valid_ip`, extracted with
  `sed` since the rest of the script performs live bridge discovery with
  no sourceable guard, so it can't be safely imported into a test process.
- **`Panel.qml`'s state machine is not unit-tested.** It's tied to
  Quickshell's `Process`/`Timer` objects and only really runs inside a
  live shell instance. The class of bug that lives here (the
  self-cancelling-refresh race, action-queue coalescing) is exercised via
  the live-debugging procedure below instead of an automated test.

## TDD workflow for this plugin

For the Python/JS/bash layers: write the failing test first in the
relevant `tests/` file, confirm it fails for the right reason, then fix
`hue-api.py`/`HueApi.js`/`pair.sh` until it passes.

`~/Projects/Hue` (dev) and `~/.config/omarchy/plugins/lunardi0x01.hue-room-remote`
(live) are both git clones of
[lunardi0x01/omarchy-hue-room-remote](https://github.com/lunardi0x01/omarchy-hue-room-remote) —
the live copy is exactly what `omarchy plugin add` would have produced.
Edit and commit in the dev copy, push, then run
`omarchy plugin update lunardi0x01.hue-room-remote` to fast-forward the
live copy (this is a real `git fetch` + `git merge --ff-only`, so it
only works once a commit is actually pushed — there's no shortcut for
testing uncommitted changes other than copying the file over by hand
for a quick local check).

For `Panel.qml` changes, there's no automated red/green cycle — use the
live-debugging procedure below to verify a fix actually resolves the
symptom before committing it.

## Live-debugging Panel.qml

The plugin runs inside the shared Omarchy Quickshell bar process, not as
its own inspectable process, so verifying a QML-side fix means watching
two log sources while reproducing the issue live. The logging calls
described below were removed from the code once the 2026-08-27 bridge-
unreachable bug was fixed and confirmed stable — this section documents
how to reinstate them if a similar class of bug needs tracing again.

### Log sources

1. **`hue-api.py` calls** — the script swallows every exception and always
   exits 0 (see `main()`'s outer `try/except: pass`), so nothing about a
   failed bridge call is visible unless logged. Add a `_log(msg)` helper
   that appends timestamped lines to `~/.cache/omarchy-hue-debug.log`,
   e.g.:

   ```python
   def _log(msg):
       try:
           ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
           with open(DEBUG_LOG, "a") as f:
               f.write("%s %s\n" % (ts, msg))
       except Exception:
           pass
   ```

   and call it around `_dispatch(op)` in `main()` with `start`/`ok`/`FAIL`
   lines (include timing and exception detail on failure).

2. **`Panel.qml`'s state transitions** — add a `dlog(msg)` helper
   (`console.log("[hue-debug] " + msg)`) and place calls at `refresh()`,
   `finishFetch()`, `assembleRooms()`, `queueAction()`/
   `drainActionQueue()`, and the `groupsProc`/`scenesProc`/`actionProc`/
   `roomLightsProc` exit and stream-finished handlers — those are the
   spots that mattered when chasing the self-cancelling-refresh race and
   action-queue coalescing bugs. Tail the *running* shell instance's
   console output with:

   ```
   quickshell log -f -p /usr/share/omarchy/shell
   ```

### Combined live watch

```
{ tail -n +1 -F "$HOME/.cache/omarchy-hue-debug.log" 2>/dev/null | sed -u 's/^/[py]  /'; } &
quickshell log -f -p /usr/share/omarchy/shell 2>&1 | grep --line-buffered "hue-debug" | sed -u 's/^/[qml] /'
```

If this is too noisy while reproducing something (rapid slider drags
easily produce dozens of lines/second), narrow the `grep` to the specific
signal you're chasing, e.g.:

```
grep -E --line-buffered "FAIL|finishFetch\(false\)"
```

### Applying a QML change

`hue-api.py`/`HueApi.js`/`pair.sh` take effect immediately (invoked
fresh per call). `Panel.qml` and other QML are loaded once at shell
startup — after editing, commit + push from the dev copy and run
`omarchy plugin update lunardi0x01.hue-room-remote` to bring the live copy
up to date (or, for a quick local-only check before committing, copy
the file directly into the live install path), then:

```
omarchy-restart-shell
```

This kills and relaunches the Quickshell bar via Hyprland, correctly
handling lock-screen state (unlike a raw `pkill quickshell`). Restarting
ends any `quickshell log -f` tail following the old process — start a new
one against the fresh instance afterward.

### Known-fragile spot to watch for

There are two independent instances of this plugin running at once (one
bar per monitor), each with its own poll timer, action queue, and fetch
state. A fix that works "within" one instance's logic doesn't
automatically protect against races *between* the two instances. Keep
this in mind when reasoning about anything involving concurrent bridge
requests.
