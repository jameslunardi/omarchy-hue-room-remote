# Testing

## Running the suite

```
tests/run.sh
```

Runs all three layers: Python (`hue_api.py`), JS (`hue_api.js`), and bash
(`pair.sh`'s `valid_ip`). Each can also be run standalone:

```
python3 -m unittest tests.test_hue_api -v
node --test tests/hue_api.test.js
bash tests/test_pair_sh.sh
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
  `_load_creds` (symlink/owner/size-cap guards), `_read_json_capped`,
  `_NoRedirectHandler`, and `_atomic_write`'s mkstemp+rename symlink
  regression test (plants a symlink at the target path first, asserts the
  real file it points at is untouched). Loaded via
  `importlib.util.spec_from_file_location` since the filename has a
  hyphen. `_request`/`_put` (the actual bridge HTTP calls) aren't
  exercised yet — they'd need a mocked HTTPS layer.
- **`pair.sh`** (`test_pair_sh.sh`): only `valid_ip`, extracted with
  `sed` since the rest of the script performs live bridge discovery with
  no sourceable guard, so it can't be safely imported into a test process.
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
