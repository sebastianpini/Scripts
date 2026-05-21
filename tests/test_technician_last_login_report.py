#!/usr/bin/env python3

import csv
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT_DIR / "python/user/last_login.py"


def load_module():
    spec = importlib.util.spec_from_file_location("last_login", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WriteCsvTests(unittest.TestCase):
    def test_write_csv_creates_file_with_correct_columns_and_rows(self):
        module = load_module()
        rows = [
            {
                "Name": "Alice Smith",
                "Email": "alice@example.com",
                "Enabled": "Yes",
                "Admin": "No",
                "Roles": "Helpdesk",
                "Last Login": "2026-01-15T10:00:00+00:00",
                "_sort_ts": 1736935200.0,
            }
        ]
        with tempfile.NamedTemporaryFile(mode="r", suffix=".csv", delete=False) as f:
            path = f.name
        self.addCleanup(os.remove, path)

        module.write_csv(rows, path)

        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            result = list(reader)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["Name"], "Alice Smith")
        self.assertEqual(result[0]["Email"], "alice@example.com")
        self.assertNotIn("_sort_ts", result[0])


class ParseArgsTests(unittest.TestCase):
    def _parse(self, argv):
        original = sys.argv
        sys.argv = ["script"] + argv
        try:
            return load_module().parse_args()
        finally:
            sys.argv = original

    def test_user_type_defaults_to_technician(self):
        args = self._parse([])
        self.assertEqual(args.user_type, "technician")

    def test_user_type_accepts_enduser(self):
        args = self._parse(["--user-type", "enduser"])
        self.assertEqual(args.user_type, "enduser")

    def test_user_type_accepts_all(self):
        args = self._parse(["--user-type", "all"])
        self.assertEqual(args.user_type, "all")


if __name__ == "__main__":
    unittest.main()
