# D:/finalProjectB/back/apcms_ai/ai_vision/tests/recognition/test_runtime_environment.py

import copy
import unittest
from importlib.metadata import PackageNotFoundError

from ai_vision.recognition.runtime_environment import collect_snapshot, compare_snapshots, validate_snapshot, PACKAGES


class RuntimeEnvironmentTests(unittest.TestCase):
    def snapshot(self):
        return collect_snapshot(lambda name: "test-version")

    def test_collects_only_selected_metadata_and_marks_missing_packages(self):
        called = []
        def reader(name):
            called.append(name)
            if name == "paddlepaddle-gpu":
                raise PackageNotFoundError(name)
            return "1.0"
        result = collect_snapshot(reader)
        self.assertIs(validate_snapshot(result), result)
        self.assertEqual(tuple(called), PACKAGES)
        self.assertIsNone(result["packages"]["paddlepaddle-gpu"])
        self.assertNotIn("path", result)
        self.assertNotIn("environment_variables", result)

    def test_comparison_reports_package_and_python_differences_without_mutating(self):
        expected = self.snapshot()
        actual = copy.deepcopy(expected)
        actual["python"] = "different-version"
        actual["packages"]["numpy"] = None
        result = compare_snapshots(expected, actual)
        self.assertFalse(result["matches"])
        self.assertEqual([row["field"] for row in result["differences"]], ["python", "packages.numpy"])
        self.assertEqual(expected["packages"]["numpy"], "test-version")
        self.assertTrue(compare_snapshots(expected, copy.deepcopy(expected))["matches"])

    def test_invalid_or_incomplete_snapshot_rejected(self):
        for changes in ({"record_type": "OTHER"}, {"virtualenv": 1}, {"packages": {}}, {"python": ""}):
            with self.assertRaises(ValueError):
                validate_snapshot({**self.snapshot(), **changes})
