# Testing

## Running the suite

```
tests/run.sh
```

Runs all three layers: Python (`hue_api.py`), JS (`hue_api.js`), and bash
(`pair.sh`'s `valid_ip`, `cleanup.sh`'s `secure_remove`). Each can also be
run standalone:

```
python3 -m unittest tests.test_hue_api -v
node --test tests/hue_api.test.js
bash tests/test_pair_sh.sh
bash tests/test_cleanup_sh.sh
```

No dependencies beyond `python3` and `node` — deliberately using stdlib
`unittest` and the built-in `node:test` runner rather than pulling in
pytest/jest/mocha for a plugin this size.

## What's covered, and what isn't

- **`hue_api.js`** (`hue_api.test.js`): pure functions with no QML
  dependency — `isValidId`, `parseStatus`, `parseGroups`, `parseScenes`
  (including the malformed-id-dropping and bounded-size/item-count/
  name-length guards on all three), `roomIcon`, `applyOrder`,
  `roomBrightness`. The file guards its one QML-only call
  (`Qt.resolvedUrl`) so it loads fine under plain Node, and exports its
  functions via `module.exports` only when `module` exists (a no-op under
  QML's JS engine).
- **`hue_api.py`** (`test_hue_api.py`): `_write_favorite`, `_write_order`
  (including its merge-not-clobber behavior across `roomOrder`/
  `sceneOrder`/`lastScene`/`hiddenRooms`), the argument-validation regexes
  in `_dispatch`, `_get_status` (never leaks `username`/`bridgeIp`),
  `_read_json_capped`, `_NoRedirectHandler`, `_atomic_write`'s
  mkstemp+rename symlink regression test (plants a symlink at the target
  path first, asserts the real file it points at is untouched) and its
  directory-lockdown test (`chmod 700` on the settings directory), and
  `_read_local_json_capped` — the shared helper behind both `_load_creds`
  and `_write_order`'s pre-read — covering symlink/owner/size-cap guards
  plus a FIFO planted at the target path (`os.mkfifo`), asserting it's
  rejected instead of hanging the call. Loaded via
  `importlib.util.spec_from_file_location` since it lives at the repo
  root rather than inside the `tests` package, so a normal `import
  hue_api` isn't guaranteed to resolve regardless of invocation method.
  `_request`/`_put` (the actual bridge HTTP calls) aren't exercised yet —
  they'd need a mocked HTTPS layer.
- **`pair.sh`** (`test_pair_sh.sh`): only `valid_ip`, extracted with
  `sed` since the rest of the script performs live bridge discovery with
  no sourceable guard, so it can't be safely imported into a test process.
  Its response-bounding (`head -c "$MAX_RESPONSE_BYTES"` on the two curl
  calls, a capped `read()` in `fetch_bridge_id`'s embedded Python) and the
  `STATE_DIR` symlink pre-check have no automated coverage for the same
  reason — verified manually instead (see `.project/tasklist.md` for how).
- **`cleanup.sh`** (`test_cleanup_sh.sh`): `secure_remove`, extracted the
  same way as `pair.sh`'s `valid_ip` — unlike the rest of `pair.sh`, this
  function is fully local and deterministic (no live network calls), so
  it's safe to test directly: a regular owned file gets zeroed before
  removal (checked via a hard link that keeps the inode alive past the
  `rm`), a symlink is removed without the shred write ever touching its
  target, and a missing path is a silent no-op.
- **`panel.qml`'s state machine is not unit-tested.** It's tied to
  Quickshell's `Process`/`Timer` objects and only really runs inside a
  live shell instance. See `../DEVELOPMENT.md` for the live-debugging
  procedure used to exercise this class of bug instead of an automated
  test.

## TDD workflow for this plugin

For the Python/JS/bash layers: write the failing test first in the
relevant file here, confirm it fails for the right reason, then fix
`hue_api.py`/`hue_api.js`/`pair.sh` until it passes.

For `panel.qml` changes, there's no automated red/green cycle — see
`../DEVELOPMENT.md` for the live-debugging procedure to verify a fix
actually resolves the symptom before committing it.
