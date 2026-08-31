#!/usr/bin/env bash
# Extracts and exercises pair.sh's valid_ip() in isolation. pair.sh itself
# runs live bridge discovery/pairing at the top level with no sourceable
# guard, so the function body is pulled out with sed rather than sourcing
# the whole script.
set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PAIR_SH="$SCRIPT_DIR/../pair.sh"

eval "$(sed -n '/^valid_ip()/,/^}/p' "$PAIR_SH")"
eval "$(sed -n '/^shred_file()/,/^}/p' "$PAIR_SH")"
eval "$(sed -n '/^fetch_bridge_id()/,/^}/p' "$PAIR_SH")"

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

# shred_file (SEC-02): zeroes a regular owned file's content in place, so a
# re-pair's rm -f doesn't leave the superseded username in unallocated disk
# sectors. Use a hard link to keep the inode alive past this call so the
# zeroed content can still be inspected.
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
target="$TMP_DIR/hue.json"
witness="$TMP_DIR/witness.json"
printf 'supersecretusername' > "$target"
ln "$target" "$witness"
shred_file "$target"
if [[ "$(od -An -tx1 -- "$witness" | tr -d ' \n')" =~ ^0*$ ]]; then
  echo "ok   shred_file zeroed the file's content"
else
  echo "FAIL shred_file left non-zero content behind"
  fail=1
fi

# A FIFO planted at the target path must not hang shred_file (H-01):
# os.O_WRONLY without O_NONBLOCK blocks until a reader opens the same
# path, which never happens here. timeout catches a regression as a
# non-zero/124 exit rather than an actual indefinite hang.
fifo="$TMP_DIR/fifo.json"
mkfifo "$fifo"
if timeout 3 bash -c '
  eval "$(sed -n "/^shred_file()/,/^}/p" "$1")"
  shred_file "$2"
' _ "$PAIR_SH" "$fifo"; then
  echo "ok   shred_file did not hang on a FIFO"
else
  echo "FAIL shred_file hung (or errored) on a FIFO"
  fail=1
fi

# fetch_bridge_id must refuse to follow a redirect (L-01): a compromised or
# malicious bridge otherwise gets to point this unauthenticated bootstrap
# lookup at a different bridge entirely. Throwaway 20-year self-signed
# cert/key, generated once for this test file (`openssl req -x509 -newkey
# rsa:2048 -days 7300 -nodes -subj "/O=Test Bridge/CN=pairtestbridge01"`)
# and embedded as a literal, same approach as tests/test_hue_api.py's own
# embedded test cert -- kept separate rather than shared between the two
# test files, matching each file's existing convention of being
# self-contained with no cross-file/cross-language dependency.
CERT_PEM='-----BEGIN CERTIFICATE-----
MIIDQzCCAiugAwIBAgIUXhcYi3EpVv9gxGon/xsdNuGj6iswDQYJKoZIhvcNAQEL
BQAwMTEUMBIGA1UECgwLVGVzdCBCcmlkZ2UxGTAXBgNVBAMMEHBhaXJ0ZXN0YnJp
ZGdlMDEwHhcNMjYwODMxMjIwMjE3WhcNNDYwODI2MjIwMjE3WjAxMRQwEgYDVQQK
DAtUZXN0IEJyaWRnZTEZMBcGA1UEAwwQcGFpcnRlc3RicmlkZ2UwMTCCASIwDQYJ
KoZIhvcNAQEBBQADggEPADCCAQoCggEBANFiiSSFi7Ai919VwUZT7hA1/njQe2fc
GOfcFLSJds4MNxOu+m9jMQpxvq1k1Pg7wSCopZS1MLxWoEYylR/yFvhJLxHhw0/V
d5ga9ODv0tHA1LcukLXrD4gEmOlahJhynl6w+8CXrZ3KQfC4SFmRgAp2J93whJ+4
ewsTx28xCWe3/88iCZjBj+gypb4m0V7vVjaL2K6glntSP6POJ1PZVJ39doAwIDaA
7Lzpe0DicftpxMiz33gnI+HEjJ0E+P4/oQ9LxsIzU/UcrxMOdh2s03YGPjge92NL
7PQ2kqSG3qXo3GDONUrVVKqbezxWbus6qrii7MlzO5VyirQ/KbgwWv0CAwEAAaNT
MFEwHQYDVR0OBBYEFPZlxpcRibKvK7Jv7y5bhLbhWpeDMB8GA1UdIwQYMBaAFPZl
xpcRibKvK7Jv7y5bhLbhWpeDMA8GA1UdEwEB/wQFMAMBAf8wDQYJKoZIhvcNAQEL
BQADggEBAJ8QXUfbvVzF5mlVhnLtgy6xyawR9IeFCJImfbx7bkpS1GllmAxIg2lu
rvpAmbrUcKE/2PUpfXFg4DIEQzIbbOriTAWvX3JWFqxv9dcPYdUgidczkNhl0CNz
5nr3QHKl88qVldrM2s+irEbLFqZj69uo4S9gmwIMScovftitWrwf5xurPXygyne0
5dWSPhQNWUCntJ820sB9qJMJE2+OU23IW+6omQV/2OBEOdbD13PrD+XKNuRsaEAu
3MteKyuXxdLDRJGJUo++6Cp08Wg9i/cqRgo5GIg2rjgFtkadq5h6UG2cDHj6Pmr0
uTRyXDyDvVYKgshKrVFTSsjRWhO87NU=
-----END CERTIFICATE-----'

