# Organization Time Usage Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a separate NinjaOne `org-time-usage` report that totals ticket time in decimal hours and NinjaOne remote-session duration in decimal minutes per organization for `this` or `last` calendar month.

**Architecture:** Add one focused Python report module with CLI parsing, period calculation, API loading, normalization, aggregation, and table rendering. Keep API-specific shapes inside loader and normalizer functions so the aggregation logic only sees organization ids, ticket ids, device ids, timestamps, and normalized durations. Wire the report into the existing Bash launcher and repository docs without modifying the existing `org-summary` report.

**Tech Stack:** Python 3 standard library, `unittest`, existing `scripts/python/_shared/ninja_api.py`, Bash launcher.

---

## Reference Notes

- NinjaOne public API calls use the environment-specific NinjaOne instance URL followed by the API endpoint, matching the current shared helper pattern. Source: https://www.ninjaone.com/docs/application-programming-interface-api/public-api-operations/
- NinjaOne documents that Activity Feed history is available through `/v2/activities` and `/v2/device/{id}/activities`, and that remote session start/end events are activity entries. Source: https://www.ninjaone.com/docs/new-to-ninjaone/alerting-and-notifications/device-system-activity-notification-feed/
- NinjaOne summary reporting exposes Ninja Remote connection duration by connected device, so the implementation should normalize remote-session duration and map device ids back to organizations. Source: https://www.ninjaone.com/docs/reporting/types-of-summary-reports/

## File Structure

- Create: `scripts/python/ninjaone-organization-time-usage-report/organization_time_usage_report.py`
  - Owns CLI parsing, period calculation, response normalization, API loading, aggregation, table rendering, and `main()`.
- Create: `scripts/python/ninjaone-organization-time-usage-report/ORGANIZATION_TIME_USAGE.md`
  - Customer-facing usage and behavior documentation.
- Create: `tests/test_organization_time_usage_report.py`
  - Unit tests for period handling, duration normalization, aggregation, API loader pagination, and table output.
- Modify: `ninja`
  - Add `org-time-usage` to usage text, script list, and script resolution.
- Modify: `tests/test_ninja_cli.sh`
  - Assert default and explicit environment routing for `org-time-usage`.
- Modify: `README.md`
  - Add the new report to quick start, script list, and Python report section.
- Modify: `scripts/README.md`
  - Add the new report to the Python script index.

Do not stage or commit existing unrelated changes in:

- `scripts/python/_shared/ninja_api.py`
- `scripts/python/ninjaone-organization-device-summary-report/ORGANIZATION_DEVICE_SUMMARY.md`
- `scripts/python/ninjaone-organization-device-summary-report/organization_device_summary_report.py`
- `tests/test_organization_device_summary_report.py`

## Task 1: Create Report Skeleton And Period Logic

**Files:**
- Create: `scripts/python/ninjaone-organization-time-usage-report/organization_time_usage_report.py`
- Create: `tests/test_organization_time_usage_report.py`

- [ ] **Step 1: Write failing period and CLI tests**

Add this test file:

```python
#!/usr/bin/env python3

import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    ROOT_DIR
    / "scripts/python/ninjaone-organization-time-usage-report/organization_time_usage_report.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "organization_time_usage_report",
        SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OrganizationTimeUsageReportTests(unittest.TestCase):
    def test_calculate_last_period_uses_previous_complete_local_month(self):
        module = load_module()
        cest = timezone(timedelta(hours=2), "CEST")
        now = datetime(2026, 5, 18, 14, 30, tzinfo=cest)

        period = module.calculate_period("last", now=now)

        self.assertEqual(period.start, datetime(2026, 4, 1, 0, 0, tzinfo=cest))
        self.assertEqual(period.end, datetime(2026, 5, 1, 0, 0, tzinfo=cest))
        self.assertEqual(period.display_start, "2026-04-01")
        self.assertEqual(period.display_end, "2026-04-30")

    def test_calculate_this_period_uses_current_month_to_now(self):
        module = load_module()
        cest = timezone(timedelta(hours=2), "CEST")
        now = datetime(2026, 5, 18, 14, 30, tzinfo=cest)

        period = module.calculate_period("this", now=now)

        self.assertEqual(period.start, datetime(2026, 5, 1, 0, 0, tzinfo=cest))
        self.assertEqual(period.end, now)
        self.assertEqual(period.display_start, "2026-05-01")
        self.assertEqual(period.display_end, "2026-05-18")

    def test_parse_args_defaults_to_last_period(self):
        module = load_module()

        args = module.parse_args([])

        self.assertEqual(args.period, "last")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests/test_organization_time_usage_report.py -v
```

Expected: FAIL because `organization_time_usage_report.py` does not exist yet.

- [ ] **Step 3: Create minimal report skeleton and period implementation**

Create `scripts/python/ninjaone-organization-time-usage-report/organization_time_usage_report.py`:

```python
#!/usr/bin/env python3
"""
[Version 1.0.0] Report cumulative NinjaOne ticket time and remote-session
duration by organization for a selected local calendar period.

Environment variables:
- NINJA_ONE_CLIENT_ID (required)
- NINJA_ONE_CLIENT_SECRET (required)
- NINJA_ONE_INSTANCE (optional, defaults to "eu.ninjarmm.com")
- NINJA_ONE_SCOPE (optional, defaults to "monitoring management")
"""

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared"))
from ninja_api import get_access_token, get_api_resource, post_api_resource  # noqa: E402


PAGE_SIZE = 1000


@dataclass(frozen=True)
class Period:
    name: str
    start: datetime
    end: datetime
    display_start: str
    display_end: str


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Report cumulative NinjaOne ticket time and remote-session "
            "duration by organization."
        )
    )
    parser.add_argument(
        "--period",
        choices=("this", "last"),
        default="last",
        help="Calendar period to report: this month to now or the previous complete month.",
    )
    return parser.parse_args(argv)


def first_day_of_month(value):
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def calculate_period(period_name, now=None):
    local_now = now if now is not None else datetime.now().astimezone()
    current_month_start = first_day_of_month(local_now)

    if period_name == "this":
        start = current_month_start
        end = local_now
        display_end = end.strftime("%Y-%m-%d")
    else:
        previous_month_end = current_month_start
        previous_month_last_day = previous_month_end - timedelta(days=1)
        start = first_day_of_month(previous_month_last_day)
        end = previous_month_end
        display_end = previous_month_last_day.strftime("%Y-%m-%d")

    return Period(
        name=period_name,
        start=start,
        end=end,
        display_start=start.strftime("%Y-%m-%d"),
        display_end=display_end,
    )


def format_api_datetime(value):
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def main(argv=None):
    args = parse_args(argv)
    calculate_period(args.period)
    print("Report data loading is added in Task 4.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m unittest tests/test_organization_time_usage_report.py -v
```

Expected: PASS for all 3 tests.

- [ ] **Step 5: Commit**

Stage only the new report and test:

```bash
git add scripts/python/ninjaone-organization-time-usage-report/organization_time_usage_report.py tests/test_organization_time_usage_report.py
git commit -m "feat: add organization time usage period handling"
```

## Task 2: Add Normalization Helpers

**Files:**
- Modify: `scripts/python/ninjaone-organization-time-usage-report/organization_time_usage_report.py`
- Modify: `tests/test_organization_time_usage_report.py`

- [ ] **Step 1: Write failing normalization tests**

Append these methods to `OrganizationTimeUsageReportTests`:

```python
    def test_parse_api_datetime_accepts_iso_and_epoch_values(self):
        module = load_module()

        iso_value = module.parse_api_datetime("2026-05-18T12:30:00.000Z")
        seconds_value = module.parse_api_datetime(1_779_107_400)
        milliseconds_value = module.parse_api_datetime(1_779_107_400_000)

        self.assertEqual(iso_value, datetime(2026, 5, 18, 12, 30, tzinfo=timezone.utc))
        self.assertEqual(seconds_value, datetime(2026, 5, 18, 12, 30, tzinfo=timezone.utc))
        self.assertEqual(milliseconds_value, datetime(2026, 5, 18, 12, 30, tzinfo=timezone.utc))

    def test_normalize_time_entry_duration_hours_accepts_common_units(self):
        module = load_module()

        self.assertEqual(module.normalize_time_entry_duration_hours({"hours": "1.25"}), 1.25)
        self.assertEqual(module.normalize_time_entry_duration_hours({"durationMinutes": 90}), 1.5)
        self.assertEqual(module.normalize_time_entry_duration_hours({"timeSpentSeconds": 3600}), 1.0)
        self.assertEqual(module.normalize_time_entry_duration_hours({"durationMilliseconds": 1800000}), 0.5)
        self.assertIsNone(module.normalize_time_entry_duration_hours({"durationMinutes": -1}))
        self.assertIsNone(module.normalize_time_entry_duration_hours({"durationMinutes": "abc"}))

    def test_normalize_remote_session_duration_minutes_accepts_common_units(self):
        module = load_module()

        self.assertEqual(module.normalize_remote_session_duration_minutes({"minutes": "12.5"}), 12.5)
        self.assertEqual(module.normalize_remote_session_duration_minutes({"durationSeconds": 90}), 1.5)
        self.assertEqual(module.normalize_remote_session_duration_minutes({"durationMilliseconds": 30000}), 0.5)
        self.assertIsNone(module.normalize_remote_session_duration_minutes({"durationSeconds": -1}))
        self.assertIsNone(module.normalize_remote_session_duration_minutes({}))

    def test_extract_ids_accepts_nested_api_shapes(self):
        module = load_module()

        self.assertEqual(module.organization_id({"organization": {"id": 10}}), "10")
        self.assertEqual(module.ticket_id({"ticket": {"id": "T-1"}}), "T-1")
        self.assertEqual(module.device_id({"references": {"device": {"id": 55}}}), "55")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests/test_organization_time_usage_report.py -v
```

Expected: FAIL with missing functions such as `parse_api_datetime`.

- [ ] **Step 3: Add normalization helpers**

Add these functions after `format_api_datetime`:

```python
def iter_items(response):
    if isinstance(response, list):
        return response
    if not isinstance(response, dict):
        return []
    for key in ("activities", "results", "data", "items", "rows"):
        value = response.get(key)
        if isinstance(value, list):
            return value
    return []


def value_at_path(data, path):
    value = data
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def first_value(data, paths):
    for path in paths:
        value = value_at_path(data, path)
        if value is not None:
            return value
    return None


def unwrap_field_value(value):
    if isinstance(value, dict):
        for key in ("value", "textValue", "displayValue", "name", "id"):
            if value.get(key) is not None:
                return value[key]
    return value


def first_field_value(data, paths):
    return unwrap_field_value(first_value(data, paths))


def normalize_number(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip().replace(",", ""))
        except ValueError:
            return None
    else:
        return None
    if number < 0:
        return None
    return number


def normalize_epoch(value):
    number = normalize_number(value)
    if number is None:
        return None
    if abs(number) >= 1_000_000_000_000:
        return number / 1000
    return number


def parse_api_datetime(value):
    if value is None:
        return None
    epoch = normalize_epoch(value)
    if epoch is not None and not isinstance(value, str):
        return datetime.fromtimestamp(epoch, tz=timezone.utc)
    if isinstance(value, str):
        stripped = value.strip()
        numeric_epoch = normalize_epoch(stripped)
        if numeric_epoch is not None:
            return datetime.fromtimestamp(numeric_epoch, tz=timezone.utc)
        if stripped.endswith("Z"):
            stripped = f"{stripped[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(stripped)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def organization_id(record):
    value = first_field_value(
        record,
        (
            ("organizationId",),
            ("organisationId",),
            ("clientId",),
            ("organization", "id"),
            ("organisation", "id"),
            ("client", "id"),
            ("references", "organization", "id"),
            ("references", "organisation", "id"),
            ("references", "client", "id"),
        ),
    )
    return str(value) if value is not None else None


def ticket_id(record):
    value = first_field_value(record, (("ticketId",), ("id",), ("ticket", "id")))
    return str(value) if value is not None else None


def device_id(record):
    value = first_field_value(
        record,
        (
            ("deviceId",),
            ("nodeId",),
            ("targetDeviceId",),
            ("device", "id"),
            ("node", "id"),
            ("references", "device", "id"),
            ("references", "node", "id"),
        ),
    )
    return str(value) if value is not None else None


def entry_datetime(record):
    return parse_api_datetime(
        first_field_value(
            record,
            (
                ("entryDate",),
                ("date",),
                ("createdAt",),
                ("created",),
                ("time",),
                ("timestamp",),
                ("activityTime",),
            ),
        )
    )


def remote_session_datetime(record):
    return parse_api_datetime(
        first_field_value(
            record,
            (
                ("sessionTimestamp",),
                ("startTime",),
                ("startedAt",),
                ("endTime",),
                ("endedAt",),
                ("activityTime",),
                ("timestamp",),
            ),
        )
    )


def normalize_time_entry_duration_hours(record):
    hour_value = normalize_number(
        first_field_value(record, (("hours",), ("durationHours",), ("timeSpentHours",)))
    )
    if hour_value is not None:
        return hour_value

    minute_value = normalize_number(
        first_field_value(record, (("minutes",), ("durationMinutes",), ("timeSpentMinutes",)))
    )
    if minute_value is not None:
        return minute_value / 60

    second_value = normalize_number(
        first_field_value(record, (("seconds",), ("durationSeconds",), ("timeSpentSeconds",)))
    )
    if second_value is not None:
        return second_value / 3600

    millisecond_value = normalize_number(
        first_field_value(record, (("milliseconds",), ("durationMilliseconds",)))
    )
    if millisecond_value is not None:
        return millisecond_value / 3_600_000

    return None


def normalize_remote_session_duration_minutes(record):
    minute_value = normalize_number(first_field_value(record, (("minutes",), ("durationMinutes",))))
    if minute_value is not None:
        return minute_value

    second_value = normalize_number(first_field_value(record, (("seconds",), ("durationSeconds",))))
    if second_value is not None:
        return second_value / 60

    millisecond_value = normalize_number(
        first_field_value(record, (("milliseconds",), ("durationMilliseconds",)))
    )
    if millisecond_value is not None:
        return millisecond_value / 60_000

    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m unittest tests/test_organization_time_usage_report.py -v
```

Expected: PASS for all normalization and period tests.

- [ ] **Step 5: Commit**

```bash
git add scripts/python/ninjaone-organization-time-usage-report/organization_time_usage_report.py tests/test_organization_time_usage_report.py
git commit -m "feat: normalize organization time usage data"
```

## Task 3: Add Aggregation And Table Rendering

**Files:**
- Modify: `scripts/python/ninjaone-organization-time-usage-report/organization_time_usage_report.py`
- Modify: `tests/test_organization_time_usage_report.py`

- [ ] **Step 1: Write failing aggregation and rendering tests**

Append these methods to `OrganizationTimeUsageReportTests`:

