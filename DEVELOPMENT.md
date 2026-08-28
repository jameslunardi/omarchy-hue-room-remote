# Development

See `tests/README.md` for the test suite. This file covers everything
else involved in working on the plugin day to day.

## Dev copy vs. live install

`~/Projects/Hue` (or wherever you've cloned this) and
`~/.config/omarchy/plugins/lunardi0x01.hue-room-remote` (the live
install Omarchy actually runs) are both plain git clones of this same
repo — the live copy is exactly what `omarchy plugin add` would have
produced. There's no build step:

1. Edit and commit in your working clone, then `git push`.
2. `omarchy plugin update lunardi0x01.hue-room-remote` fast-forwards the
   live copy (a real `git fetch` + `git merge --ff-only`, so it only
   picks up pushed commits — no shortcut for testing uncommitted changes
   other than copying the file over by hand for a quick local check).
3. `hue-api.py`/`HueApi.js`/`pair.sh` take effect immediately (invoked
   fresh per call). `Panel.qml` and other QML are loaded once at shell
   startup, so QML changes additionally need:

   ```
   omarchy-restart-shell
   ```

   This kills and relaunches the Quickshell bar via Hyprland, correctly
   handling lock-screen state (unlike a raw `pkill quickshell`).

## Live-debugging Panel.qml

The plugin runs inside the shared Omarchy Quickshell bar process, not as
its own inspectable process, so verifying a QML-side fix means watching
two log sources while reproducing the issue live. Neither logging path
exists in the shipped code right now (removed once the bug that needed
it was fixed and confirmed stable) — this section documents how to
reinstate it if a similar class of bug needs tracing again.

### Log sources

1. **`hue-api.py` calls** — the script swallows every exception and
   always exits 0 (see `main()`'s outer `try/except: pass`), so nothing
   about a failed bridge call is visible unless logged. Add a `_log(msg)`
   helper that appends timestamped lines to
   `~/.cache/omarchy-hue-debug.log`, e.g.:

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
   `roomLightsProc` exit and stream-finished handlers. Tail the *running*
   shell instance's console output with:

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

Restarting the shell ends any `quickshell log -f` tail following the old
process — start a new one against the fresh instance afterward.

## Known-fragile spot: two concurrent shell instances

There are two independent instances of this plugin running at once (one
bar per monitor, in a multi-monitor setup), each with its own poll
timer, action queue, and fetch state. A fix that works "within" one
instance's logic doesn't automatically protect against races *between*
the two instances. Keep this in mind when reasoning about anything
involving concurrent bridge requests or shared settings-file writes.