KEY_PEM='-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDRYokkhYuwIvdf
VcFGU+4QNf540Htn3Bjn3BS0iXbODDcTrvpvYzEKcb6tZNT4O8EgqKWUtTC8VqBG
MpUf8hb4SS8R4cNP1XeYGvTg79LRwNS3LpC16w+IBJjpWoSYcp5esPvAl62dykHw
uEhZkYAKdifd8ISfuHsLE8dvMQlnt//PIgmYwY/oMqW+JtFe71Y2i9iuoJZ7Uj+j
zidT2VSd/XaAMCA2gOy86XtA4nH7acTIs994JyPhxIydBPj+P6EPS8bCM1P1HK8T
DnYdrNN2Bj44HvdjS+z0NpKkht6l6NxgzjVK1VSqm3s8Vm7rOqq4ouzJczuVcoq0
Pym4MFr9AgMBAAECggEAG7BxfRLsAMRJp6HU3VKxY2jAg4Q5IuhITYvHxoLR4zha
UDq42OIVKicV6s2Fcbj1NoxsLoOHiQsrnBze+5/YHx1jzB7pj9/QNkfaT6S8twr5
FlW3bVdDG97/xFw5YgTw9zS7FiJOI1UL7flwwpIrNzbzhAtlKSS29iViH6IsduVG
VAK1oHG/W2ns+jXE+RBCfDZTrV7zuIPbv41l7KhTcc8YC0ZHR2ra+txrjEOgwbjp
4RD3hlj9t41uB9SVTxsanMYCh0ze8Ez3s2Lak6flLPJ20hf7ycjAgHzKnuTj72uv
xB/0oW32TH/sSlsbgiWNr+7woZrPJEb+3iViMUTtQQKBgQDs/SsYiehZ/xGWQ6+7
TIK5i41J3I43/m/8vU9B8C0LtUcMZQRgG5OWm7oVoKFa5gNxtAlK5NsNQ8VTEb1S
iXkbuUw/BvSraawE1YsblVHMJleE6JcP787NzE1Q86IfnbY9eynpEQrWL1pv9WV1
zM5VnAjDx9XyzHJMkEugUf7fCwKBgQDiLnzhNgPozPh7lcu1YLlOohHH5dgMMJGi
HELeohwiU+vYE6iaXTAP2y1RNF1gp09L2q/XJ9c7dxIfPL+fGbS/PCS62nSCgQGF
hfvuRNspWqRfYQ2PLWhWfnrPIWP0JxYhWC4zSzOAYMLpQqB0jXTYLd+eMuas2Vx3
pcuDDwWTFwKBgQDqc09mOFCAcCGy+YVpkzikXNXLI4IjDPk3HQXC4tt9gLooHeul
NMLetXLzoHTgmzr/CrBCwoOe7NPS6XLVq6D/d2Jh2/zDc4g1RBkZkbBZefkNSJjh
sEl0OVCn7E8QXhMDYcxFgZGp8TDUH/5e+t2JvhLBtPoI+I9/BSV8FoJBnwKBgGdc
MStF4OF5EbCAUtgvPF+HxrJgAawIYfUADzroQA0b5rIWwbzRCw6j7YCnemiZ7K3Q
YPzkswH0tu5Zd4QAXk3p8SsGe6nLxGM9SFSpWLH8PxNrKaQdbwnfwMV5D9FaL03L
m0lLe1yWW1v3W5YHsra7t+32et3QcuYmeOsKaVS/AoGABEo7755T9NwubR4eHC+x
altkapCJ/X5E30v4j0THFyG1f6r4aMNdEURM+9osTQlGrBdskwcJa1uBYcMHVsZE
mPkzO0FQOtyjmAYGlXyLoPPj9syfUJZfNSUVgramA5tZ7kA5Hez/5PGpz3AHwAGA
fyfPDUDcQsNUfNaKtCjcolo=
-----END PRIVATE KEY-----'