```python
    def test_build_summary_aggregates_ticket_time_and_remote_minutes(self):
        module = load_module()
        cest = timezone(timedelta(hours=2), "CEST")
        period = module.calculate_period("last", now=datetime(2026, 5, 18, 14, 30, tzinfo=cest))
        organizations = [
            {"id": 10, "name": "Example Org"},
            {"id": 20, "name": "Zero Org"},
        ]
        devices = [
            {"id": 100, "organizationId": 10},
            {"id": 200, "organizationId": 20},
        ]
        time_entries = [
            {
                "id": "entry-1",
                "organizationId": 10,
                "ticketId": "T-1",
                "entryDate": "2026-04-05T10:00:00Z",
                "durationMinutes": 90,
            },
            {
                "id": "entry-2",
                "ticketId": "T-2",
                "entryDate": "2026-04-06T10:00:00Z",
                "hours": "0.75",
            },
            {
                "id": "entry-out-of-period",
                "organizationId": 10,
                "ticketId": "T-3",
                "entryDate": "2026-05-06T10:00:00Z",
                "hours": 5,
            },
        ]
        ticket_org_lookup = {"T-2": "10"}
        remote_sessions = [
            {
                "deviceId": 100,
                "sessionTimestamp": "2026-04-07T10:00:00Z",
                "durationSeconds": 90,
            },
            {
                "deviceId": 200,
                "sessionTimestamp": "2026-05-07T10:00:00Z",
                "durationSeconds": 900,
            },
        ]

        rows, warnings = module.build_summary(
            organizations,
            devices,
            time_entries,
            remote_sessions,
            ticket_org_lookup,
            period,
        )

        self.assertEqual(
            rows,
            [
                {
                    "Name": "Example Org",
                    "TicketTimeHours": "2.25",
                    "RemoteSessionMinutes": "1.50",
                    "TimeEntries": 2,
                    "TicketsWithTime": 2,
                    "PeriodStart": "2026-04-01",
                    "PeriodEnd": "2026-04-30",
                },
                {
                    "Name": "Zero Org",
                    "TicketTimeHours": "0.00",
                    "RemoteSessionMinutes": "0.00",
                    "TimeEntries": 0,
                    "TicketsWithTime": 0,
                    "PeriodStart": "2026-04-01",
                    "PeriodEnd": "2026-04-30",
                },
            ],
        )
        self.assertEqual(warnings, {"skipped_time_entries": 0, "skipped_remote_sessions": 0})

    def test_build_summary_counts_skipped_invalid_records(self):
        module = load_module()
        cest = timezone(timedelta(hours=2), "CEST")
        period = module.calculate_period("last", now=datetime(2026, 5, 18, 14, 30, tzinfo=cest))

        rows, warnings = module.build_summary(
            [{"id": 10, "name": "Example Org"}],
            [{"id": 100, "organizationId": 10}],
            [{"organizationId": 10, "entryDate": "not-a-date", "durationMinutes": 30}],
            [{"deviceId": 999, "sessionTimestamp": "2026-04-07T10:00:00Z", "durationSeconds": 60}],
            {},
            period,
        )

        self.assertEqual(rows[0]["TicketTimeHours"], "0.00")
        self.assertEqual(rows[0]["RemoteSessionMinutes"], "0.00")
        self.assertEqual(warnings, {"skipped_time_entries": 1, "skipped_remote_sessions": 1})
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests/test_organization_time_usage_report.py -v
```

Expected: FAIL because `build_summary` is not implemented.

- [ ] **Step 3: Add aggregation and rendering functions**

Add these functions before `main()`:

```python
def in_period(value, period):
    if value is None:
        return False
    local_value = value.astimezone(period.start.tzinfo)
    return period.start <= local_value < period.end


def build_device_org_lookup(devices):
    lookup = {}
    for device in iter_items(devices):
        current_device_id = device_id(device) or first_field_value(device, (("id",),))
        current_org_id = organization_id(device)
        if current_device_id is None or current_org_id is None:
            continue
        lookup[str(current_device_id)] = str(current_org_id)
    return lookup


def build_initial_summary(organizations, period):
    summary_by_org_id = {}
    for organization in organizations:
        org_id = organization.get("id")
        if org_id is None:
            continue
        summary_by_org_id[str(org_id)] = {
            "Name": organization.get("name") or f"Organization #{org_id}",
            "TicketTimeHours": 0.0,
            "RemoteSessionMinutes": 0.0,
            "TimeEntries": 0,
            "TicketIds": set(),
            "PeriodStart": period.display_start,
            "PeriodEnd": period.display_end,
        }
    return summary_by_org_id


def sorted_summary_rows(summary_by_org_id):
    rows = []
    for entry in summary_by_org_id.values():
        rows.append(
            {
                "Name": entry["Name"],
                "TicketTimeHours": f"{entry['TicketTimeHours']:.2f}",
                "RemoteSessionMinutes": f"{entry['RemoteSessionMinutes']:.2f}",
                "TimeEntries": entry["TimeEntries"],
                "TicketsWithTime": len(entry["TicketIds"]),
                "PeriodStart": entry["PeriodStart"],
                "PeriodEnd": entry["PeriodEnd"],
            }
        )
    return rows


def build_summary(organizations, devices, time_entries, remote_sessions, ticket_org_lookup, period):
    summary_by_org_id = build_initial_summary(organizations, period)
    device_org_lookup = build_device_org_lookup(devices)
    warnings = {"skipped_time_entries": 0, "skipped_remote_sessions": 0}

    for entry in iter_items(time_entries):
        timestamp = entry_datetime(entry)
        if not in_period(timestamp, period):
            if timestamp is None:
                warnings["skipped_time_entries"] += 1
            continue

        duration_hours = normalize_time_entry_duration_hours(entry)
        current_ticket_id = ticket_id(entry)
        current_org_id = organization_id(entry)
        if current_org_id is None and current_ticket_id is not None:
            current_org_id = ticket_org_lookup.get(str(current_ticket_id))

        organization = summary_by_org_id.get(str(current_org_id))
        if organization is None or duration_hours is None:
            warnings["skipped_time_entries"] += 1
            continue

        organization["TicketTimeHours"] += duration_hours
        organization["TimeEntries"] += 1
        if current_ticket_id is not None:
            organization["TicketIds"].add(str(current_ticket_id))

    for session in iter_items(remote_sessions):
        timestamp = remote_session_datetime(session)
        if not in_period(timestamp, period):
            if timestamp is None:
                warnings["skipped_remote_sessions"] += 1
            continue

        duration_minutes = normalize_remote_session_duration_minutes(session)
        current_device_id = device_id(session)
        current_org_id = device_org_lookup.get(str(current_device_id))
        organization = summary_by_org_id.get(str(current_org_id))
        if organization is None or duration_minutes is None:
            warnings["skipped_remote_sessions"] += 1
            continue

        organization["RemoteSessionMinutes"] += duration_minutes

    return sorted_summary_rows(summary_by_org_id), warnings


def print_table(rows):
    if not rows:
        print("No rows returned.")
        return

    columns = [
        "Name",
        "TicketTimeHours",
        "RemoteSessionMinutes",
        "TimeEntries",
        "TicketsWithTime",
        "PeriodStart",
        "PeriodEnd",
    ]
    widths = {column: len(column) for column in columns}
    for row in rows:
        for column in columns:
            widths[column] = max(widths[column], len(str(row[column])))

    print(" ".join(column.ljust(widths[column]) for column in columns))
    print(" ".join("-" * widths[column] for column in columns))
    for row in rows:
        print(" ".join(str(row[column]).ljust(widths[column]) for column in columns))
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m unittest tests/test_organization_time_usage_report.py -v
```

