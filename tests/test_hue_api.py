import http.server
import importlib.util
import json
import os
import ssl
import stat
import sys
import tempfile
import threading
import unittest
import urllib.error
from unittest import mock

MODULE_PATH = os.path.join(os.path.dirname(__file__), "..", "hue_api.py")


def load_hue_api():
    spec = importlib.util.spec_from_file_location("hue_api_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hue_api = load_hue_api()


class WriteFavoriteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config_patch = mock.patch.object(hue_api, "CONFIG_HOME", self.tmp.name)
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)

    def favorite_path(self):
        return os.path.join(self.tmp.name, "omarchy/settings/hue-favorite.json")

    def test_creates_missing_settings_directory(self):
        self.assertFalse(os.path.isdir(os.path.dirname(self.favorite_path())))
        hue_api._write_favorite(json.dumps({"roomId": "5"}))
        with open(self.favorite_path()) as f:
            saved = json.load(f)
        self.assertEqual(saved, {"favoriteRoomId": "5"})

    def test_overwrites_existing_favorite(self):
        os.makedirs(os.path.dirname(self.favorite_path()))
        with open(self.favorite_path(), "w") as f:
            json.dump({"favoriteRoomId": "1"}, f)
        hue_api._write_favorite(json.dumps({"roomId": "2"}))
        with open(self.favorite_path()) as f:
            saved = json.load(f)
        self.assertEqual(saved, {"favoriteRoomId": "2"})

    def test_empty_room_id_clears_favorite(self):
        hue_api._write_favorite(json.dumps({"roomId": ""}))
        with open(self.favorite_path()) as f:
            saved = json.load(f)
        self.assertEqual(saved, {"favoriteRoomId": ""})

    def test_rejects_invalid_room_id_silently(self):
        hue_api._write_favorite(json.dumps({"roomId": "has space"}))
        self.assertFalse(os.path.exists(self.favorite_path()))

    def test_rejects_non_dict_payload_silently(self):
        hue_api._write_favorite(json.dumps(["not", "a", "dict"]))
        self.assertFalse(os.path.exists(self.favorite_path()))


class WriteOrderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config_patch = mock.patch.object(hue_api, "CONFIG_HOME", self.tmp.name)
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)

    def order_path(self):
        return os.path.join(self.tmp.name, "omarchy/settings/hue-order.json")

    def test_creates_missing_settings_directory(self):
        self.assertFalse(os.path.isdir(os.path.dirname(self.order_path())))
        hue_api._write_order(json.dumps({"roomOrder": ["2", "5", "1"]}))
        with open(self.order_path()) as f:
            saved = json.load(f)
        self.assertEqual(saved, {"roomOrder": ["2", "5", "1"]})

    def test_writes_scene_order(self):
        hue_api._write_order(json.dumps({"sceneOrder": {"2": ["s3", "s1"]}}))
        with open(self.order_path()) as f:
            saved = json.load(f)
        self.assertEqual(saved, {"sceneOrder": {"2": ["s3", "s1"]}})

    def test_merges_room_order_without_clobbering_scene_order(self):
        os.makedirs(os.path.dirname(self.order_path()))
        with open(self.order_path(), "w") as f:
            json.dump({"sceneOrder": {"2": ["s1"]}}, f)
        hue_api._write_order(json.dumps({"roomOrder": ["2", "1"]}))
        with open(self.order_path()) as f:
            saved = json.load(f)
        self.assertEqual(saved, {"sceneOrder": {"2": ["s1"]}, "roomOrder": ["2", "1"]})

    def test_merges_scene_order_without_clobbering_room_order(self):
        os.makedirs(os.path.dirname(self.order_path()))
        with open(self.order_path(), "w") as f:
            json.dump({"roomOrder": ["2", "1"]}, f)
        hue_api._write_order(json.dumps({"sceneOrder": {"2": ["s1"]}}))
        with open(self.order_path()) as f:
            saved = json.load(f)
        self.assertEqual(saved, {"roomOrder": ["2", "1"], "sceneOrder": {"2": ["s1"]}})

    def test_rejects_non_list_room_order_silently(self):
        hue_api._write_order(json.dumps({"roomOrder": "not-a-list"}))
        self.assertFalse(os.path.exists(self.order_path()))

    def test_rejects_invalid_room_id_in_room_order_silently(self):
        hue_api._write_order(json.dumps({"roomOrder": ["has space"]}))
        self.assertFalse(os.path.exists(self.order_path()))

    def test_rejects_non_dict_scene_order_silently(self):
        hue_api._write_order(json.dumps({"sceneOrder": ["not", "a", "dict"]}))
        self.assertFalse(os.path.exists(self.order_path()))

    def test_rejects_invalid_scene_id_in_scene_order_silently(self):
        hue_api._write_order(json.dumps({"sceneOrder": {"2": ["has space"]}}))
        self.assertFalse(os.path.exists(self.order_path()))

    def test_rejects_invalid_room_id_key_in_scene_order_silently(self):
        hue_api._write_order(json.dumps({"sceneOrder": {"has space": ["s1"]}}))
        self.assertFalse(os.path.exists(self.order_path()))

    def test_rejects_non_dict_payload_silently(self):
        hue_api._write_order(json.dumps(["not", "a", "dict"]))
        self.assertFalse(os.path.exists(self.order_path()))

    def test_writes_last_scene(self):
        hue_api._write_order(json.dumps({"lastScene": {"2": "s1"}}))
        with open(self.order_path()) as f:
            saved = json.load(f)
        self.assertEqual(saved, {"lastScene": {"2": "s1"}})

    def test_merges_last_scene_without_clobbering_room_order(self):
        os.makedirs(os.path.dirname(self.order_path()))
        with open(self.order_path(), "w") as f:
            json.dump({"roomOrder": ["2", "1"]}, f)
        hue_api._write_order(json.dumps({"lastScene": {"2": "s1"}}))
        with open(self.order_path()) as f:
            saved = json.load(f)
        self.assertEqual(saved, {"roomOrder": ["2", "1"], "lastScene": {"2": "s1"}})

    def test_rejects_non_dict_last_scene_silently(self):
        hue_api._write_order(json.dumps({"lastScene": ["not", "a", "dict"]}))
        self.assertFalse(os.path.exists(self.order_path()))

    def test_rejects_invalid_room_id_key_in_last_scene_silently(self):
        hue_api._write_order(json.dumps({"lastScene": {"has space": "s1"}}))
        self.assertFalse(os.path.exists(self.order_path()))

    def test_rejects_invalid_scene_id_value_in_last_scene_silently(self):
        hue_api._write_order(json.dumps({"lastScene": {"2": "has space"}}))
        self.assertFalse(os.path.exists(self.order_path()))

    def test_writes_hidden_rooms(self):
        hue_api._write_order(json.dumps({"hiddenRooms": ["3"]}))
        with open(self.order_path()) as f:
            saved = json.load(f)
        self.assertEqual(saved, {"hiddenRooms": ["3"]})

    def test_merges_hidden_rooms_without_clobbering_room_order(self):
        os.makedirs(os.path.dirname(self.order_path()))
        with open(self.order_path(), "w") as f:
            json.dump({"roomOrder": ["2", "1"]}, f)
        hue_api._write_order(json.dumps({"hiddenRooms": ["1"]}))
        with open(self.order_path()) as f:
            saved = json.load(f)
        self.assertEqual(saved, {"roomOrder": ["2", "1"], "hiddenRooms": ["1"]})

    def test_rejects_non_list_hidden_rooms_silently(self):
        hue_api._write_order(json.dumps({"hiddenRooms": "not-a-list"}))
        self.assertFalse(os.path.exists(self.order_path()))

    def test_rejects_invalid_room_id_in_hidden_rooms_silently(self):
        hue_api._write_order(json.dumps({"hiddenRooms": ["has space"]}))
        self.assertFalse(os.path.exists(self.order_path()))


