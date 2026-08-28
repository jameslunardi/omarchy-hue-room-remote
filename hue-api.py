#!/usr/bin/env python3
"""Hue bridge API helper — reads credentials from file, never exposes
the username in process arguments."""

import json
import os
import re
import socket
import ssl
import sys
import urllib.request

CREDS_FILE = os.path.join(
    os.path.expanduser("~"), ".local/state/omarchy/settings/hue.json")
CACERT = os.path.join(
    os.path.expanduser("~"),
    ".config/omarchy/plugins/omarchy-hue-room-remote/hue_bridge_cacert.pem")

_opener = None


def _get_opener():
    global _opener
    if _opener is None:
        ctx = ssl.create_default_context(cafile=CACERT)
        ctx.check_hostname = True
        _opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx))
    return _opener


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


def _load_creds():
    with open(CREDS_FILE) as f:
        return json.load(f)


def _bridge_url(creds, path):
    bridge_id = creds.get("bridgeId", "").strip().lower()
    bridge_ip = creds["bridgeIp"]
    username = creds["username"]
    if bridge_id:
        return ("https://%s/api/%s%s" % (bridge_id, username, path),
                bridge_id, bridge_ip)
    return ("https://%s/api/%s%s" % (bridge_ip, username, path),
            None, bridge_ip)


def _request(req_or_url, creds):
    if isinstance(req_or_url, str):
        url, hostname, ip = _bridge_url(creds, req_or_url)
        req = urllib.request.Request(url)
    else:
        url = req_or_url.full_url
        hostname, ip = None, None
        for c in creds, None:
            if c:
                _, hostname, ip = _bridge_url(c, "")
                break
    if hostname and ip:
        opener = _get_opener()
        with _BridgeResolver(hostname, ip):
            with opener.open(req, timeout=5) as r:
                return json.load(r)
    else:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.load(r)


def _put(creds, path, body):
    url, hostname, ip = _bridge_url(creds, path)
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="PUT")
    if hostname and ip:
        opener = _get_opener()
        with _BridgeResolver(hostname, ip):
            with opener.open(req, timeout=5) as r:
                r.read()
    else:
        with urllib.request.urlopen(req, timeout=5) as r:
            r.read()


def main():
    if len(sys.argv) < 2:
        return
    _dispatch(sys.argv[1])


def _dispatch(op):
    if op == "write-favorite" and len(sys.argv) >= 4:
        _write_favorite(sys.argv[3])
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


def _write_favorite(body_json):
    body = json.loads(body_json)
    if not isinstance(body, dict):
        return
    room_id = str(body.get("roomId", ""))
    if room_id and not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', room_id):
        return
    config_path = os.path.join(
        os.path.expanduser("~"), ".config/omarchy/settings/hue-favorite.json")
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    payload = json.dumps({"favoriteRoomId": room_id}) + "\n"
    try:
        fd = os.open(config_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        try:
            fd = os.open(config_path, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW)
            os.fchmod(fd, 0o600)
        except (OSError, ValueError):
            try:
                os.remove(config_path)
            except OSError:
                pass
            fd = os.open(config_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(payload)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
