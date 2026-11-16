
import json
import os
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import config


class TestConfig(unittest.TestCase):

    def setUp(self):
        self.original_config = config._config
        config._config = {}
        self.env_patch = patch.dict(os.environ, {}, clear=False)
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()
        config._config = self.original_config

    # Test JSON and string conversion

    def test_convert_integer(self):
        self.assertEqual(config.convert_to_typed_value("42"), 42)

    def test_convert_boolean(self):
        self.assertIs(config.convert_to_typed_value("true"), True)

    def test_convert_list(self):
        self.assertEqual(
            config.convert_to_typed_value("[1, 2, 3]"),
            [1, 2, 3]
        )

    def test_convert_dictionary(self):
        self.assertEqual(
            config.convert_to_typed_value('{"a": 1}'),
            {"a": 1}
        )

    def test_convert_plain_string(self):
        self.assertEqual(
            config.convert_to_typed_value("hello"),
            "hello"
        )

    def test_convert_none(self):
        self.assertIsNone(config.convert_to_typed_value(None))

    def test_convert_non_string(self):
        self.assertEqual(config.convert_to_typed_value(12), 12)

    # Test reading configuration parameters

    def test_get_existing_parameter(self):
        config._config = {"sample_key": "stored_value"}
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("sample_key", None)
            self.assertEqual(
                config.get_parameter("sample_key"),
                "stored_value"
            )

    def test_get_missing_parameter(self):
        self.assertIsNone(
            config.get_parameter("ENPM611_MISSING_TEST_KEY")
        )

    def test_get_default_parameter(self):
        self.assertEqual(
            config.get_parameter(
                "ENPM611_MISSING_TEST_KEY",
                "fallback"
            ),
            "fallback"
        )

    def test_get_falsy_numeric_default(self):
        # A default of 0 is a valid value and should be returned when
        # the key is absent. The implementation currently treats any
        # falsy default as "no default" and returns None instead.
        self.assertEqual(
            config.get_parameter("ENPM611_MISSING_TEST_KEY", 0),
            0
        )

    def test_environment_overrides_config(self):
        config._config = {"ENPM611_TEST_KEY": "file_value"}
        with patch.dict(
            os.environ,
            {"ENPM611_TEST_KEY": "environment_value"}
        ):
            self.assertEqual(
                config.get_parameter("ENPM611_TEST_KEY"),
                "environment_value"
            )

    def test_environment_json_prefix(self):
        with patch.dict(
            os.environ,
            {"ENPM611_TEST_KEY": "json:[1, 2]"}
        ):
            self.assertEqual(
                config.get_parameter("ENPM611_TEST_KEY"),
                [1, 2]
            )

    # Test setting parameters

    def test_set_string_parameter(self):
        with patch.dict(os.environ, {}, clear=False):
            config.set_parameter("ENPM611_SET_TEST", "hello")
            self.assertEqual(
                config.get_parameter("ENPM611_SET_TEST"),
                "hello"
            )

    def test_set_non_string_parameter(self):
        with patch.dict(os.environ, {}, clear=False):
            config.set_parameter("ENPM611_SET_TEST", {"count": 3})
            self.assertEqual(
                config.get_parameter("ENPM611_SET_TEST"),
                {"count": 3}
            )

    # Test command-line argument handling

    def test_overwrite_from_args(self):
        args = Namespace(
            ENPM611_ARG_TEST=25,
            ENPM611_UNUSED_TEST=None
        )
        with patch.dict(os.environ, {}, clear=False):
            config.overwrite_from_args(args)
            self.assertEqual(
                config.get_parameter("ENPM611_ARG_TEST"),
                25
            )
            self.assertNotIn(
                "ENPM611_UNUSED_TEST",
                os.environ
            )

    def test_overwrite_from_invalid_args(self):
        # The implementation catches errors from vars(args).
        config.overwrite_from_args(None)

    # Test initialization and configuration file lookup

    def test_init_empty_config(self):
        config._config = None
        with patch.object(config, "_get_default_path", return_value=None):
            config._init_config()
        self.assertEqual(config._config, {})

    def test_init_from_json_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(
                json.dumps({"sample": 123}),
                encoding="utf-8"
            )

            config._config = None
            with patch.object(
                config, "_get_default_path", return_value=str(path)
            ):
                config._init_config()

            self.assertEqual(config._config["sample"], 123)

    def test_init_when_already_initialized(self):
        config._config = {"existing": 1}
        with patch.object(config, "_get_default_path") as lookup:
            config._init_config()
            lookup.assert_not_called()
        self.assertEqual(config._config, {"existing": 1})

    def test_find_config_in_current_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text("{}", encoding="utf-8")

            with patch.object(os, "getcwd", return_value=directory):
                result = config._get_default_path()

            # Match production code, which uses os.path.abspath rather
            # than Path.resolve(). On macOS those differ by a /private prefix.
            self.assertEqual(result, os.path.abspath(str(path)))

    def test_find_config_in_parent_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            child = parent / "child"
            child.mkdir()
            path = parent / "config.json"
            path.write_text("{}", encoding="utf-8")

            with patch.object(os, "getcwd", return_value=str(child)):
                result = config._get_default_path()

            self.assertEqual(result, os.path.abspath(str(path)))

    def test_find_config_when_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(os, "getcwd", return_value=directory):
                result = config._get_default_path()

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