class XdgHomeTests(unittest.TestCase):
    def test_state_home_uses_xdg_var_when_set(self):
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": "/custom/state"}):
            self.assertEqual(hue_api._xdg_state_home(), "/custom/state")

    def test_state_home_falls_back_when_unset(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ["HOME"] = "/home/testuser"
            self.assertEqual(hue_api._xdg_state_home(), "/home/testuser/.local/state")

    def test_state_home_falls_back_when_empty(self):
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": "", "HOME": "/home/testuser"}):
            self.assertEqual(hue_api._xdg_state_home(), "/home/testuser/.local/state")

    def test_config_home_uses_xdg_var_when_set(self):
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/config"}):
            self.assertEqual(hue_api._xdg_config_home(), "/custom/config")

    def test_config_home_falls_back_when_unset(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ["HOME"] = "/home/testuser"
            self.assertEqual(hue_api._xdg_config_home(), "/home/testuser/.config")


class ResolveCacertTests(unittest.TestCase):
    def test_prefers_the_copy_next_to_the_script(self):
        # hue_api.py's own directory really does have hue_bridge_cacert.pem
        # checked in next to it -- resolving to that, not the install path,
        # is exactly the point of this fix.
        script_dir = os.path.dirname(os.path.abspath(hue_api.__file__))
        expected = os.path.join(script_dir, "hue_bridge_cacert.pem")
        self.assertEqual(hue_api._resolve_cacert("/unused/config/home"), expected)

    def test_falls_back_to_install_path_when_no_local_copy(self):
        with mock.patch("os.path.isfile", return_value=False):
            result = hue_api._resolve_cacert("/custom/config")
        self.assertEqual(
            result,
            "/custom/config/omarchy/plugins/lunardi0x01.hue-room-remote/hue_bridge_cacert.pem")


class LoadCredsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.creds_path = os.path.join(self.tmp.name, "hue.json")
        self.creds_patch = mock.patch.object(hue_api, "CREDS_FILE", self.creds_path)
        self.creds_patch.start()
        self.addCleanup(self.creds_patch.stop)

    def test_loads_well_formed_creds(self):
        with open(self.creds_path, "w") as f:
            json.dump({"bridgeIp": "1.2.3.4", "bridgeId": "aabb", "username": "u"}, f)
        self.assertEqual(
            hue_api._load_creds(),
            {"bridgeIp": "1.2.3.4", "bridgeId": "aabb", "username": "u"})

    def test_rejects_symlinked_creds_file(self):
        real = os.path.join(self.tmp.name, "real.json")
        with open(real, "w") as f:
            f.write("{}")
        os.symlink(real, self.creds_path)
        with self.assertRaises(OSError):
            hue_api._load_creds()

    def test_rejects_oversized_creds_file(self):
        with open(self.creds_path, "w") as f:
            f.write("x" * (hue_api.MAX_CREDS_BYTES + 1))
        with self.assertRaises(ValueError):
            hue_api._load_creds()


class ReadLocalJsonCappedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "data.json")

    def test_parses_well_formed_file(self):
        with open(self.path, "w") as f:
            json.dump({"a": 1}, f)
        self.assertEqual(hue_api._read_local_json_capped(self.path, 4096), {"a": 1})

    def test_rejects_oversized_file(self):
        with open(self.path, "w") as f:
            f.write("x" * 4097)
        with self.assertRaises(ValueError):
            hue_api._read_local_json_capped(self.path, 4096)

    def test_rejects_symlinked_file(self):
        real = os.path.join(self.tmp.name, "real.json")
        with open(real, "w") as f:
            f.write("{}")
        os.symlink(real, self.path)
        with self.assertRaises(OSError):
            hue_api._read_local_json_capped(self.path, 4096)

    def test_rejects_file_not_owned_by_current_user(self):
        with open(self.path, "w") as f:
            f.write("{}")
        with mock.patch("os.getuid", return_value=os.getuid() + 1):
            with self.assertRaises(ValueError):
                hue_api._read_local_json_capped(self.path, 4096)

    def test_rejects_fifo_without_hanging(self):
        os.mkfifo(self.path)
        with self.assertRaises(ValueError):
            hue_api._read_local_json_capped(self.path, 4096)


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def read(self, n):
        return self._data[:n]


class ReadJsonCappedTests(unittest.TestCase):
    def test_parses_json_within_cap(self):
        payload = json.dumps({"a": 1}).encode()
        result = hue_api._read_json_capped(_FakeResponse(payload), max_bytes=1024)
        self.assertEqual(result, {"a": 1})

    def test_rejects_oversized_response(self):
        payload = json.dumps({"a": "x" * 2000}).encode()
        with self.assertRaises(ValueError):
            hue_api._read_json_capped(_FakeResponse(payload), max_bytes=100)


class NoRedirectHandlerTests(unittest.TestCase):
    def test_refuses_redirect(self):
        handler = hue_api._NoRedirectHandler()
        result = handler.redirect_request(
            mock.Mock(), None, 302, "Found", {}, "https://evil.example/steal")
        self.assertIsNone(result)


# Throwaway 20-year self-signed cert/key, generated once for this test file
# (`openssl req -x509 -newkey rsa:2048 -days 7300 -nodes
# -subj "/O=Test Bridge/CN=aabbccddeeff0011"`) and embedded as a literal so
# the test suite never needs `openssl` (or any dependency beyond the
# stdlib) at run time.
_TEST_CERT_PEM = """-----BEGIN CERTIFICATE-----
MIIDQzCCAiugAwIBAgIUN07ZbgLeJhFInjiBbBIEWO9yz0swDQYJKoZIhvcNAQEL
BQAwMTEUMBIGA1UECgwLVGVzdCBCcmlkZ2UxGTAXBgNVBAMMEGFhYmJjY2RkZWVm
ZjAwMTEwHhcNMjYwODMxMTQzNjIwWhcNNDYwODI2MTQzNjIwWjAxMRQwEgYDVQQK
DAtUZXN0IEJyaWRnZTEZMBcGA1UEAwwQYWFiYmNjZGRlZWZmMDAxMTCCASIwDQYJ
KoZIhvcNAQEBBQADggEPADCCAQoCggEBAL9t1DuLviVDp5UHlvrJ+omK8DE55uY+
fA6igRSi6tuMRIrYWp8pTWQMcDJq1P/YulcNCvEckHauhqpp+8IyW0IJrLD/MQf3
LBi6kHK8UbEDUW9KXsmdz+owiW9LLebyDbgSCqOjRvSHKKLVO2/YJ8G1gE8XQsKP
f1wG3sBG/vjmCM+dZZBAJxEIqu3rvDQ/ga67zrMifaqviezqbHk1aJi7QUZg389b
ww0K0czZGYkqu32wYP1LfpfpAApOPJtdzCwadZ51KufOzU4QxHnU2HfgC1I53YLV
pe5ZlvcYh75d1Idyw7qYI9ZfuHfZ2gCDN2MJKMJKHRNGmTrJ6KomB/cCAwEAAaNT
MFEwHQYDVR0OBBYEFPmlgj/6TyiTBrPcoe6IwFcqyQA7MB8GA1UdIwQYMBaAFPml
gj/6TyiTBrPcoe6IwFcqyQA7MA8GA1UdEwEB/wQFMAMBAf8wDQYJKoZIhvcNAQEL
BQADggEBAKZDn77ZMkuHdyIUlxfCsW5vk6qA0yIkVF8cJmD8Vo2q29Z5aPNLETEC
c3ZDxPt6QrIqeNeXYeLfc44SWtbH9oswsdhugujTl/KUWiVn8uSXcxx8Kla9Cthl
JZbh8CK72KHMBXH/tgfufRWFKNSYUCfQ02XAYNPqyoSKz8CRTh1+5fLkRJshA+6x
YFTOzeYLG+RTSGHMf4qaoUKvCNjcXRhl8HFDO+41BpNbnW7vxKMup1K2Obys8iWI
R9ofAMa/QGdkyy4EHy5scZMqqir0CvQdenGU/bwH/Iy+cJHTCntSWR8qsdKip2wR
zc5e/AgJjQz4w16oZZxog/jg1P6pLrI=
-----END CERTIFICATE-----
"""

_TEST_KEY_PEM = """-----BEGIN PRIVATE KEY-----
MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQC/bdQ7i74lQ6eV
B5b6yfqJivAxOebmPnwOooEUourbjESK2FqfKU1kDHAyatT/2LpXDQrxHJB2roaq
afvCMltCCayw/zEH9ywYupByvFGxA1FvSl7Jnc/qMIlvSy3m8g24Egqjo0b0hyii
1Ttv2CfBtYBPF0LCj39cBt7ARv745gjPnWWQQCcRCKrt67w0P4Guu86zIn2qr4ns
6mx5NWiYu0FGYN/PW8MNCtHM2RmJKrt9sGD9S36X6QAKTjybXcwsGnWedSrnzs1O
EMR51Nh34AtSOd2C1aXuWZb3GIe+XdSHcsO6mCPWX7h32doAgzdjCSjCSh0TRpk6
yeiqJgf3AgMBAAECggEANXLad7fIYwo1T9CbMLHVcLLo5q22kSHwLHvmE5d7gMp0
1tmaz+bN03n/l6wphbgDK0waeoDRuzl2oz1NTIcX4OPnolHWZFV4q/znWQnIu2Zk
RfEbbyrPgyGDNh5lFh8Ogo8TBmaP6LWWPITSACP30ce2KB8kBkPfuRe3+TK5fU/t
M0TDwVwuUyHjimZCRUWpVkOSnttv449blMln6PPyx7Pwz/ewVLEQU8nYzaGko6EC
iV3IqwB/V0U+rAHvxQIfu3QhIZqoJ00WBrbzvrfI0mXCUkA4is/NtODX8RcgGQL4
XDU9QPlamYdjEw3eoHZIbzCZHTkLX45b2Mf16N4xsQKBgQDvkquCFZJ34NDHS8yf
HVs37QaK8q25Yx/ThEohEUw7aGjBXqRc+YPTk5RUULvVSsQ2xCfrLiCp6JFiI1On
tH0GahUvWBvalOiX1R/1QHxwEeSKP2WW7ZUJdjY+Vu0jr3kLrGMu8zOXJ7uV12Xk
OL8PmVcwNX1Sp7tjlN9xTF/rxwKBgQDMjhFROUZrgZxEPuYSuOR2InrLTdHIw3D5
W1tKw6rsfSdInDQC50iluiMfBe7F9thsq5gkiwaQOFVQ89krTCeaAmfQPG7Kyaw/
9DHdUuJSpBrYoZW1FZRu74JHgnJDPgE6fum0BBva91INnww4V1XJvS//XaE1t3cn
6/e0kaQiUQKBgQCjt4WBBiDrzzSdnU0eRz94/n+EIMdbc0PilfrakimYR4ee7YBB
ETpnMekhnXJfFhL0oiPtcb5cnlQLzrxyVMNDyOblTb7rJuu0Jq8KOKFRLMkTOLPB
6mX461GyVFEGG/oKYin9gbF10G8+vM4ioizfChktFsCn5XwHV0tC78B1LQKBgQCk
2zKVtYVNi223isG+AQkPNIamZxdVqD3amYgf30ZXxh3s5Qb9+AySlEtN62geX+zY
2AqMGQe3H8+SqJQz0vJvqtSj/LCF+rc568JsTypb1CpWwRN4l+XC6oCixTz1eHlg
/Xu4Oz9/36dflvkwRyK6riCKvJj6Q9xibkh6XI5doQKBgQCYkbuWeoArR35uk4aA
+WFtUrxHXwnxvT6lIKX/G2KYz8tV6jjHrc5lxtEZLN1qxLgjsOmhl+QD6JjZPuj8
ZcGQ9r02+Tf1rB3wljI728/WlqUdeRAyFdW1izggGl+DISDHi4cT+v6son3A0IzP
k22xJk14mIg0x6n4EvZgmGXKdA==
-----END PRIVATE KEY-----
"""

# A second, unrelated self-signed cert -- used to prove the opener still
# fails closed against a cert that doesn't chain to our trusted CACERT,
# not just that it happens to accept the one it's pointed at.
_OTHER_CERT_PEM = """-----BEGIN CERTIFICATE-----
MIIDRTCCAi2gAwIBAgIULcuBSo3y4pwhRlgfOIIERB+k1/cwDQYJKoZIhvcNAQEL
BQAwMjEVMBMGA1UECgwMT3RoZXIgQnJpZGdlMRkwFwYDVQQDDBAwMDExMjIzMzQ0
NTU2Njc3MB4XDTI2MDgzMTE0MzczMVoXDTQ2MDgyNjE0MzczMVowMjEVMBMGA1UE
CgwMT3RoZXIgQnJpZGdlMRkwFwYDVQQDDBAwMDExMjIzMzQ0NTU2Njc3MIIBIjAN
BgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAofaHmermjW58LisWW7rbVwpCEEKW
uG2O9W9Ms8jqJFjg2+eOYeUykRtrxWGhkhabdLckBBy3Sjtsldre38MzRpp872z2
u9Z/ciR6/KmBE26Gbpos4H58P3x3pnHAYk2sWdTATv+KdN0wn8E1jLvvQVmXFc0t
orjHIoXNmgQGgl3wc7zHhxzWNhcULfnWJvnn17BaggrttKWaUoUOckZpLkjUG7yc
C0z3/dQbAP/AhM4qU1UYCoLDls2c025BVR1cN4uGqm1tljctMDCYMnuVaPmzhhA9
tRIt/02qUw83VeDtL6+DH/6FmqfZ8ewnmQW5U0ORg2yMowCE8aIwmlTbZQIDAQAB
o1MwUTAdBgNVHQ4EFgQUPZ7uRkaRE1o2FPamn1nBjG5hsmMwHwYDVR0jBBgwFoAU
PZ7uRkaRE1o2FPamn1nBjG5hsmMwDwYDVR0TAQH/BAUwAwEB/zANBgkqhkiG9w0B
AQsFAAOCAQEAHjMy13zIkmb2AymfUWwEG4EYogm3Q/ELAq0vxn3Y1ohF0JlsJu6L
AoffA4KOF+MnBE2Gojwc2rf9sDCjfg5cYcsSZx+jsEElubu7svDAcWUxSliTIZen
Mg0lf+Ln35Gq87pibPWamnTooDAOFi6fPRDTBpquDHuupgZgXbNRge9OxFlLBRJv
VInNbur3W9aJwVTW4/3GYosgQNajmXo/evwRXTfCET5cNPVOHv/h0A34BhcvvjHB
/FU3AmXdnbB1j3rmqTcWREfKTDijc40DCIAKmSxHQH/noJt84Rtp6hoBSzG1W2dq
jbapVFV6mWatTARlIhAlk+U9cHyPM6gPag==
-----END CERTIFICATE-----
"""


class _QuietHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *args):
        pass


