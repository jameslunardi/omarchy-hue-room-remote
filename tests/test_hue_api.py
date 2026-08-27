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


class WriteThemeConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home_patch = mock.patch("os.path.expanduser", side_effect=self._expanduser)
        self.home_patch.start()
        self.addCleanup(self.home_patch.stop)

    def _expanduser(self, path):
        return path.replace("~", self.tmp.name)

    def config_path(self):
        return os.path.join(self.tmp.name, ".config/omarchy/settings/hue-theme.json")

    def test_creates_missing_settings_directory(self):
        self.assertFalse(os.path.isdir(os.path.dirname(self.config_path())))
        hue_api._write_theme_config(json.dumps({"5": True}))
        with open(self.config_path()) as f:
            saved = json.load(f)
        self.assertEqual(saved["themeSync"], {"5": True})

    def test_merges_with_existing_config(self):
        os.makedirs(os.path.dirname(self.config_path()))
        with open(self.config_path(), "w") as f:
            json.dump({"unrelated": "keep-me"}, f)
        hue_api._write_theme_config(json.dumps({"5": False}))
        with open(self.config_path()) as f:
            saved = json.load(f)
        self.assertEqual(saved["unrelated"], "keep-me")
        self.assertEqual(saved["themeSync"], {"5": False})

    def test_rejects_non_bool_values_silently(self):
        hue_api._write_theme_config(json.dumps({"5": "not-a-bool"}))
        self.assertFalse(os.path.exists(self.config_path()))

    def test_rejects_invalid_room_id_silently(self):
        hue_api._write_theme_config(json.dumps({"has space": True}))
        self.assertFalse(os.path.exists(self.config_path()))

    def test_rejects_non_dict_payload_silently(self):
        hue_api._write_theme_config(json.dumps(["not", "a", "dict"]))
        self.assertFalse(os.path.exists(self.config_path()))


class DispatchValidationTests(unittest.TestCase):
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


class MainLoggingTests(unittest.TestCase):
    def test_main_logs_and_reraises_on_failure(self):
        with mock.patch.object(hue_api, "_dispatch", side_effect=RuntimeError("boom")), \
             mock.patch.object(hue_api, "_log") as log:
            sys.argv = ["hue-api.py", "get-lights"]
            with self.assertRaises(RuntimeError):
                hue_api.main()
            fail_calls = [c for c in log.call_args_list if "FAIL" in c.args[0]]
            self.assertEqual(len(fail_calls), 1)
            self.assertIn("RuntimeError", fail_calls[0].args[0])

    def test_main_logs_ok_on_success(self):
        with mock.patch.object(hue_api, "_dispatch"), \
             mock.patch.object(hue_api, "_log") as log:
            sys.argv = ["hue-api.py", "get-lights"]
            hue_api.main()
            ok_calls = [c for c in log.call_args_list if c.args[0].startswith("ok")]
            self.assertEqual(len(ok_calls), 1)


if __name__ == "__main__":
    unittest.main()
