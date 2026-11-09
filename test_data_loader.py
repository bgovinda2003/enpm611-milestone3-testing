
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import data_loader


class TestDataLoader(unittest.TestCase):

    def setUp(self):
        # Preserve the application's global cache.
        self.original_issues = data_loader._ISSUES
        data_loader._ISSUES = None

    def tearDown(self):
        # Restore the cache so tests do not affect one another.
        data_loader._ISSUES = self.original_issues

    def make_loader(self, path):
        # Supply a controlled dataset path without changing config.json.
        with patch.object(
            data_loader.config,
            "get_parameter",
            return_value=path
        ) as mock_parameter:
            loader = data_loader.DataLoader()

        mock_parameter.assert_called_once_with(
            "ENPM611_PROJECT_DATA_PATH"
        )
        return loader

    def test_constructor_reads_configured_path(self):
        loader = self.make_loader("sample.json")
        self.assertEqual(loader.data_path, "sample.json")

    def test_constructor_with_missing_configuration(self):
        loader = self.make_loader(None)
        self.assertIsNone(loader.data_path)

    def test_load_valid_json(self):
        records = [
            {"number": 1, "title": "First issue"},
            {"number": 2, "title": "Second issue"}
        ]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "issues.json"
            path.write_text(json.dumps(records), encoding="utf-8")

            loader = self.make_loader(str(path))

            # Mock Issue so this test focuses on the loader,
            # not the model's field requirements.
            with patch.object(
                data_loader, "Issue", side_effect=lambda x: x
            ) as mock_issue:
                result = loader._load()

            self.assertEqual(result, records)
            self.assertEqual(mock_issue.call_count, 2)

    def test_load_empty_json_list(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.json"
            path.write_text("[]", encoding="utf-8")

            loader = self.make_loader(str(path))
            result = loader._load()

            self.assertEqual(result, [])

    def test_load_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "does_not_exist.json"
            loader = self.make_loader(str(missing))

            with self.assertRaises(SystemExit) as context:
                loader._load()

            self.assertIn(
                "Data file not found",
                str(context.exception)
            )
            self.assertIn(
                "ENPM611_PROJECT_DATA_PATH",
                str(context.exception)
            )

    def test_load_without_configured_path(self):
        loader = self.make_loader(None)

        with self.assertRaises(SystemExit) as context:
            loader._load()

        self.assertIn(
            "Data file not found: None",
            str(context.exception)
        )

    def test_load_invalid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("{invalid json", encoding="utf-8")

            loader = self.make_loader(str(path))

            with self.assertRaises(json.JSONDecodeError):
                loader._load()

    def test_get_issues_loads_once(self):
        loader = self.make_loader("sample.json")
        expected = ["issue1", "issue2"]

        with patch.object(
            loader, "_load", return_value=expected
        ) as mock_load:
            with patch("builtins.print") as mock_print:
                first = loader.get_issues()
                second = loader.get_issues()

        self.assertIs(first, second)
        self.assertEqual(first, expected)
        mock_load.assert_called_once()
        mock_print.assert_called_once_with(
            "Loaded 2 issues from sample.json."
        )

    def test_get_issues_uses_existing_cache(self):
        cached = ["previously_loaded"]
        data_loader._ISSUES = cached
        loader = self.make_loader("sample.json")

        with patch.object(loader, "_load") as mock_load:
            result = loader.get_issues()

        self.assertIs(result, cached)
        mock_load.assert_not_called()

    def test_get_issues_with_empty_dataset(self):
        loader = self.make_loader("empty.json")

        with patch.object(loader, "_load", return_value=[]):
            with patch("builtins.print") as mock_print:
                result = loader.get_issues()

        self.assertEqual(result, [])
        mock_print.assert_called_once_with(
            "Loaded 0 issues from empty.json."
        )

    def test_load_converts_each_record_to_issue(self):
        records = [{"number": 10}, {"number": 20}]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "issues.json"
            path.write_text(json.dumps(records), encoding="utf-8")

            loader = self.make_loader(str(path))
            objects = [object(), object()]

            with patch.object(
                data_loader, "Issue", side_effect=objects
            ) as mock_issue:
                result = loader._load()

            self.assertEqual(result, objects)
            self.assertEqual(
                mock_issue.call_args_list[0].args[0],
                records[0]
            )
            self.assertEqual(
                mock_issue.call_args_list[1].args[0],
                records[1]
            )


if __name__ == "__main__":
    unittest.main()