class NoRedirectOpenerTlsTests(unittest.TestCase):
    """SEC-01: the insecure-mode opener must still validate against our
    bundled CA (just not the hostname, since we connect by IP) -- not fall
    through to the system trust store with no context configured at all."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        cert_path = os.path.join(self.tmp.name, "cert.pem")
        key_path = os.path.join(self.tmp.name, "key.pem")
        with open(cert_path, "w") as f:
            f.write(_TEST_CERT_PEM)
        with open(key_path, "w") as f:
            f.write(_TEST_KEY_PEM)

        self.httpd = http.server.HTTPServer(("127.0.0.1", 0), _QuietHandler)
        server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_ctx.load_cert_chain(cert_path, key_path)
        self.httpd.socket = server_ctx.wrap_socket(self.httpd.socket, server_side=True)
        self.port = self.httpd.socket.getsockname()[1]
        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        thread.start()
        # addCleanup runs LIFO -- register server_close first so shutdown
        # (stop serving) still runs before it (release the socket).
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

        self.cacert_patch = mock.patch.object(hue_api, "CACERT", cert_path)
        self.cacert_patch.start()
        self.addCleanup(self.cacert_patch.stop)
        hue_api._no_redirect_opener = None
        self.addCleanup(setattr, hue_api, "_no_redirect_opener", None)

    def test_connects_when_cert_chains_to_bundled_cacert(self):
        opener = hue_api._get_no_redirect_opener()
        with opener.open("https://127.0.0.1:%d/api/config" % self.port, timeout=3) as r:
            self.assertEqual(r.read(), b"{}")

    def test_rejects_a_cert_that_does_not_chain_to_bundled_cacert(self):
        # Point CACERT at a cert genuinely unrelated to the one the server
        # actually presents -- must still fail closed, not just happen to
        # accept whatever it's pointed at.
        other_cacert = os.path.join(self.tmp.name, "other-cacert.pem")
        with open(other_cacert, "w") as f:
            f.write(_OTHER_CERT_PEM)
        hue_api.CACERT = other_cacert
        hue_api._no_redirect_opener = None
        opener = hue_api._get_no_redirect_opener()
        with self.assertRaises(urllib.error.URLError):
            with opener.open("https://127.0.0.1:%d/api/config" % self.port, timeout=3):
                pass


class AtomicWriteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_symlinked_target_is_replaced_not_written_through(self):
        directory = os.path.join(self.tmp.name, "settings")
        os.makedirs(directory)
        target = os.path.join(directory, "hue-favorite.json")
        decoy = os.path.join(self.tmp.name, "decoy.txt")
        with open(decoy, "w") as f:
            f.write("do not touch")
        os.symlink(decoy, target)

        hue_api._atomic_write(target, '{"favoriteRoomId": "1"}\n')

        with open(decoy) as f:
            self.assertEqual(f.read(), "do not touch")
        self.assertFalse(os.path.islink(target))
        with open(target) as f:
            self.assertEqual(f.read(), '{"favoriteRoomId": "1"}\n')

    def test_no_leftover_temp_files_on_success(self):
        directory = os.path.join(self.tmp.name, "settings")
        target = os.path.join(directory, "hue-order.json")
        hue_api._atomic_write(target, "{}\n")
        self.assertEqual(os.listdir(directory), ["hue-order.json"])

    def test_locks_settings_directory_to_owner_only(self):
        directory = os.path.join(self.tmp.name, "settings")
        os.makedirs(directory, mode=0o777)
        os.chmod(directory, 0o777)
        target = os.path.join(directory, "hue-favorite.json")
        hue_api._atomic_write(target, "{}\n")
        self.assertEqual(stat.S_IMODE(os.stat(directory).st_mode), 0o700)

    def test_does_not_chmod_through_a_symlinked_settings_directory(self):
        real_dir = os.path.join(self.tmp.name, "attacker_owned")
        os.makedirs(real_dir, mode=0o755)
        settings_dir = os.path.join(self.tmp.name, "settings")
        os.symlink(real_dir, settings_dir)
        target = os.path.join(settings_dir, "hue-favorite.json")

        with self.assertRaises(OSError):
            hue_api._atomic_write(target, "{}\n")

        self.assertEqual(stat.S_IMODE(os.stat(real_dir).st_mode), 0o755)


class GetStatusTests(unittest.TestCase):
    def test_prints_paired_with_bridge_id_when_creds_exist(self):
        with mock.patch.object(
            hue_api, "_load_creds",
            return_value={"bridgeIp": "1.2.3.4", "bridgeId": "AABBCC", "username": "u"}
        ), mock.patch("builtins.print") as mock_print:
            hue_api._get_status()
            mock_print.assert_called_once_with(json.dumps({"paired": True, "bridgeId": "aabbcc"}))

    def test_prints_unpaired_when_creds_missing(self):
        with mock.patch.object(hue_api, "_load_creds", side_effect=OSError("no file")), \
             mock.patch("builtins.print") as mock_print:
            hue_api._get_status()
            mock_print.assert_called_once_with(json.dumps({"paired": False}))

    def test_never_includes_username_or_bridge_ip_in_output(self):
        with mock.patch.object(
            hue_api, "_load_creds",
            return_value={"bridgeIp": "1.2.3.4", "bridgeId": "", "username": "supersecretuser"}
        ), mock.patch("builtins.print") as mock_print:
            hue_api._get_status()
            output = mock_print.call_args[0][0]
            self.assertNotIn("supersecretuser", output)
            self.assertNotIn("1.2.3.4", output)

    def test_drops_malformed_bridge_id(self):
        with mock.patch.object(
            hue_api, "_load_creds",
            return_value={"bridgeIp": "1.2.3.4", "bridgeId": "has space", "username": "u"}
        ), mock.patch("builtins.print") as mock_print:
            hue_api._get_status()
            mock_print.assert_called_once_with(json.dumps({"paired": True, "bridgeId": ""}))

    def test_dispatch_get_status_routes_here(self):
        with mock.patch.object(hue_api, "_get_status") as get_status:
            sys.argv = ["hue_api.py", "get-status"]
            hue_api._dispatch("get-status")
            get_status.assert_called_once_with()


class DispatchValidationTests(unittest.TestCase):
    def test_get_scenes_requests_scenes_path(self):
        with mock.patch.object(hue_api, "_load_creds", return_value={}), \
             mock.patch.object(hue_api, "_request", return_value={}) as request:
            sys.argv = ["hue_api.py", "get-scenes"]
            hue_api._dispatch("get-scenes")
            request.assert_called_once_with("/scenes", {})

    def test_write_favorite_dispatches_with_body_argument(self):
        with mock.patch.object(hue_api, "_write_favorite") as write_favorite:
            sys.argv = ["hue_api.py", "write-favorite", "favorite", '{"roomId": "3"}']
            hue_api._dispatch("write-favorite")
            write_favorite.assert_called_once_with('{"roomId": "3"}')

    def test_write_order_dispatches_with_body_argument(self):
        with mock.patch.object(hue_api, "_write_order") as write_order:
            sys.argv = ["hue_api.py", "write-order", "order", '{"roomOrder": ["1"]}']
            hue_api._dispatch("write-order")
            write_order.assert_called_once_with('{"roomOrder": ["1"]}')

    def test_put_light_rejects_non_numeric_id(self):
        with mock.patch.object(hue_api, "_load_creds", return_value={}), \
             mock.patch.object(hue_api, "_put") as put:
            sys.argv = ["hue_api.py", "put-light", "5; rm -rf /", '{"on": true}']
            hue_api._dispatch("put-light")
            put.assert_not_called()

    def test_put_light_accepts_numeric_id(self):
        with mock.patch.object(hue_api, "_load_creds", return_value={}), \
             mock.patch.object(hue_api, "_put") as put:
            sys.argv = ["hue_api.py", "put-light", "12", '{"on": true}']
            hue_api._dispatch("put-light")
            put.assert_called_once_with({}, "/lights/12/state", {"on": True})

    def test_put_group_rejects_non_numeric_id(self):
        with mock.patch.object(hue_api, "_load_creds", return_value={}), \
             mock.patch.object(hue_api, "_put") as put:
            sys.argv = ["hue_api.py", "put-group", "abc", '{"on": true}']
            hue_api._dispatch("put-group")
            put.assert_not_called()


class MainDispatchTests(unittest.TestCase):
    def test_main_dispatches_with_op_argument(self):
        with mock.patch.object(hue_api, "_dispatch") as dispatch:
            sys.argv = ["hue_api.py", "get-lights"]
            hue_api.main()
            dispatch.assert_called_once_with("get-lights")

    def test_main_noop_without_op_argument(self):
        with mock.patch.object(hue_api, "_dispatch") as dispatch:
            sys.argv = ["hue_api.py"]
            hue_api.main()
            dispatch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
