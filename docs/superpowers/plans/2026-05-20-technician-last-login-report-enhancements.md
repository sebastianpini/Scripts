# Technician Last Login Report Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--user-type {technician,enduser,all}` and `--csv PATH` flags to the technician last login report script.

**Architecture:** All changes are in a single script file. A new test file follows the existing `importlib.util` pattern used by other tests in this repo. The `--user-type` flag parameterizes user fetching and activity status lookup. The `--csv` flag adds an optional file export alongside the existing terminal output.

**Tech Stack:** Python 3 stdlib only (`csv`, `unittest`, `importlib.util`). Run tests with `python3 -m unittest discover tests/ -v`.

---

### Task 1: Create test file with `write_csv` failing test

**Files:**
- Create: `tests/test_technician_last_login_report.py`

- [ ] **Step 1: Create the test file**

```python
#!/usr/bin/env python3

import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    ROOT_DIR
    / "scripts/python/ninjaone-technician-inactive-login-report/technician_last_login_report.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "technician_last_login_report",
        SCRIPT_PATH,
    )
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
                "Last Login": "2026-01-15 10:00:00 UTC",
                "_sort_ts": 1736935200.0,
            }
        ]
        with tempfile.NamedTemporaryFile(mode="r", suffix=".csv", delete=False) as f:
            path = f.name

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
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
python3 -m unittest tests.test_technician_last_login_report -v
```

Expected: `AttributeError: module ... has no attribute 'write_csv'` and `error: unrecognized arguments: --user-type`

---

### Task 2: Implement `write_csv` and `--csv PATH` flag

**Files:**
- Modify: `scripts/python/ninjaone-technician-inactive-login-report/technician_last_login_report.py`

- [ ] **Step 1: Add `import csv` to the imports block**

Find:
```python
import argparse
import sys
```

Replace with:
```python
import argparse
import csv
import sys
```

- [ ] **Step 2: Add `write_csv` function directly above `def main():`**

```python
def write_csv(rows, path):
    columns = ["Name", "Email", "Enabled", "Admin", "Roles", "Last Login"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
```

- [ ] **Step 3: Add `--csv` argument to `parse_args()`**

Find:
```python
    parser.add_argument(
        "--enabled-only",
        action="store_true",
        help="Only include enabled technicians.",
    )
    return parser.parse_args()
```

Replace with:
```python
    parser.add_argument(
        "--enabled-only",
        action="store_true",
        help="Only include enabled users.",
    )
    parser.add_argument(
        "--csv",
        metavar="PATH",
        help="Write results to a CSV file at PATH.",
    )
    return parser.parse_args()
```

- [ ] **Step 4: Wire `--csv` into `main()`**

Find:
```python
    rows = build_rows(technicians, last_login_by_user_id)
    scope = "enabled technicians" if args.enabled_only else "all technicians"
    print(f"Technician last login report for {scope}: {len(rows)}")
    print_table(rows)
    print(f"Total: {len(rows)}")
    return 0
```

Replace with:
```python
    rows = build_rows(technicians, last_login_by_user_id)
    scope = "enabled technicians" if args.enabled_only else "all technicians"
    print(f"Technician last login report for {scope}: {len(rows)}")
    print_table(rows)
    print(f"Total: {len(rows)}")
    if args.csv:
        write_csv(rows, args.csv)
        print(f"Wrote {len(rows)} rows to {args.csv}")
    return 0
```

- [ ] **Step 5: Run the `WriteCsvTests` to confirm they pass**

```bash
python3 -m unittest tests.test_technician_last_login_report.WriteCsvTests -v
```

Expected: `test_write_csv_creates_file_with_correct_columns_and_rows ... ok`

- [ ] **Step 6: Commit**

```bash
git add scripts/python/ninjaone-technician-inactive-login-report/technician_last_login_report.py tests/test_technician_last_login_report.py
git commit -m "feat: add --csv export to technician last login report"
```

---

### Task 3: Add `--user-type` flag — all changes in one atomic step

This task renames `load_technicians` → `load_users`, adds `login_status` to `fetch_last_login_by_user_id`, adds `--user-type` to `parse_args`, and rewires `main()` — all together so the code is never left in a broken state between commits.

**Files:**
- Modify: `scripts/python/ninjaone-technician-inactive-login-report/technician_last_login_report.py`

- [ ] **Step 1: Replace `load_technicians` with `load_users`**

Find:
```python
def load_technicians(access_token, enabled_only):
    users = get_api_resource("/v2/users?userType=TECHNICIAN&includeRoles=true", access_token)
    technicians = {}

    for user in users:
        if enabled_only and not user.get("enabled", False):
            continue

        user_id = user.get("id")
        if user_id is None:
            continue

        technicians[user_id] = user

    return technicians
```

Replace with:
```python
def load_users(access_token, user_type, enabled_only):
    if user_type == "all":
        raw = (
            get_api_resource("/v2/users?userType=TECHNICIAN&includeRoles=true", access_token)
            + get_api_resource("/v2/users?userType=END_USER&includeRoles=true", access_token)
        )
    elif user_type == "enduser":
        raw = get_api_resource("/v2/users?userType=END_USER&includeRoles=true", access_token)
    else:
        raw = get_api_resource("/v2/users?userType=TECHNICIAN&includeRoles=true", access_token)

    users = {}
    for user in raw:
        if enabled_only and not user.get("enabled", False):
            continue
        user_id = user.get("id")
        if user_id is None:
            continue
        users[user_id] = user

    return users
```

- [ ] **Step 2: Add `login_status` parameter to `fetch_last_login_by_user_id`**