Expected: PASS for all current tests.

- [ ] **Step 5: Commit**

```bash
git add scripts/python/ninjaone-organization-time-usage-report/organization_time_usage_report.py tests/test_organization_time_usage_report.py
git commit -m "feat: aggregate organization time usage"
```

## Task 4: Add API Loading And Main Flow

**Files:**
- Modify: `scripts/python/ninjaone-organization-time-usage-report/organization_time_usage_report.py`
- Modify: `tests/test_organization_time_usage_report.py`

- [ ] **Step 1: Write failing API loader tests**

Append these methods to `OrganizationTimeUsageReportTests`:

```python
    def test_fetch_activity_pages_uses_after_before_and_older_than(self):
        module = load_module()
        calls = []

        def fake_get_api_resource(path, access_token):
            calls.append((path, access_token))
            if "olderThan=activity-2" in path:
                return {"activities": [{"id": "activity-3"}]}
            return {"activities": [{"id": "activity-1"}, {"id": "activity-2"}]}

        module.get_api_resource = fake_get_api_resource
        cest = timezone(timedelta(hours=2), "CEST")
        period = module.calculate_period("last", now=datetime(2026, 5, 18, 14, 30, tzinfo=cest))

        activities = module.fetch_activity_pages("token", period, {"class": "DEVICE"}, page_size=2)

        self.assertEqual([activity["id"] for activity in activities], ["activity-1", "activity-2", "activity-3"])
        self.assertEqual(len(calls), 2)
        self.assertIn("/v2/activities?", calls[0][0])
        self.assertIn("after=2026-03-31T22%3A00%3A00.000Z", calls[0][0])
        self.assertIn("before=2026-04-30T22%3A00%3A00.000Z", calls[0][0])

    def test_build_ticket_org_lookup_from_ticket_records(self):
        module = load_module()
        tickets = [
            {"id": "T-1", "organizationId": 10},
            {"ticketId": "T-2", "client": {"id": 20}},
            {"id": "missing-org"},
        ]

        lookup = module.build_ticket_org_lookup(tickets)

        self.assertEqual(lookup, {"T-1": "10", "T-2": "20"})

    def test_filter_remote_session_activities_requires_remote_session_marker(self):
        module = load_module()
        activities = [
            {"status": "NINJA_REMOTE_SESSION_ENDED", "deviceId": 10, "durationSeconds": 60},
            {"message": "Remote session ended", "deviceId": 11, "durationSeconds": 120},
            {"status": "PATCH_SCAN_COMPLETED", "deviceId": 12, "durationSeconds": 300},
        ]

        sessions = module.filter_remote_session_activities(activities)

        self.assertEqual([session["deviceId"] for session in sessions], [10, 11])

    def test_load_tickets_pages_boards_and_deduplicates_ticket_ids(self):
        module = load_module()
        post_calls = []

        def fake_get_api_resource(path, access_token):
            self.assertEqual(access_token, "token")
            if path == "/v2/ticketing/trigger/boards":
                return [{"id": 100}, {"id": 200}]
            raise AssertionError(f"unexpected GET path: {path}")

        def fake_post_api_resource(path, access_token, json_body=None):
            post_calls.append((path, access_token, json_body))
            first_page_body = {
                "pageSize": 1000,
                "includeColumns": module.TICKET_INCLUDE_COLUMNS,
            }
            second_page_body = {
                "pageSize": 1000,
                "includeColumns": module.TICKET_INCLUDE_COLUMNS,
                "lastCursorId": 2,
            }
            if path == "/v2/ticketing/trigger/board/100/run" and json_body == first_page_body:
                return {
                    "data": [{"id": 1, "organizationId": 10}, {"id": 2, "organizationId": 10}],
                    "metadata": {"lastCursorId": 2},
                }
            if path == "/v2/ticketing/trigger/board/100/run" and json_body == second_page_body:
                return {"data": [{"id": 3, "organizationId": 20}], "metadata": {}}
            if path == "/v2/ticketing/trigger/board/200/run" and json_body == first_page_body:
                return {"data": [{"id": 2, "organizationId": 10}, {"id": 4, "organizationId": 20}]}
            raise AssertionError(f"unexpected POST call: {path} {json_body}")

        module.get_api_resource = fake_get_api_resource
        module.post_api_resource = fake_post_api_resource

        tickets = module.load_tickets("token")

        self.assertEqual([ticket["id"] for ticket in tickets], [1, 2, 3, 4])
        self.assertEqual(len(post_calls), 3)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests/test_organization_time_usage_report.py -v
```

