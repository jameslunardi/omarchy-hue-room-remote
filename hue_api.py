#!/usr/bin/env python3
"""Hue bridge API helper — reads credentials from file, never exposes
the username in process arguments."""

import contextlib
import json
import os
import re
import socket
import ssl
import stat
import sys
import tempfile
import urllib.request

CREDS_FILE = os.path.join(
    os.path.expanduser("~"), ".local/state/omarchy/settings/hue.json")
CACERT = os.path.join(
    os.path.expanduser("~"),
    ".config/omarchy/plugins/lunardi0x01.hue-room-remote/hue_bridge_cacert.pem")

MAX_CREDS_BYTES = 4096
MAX_ORDER_BYTES = 65536
MAX_RESPONSE_BYTES = 1024 * 1024

_opener = None
_no_redirect_opener = None


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuses to follow redirects on credential-bearing requests -- a
    compromised bridge could otherwise 302 an authenticated request (with
    the username embedded in the URL path) to an attacker-controlled
    host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _get_opener():
    global _opener
    if _opener is None:
        ctx = ssl.create_default_context(cafile=CACERT)
        ctx.check_hostname = True
        _opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx), _NoRedirectHandler())
    return _opener


def _get_no_redirect_opener():
    global _no_redirect_opener
    if _no_redirect_opener is None:
        _no_redirect_opener = urllib.request.build_opener(_NoRedirectHandler())
    return _no_redirect_opener


class _BridgeResolver:
    def __init__(self, hostname, ip):
        self._hostname = hostname
        self._ip = ip
        self._orig = None

    def __enter__(self):
        self._orig = socket.getaddrinfo
        def _patched(host, port, *args, **kwargs):
            if host == self._hostname:
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, '',
                         (self._ip, port))]
            return self._orig(host, port, *args, **kwargs)
        socket.getaddrinfo = _patched
        return self

    def __exit__(self, *args):
        socket.getaddrinfo = self._orig


def _read_local_json_capped(path, max_bytes):
    # O_NONBLOCK makes open() return immediately even if `path` is a FIFO
    # with no writer -- without it, a named pipe planted at a predictable
    # settings path would hang this call (and everything waiting on it)
    # indefinitely. It has no effect on a regular file. The S_ISREG check
    # below then rejects a FIFO/socket/device before any read is attempted.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd) as f:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise ValueError("not a regular file")
        if st.st_uid != os.getuid():
            raise ValueError("not owned by current user")
        data = f.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("file too large")
    return json.loads(data)


def _load_creds():
    return _read_local_json_capped(CREDS_FILE, MAX_CREDS_BYTES)


def _bridge_url(creds, path):
    bridge_id = creds.get("bridgeId", "").strip().lower()
    bridge_ip = creds["bridgeIp"]
    username = creds["username"]
    if bridge_id:
        return ("https://%s/api/%s%s" % (bridge_id, username, path),
                bridge_id, bridge_ip)
    return ("https://%s/api/%s%s" % (bridge_ip, username, path),
            None, bridge_ip)


def _read_json_capped(resp, max_bytes=MAX_RESPONSE_BYTES):
    data = resp.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("response too large")
    return json.loads(data)


@contextlib.contextmanager
def _open_bridge_request(req, hostname, ip):
    if hostname:
        with _BridgeResolver(hostname, ip):
            with _get_opener().open(req, timeout=5) as r:
                yield r
    else:
        with _get_no_redirect_opener().open(req, timeout=5) as r:
            yield r


def _request(path, creds):
    url, hostname, ip = _bridge_url(creds, path)
    req = urllib.request.Request(url)
    with _open_bridge_request(req, hostname, ip) as r:
        return _read_json_capped(r)


def _put(creds, path, body):
    url, hostname, ip = _bridge_url(creds, path)
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="PUT")
    with _open_bridge_request(req, hostname, ip) as r:
        r.read(MAX_RESPONSE_BYTES)


_ID_RE = re.compile(r'[a-zA-Z0-9_-]{1,40}')


def main():
    if len(sys.argv) < 2:
        return
    _dispatch(sys.argv[1])


def _get_status():
    try:
        creds = _load_creds()
    except Exception:
        print(json.dumps({"paired": False}))
        return
    bridge_id = str(creds.get("bridgeId", "")).strip().lower()
    if not _ID_RE.fullmatch(bridge_id):
        bridge_id = ""
    print(json.dumps({"paired": True, "bridgeId": bridge_id}))


