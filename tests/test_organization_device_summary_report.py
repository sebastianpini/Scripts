#!/usr/bin/env python3

import importlib.util
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT_DIR / "python/organization/overview.py"


def load_module():
    spec = importlib.util.spec_from_file_location("overview", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OrganizationDeviceSummaryReportTests(unittest.TestCase):
    def test_build_summary_counts_ticket_statuses_and_creation_sources(self):
        module = load_module()
        organizations = [
            {"id": 10, "name": "Example Org"},
            {"id": 20, "name": "Other Org"},
        ]
        tickets = [
            {"id": 1, "clientId": 10, "status": "OPEN", "source": "END_USER"},
            {"id": 2, "clientId": 10, "status": "RESOLVED", "source": "CONDITION"},
            {"id": 3, "clientId": 10, "status": "CLOSED", "source": "SCHEDULED_SCRIPT"},
            {"id": 4, "clientId": 10, "status": "WAITING", "source": "TECHNICIAN"},
            {"id": 5, "clientId": 20, "status": "OPEN", "source": "EMAIL"},
        ]

        summary = module.build_summary(organizations, [], [], [], tickets)

        self.assertEqual(
            summary[0],
            {
                "Name": "Example Org",
                "Workstations": 0,
                "Servers": 0,
                "TotalDevices": 0,
                "AppleDevices": 0,
                "AndroidDevices": 0,
                "NetworkDevices": 0,
                "EndUsers": 0,
                "CloudStorageUsedGB": "0.00",
                "TotalTickets": 4,
                "OpenTickets": 1,
                "ResolvedOrClosedTickets": 2,
                "TicketsCreatedByUser": 2,
                "TicketsCreatedByAutomation": 2,
            },
        )

    def test_build_summary_matches_ticket_board_rows_by_organization_name_and_parent_status(self):
        module = load_module()
        organizations = [{"id": 10, "name": "Example Org"}]
        tickets = [
            {
                "id": 1,
                "organization": "Example Org",
                "status": {"statusId": 2000, "displayName": "Offen", "parentId": 2000},
                "source": "CONDITION",
            },
            {
                "id": 2,
                "organization": "Example Org",
                "status": {"statusId": 6000, "displayName": "Closed", "parentId": 6000},
                "source": "TECHNICIAN",
            },
            {
                "id": 3,
                "organization": "Example Org",
                "status": {"statusId": 1000, "displayName": "New", "parentId": 1000},
                "source": "ACTIVITY",
            },
        ]

        summary = module.build_summary(organizations, [], [], [], tickets)

        self.assertEqual(summary[0]["TotalTickets"], 3)
        self.assertEqual(summary[0]["OpenTickets"], 1)
        self.assertEqual(summary[0]["ResolvedOrClosedTickets"], 1)
        self.assertEqual(summary[0]["TicketsCreatedByUser"], 1)
        self.assertEqual(summary[0]["TicketsCreatedByAutomation"], 2)

    def test_get_all_tickets_pages_boards_and_deduplicates_ticket_ids(self):
        module = load_module()
        calls = []

        def fake_get_api_resource(path, access_token):
            self.assertEqual(access_token, "token")
            if path == "/v2/ticketing/trigger/boards":
                return [{"id": 100}, {"id": 200}]
            raise AssertionError(f"unexpected GET path: {path}")

        def fake_post_api_resource(path, access_token, json_body=None):
            calls.append((path, access_token, json_body))
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
                    "data": [{"id": 1, "clientId": 10}, {"id": 2, "clientId": 10}],
                    "metadata": {"lastCursorId": 2},
                }
            if path == "/v2/ticketing/trigger/board/100/run" and json_body == second_page_body:
                return {"data": [{"id": 3, "clientId": 10}], "metadata": {}}
            if path == "/v2/ticketing/trigger/board/200/run" and json_body == first_page_body:
                return {"data": [{"id": 2, "clientId": 10}, {"id": 4, "clientId": 20}]}
            raise AssertionError(f"unexpected POST call: {path} {json_body}")

        module.get_api_resource = fake_get_api_resource
        module.post_api_resource = fake_post_api_resource

        tickets = module.get_all_tickets("token")

        self.assertEqual([ticket["id"] for ticket in tickets], [1, 2, 3, 4])
        self.assertEqual(len(calls), 3)


if __name__ == "__main__":
    unittest.main()