Expected: FAIL with missing API loader functions.

- [ ] **Step 3: Add API loader constants and functions**

Add these constants near `PAGE_SIZE`:

```python
TIME_ENTRY_PATHS = (
    "/v2/ticketing/time-entries",
    "/v2/ticketing/timeEntries",
    "/v2/ticketing/tickets/time-entries",
)

TICKET_BOARD_PATH = "/v2/ticketing/trigger/boards"
TICKET_INCLUDE_COLUMNS = [
    "id",
    "ticketId",
    "clientId",
    "organizationId",
]
REMOTE_ACTIVITY_MARKERS = ("REMOTE_SESSION", "REMOTE SESSION", "NINJA_REMOTE")
```

Add these loader functions before `main()`:

```python
def fetch_collection_pages(access_token, base_path, period, extra_params=None, page_size=PAGE_SIZE):
    records = []
    older_than = None

    while True:
        params = {
            "after": format_api_datetime(period.start),
            "before": format_api_datetime(period.end),
            "pageSize": page_size,
        }
        if extra_params:
            params.update(extra_params)
        if older_than is not None:
            params["olderThan"] = older_than

        response = get_api_resource(f"{base_path}?{urlencode(params)}", access_token)
        page_items = list(iter_items(response))
        records.extend(page_items)

        if len(page_items) < page_size:
            break

        older_than = page_items[-1].get("id") if isinstance(page_items[-1], dict) else None
        if older_than is None:
            break

    return records


def fetch_activity_pages(access_token, period, extra_params=None, page_size=PAGE_SIZE):
    return fetch_collection_pages(
        access_token,
        "/v2/activities",
        period,
        extra_params=extra_params,
        page_size=page_size,
    )


def fetch_first_available_collection(access_token, paths, period, description):
    errors = []
    for path in paths:
        try:
            return fetch_collection_pages(access_token, path, period)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path}: {exc}")
    raise RuntimeError(f"Could not query {description}. Tried: {'; '.join(errors)}")


def load_time_entries(access_token, period):
    return fetch_first_available_collection(
        access_token,
        TIME_ENTRY_PATHS,
        period,
        "ticket time entries",
    )


def is_remote_session_activity(activity):
    haystack = " ".join(
        str(value or "")
        for value in (
            activity.get("status"),
            activity.get("activityType"),
            activity.get("type"),
            activity.get("message"),
            activity.get("subject"),
        )
    ).upper().replace("-", "_")
    return any(marker in haystack for marker in REMOTE_ACTIVITY_MARKERS)


def filter_remote_session_activities(activities):
    return [activity for activity in iter_items(activities) if is_remote_session_activity(activity)]


def load_remote_sessions(access_token, period):
    activities = fetch_activity_pages(access_token, period, {"class": "DEVICE"})
    return filter_remote_session_activities(activities)


def load_ticket_board_tickets(board_id, access_token):
    tickets = []
    last_cursor_id = None

    while True:
        json_body = {
            "pageSize": PAGE_SIZE,
            "includeColumns": TICKET_INCLUDE_COLUMNS,
        }
        if last_cursor_id is not None:
            json_body["lastCursorId"] = last_cursor_id

        response = post_api_resource(
            f"/v2/ticketing/trigger/board/{board_id}/run",
            access_token,
            json_body=json_body,
        )
        tickets.extend(iter_items(response))

        metadata = response.get("metadata", {}) if isinstance(response, dict) else {}
        next_cursor_id = metadata.get("lastCursorId")
        if not next_cursor_id or next_cursor_id == last_cursor_id:
            break
        last_cursor_id = next_cursor_id

    return tickets


def load_tickets(access_token):
    boards = get_api_resource(TICKET_BOARD_PATH, access_token)
    tickets = []
    seen_ticket_ids = set()

    for board in iter_items(boards):
        board_id = first_field_value(board, (("id",), ("boardId",)))
        if board_id is None:
            continue

        for ticket in load_ticket_board_tickets(board_id, access_token):
            current_ticket_id = ticket_id(ticket)
            if current_ticket_id is not None:
                normalized_ticket_id = str(current_ticket_id)
                if normalized_ticket_id in seen_ticket_ids:
                    continue
                seen_ticket_ids.add(normalized_ticket_id)
            tickets.append(ticket)

    return tickets


def build_ticket_org_lookup(tickets):
    lookup = {}
    for ticket in iter_items(tickets):
        current_ticket_id = ticket_id(ticket)
        current_org_id = organization_id(ticket)
        if current_ticket_id is None or current_org_id is None:
            continue
        lookup[str(current_ticket_id)] = str(current_org_id)
    return lookup
```

