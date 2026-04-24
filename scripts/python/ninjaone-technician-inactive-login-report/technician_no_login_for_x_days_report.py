#!/usr/bin/env python3
"""
[Version 1.0.0] Report NinjaOne technicians inactive since a midnight-based
cutoff date, including name, email, admin status, roles, and last platform
login before that cutoff.

Environment variables:
- NINJA_ONE_CLIENT_ID (required)
- NINJA_ONE_CLIENT_SECRET (required)
- NINJA_ONE_INSTANCE (optional, defaults to "eu.ninjarmm.com")
- NINJA_ONE_SCOPE (optional, defaults to "monitoring management")
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared"))
from ninja_api import get_access_token, get_api_resource


LOGIN_STATUS = "APP_USER_LOGGED_IN"
PAGE_SIZE = 1000


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "List NinjaOne technicians who have not logged into the Ninja "
            "platform during the last N full days."
        )
    )
    parser.add_argument(
        "--days",
        type=int,
        default=4,
        help="Number of full days to look back from local midnight (default: 4).",
    )
    parser.add_argument(
        "--include-disabled",
        action="store_true",
        help="Include disabled technicians in the inactive list.",
    )
    return parser.parse_args()


def technician_name(user):
    first_name = (user.get("firstName") or "").strip()
    last_name = (user.get("lastName") or "").strip()
    full_name = f"{first_name} {last_name}".strip()
    if full_name:
        return full_name
    return user.get("email") or f"Technician #{user.get('id', 'unknown')}"


def normalize_epoch(value):
    if value is None:
        return None

    timestamp = float(value)
    if abs(timestamp) >= 1_000_000_000_000:
        return timestamp / 1000
    return timestamp


def format_api_datetime(value):
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def load_technicians(access_token, include_disabled):
    users = get_api_resource("/v2/users?userType=TECHNICIAN&includeRoles=true", access_token)
    technicians = {}

    for user in users:
        if not include_disabled and not user.get("enabled", False):
            continue

        user_id = user.get("id")
        if user_id is None:
            continue

        technicians[user_id] = user

    return technicians


def fetch_active_user_ids(access_token, technician_ids, cutoff):
    active_user_ids = set()
    older_than = None

    while True:
        params = {
            "class": "USER",
            "status": LOGIN_STATUS,
            "after": format_api_datetime(cutoff),
            "pageSize": PAGE_SIZE,
        }
        if older_than is not None:
            params["olderThan"] = older_than

        response = get_api_resource(f"/v2/activities?{urlencode(params)}", access_token)
        activities = response.get("activities") or []
        if not activities:
            break

        for activity in activities:
            activity_timestamp = normalize_epoch(activity.get("activityTime"))
            user_id = activity.get("userId")

            if activity_timestamp is None or user_id is None:
                continue
            if user_id not in technician_ids:
                continue

            active_user_ids.add(user_id)

        if len(active_user_ids) == len(technician_ids) or len(activities) < PAGE_SIZE:
            break

        older_than = activities[-1].get("id")
        if older_than is None:
            break

    return active_user_ids


def fetch_latest_login_before_cutoff(access_token, technician_ids, cutoff):
    latest_login_by_user_id = {}
    older_than = None

    if not technician_ids:
        return latest_login_by_user_id

    while True:
        params = {
            "class": "USER",
            "status": LOGIN_STATUS,
            "before": format_api_datetime(cutoff),
            "pageSize": PAGE_SIZE,
        }
        if older_than is not None:
            params["olderThan"] = older_than

        response = get_api_resource(f"/v2/activities?{urlencode(params)}", access_token)
        activities = response.get("activities") or []
        if not activities:
            break

        for activity in activities:
            activity_timestamp = normalize_epoch(activity.get("activityTime"))
            user_id = activity.get("userId")

            if activity_timestamp is None or user_id is None:
                continue
            if user_id not in technician_ids or user_id in latest_login_by_user_id:
                continue

            latest_login_by_user_id[user_id] = activity_timestamp

        if len(latest_login_by_user_id) == len(technician_ids) or len(activities) < PAGE_SIZE:
            break

        older_than = activities[-1].get("id")
        if older_than is None:
            break

    return latest_login_by_user_id


def format_last_login(timestamp):
    if timestamp is None:
        return "(never)"

    return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone().strftime(
        "%Y-%m-%d %H:%M:%S %Z"
    )


def build_rows(technicians, inactive_user_ids, latest_login_by_user_id):
    rows = []

    for user_id in inactive_user_ids:
        user = technicians[user_id]
        roles = user.get("roles") or []
        rows.append(
            {
                "Name": technician_name(user),
                "Email": user.get("email", ""),
                "Enabled": "Yes" if user.get("enabled") else "No",
                "Admin": "Yes" if user.get("administrator") else "No",
                "Roles": ", ".join(roles) if roles else "(none)",
                "Last Login": format_last_login(latest_login_by_user_id.get(user_id)),
            }
        )

    return sorted(rows, key=lambda row: row["Name"].casefold())


def print_table(rows):
    columns = ["Name", "Email", "Enabled", "Admin", "Roles", "Last Login"]

    if not rows:
        print("No inactive technicians matched the report criteria.")
        return

    widths = {column: len(column) for column in columns}
    for row in rows:
        for column in columns:
            widths[column] = max(widths[column], len(str(row[column])))

    print(" ".join(column.ljust(widths[column]) for column in columns))
    print(" ".join("-" * widths[column] for column in columns))
    for row in rows:
        print(" ".join(str(row[column]).ljust(widths[column]) for column in columns))


def build_cutoff(days):
    local_now = datetime.now().astimezone()
    local_midnight_today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_local = local_midnight_today - timedelta(days=days)
    cutoff_utc = cutoff_local.astimezone(timezone.utc)
    return cutoff_local, cutoff_utc


def main():
    args = parse_args()
    if args.days < 0:
        print("--days must be 0 or greater.", file=sys.stderr)
        return 2

    cutoff_local, cutoff = build_cutoff(args.days)

    try:
        access_token = get_access_token()
        technicians = load_technicians(access_token, args.include_disabled)
        technician_ids = set(technicians)
        active_user_ids = fetch_active_user_ids(access_token, technician_ids, cutoff)
        inactive_user_ids = technician_ids - active_user_ids
        latest_login_by_user_id = fetch_latest_login_before_cutoff(
            access_token, inactive_user_ids, cutoff
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to query NinjaOne API: {exc}", file=sys.stderr)
        return 1

    rows = build_rows(technicians, inactive_user_ids, latest_login_by_user_id)

    scope = "all technicians" if args.include_disabled else "enabled technicians"
    print(f"Cutoff: {cutoff_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(
        f"Inactive {scope} with no Ninja platform login in the last "
        f"{args.days} day(s): {len(rows)}"
    )
    print_table(rows)
    print(f"Total: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
