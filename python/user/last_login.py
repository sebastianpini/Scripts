#!/usr/bin/env python3
"""
[Version 2.0.0] Report NinjaOne users sorted by most recent platform
login activity, including name, email, type, enabled status, admin status,
roles, and last login timestamp. Supports technicians, end users, or both
via --user-type, with optional CSV and Excel export.

Usage:
  python ninja.py last-login [--user-type {technician,enduser,all}]
                             [--enabled-only]
                             [--csv PATH]
                             [--xlsx PATH]

Arguments:
  --user-type    User type to include: technician (default), enduser, or all.
  --enabled-only Only include enabled users.
  --csv PATH     Write results to a CSV file at PATH.
  --xlsx PATH    Write results to a formatted Excel (.xlsx) file at PATH.

Environment variables:
- NINJA_ONE_CLIENT_ID (required)
- NINJA_ONE_CLIENT_SECRET (required)
- NINJA_ONE_INSTANCE (optional, defaults to "eu.ninjarmm.com")
- NINJA_ONE_SCOPE (optional, defaults to "monitoring management")
"""

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared"))
from ninja_api import get_access_token, get_api_resource


TECHNICIAN_LOGIN_STATUS = "APP_USER_LOGGED_IN"
END_USER_LOGIN_STATUS = "END_USER_LOGGED_IN"
PAGE_SIZE = 1000


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "List NinjaOne users sorted by most recent Ninja platform "
            "login activity."
        )
    )
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
    parser.add_argument(
        "--csv",
        metavar="PATH",
        help="Write results to a CSV file at PATH.",
    )
    parser.add_argument(
        "--xlsx",
        metavar="PATH",
        help="Write results to an Excel (.xlsx) file at PATH.",
    )
    return parser.parse_args()


def user_display_name(user):
    first_name = (user.get("firstName") or "").strip()
    last_name = (user.get("lastName") or "").strip()
    full_name = f"{first_name} {last_name}".strip()
    if full_name:
        return full_name
    return user.get("email") or f"User #{user.get('id', 'unknown')}"


def normalize_epoch(value):
    if value is None:
        return None

    timestamp = float(value)
    if abs(timestamp) >= 1_000_000_000_000:
        return timestamp / 1000
    return timestamp


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


def fetch_last_login_by_user_id(access_token, user_ids, login_status):
    # The NinjaOne activities API does not reliably return a full page on non-final
    # pages — the first page can return fewer than PAGE_SIZE items even when more
    # pages exist. End-of-results is detected by an empty activities list or a
    # missing olderThan cursor, not by page size.
    last_login_by_user_id = {}
    remaining_user_ids = set(user_ids)
    older_than = None

    while remaining_user_ids:
        params = {
            "class": "USER",
            "status": login_status,
            "pageSize": PAGE_SIZE,
        }
        if older_than is not None:
            params["olderThan"] = older_than

        response = get_api_resource(f"/v2/activities?{urlencode(params)}", access_token)
        activities = response.get("activities") or []
        if not activities:
            break

        for activity in activities:
            user_id = activity.get("userId")
            if user_id not in remaining_user_ids:
                continue

            activity_timestamp = normalize_epoch(activity.get("activityTime"))
            if activity_timestamp is None:
                continue

            last_login_by_user_id[user_id] = activity_timestamp
            remaining_user_ids.remove(user_id)

            if not remaining_user_ids:
                break

        older_than = activities[-1].get("id")
        if older_than is None:
            break

    return last_login_by_user_id


def format_last_login(timestamp):
    if timestamp is None:
        return "(never)"

    return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone().isoformat(timespec="seconds")


def build_rows(technicians, last_login_by_user_id):
    rows = []

    for user_id, user in technicians.items():
        roles = user.get("roles") or []
        last_login = last_login_by_user_id.get(user_id)
        user_type = user.get("userType", "")
        rows.append(
            {
                "Name": user_display_name(user),
                "Email": user.get("email", ""),
                "Type": "Technician" if user_type == "TECHNICIAN" else "End User" if user_type == "END_USER" else user_type,
                "Enabled": "Yes" if user.get("enabled") else "No",
                "Admin": "Yes" if user.get("administrator") else "No",
                "Roles": ", ".join(roles) if roles else "(none)",
                "Last Login": format_last_login(last_login),
                "_sort_ts": float("-inf") if last_login is None else last_login,
            }
        )

    return sorted(
        rows,
        key=lambda row: (-row["_sort_ts"], row["Name"].casefold(), row["Email"].casefold()),
    )


def print_table(rows):
    columns = ["Name", "Email", "Type", "Enabled", "Admin", "Roles", "Last Login"]

    if not rows:
        print("No users returned.")
        return

    widths = {column: len(column) for column in columns}
    for row in rows:
        for column in columns:
            widths[column] = max(widths[column], len(str(row[column])))

    print(" ".join(column.ljust(widths[column]) for column in columns))
    print(" ".join("-" * widths[column] for column in columns))
    for row in rows:
        print(" ".join(str(row[column]).ljust(widths[column]) for column in columns))


def write_csv(rows, path):
    columns = ["Name", "Email", "Type", "Enabled", "Admin", "Roles", "Last Login"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    args = parse_args()

    if args.user_type in ("enduser", "all"):
        print(
            "Warning: end user activity scan may be slow with large user counts.",
            file=sys.stderr,
        )

    try:
        access_token = get_access_token()
        users = load_users(access_token, args.user_type, args.enabled_only)
        if args.user_type == "all":
            # Relies on userType field from /v2/users API; users missing it get no login lookup.
            tech_ids = {uid for uid, u in users.items() if u.get("userType") == "TECHNICIAN"}
            enduser_ids = {uid for uid, u in users.items() if u.get("userType") == "END_USER"}
            unclassified = set(users) - tech_ids - enduser_ids
            if unclassified:
                print(
                    f"Warning: {len(unclassified)} user(s) have no userType and will show as (never).",
                    file=sys.stderr,
                )
            last_login_by_user_id = {
                **fetch_last_login_by_user_id(access_token, tech_ids, TECHNICIAN_LOGIN_STATUS),
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
    if not args.csv and not args.xlsx:
        print(f"Login report for {scope}: {len(rows)}")
        print_table(rows)
        print(f"Total: {len(rows)}")
    if args.csv:
        write_csv(rows, args.csv)
        print(f"Wrote {len(rows)} rows to {args.csv}")
    if args.xlsx:
        from excel_export import write_xlsx

        columns = ["Name", "Email", "Type", "Enabled", "Admin", "Roles", "Last Login"]
        write_xlsx(rows, columns, args.xlsx)
        print(f"Wrote {len(rows)} rows to {args.xlsx}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