- [ ] **Step 4: Replace `main()` with API flow**

Replace the current `main()` with:

```python
def main(argv=None):
    args = parse_args(argv)
    period = calculate_period(args.period)

    try:
        access_token = get_access_token()
        organizations = get_api_resource("/v2/organizations-detailed", access_token)
        devices = get_api_resource("/v2/devices-detailed", access_token)
        time_entries = load_time_entries(access_token, period)
        remote_sessions = load_remote_sessions(access_token, period)
        tickets = load_tickets(access_token)
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to query NinjaOne API: {exc}", file=sys.stderr)
        return 1

    ticket_org_lookup = build_ticket_org_lookup(tickets)
    rows, warnings = build_summary(
        organizations,
        devices,
        time_entries,
        remote_sessions,
        ticket_org_lookup,
        period,
    )
    print_table(rows)

    if warnings["skipped_time_entries"]:
        print(f"Skipped time entries: {warnings['skipped_time_entries']}", file=sys.stderr)
    if warnings["skipped_remote_sessions"]:
        print(f"Skipped remote sessions: {warnings['skipped_remote_sessions']}", file=sys.stderr)

    return 0
```

- [ ] **Step 5: Run unit tests**

Run:

```bash
python3 -m unittest tests/test_organization_time_usage_report.py -v
```

Expected: PASS for all report tests.

- [ ] **Step 6: Commit**

```bash
git add scripts/python/ninjaone-organization-time-usage-report/organization_time_usage_report.py tests/test_organization_time_usage_report.py
git commit -m "feat: load organization time usage data"
```

## Task 5: Wire Launcher And CLI Tests

**Files:**
- Modify: `ninja`
- Modify: `tests/test_ninja_cli.sh`

- [ ] **Step 1: Write failing launcher test**

Add this block to `tests/test_ninja_cli.sh` after the `EXPLICIT_OUTPUT` assertions:

```bash
TIME_USAGE_OUTPUT="$(PATH="$TMP_DIR/bin:$PATH" run_successfully "$TMP_DIR/ninja" org-time-usage --period this)"
assert_contains "$TIME_USAGE_OUTPUT" "instance=default.example.test"
assert_contains "$TIME_USAGE_OUTPUT" "script=scripts/python/ninjaone-organization-time-usage-report/organization_time_usage_report.py"
assert_contains "$TIME_USAGE_OUTPUT" "args=--period this"

EXPLICIT_TIME_USAGE_OUTPUT="$(PATH="$TMP_DIR/bin:$PATH" run_successfully "$TMP_DIR/ninja" demo-eu org-time-usage --period last)"
assert_contains "$EXPLICIT_TIME_USAGE_OUTPUT" "instance=demo-eu.example.test"
assert_contains "$EXPLICIT_TIME_USAGE_OUTPUT" "script=scripts/python/ninjaone-organization-time-usage-report/organization_time_usage_report.py"
assert_contains "$EXPLICIT_TIME_USAGE_OUTPUT" "args=--period last"
```

- [ ] **Step 2: Run launcher test to verify it fails**

Run:

```bash
bash tests/test_ninja_cli.sh
```

Expected: FAIL with `Unknown script: org-time-usage`.

- [ ] **Step 3: Update launcher usage, list, and resolver**

In `ninja`, add `org-time-usage` to the usage script list:

```text
  org-time-usage  Organization ticket time and remote-session usage report
```

Add it to `list_scripts()`:

```bash
org-time-usage
```

Add this case to `resolve_script()`:

```bash
    org-time-usage)
      echo "scripts/python/ninjaone-organization-time-usage-report/organization_time_usage_report.py"
      ;;
```

- [ ] **Step 4: Run launcher test to verify it passes**

Run:

```bash
bash tests/test_ninja_cli.sh
```

Expected: PASS with no output.

- [ ] **Step 5: Commit**

```bash
git add ninja tests/test_ninja_cli.sh
git commit -m "feat: add organization time usage launcher"
```

## Task 6: Add Documentation

**Files:**
- Create: `scripts/python/ninjaone-organization-time-usage-report/ORGANIZATION_TIME_USAGE.md`
- Modify: `README.md`
- Modify: `scripts/README.md`

- [ ] **Step 1: Create report documentation**

Create `scripts/python/ninjaone-organization-time-usage-report/ORGANIZATION_TIME_USAGE.md`:

