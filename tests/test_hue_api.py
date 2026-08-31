import importlib.util
import json
import os
import sys
import tempfile
import unittest
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
        self.home_patch = mock.patch("os.path.expanduser", side_effect=self._expanduser)
        self.home_patch.start()
        self.addCleanup(self.home_patch.stop)

    def _expanduser(self, path):
        return path.replace("~", self.tmp.name)

    def favorite_path(self):
        return os.path.join(self.tmp.name, ".config/omarchy/settings/hue-favorite.json")

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
        self.home_patch = mock.patch("os.path.expanduser", side_effect=self._expanduser)
        self.home_patch.start()
        self.addCleanup(self.home_patch.stop)

    def _expanduser(self, path):
        return path.replace("~", self.tmp.name)

    def order_path(self):
        return os.path.join(self.tmp.name, ".config/omarchy/settings/hue-order.json")

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
