import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

MODULE_PATH = os.path.join(os.path.dirname(__file__), "..", "hue-api.py")


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


class DispatchValidationTests(unittest.TestCase):
    def test_get_scenes_requests_scenes_path(self):
        with mock.patch.object(hue_api, "_load_creds", return_value={}), \
             mock.patch.object(hue_api, "_request", return_value={}) as request:
            sys.argv = ["hue-api.py", "get-scenes"]
            hue_api._dispatch("get-scenes")
            request.assert_called_once_with("/scenes", {})

    def test_write_favorite_dispatches_with_body_argument(self):
        with mock.patch.object(hue_api, "_write_favorite") as write_favorite:
            sys.argv = ["hue-api.py", "write-favorite", "favorite", '{"roomId": "3"}']
            hue_api._dispatch("write-favorite")
            write_favorite.assert_called_once_with('{"roomId": "3"}')

    def test_write_order_dispatches_with_body_argument(self):
        with mock.patch.object(hue_api, "_write_order") as write_order:
            sys.argv = ["hue-api.py", "write-order", "order", '{"roomOrder": ["1"]}']
            hue_api._dispatch("write-order")
            write_order.assert_called_once_with('{"roomOrder": ["1"]}')

    def test_put_light_rejects_non_numeric_id(self):
        with mock.patch.object(hue_api, "_load_creds", return_value={}), \
             mock.patch.object(hue_api, "_put") as put:
            sys.argv = ["hue-api.py", "put-light", "5; rm -rf /", '{"on": true}']
            hue_api._dispatch("put-light")
            put.assert_not_called()

    def test_put_light_accepts_numeric_id(self):
        with mock.patch.object(hue_api, "_load_creds", return_value={}), \
             mock.patch.object(hue_api, "_put") as put:
            sys.argv = ["hue-api.py", "put-light", "12", '{"on": true}']
            hue_api._dispatch("put-light")
            put.assert_called_once_with({}, "/lights/12/state", {"on": True})

    def test_put_group_rejects_non_numeric_id(self):
        with mock.patch.object(hue_api, "_load_creds", return_value={}), \
             mock.patch.object(hue_api, "_put") as put:
            sys.argv = ["hue-api.py", "put-group", "abc", '{"on": true}']
            hue_api._dispatch("put-group")
            put.assert_not_called()


class MainDispatchTests(unittest.TestCase):
    def test_main_dispatches_with_op_argument(self):
        with mock.patch.object(hue_api, "_dispatch") as dispatch:
            sys.argv = ["hue-api.py", "get-lights"]
            hue_api.main()
            dispatch.assert_called_once_with("get-lights")

    def test_main_noop_without_op_argument(self):
        with mock.patch.object(hue_api, "_dispatch") as dispatch:
            sys.argv = ["hue-api.py"]
            hue_api.main()
            dispatch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
