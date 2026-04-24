#!/usr/bin/env python3
"""
[Version 1.0.0] Report NinjaOne technicians sorted by most recent platform
login activity, including name, email, enabled status, admin status, roles,
and last login timestamp.

Environment variables:
- NINJA_ONE_INSTANCE (required), e.g. eu.ninjarmm.com
- NINJA_ONE_CLIENT_ID (required)
- NINJA_ONE_CLIENT_SECRET (required)
- NINJA_ONE_SCOPE (optional, defaults to "monitoring management")
"""

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlencode


LOGIN_STATUS = "APP_USER_LOGGED_IN"
PAGE_SIZE = 1000
DEFAULT_SCOPE = "monitoring management"


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "List NinjaOne technicians sorted by most recent Ninja platform "
            "login activity."
        )
    )
    parser.add_argument(
        "--enabled-only",
        action="store_true",
        help="Only include enabled technicians.",
    )
    return parser.parse_args()


def require_env(name, default=None):
    value = os.getenv(name, default)
    if value:
        return value
    raise RuntimeError(f"Missing required environment variable: {name}")


def request_json(url, method="GET", headers=None, form_body=None):
    body = None
    request_headers = headers.copy() if headers else {}

    if form_body is not None:
        body = urllib.parse.urlencode(form_body).encode("utf-8")
        request_headers["Content-Type"] = "application/x-www-form-urlencoded"

    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    context = ssl.create_default_context()

    try:
        with urllib.request.urlopen(request, context=context) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {exc.reason}: {error_body}") from exc


def get_access_token():
    instance = require_env("NINJA_ONE_INSTANCE")
    client_id = require_env("NINJA_ONE_CLIENT_ID")
    client_secret = require_env("NINJA_ONE_CLIENT_SECRET")
    scope = require_env("NINJA_ONE_SCOPE", DEFAULT_SCOPE)

    auth_response = request_json(
        f"https://{instance}/oauth/token",
        method="POST",
        headers={"Accept": "application/json"},
        form_body={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
        },
    )

    access_token = auth_response.get("access_token")
    if not access_token:
        raise RuntimeError("OAuth response did not contain an access token.")

    return access_token


def get_api_resource(path, access_token):
    instance = require_env("NINJA_ONE_INSTANCE")
    return request_json(
        f"https://{instance}{path}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
    )


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


def fetch_last_login_by_user_id(access_token, technician_ids):
    last_login_by_user_id = {}
    remaining_user_ids = set(technician_ids)
    older_than = None

    while remaining_user_ids:
        params = {
            "class": "USER",
            "status": LOGIN_STATUS,
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

        if len(activities) < PAGE_SIZE:
            break

        older_than = activities[-1].get("id")
        if older_than is None:
            break

    return last_login_by_user_id


def format_last_login(timestamp):
    if timestamp is None:
        return "(never)"

    return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone().strftime(
        "%Y-%m-%d %H:%M:%S %Z"
    )


def build_rows(technicians, last_login_by_user_id):
    rows = []

    for user_id, user in technicians.items():
        roles = user.get("roles") or []
        last_login = last_login_by_user_id.get(user_id)
        rows.append(
            {
                "Name": technician_name(user),
                "Email": user.get("email", ""),
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
    columns = ["Name", "Email", "Enabled", "Admin", "Roles", "Last Login"]

    if not rows:
        print("No technicians returned.")
        return

    widths = {column: len(column) for column in columns}
    for row in rows:
        for column in columns:
            widths[column] = max(widths[column], len(str(row[column])))

    print(" ".join(column.ljust(widths[column]) for column in columns))
    print(" ".join("-" * widths[column] for column in columns))
    for row in rows:
        print(" ".join(str(row[column]).ljust(widths[column]) for column in columns))


def main():
    args = parse_args()

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