def _dispatch(op):
    if op == "write-favorite" and len(sys.argv) >= 4:
        _write_favorite(sys.argv[3])
        return
    if op == "write-order" and len(sys.argv) >= 4:
        _write_order(sys.argv[3])
        return
    if op == "get-status":
        _get_status()
        return

    creds = _load_creds()

    if op == "get-lights":
        print(json.dumps(_request("/lights", creds)))
    elif op == "get-groups":
        print(json.dumps(_request("/groups", creds)))
    elif op == "get-scenes":
        print(json.dumps(_request("/scenes", creds)))
    elif op == "put-light" and len(sys.argv) >= 4:
        light_id = sys.argv[2]
        if not re.fullmatch(r'[0-9]+', light_id):
            return
        state = json.loads(sys.argv[3])
        _put(creds, "/lights/%s/state" % light_id, state)
    elif op == "put-group" and len(sys.argv) >= 4:
        group_id = sys.argv[2]
        if not re.fullmatch(r'[0-9]+', group_id):
            return
        action = json.loads(sys.argv[3])
        _put(creds, "/groups/%s/action" % group_id, action)
    elif op == "verify":
        lights = _request("/lights", creds)
        print(len(lights))


def _atomic_write(path, payload):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    dir_fd = os.open(directory, os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if os.fstat(dir_fd).st_uid != os.getuid():
            raise OSError("settings directory not owned by current user")
        # chmod via the already-validated descriptor (fchmod), not the path --
        # os.chmod(path, ...) follows symlinks by default, which would have
        # silently relocked whatever an attacker-planted symlink pointed at
        # before O_NOFOLLOW ever got a chance to reject it.
        os.chmod(dir_fd, 0o700)
        fd, tmp_path = tempfile.mkstemp(dir=directory)
        tmp_name = os.path.basename(tmp_path)
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, os.path.basename(path),
                       src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        except BaseException:
            try:
                os.unlink(tmp_name, dir_fd=dir_fd)
            except OSError:
                pass
            raise
    finally:
        os.close(dir_fd)


def _write_favorite(body_json):
    body = json.loads(body_json)
    if not isinstance(body, dict):
        return
    room_id = str(body.get("roomId", ""))
    if room_id and not _ID_RE.fullmatch(room_id):
        return
    config_path = os.path.join(
        os.path.expanduser("~"), ".config/omarchy/settings/hue-favorite.json")
    _atomic_write(config_path, json.dumps({"favoriteRoomId": room_id}) + "\n")


def _valid_id_list(value):
    return isinstance(value, list) and all(
        _ID_RE.fullmatch(str(v)) for v in value)


def _valid_id_map_of_id_lists(value):
    if not isinstance(value, dict):
        return False
    for k, v in value.items():
        if not _ID_RE.fullmatch(str(k)):
            return False
        if not _valid_id_list(v):
            return False
    return True


def _valid_id_map_of_ids(value):
    if not isinstance(value, dict):
        return False
    for k, v in value.items():
        if not _ID_RE.fullmatch(str(k)):
            return False
        if not _ID_RE.fullmatch(str(v)):
            return False
    return True


def _write_order(body_json):
    body = json.loads(body_json)
    if not isinstance(body, dict):
        return
    if "roomOrder" in body and not _valid_id_list(body["roomOrder"]):
        return
    if "sceneOrder" in body and not _valid_id_map_of_id_lists(body["sceneOrder"]):
        return
    if "hiddenRooms" in body and not _valid_id_list(body["hiddenRooms"]):
        return
    if "lastScene" in body and not _valid_id_map_of_ids(body["lastScene"]):
        return

    config_path = os.path.join(
        os.path.expanduser("~"), ".config/omarchy/settings/hue-order.json")
    try:
        cfg = _read_local_json_capped(config_path, MAX_ORDER_BYTES)
        if not isinstance(cfg, dict):
            cfg = {}
    except Exception:
        cfg = {}

    for key in ("roomOrder", "sceneOrder", "lastScene", "hiddenRooms"):
        if key in body:
            cfg[key] = body[key]

    _atomic_write(config_path, json.dumps(cfg, indent=2) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