Find:
```python
def fetch_last_login_by_user_id(access_token, technician_ids):
    last_login_by_user_id = {}
    remaining_user_ids = set(technician_ids)
    older_than = None

    while remaining_user_ids:
        params = {
            "class": "USER",
            "status": TECHNICIAN_LOGIN_STATUS,
            "pageSize": PAGE_SIZE,
        }
```

Replace with:
```python
def fetch_last_login_by_user_id(access_token, user_ids, login_status):
    last_login_by_user_id = {}
    remaining_user_ids = set(user_ids)
    older_than = None

    while remaining_user_ids:
        params = {
            "class": "USER",
            "status": login_status,
            "pageSize": PAGE_SIZE,
        }
```

- [ ] **Step 3: Add `--user-type` argument to `parse_args()`**

Find:
```python
    parser.add_argument(
        "--enabled-only",
        action="store_true",
        help="Only include enabled users.",
    )
```

Replace with:
```python
    parser.add_argument(
        "--user-type",
        choices=["technician", "enduser", "all"],
        default="technician",
        help="User type to include (default: technician).",
    )
    parser.add_argument(
        "--enabled-only",
        action="store_true",
        help="Only include enabled users.",
    )
```

- [ ] **Step 4: Rewrite the try/except and output block in `main()`**

Find:
```python
    try:
        access_token = get_access_token()
        technicians = load_technicians(access_token, args.enabled_only)
        last_login_by_user_id = fetch_last_login_by_user_id(
            access_token, set(technicians)
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to query NinjaOne API: {exc}", file=sys.stderr)
        return 1

    rows = build_rows(technicians, last_login_by_user_id)
    scope = "enabled technicians" if args.enabled_only else "all technicians"
    print(f"Technician last login report for {scope}: {len(rows)}")
    print_table(rows)
    print(f"Total: {len(rows)}")
    if args.csv:
        write_csv(rows, args.csv)
        print(f"Wrote {len(rows)} rows to {args.csv}")
    return 0
```

Replace with:
```python
    if args.user_type in ("enduser", "all"):
        print(
            "Warning: end user activity scan may be slow with large user counts.",
            file=sys.stderr,
        )

    try:
        access_token = get_access_token()
        users = load_users(access_token, args.user_type, args.enabled_only)
        if args.user_type == "all":
            technician_ids = {uid for uid, u in users.items() if u.get("userType") == "TECHNICIAN"}
            enduser_ids = {uid for uid, u in users.items() if u.get("userType") == "END_USER"}
            last_login_by_user_id = {
                **fetch_last_login_by_user_id(access_token, technician_ids, TECHNICIAN_LOGIN_STATUS),
                **fetch_last_login_by_user_id(access_token, enduser_ids, END_USER_LOGIN_STATUS),
            }
        elif args.user_type == "enduser":
            last_login_by_user_id = fetch_last_login_by_user_id(
                access_token, set(users), END_USER_LOGIN_STATUS
            )
        else:
            last_login_by_user_id = fetch_last_login_by_user_id(
                access_token, set(users), TECHNICIAN_LOGIN_STATUS
            )
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to query NinjaOne API: {exc}", file=sys.stderr)
        return 1

    _scope_labels = {
        "technician": "technicians",
        "enduser": "end users",
        "all": "technicians and end users",
    }
    scope = ("enabled " if args.enabled_only else "") + _scope_labels[args.user_type]
    rows = build_rows(users, last_login_by_user_id)
    print(f"Login report for {scope}: {len(rows)}")
    print_table(rows)
    print(f"Total: {len(rows)}")
    if args.csv:
        write_csv(rows, args.csv)
        print(f"Wrote {len(rows)} rows to {args.csv}")
    return 0
```

- [ ] **Step 5: Run all tests**

```bash
python3 -m unittest tests.test_technician_last_login_report -v
```

Expected: all tests pass including `ParseArgsTests`.

- [ ] **Step 6: Commit**

```bash
git add scripts/python/ninjaone-technician-inactive-login-report/technician_last_login_report.py
git commit -m "feat: add --user-type flag to include technicians, end users, or both"
```

---

### Task 4: Clean up docstring and run full test suite

**Files:**
- Modify: `scripts/python/ninjaone-technician-inactive-login-report/technician_last_login_report.py`

- [ ] **Step 1: Update version and remove resolved TODOs from the module docstring**

Find:
```python
"""
[Version 1.0.0] Report NinjaOne technicians sorted by most recent platform
login activity, including name, email, enabled status, admin status, roles,
and last login timestamp.

Environment variables:
- NINJA_ONE_CLIENT_ID (required)
- NINJA_ONE_CLIENT_SECRET (required)
- NINJA_ONE_INSTANCE (optional, defaults to "eu.ninjarmm.com")
- NINJA_ONE_SCOPE (optional, defaults to "monitoring management")

TODO:
- csv export functionality
- get technicians and endusers with the option of only pulling one, the other or both as there can be thousands of endusers

"""
```

Replace with:
```python
"""
[Version 2.0.0] Report NinjaOne users sorted by most recent platform
login activity, including name, email, enabled status, admin status, roles,
and last login timestamp. Supports technicians, end users, or both via
--user-type, and optional CSV export via --csv.

Environment variables:
- NINJA_ONE_CLIENT_ID (required)
- NINJA_ONE_CLIENT_SECRET (required)
- NINJA_ONE_INSTANCE (optional, defaults to "eu.ninjarmm.com")
- NINJA_ONE_SCOPE (optional, defaults to "monitoring management")

"""
```

- [ ] **Step 2: Run the full test suite**

```bash
python3 -m unittest discover tests/ -v
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add scripts/python/ninjaone-technician-inactive-login-report/technician_last_login_report.py
git commit -m "docs: bump version to 2.0.0 and remove resolved TODOs"
```
