#!/usr/bin/env python3

import importlib.util
import io
import tempfile
import time
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT_DIR / "python/device/assign_owner.py"


def load_module():
    spec = importlib.util.spec_from_file_location("assign_owner", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AssignDeviceOwnerTests(unittest.TestCase):
    def test_find_owner_user_by_name_returns_matching_technician_uid(self):
        module = load_module()
        users = [
            {
                "id": 101,
                "uid": "11111111-1111-1111-1111-111111111111",
                "firstName": "Sebastian",
                "lastName": "Pini",
                "email": "sebastian@example.test",
                "userType": "TECHNICIAN",
            }
        ]

        owner = module.find_owner_user(users, owner_name="sebastian pini")

        self.assertEqual(owner["uid"], "11111111-1111-1111-1111-111111111111")

    def test_find_owner_user_rejects_ambiguous_names(self):
        module = load_module()
        users = [
            {
                "uid": "11111111-1111-1111-1111-111111111111",
                "firstName": "Sebastian",
                "lastName": "Pini",
                "email": "sebastian.one@example.test",
            },
            {
                "uid": "22222222-2222-2222-2222-222222222222",
                "firstName": "Sebastian",
                "lastName": "Pini",
                "email": "sebastian.two@example.test",
            },
        ]

        with self.assertRaisesRegex(RuntimeError, "More than one technician matched"):
            module.find_owner_user(users, owner_name="sebastian pini")

    def test_build_assignment_plan_changes_every_device_not_already_owned(self):
        module = load_module()
        devices = [
            {
                "id": 1,
                "displayName": "iPhone",
                "nodeClass": "APPLE_IOS",
                "assignedOwnerUid": None,
            },
            {
                "id": 2,
                "displayName": "Android",
                "nodeClass": "ANDROID",
                "assignedOwnerUid": "target-owner",
            },
            {
                "id": 3,
                "displayName": "MacBook",
                "nodeClass": "MAC",
                "assignedOwnerUid": None,
            },
            {
                "id": 4,
                "displayName": "Windows Server",
                "nodeClass": "WINDOWS_SERVER",
                "assignedOwnerUid": "other-owner",
            },
        ]

        plan = module.build_assignment_plan(devices, "target-owner")

        self.assertEqual([entry["id"] for entry in plan.to_update], [1, 3, 4])
        self.assertEqual([entry["id"] for entry in plan.already_owned], [2])

    def test_print_plan_shows_current_owner_name_before_uuid(self):
        module = load_module()
        plan = module.AssignmentPlan(
            to_update=[
                {
                    "id": 10,
                    "displayName": "MacBook",
                    "nodeClass": "MAC",
                    "assignedOwnerUid": "22222222-2222-2222-2222-222222222222",
                }
            ],
            already_owned=[],
        )
        owner = {
            "uid": "11111111-1111-1111-1111-111111111111",
            "firstName": "Sebastian",
            "lastName": "Pini",
            "email": "sebastian@example.test",
        }
        users_by_uid = {
            "22222222-2222-2222-2222-222222222222": {
                "uid": "22222222-2222-2222-2222-222222222222",
                "firstName": "Alex",
                "lastName": "Owner",
                "email": "alex@example.test",
            }
        }
        output = io.StringIO()

        with redirect_stdout(output):
            module.print_plan(plan, owner, users_by_uid)

        self.assertIn(
            "current owner: Alex Owner (22222222-2222-2222-2222-222222222222)",
            output.getvalue(),
        )

    def test_get_delegated_access_token_reuses_unexpired_cached_access_token(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "token-cache.json"
            args = Namespace(
                auth_code=None,
                no_token_cache=False,
                pkce=False,
                redirect_uri="http://localhost:8080/",
                reset_token_cache=False,
                token_cache=str(cache_path),
            )
            module.NINJA_ONE_CLIENT_ID = "client-1"
            module.NINJA_ONE_INSTANCE = "eu.ninjarmm.com"
            module.NINJA_ONE_AUTH_CODE_SCOPE = "monitoring management offline_access"
            module.write_token_cache(
                cache_path,
                {
                    "access_token": "cached-access",
                    "refresh_token": "cached-refresh",
                    "expires_in": 3600,
                    "scope": "monitoring management offline_access",
                },
                args,
                now=time.time(),
            )

            access_token = module.get_delegated_access_token(args)

            self.assertEqual(access_token, "cached-access")

    def test_get_delegated_access_token_refreshes_expired_cache_and_rotates_refresh_token(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "token-cache.json"
            args = Namespace(
                auth_code=None,
                no_token_cache=False,
                pkce=False,
                redirect_uri="http://localhost:8080/",
                reset_token_cache=False,
                token_cache=str(cache_path),
            )
            module.NINJA_ONE_CLIENT_ID = "client-1"
            module.NINJA_ONE_CLIENT_SECRET = "secret-1"
            module.NINJA_ONE_INSTANCE = "eu.ninjarmm.com"
            module.NINJA_ONE_AUTH_CODE_SCOPE = "monitoring management offline_access"
            module.write_token_cache(
                cache_path,
                {
                    "access_token": "expired-access",
                    "refresh_token": "old-refresh",
                    "expires_in": -10,
                    "scope": "monitoring management offline_access",
                },
                args,
                now=time.time(),
            )
            calls = []

            def fake_request_json(url, method="GET", headers=None, form_body=None):
                calls.append((url, method, form_body))
                return {
                    "access_token": "refreshed-access",
                    "refresh_token": "new-refresh",
                    "expires_in": 3600,
                    "scope": "monitoring management offline_access",
                }

            module.request_json = fake_request_json

            access_token = module.get_delegated_access_token(args)
            refreshed_cache = module.read_token_cache(cache_path)

            self.assertEqual(access_token, "refreshed-access")
            self.assertEqual(calls[0][2]["grant_type"], "refresh_token")
            self.assertEqual(calls[0][2]["refresh_token"], "old-refresh")
            self.assertEqual(refreshed_cache["refresh_token"], "new-refresh")

    def test_write_token_cache_preserves_existing_refresh_token_when_refresh_response_omits_one(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "token-cache.json"
            args = Namespace(
                pkce=False,
                redirect_uri="http://localhost:8080/",
            )
            module.NINJA_ONE_CLIENT_ID = "client-1"
            module.NINJA_ONE_INSTANCE = "eu.ninjarmm.com"
            module.NINJA_ONE_AUTH_CODE_SCOPE = "monitoring management offline_access"

            module.write_token_cache(
                cache_path,
                {
                    "access_token": "new-access",
                    "expires_in": 3600,
                    "scope": "monitoring management offline_access",
                },
                args,
                existing_refresh_token="still-valid-refresh",
            )

            cached = module.read_token_cache(cache_path)

            self.assertEqual(cached["refresh_token"], "still-valid-refresh")


if __name__ == "__main__":
    unittest.main()