CERT_PATH="$TMP_DIR/pair_test_cert.pem"
KEY_PATH="$TMP_DIR/pair_test_key.pem"
printf '%s\n' "$CERT_PEM" > "$CERT_PATH"
printf '%s\n' "$KEY_PEM" > "$KEY_PATH"

# Minimal local HTTPS server for /api/config, in either "direct" mode
# (responds with a given bridgeid) or "redirect" mode (302s to a given
# Location). Prints the OS-assigned port as its first line of stdout so the
# caller can read it back after backgrounding the process.
cat > "$TMP_DIR/https_server.py" <<'PYEOF'
import http.server, json, ssl, sys

cert_path, key_path, mode, arg = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if mode == "redirect":
            self.send_response(302)
            self.send_header("Location", arg)
            self.end_headers()
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"bridgeid": arg}).encode())

    def log_message(self, *a):
        pass

httpd = http.server.HTTPServer(("127.0.0.1", 0), Handler)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(cert_path, key_path)
httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
sys.stdout.write(str(httpd.socket.getsockname()[1]) + "\n")
sys.stdout.flush()
httpd.serve_forever()
PYEOF

start_server() {
  # $1=mode $2=arg $3=portfile -- backgrounds the server and blocks until
  # its port has actually been written, rather than a fixed sleep.
  python3 "$TMP_DIR/https_server.py" "$CERT_PATH" "$KEY_PATH" "$1" "$2" > "$3" 2>/dev/null &
  echo $!
}

wait_for_port() {
  local portfile="$1" waited=0
  while [[ ! -s "$portfile" ]]; do
    sleep 0.05
    waited=$((waited + 1))
    if [[ $waited -gt 100 ]]; then return 1; fi
  done
  cat "$portfile"
}

CACERT="$CERT_PATH"
MAX_BOOTSTRAP_RESPONSE_BYTES=65536

# --- redirect refusal ---
decoy_portfile="$TMP_DIR/decoy_port"
decoy_pid=$(start_server "direct" "deaddeaddeaddead" "$decoy_portfile")
decoy_port=$(wait_for_port "$decoy_portfile") || { echo "FAIL decoy server never started"; fail=1; }

redirect_portfile="$TMP_DIR/redirect_port"
redirect_pid=$(start_server "redirect" "https://127.0.0.1:${decoy_port}/api/config" "$redirect_portfile")
redirect_port=$(wait_for_port "$redirect_portfile") || { echo "FAIL redirect server never started"; fail=1; }

result=$(fetch_bridge_id "127.0.0.1:${redirect_port}")
kill "$decoy_pid" "$redirect_pid" 2>/dev/null
wait "$decoy_pid" "$redirect_pid" 2>/dev/null

if [[ -z "$result" ]]; then
  echo "ok   fetch_bridge_id refused to follow a redirect"
else
  echo "FAIL fetch_bridge_id followed a redirect and returned '$result'"
  fail=1
fi

# --- positive path: proves the fix didn't break normal (non-redirecting) discovery ---
direct_portfile="$TMP_DIR/direct_port"
direct_pid=$(start_server "direct" "aabbccddeeff1122" "$direct_portfile")
direct_port=$(wait_for_port "$direct_portfile") || { echo "FAIL direct server never started"; fail=1; }

result=$(fetch_bridge_id "127.0.0.1:${direct_port}")
kill "$direct_pid" 2>/dev/null
wait "$direct_pid" 2>/dev/null

if [[ "$result" == "aabbccddeeff1122" ]]; then
  echo "ok   fetch_bridge_id still returns the bridge id on a normal (non-redirecting) response"
else
  echo "FAIL fetch_bridge_id returned '$result', expected 'aabbccddeeff1122'"
  fail=1
fi

exit $fail
