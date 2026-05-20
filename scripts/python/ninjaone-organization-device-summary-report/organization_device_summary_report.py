#!/usr/bin/env python3
"""
[Version 1.3.0] Report NinjaOne organization counts for workstations,
servers, mobile devices, network devices, end users, used cloud storage, and
ticket totals.

Environment variables:
- NINJA_ONE_CLIENT_ID (required)
- NINJA_ONE_CLIENT_SECRET (required)
- NINJA_ONE_INSTANCE (optional, defaults to "eu.ninjarmm.com")
- NINJA_ONE_SCOPE (optional, defaults to "monitoring management")
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared"))
from ninja_api import get_access_token, get_api_resource, post_api_resource


TICKET_INCLUDE_COLUMNS = [
    "id",
    "ticketId",
    "clientId",
    "organizationId",
    "status",
    "source",
]


def iter_items(response):
    if isinstance(response, list):
        return response

    if not isinstance(response, dict):
        return []

    for key in ("results", "data", "items", "rows"):
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
    value = first_value(data, paths)
    return unwrap_field_value(value)


def normalized_label(value):
    return str(value or "").strip().upper().replace("-", "_").replace(" ", "_")


def numeric_value(value):
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        normalized = value.strip().replace(",", "")
        try:
            return float(normalized)
        except ValueError:
            return 0
    return 0


def storage_gb(bytes_value):
    return round(bytes_value / 1024 / 1024 / 1024, 2)


def is_server_device(device):
    node_class = str(device.get("nodeClass", ""))
    return node_class.endswith("_SERVER")


def is_workstation_device(device):
    node_class = str(device.get("nodeClass", ""))
    return node_class.endswith("_WORKSTATION") or node_class == "MAC"


def is_android_device(device):
    node_class = str(device.get("nodeClass", "")).upper()
    os_name = str(first_value(device, (("os", "name"), ("os", "manufacturer"))) or "").upper()
    return "ANDROID" in node_class or "ANDROID" in os_name


def is_apple_mobile_device(device):
    node_class = str(device.get("nodeClass", "")).upper()
    os_name = str(first_value(device, (("os", "name"), ("os", "manufacturer"))) or "").upper()
    apple_mobile_node_class_markers = ("APPLE", "IOS", "IPAD", "IPHONE", "IPADOS", "TVOS")
    apple_mobile_os_markers = ("IOS", "IPAD", "IPHONE", "IPADOS", "TVOS")

    if is_workstation_device(device) or is_server_device(device):
        return False

    return any(marker in node_class for marker in apple_mobile_node_class_markers) or any(
        marker in os_name for marker in apple_mobile_os_markers
    )


def is_network_device(device):
    node_class = str(device.get("nodeClass", "")).upper()
    node_role = str(
        first_value(
            device,
            (
                ("nodeRole",),
                ("nodeRoleName",),
                ("role",),
                ("roleName",),
            ),
        )
        or ""
    ).upper()
    network_markers = (
        "NETWORK",
        "NMS",
        "SNMP",
        "SWITCH",
        "ROUTER",
        "FIREWALL",
        "ACCESS_POINT",
        "WIRELESS",
        "WAP",
        "PRINTER",
        "UPS",
        "NAS",
        "SAN",
    )

    return any(marker in node_class or marker in node_role for marker in network_markers)


def organization_id_from_usage(usage):
    return first_value(
        usage,
        (
            ("organizationId",),
            ("organisationId",),
            ("clientId",),
            ("references", "organization", "id"),
            ("references", "organisation", "id"),
            ("references", "client", "id"),
            ("references", "device", "organizationId"),
            ("references", "node", "organizationId"),
        ),
    )


def storage_value(usage, paths):
    return numeric_value(first_value(usage, paths))


def ticket_id(ticket):
    return first_field_value(ticket, (("id",), ("ticketId",), ("ticket", "id")))


def ticket_organization_id(ticket):
    return first_field_value(
        ticket,
        (
            ("clientId",),
            ("organizationId",),
            ("client", "id"),
            ("organization", "id"),
            ("references", "client", "id"),
            ("references", "organization", "id"),
            ("references", "device", "organizationId"),
            ("references", "node", "organizationId"),
            ("node", "organizationId"),
        ),
    )


def ticket_organization_name(ticket):
    organization = ticket.get("organization") if isinstance(ticket, dict) else None
    if isinstance(organization, str):
        return organization.strip()
    return first_field_value(
        ticket,
        (
            ("organization", "name"),
            ("organization", "displayName"),
            ("client", "name"),
            ("client", "displayName"),
            ("references", "client", "name"),
            ("references", "organization", "name"),
        ),
    )


def ticket_status(ticket):
    return normalized_label(
        first_field_value(
            ticket,
            (
                ("status", "displayName"),
                ("status", "value"),
                ("status", "name"),
                ("status",),
                ("ticket", "status"),
            ),
        )
    )


def ticket_status_parent_id(ticket):
    return numeric_value(
        first_field_value(
            ticket,
            (
                ("status", "parentId"),
                ("status", "parentStatusId"),
                ("status", "statusId"),
                ("ticket", "status", "parentId"),
            ),
        )
    )


def ticket_source(ticket):
    return normalized_label(
        first_field_value(
            ticket,
            (
                ("source", "value"),
                ("source", "name"),
                ("source",),
                ("valueSource", "source"),
                ("metadata", "source"),
                ("ticket", "source"),
            ),
        )
    )


def is_user_ticket_source(source):
    return source in {
        "USER",
        "TECHNICIAN",
        "EMAIL",
        "WEB_FORM",
        "HELP_REQUEST",
        "END_USER",
        "CONTACT",
    }


def is_automation_ticket_source(source):
    return source in {
        "AUTOMATION",
        "CONDITION",
        "ACTIVITY",
        "SCHEDULED_SCRIPT",
        "SCRIPT",
        "API",
        "SYSTEM",
        "POLICY",
        "MONITOR",
        "WEBHOOK",
    }


def is_open_ticket_status(ticket):
    parent_id = ticket_status_parent_id(ticket)
    status = ticket_status(ticket)
    return parent_id == 2000 or status in {"OPEN", "OFFEN", "WORK_IN_PROGRESS"}


def is_resolved_or_closed_ticket_status(ticket):
    parent_id = ticket_status_parent_id(ticket)
    status = ticket_status(ticket)
    return parent_id in {5000, 6000} or status in {
        "RESOLVED",
        "CLOSED",
        "GELOEST",
        "GELÖST",
        "GESCHLOSSEN",
    }


def get_optional_api_resource(paths, access_token, description):
    errors = []

    for path in paths:
        try:
            return get_api_resource(path, access_token)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path}: {exc}")

    print(
        f"Could not query {description}; continuing without that data. Tried: {'; '.join(errors)}",
        file=sys.stderr,
    )
    return []


def get_ticket_board_tickets(board_id, access_token):
    tickets = []
    last_cursor_id = None

    while True:
        json_body = {
            "pageSize": 1000,
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


def get_all_tickets(access_token):
    boards = get_optional_api_resource(
        ("/v2/ticketing/trigger/boards",),
        access_token,
        "ticket boards",
    )
    tickets = []
    seen_ticket_ids = set()

    for board in iter_items(boards):
        board_id = first_field_value(board, (("id",), ("boardId",)))
        if board_id is None:
            continue

        try:
            board_tickets = get_ticket_board_tickets(board_id, access_token)
        except Exception as exc:  # noqa: BLE001
            print(
                f"Could not query tickets for board {board_id}; skipping that board: {exc}",
                file=sys.stderr,
            )
            continue

        for ticket in board_tickets:
            current_ticket_id = ticket_id(ticket)
            if current_ticket_id is not None:
                normalized_ticket_id = str(current_ticket_id)
                if normalized_ticket_id in seen_ticket_ids:
                    continue
                seen_ticket_ids.add(normalized_ticket_id)
            tickets.append(ticket)

    return tickets


def build_summary(organizations, devices, end_users, backup_usage, tickets=()):
    summary_by_org_id = {}
    summary_by_org_name = {}

    for organization in organizations:
        entry = {
            "Name": organization["name"],
            "Workstations": 0,
            "Servers": 0,
            "AppleDevices": 0,
            "AndroidDevices": 0,
            "NetworkDevices": 0,
            "EndUsers": 0,
            "CloudStorageUsedBytes": 0,
            "TotalTickets": 0,
            "OpenTickets": 0,
            "ResolvedOrClosedTickets": 0,
            "TicketsCreatedByUser": 0,
            "TicketsCreatedByAutomation": 0,
        }
        summary_by_org_id[str(organization["id"])] = entry
        summary_by_org_name[str(organization["name"]).strip().casefold()] = entry

    for device in devices:
        organization = summary_by_org_id.get(str(device.get("organizationId")))
        if organization is None:
            continue

        if is_server_device(device):
            organization["Servers"] += 1
        elif is_workstation_device(device):
            organization["Workstations"] += 1

        if is_android_device(device):
            organization["AndroidDevices"] += 1
        elif is_apple_mobile_device(device):
            organization["AppleDevices"] += 1

        if is_network_device(device):
            organization["NetworkDevices"] += 1

    for end_user in end_users:
        organization = summary_by_org_id.get(str(end_user.get("organizationId")))
        if organization is None:
            continue

        organization["EndUsers"] += 1

    for usage in iter_items(backup_usage):
        organization = summary_by_org_id.get(str(organization_id_from_usage(usage)))
        if organization is None:
            continue

        organization["CloudStorageUsedBytes"] += storage_value(
            usage,
            (
                ("references", "backupUsage", "cloudTotalSize"),
                ("references", "backupUsage", "cloudStorageUsed"),
                ("references", "backupUsage", "cloudUsedStorage"),
                ("cloudTotalSize",),
                ("cloudStorageUsed",),
                ("cloudUsedStorage",),
            ),
        )

    seen_ticket_ids = set()
    for ticket in iter_items(tickets):
        current_ticket_id = ticket_id(ticket)
        if current_ticket_id is not None:
            normalized_ticket_id = str(current_ticket_id)
            if normalized_ticket_id in seen_ticket_ids:
                continue
            seen_ticket_ids.add(normalized_ticket_id)

        organization = summary_by_org_id.get(str(ticket_organization_id(ticket)))
        if organization is None:
            organization_name = ticket_organization_name(ticket)
            if organization_name is not None:
                organization = summary_by_org_name.get(str(organization_name).strip().casefold())
        if organization is None:
            continue

        organization["TotalTickets"] += 1

        if is_open_ticket_status(ticket):
            organization["OpenTickets"] += 1
        elif is_resolved_or_closed_ticket_status(ticket):
            organization["ResolvedOrClosedTickets"] += 1

        source = ticket_source(ticket)
        if is_user_ticket_source(source):
            organization["TicketsCreatedByUser"] += 1
        elif is_automation_ticket_source(source):
            organization["TicketsCreatedByAutomation"] += 1

    return [
        {
            "Name": entry["Name"],
            "Workstations": entry["Workstations"],
            "Servers": entry["Servers"],
            "TotalDevices": (
                entry["Workstations"]
                + entry["Servers"]
                + entry["AppleDevices"]
                + entry["AndroidDevices"]
                + entry["NetworkDevices"]
            ),
            "AppleDevices": entry["AppleDevices"],
            "AndroidDevices": entry["AndroidDevices"],
            "NetworkDevices": entry["NetworkDevices"],
            "EndUsers": entry["EndUsers"],
            "CloudStorageUsedGB": f"{storage_gb(entry['CloudStorageUsedBytes']):.2f}",
            "TotalTickets": entry["TotalTickets"],
            "OpenTickets": entry["OpenTickets"],
            "ResolvedOrClosedTickets": entry["ResolvedOrClosedTickets"],
            "TicketsCreatedByUser": entry["TicketsCreatedByUser"],
            "TicketsCreatedByAutomation": entry["TicketsCreatedByAutomation"],
        }
        for entry in summary_by_org_id.values()
    ]


def print_table(rows):
    if not rows:
        print("No rows returned.")
        return

    columns = [
        "Name",
        "TotalDevices",
        "Workstations",
        "Servers",
        "AppleDevices",
        "AndroidDevices",
        "NetworkDevices",
        "EndUsers",
        "TotalTickets",
        "OpenTickets",
        "ResolvedOrClosedTickets",
        "TicketsCreatedByUser",
        "TicketsCreatedByAutomation",
        "CloudStorageUsedGB",
    ]
    widths = {column: len(column) for column in columns}

    for row in rows:
        for column in columns:
            widths[column] = max(widths[column], len(str(row[column])))

    header = " ".join(column.ljust(widths[column]) for column in columns)
    divider = " ".join("-" * widths[column] for column in columns)
    print(header)
    print(divider)

    for row in rows:
        print(" ".join(str(row[column]).ljust(widths[column]) for column in columns))


def main():
    try:
        access_token = get_access_token()
        devices = get_api_resource("/v2/devices-detailed", access_token)
        organizations = get_api_resource("/v2/organizations-detailed", access_token)
        end_users = get_api_resource("/v2/user/end-users", access_token)
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to query NinjaOne API: {exc}", file=sys.stderr)
        return 1

    backup_usage = get_optional_api_resource(
        (
            "/v2/queries/backup/usage",
            "/v2/queries/backup-usage",
        ),
        access_token,
        "cloud backup usage",
    )
    tickets = get_all_tickets(access_token)
    summary = build_summary(organizations, devices, end_users, backup_usage, tickets)
    print_table(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
