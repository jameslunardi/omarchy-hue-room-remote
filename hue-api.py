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
    ".config/omarchy/plugins/omarchy-philips-hue/hue_bridge_cacert.pem")

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
    op = sys.argv[1]
    creds = _load_creds()

    if op == "get-lights":
        print(json.dumps(_request("/lights", creds)))
    elif op == "get-groups":
        print(json.dumps(_request("/groups", creds)))
    elif op == "put-light" and len(sys.argv) >= 4:
        light_id = sys.argv[2]
        state = json.loads(sys.argv[3])
        _put(creds, "/lights/%s/state" % light_id, state)
    elif op == "put-group" and len(sys.argv) >= 4:
        group_id = sys.argv[2]
        action = json.loads(sys.argv[3])
        _put(creds, "/groups/%s/action" % group_id, action)
    elif op == "verify":
        lights = _request("/lights", creds)
        print(len(lights))


if __name__ == "__main__":
    main()
