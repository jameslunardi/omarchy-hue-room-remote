#!/usr/bin/env bash
# Extracts and exercises pair.sh's valid_ip() in isolation. pair.sh itself
# runs live bridge discovery/pairing at the top level with no sourceable
# guard, so the function body is pulled out with sed rather than sourcing
# the whole script.
set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PAIR_SH="$SCRIPT_DIR/../pair.sh"

eval "$(sed -n '/^valid_ip()/,/^}/p' "$PAIR_SH")"

fail=0

assert_valid() {
  if valid_ip "$1"; then
    echo "ok   valid_ip('$1') accepted"
  else
    echo "FAIL valid_ip('$1') should be valid but was rejected"
    fail=1
  fi
}

assert_invalid() {
  if valid_ip "$1"; then
    echo "FAIL valid_ip('$1') should be invalid but was accepted"
    fail=1
  else
    echo "ok   valid_ip('$1') rejected"
  fi
}

assert_valid "192.168.1.1"
assert_valid "0.0.0.0"
assert_valid "255.255.255.255"
# Leading-zero octets: valid_ip must not misread these as octal (the bug
# fixed by the `10#$part` guard) and must still bound-check them correctly.
assert_valid "192.168.1.08"
assert_valid "010.0.0.1"

assert_invalid "256.1.1.1"
assert_invalid "1.2.3"
assert_invalid "1.2.3.4.5"
assert_invalid "not.an.ip.addr"
assert_invalid ""

exit $fail