```markdown
# NinjaOne Organization Time Usage Report

Reports cumulative NinjaOne ticket time and NinjaOne remote-session duration by organization for a selected local calendar period.

## Usage

Store NinjaOne credentials in `env/default.env` as described in the repository root README. Then run from the repository root:

```bash
./ninja org-time-usage
```

For the current month to now:

```bash
./ninja org-time-usage --period this
```

For a named environment:

```bash
./ninja demo-eu org-time-usage --period last
```

## Environment variables

These variables belong in `env/default.env` or another selected `env/*.env` file.

- `NINJA_ONE_CLIENT_ID` (required): OAuth client ID.
- `NINJA_ONE_CLIENT_SECRET` (required): OAuth client secret.
- `NINJA_ONE_INSTANCE` (optional): NinjaOne instance hostname. Defaults to `eu.ninjarmm.com`.
- `NINJA_ONE_SCOPE` (optional): OAuth scope. Defaults to `monitoring management`.

## Periods

- `--period last`: previous complete local calendar month. This is the default.
- `--period this`: current local calendar month from the first day of the month through the execution time.

Ticket time is filtered by time-entry date. Remote-session duration is filtered by remote-session timestamp.

## Output

- `Name`: Organization name.
- `TicketTimeHours`: Cumulative ticket time-entry duration in decimal hours.
- `RemoteSessionMinutes`: Cumulative NinjaOne remote-session duration in decimal minutes.
- `TimeEntries`: Count of valid ticket time entries in the period.
- `TicketsWithTime`: Count of unique tickets with valid time entries in the period.
- `PeriodStart`: Local period start date.
- `PeriodEnd`: Local period end date displayed in the table.

## Behavior

- Loads organizations from `/v2/organizations-detailed`.
- Loads devices from `/v2/devices-detailed` and maps remote sessions to organizations through the session device id.
- Queries ticket time entries through the first available ticket time-entry endpoint configured in the script.
- Queries NinjaOne remote-session activity through `/v2/activities`.
- Prints skipped-entry counts to stderr when records are missing required date, duration, or mapping fields.

## No Liability / No Warranty

This script is provided as-is, without warranty of any kind, express or implied. Use it at your own risk and validate it in a safe test environment before using it in production. The author and contributors are not liable for any damages, data loss, service disruption, security issue, or other consequence resulting from use, misuse, or inability to use this script.
```

- [ ] **Step 2: Update root README quick start and Python report section**

In `README.md`, add `./ninja org-time-usage` to the quick start command block and add this Python section near `org-summary`:

```markdown
### NinjaOne organization time usage report
Reports cumulative ticket time and NinjaOne remote-session duration by organization for a selected calendar period.

- Language: Python
- Path: `scripts/python/ninjaone-organization-time-usage-report/`
- Docs: [`ORGANIZATION_TIME_USAGE.md`](scripts/python/ninjaone-organization-time-usage-report/ORGANIZATION_TIME_USAGE.md)
- Usage: `./ninja org-time-usage`
- Prereqs: Python 3, NinjaOne OAuth client credentials in `env/default.env`
```

- [ ] **Step 3: Update scripts index**

In `scripts/README.md`, add this row to the Python table:

```markdown
| `python/ninjaone-organization-time-usage-report/organization_time_usage_report.py` | Reports NinjaOne organization ticket time and remote-session usage. | [`ORGANIZATION_TIME_USAGE.md`](python/ninjaone-organization-time-usage-report/ORGANIZATION_TIME_USAGE.md) |
```

- [ ] **Step 4: Run documentation smoke checks**

Run:

```bash
test -f scripts/python/ninjaone-organization-time-usage-report/ORGANIZATION_TIME_USAGE.md
rg -n "org-time-usage|ORGANIZATION_TIME_USAGE" README.md scripts/README.md scripts/python/ninjaone-organization-time-usage-report/ORGANIZATION_TIME_USAGE.md
```

Expected: the `test` command exits `0`, and `rg` prints matches in all three documentation files.

- [ ] **Step 5: Commit**

```bash
git add README.md scripts/README.md scripts/python/ninjaone-organization-time-usage-report/ORGANIZATION_TIME_USAGE.md
git commit -m "docs: document organization time usage report"
```

## Task 7: Full Verification

**Files:**
- No new files.
- Verify all files changed by Tasks 1-6.

- [ ] **Step 1: Run focused unit tests**

Run:

```bash
python3 -m unittest tests/test_organization_time_usage_report.py -v
```

Expected: PASS for all organization time usage tests.

- [ ] **Step 2: Run existing Python unit tests**

Run:

```bash
python3 -m unittest tests/test_assign_device_owner.py tests/test_organization_device_summary_report.py tests/test_organization_time_usage_report.py -v
```

Expected: PASS for all listed tests. If `tests/test_organization_device_summary_report.py` reflects unrelated local work and fails, stop and inspect without reverting unrelated changes.

- [ ] **Step 3: Run launcher test**

Run:

```bash
bash tests/test_ninja_cli.sh
```

Expected: PASS with no output.

- [ ] **Step 4: Check final diff is scoped**

Run:

```bash
git status --short
git diff --name-only
```

Expected: changed files for this feature are only:

```text
README.md
ninja
scripts/README.md
scripts/python/ninjaone-organization-time-usage-report/ORGANIZATION_TIME_USAGE.md
scripts/python/ninjaone-organization-time-usage-report/organization_time_usage_report.py
tests/test_ninja_cli.sh
tests/test_organization_time_usage_report.py
```

Existing unrelated changes may still appear in `git status`; leave them unstaged.

- [ ] **Step 5: Commit final fixes if verification required changes**

If verification required edits, stage only files from this feature and commit:

```bash
git add README.md ninja scripts/README.md scripts/python/ninjaone-organization-time-usage-report/ORGANIZATION_TIME_USAGE.md scripts/python/ninjaone-organization-time-usage-report/organization_time_usage_report.py tests/test_ninja_cli.sh tests/test_organization_time_usage_report.py
git commit -m "fix: verify organization time usage report"
```

If no verification edits were needed, skip this commit step.
