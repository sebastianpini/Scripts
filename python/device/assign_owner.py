#!/usr/bin/env python3
"""
[Version 1.1.0] Assign all NinjaOne devices to a technician owner.

This script uses delegated Authorization Code Flow because setting device
ownership requires a user-authenticated token with the management scope.

Environment variables:
- NINJA_ONE_CLIENT_ID (required)
- NINJA_ONE_CLIENT_SECRET (required unless using --pkce)
- NINJA_ONE_INSTANCE (optional, defaults to "eu.ninjarmm.com")
- NINJA_ONE_SCOPE (optional, defaults to "monitoring management")
- NINJA_ONE_AUTH_CODE_SCOPE (optional, defaults to NINJA_ONE_SCOPE + offline_access)
- NINJA_ONE_REDIRECT_URI (optional, defaults to "http://localhost:8080/")
- NINJA_ONE_TOKEN_CACHE (optional, defaults to ".do_not_push/ninjaone-device-owner-token-cache.json")
"""

import argparse
import base64
import hashlib
import json
import os
import secrets
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


NINJA_ONE_INSTANCE = os.getenv("NINJA_ONE_INSTANCE", "eu.ninjarmm.com")
NINJA_ONE_CLIENT_ID = os.getenv("NINJA_ONE_CLIENT_ID")
NINJA_ONE_CLIENT_SECRET = os.getenv("NINJA_ONE_CLIENT_SECRET")
NINJA_ONE_SCOPE = os.getenv("NINJA_ONE_SCOPE", "monitoring management")
DEFAULT_AUTH_CODE_SCOPE = (
    NINJA_ONE_SCOPE
    if "offline_access" in NINJA_ONE_SCOPE.split()
    else f"{NINJA_ONE_SCOPE} offline_access"
)
NINJA_ONE_AUTH_CODE_SCOPE = os.getenv("NINJA_ONE_AUTH_CODE_SCOPE", DEFAULT_AUTH_CODE_SCOPE)
NINJA_ONE_REDIRECT_URI = os.getenv(
    "NINJA_ONE_REDIRECT_URI", "http://localhost:8080/"
)
ROOT_DIR = Path(__file__).resolve().parents[2]
NINJA_ONE_TOKEN_CACHE = Path(
    os.getenv(
        "NINJA_ONE_TOKEN_CACHE",
        str(ROOT_DIR / ".do_not_push" / "token.json"),
    )
)

PAGE_SIZE = 1000
DEFAULT_OWNER_NAME = "Sebastian Pini"
ACCESS_TOKEN_EXPIRY_SAFETY_SECONDS = 60


@dataclass
class AssignmentPlan:
    to_update: list
    already_owned: list


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    server_version = "NinjaOneOAuthCallback/1.0"

    def log_message(self, format, *args):  # noqa: A002
        return

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        expected_path = self.server.expected_path

        if parsed.path != expected_path:
            self.send_error(404)
            return

        query = urllib.parse.parse_qs(parsed.query)
        state = single_value(query, "state")
        if state != self.server.expected_state:
            self.send_error(400, "Invalid OAuth state")
            return

        error = single_value(query, "error")
        if error:
            self.server.oauth_error = error
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Authorization failed. You can close this window.")
            return

        code = single_value(query, "code")
        if not code:
            self.send_error(400, "Missing authorization code")
            return

        self.server.authorization_code = code
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Authorization complete. You can close this window.")

        threading.Thread(target=self.server.shutdown, daemon=True).start()


def single_value(query, key):
    values = query.get(key)
    if not values:
        return None
    return values[0]


def require_env(name, value):
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


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
            response_body = response.read().decode("utf-8", errors="replace")
            if not response_body.strip():
                return {}
            return json.loads(response_body)
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {exc.reason}: {error_body}") from exc


# ---------------------------------------------------------------------------
# Delegated OAuth token cache
#
# The first interactive login uses Authorization Code Flow and asks NinjaOne for
# offline_access. That scope is what lets NinjaOne return a refresh_token.
#
# Later runs do this, in order:
# 1. Reuse the cached access_token if it is still safely before expires_at.
# 2. If the access token is expired, exchange the cached refresh_token for a new
#    access_token.
# 3. Save the refreshed response back to disk. If NinjaOne rotates/slides the
#    refresh token, the new refresh_token replaces the old one. If the response
#    does not include a new refresh_token, the existing one is kept.
# 4. Only fall back to browser login when the cache is missing, expired without
#    a refresh token, invalid for this API app/instance, or rejected by NinjaOne.
#
# The cache is local and intentionally stored under .do_not_push by default.
# Treat it like a password: a refresh token can mint new access tokens until it
# expires or is revoked.
# ---------------------------------------------------------------------------


def token_cache_context(args):
    return {
        "instance": NINJA_ONE_INSTANCE,
        "client_id": require_env("NINJA_ONE_CLIENT_ID", NINJA_ONE_CLIENT_ID),
        "redirect_uri": args.redirect_uri,
        "scope": NINJA_ONE_AUTH_CODE_SCOPE,
        "pkce": bool(args.pkce),
    }


def read_token_cache(cache_path):
    path = Path(cache_path)
    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as cache_file:
            cache = json.load(cache_file)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(cache, dict):
        return None
    return cache


def write_token_cache(cache_path, token_response, args, now=None, existing_refresh_token=None):
    access_token = token_response.get("access_token")
    if not access_token:
        raise RuntimeError("OAuth response did not contain an access token.")

    refresh_token = token_response.get("refresh_token") or existing_refresh_token
    expires_in = int(token_response.get("expires_in") or 3600)
    current_time = time.time() if now is None else now
    cache = {
        **token_cache_context(args),
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": current_time + expires_in,
        "token_type": token_response.get("token_type", "Bearer"),
        "returned_scope": token_response.get("scope"),
    }

    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as cache_file:
        json.dump(cache, cache_file, indent=2, sort_keys=True)
        cache_file.write("\n")

    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def remove_token_cache(cache_path):
    try:
        Path(cache_path).unlink()
    except FileNotFoundError:
        pass


def token_cache_matches(cache, args):
    expected = token_cache_context(args)
    return all(cache.get(key) == value for key, value in expected.items())


def cached_access_token_is_valid(cache, now=None):
    current_time = time.time() if now is None else now
    expires_at = float(cache.get("expires_at") or 0)
    return bool(cache.get("access_token")) and (
        expires_at - ACCESS_TOKEN_EXPIRY_SAFETY_SECONDS > current_time
    )


def validate_token_response(token_response):
    access_token = token_response.get("access_token")
    if not access_token:
        raise RuntimeError("OAuth response did not contain an access token.")
    return access_token


def refresh_access_token(refresh_token, args):
    form_body = {
        "grant_type": "refresh_token",
        "client_id": require_env("NINJA_ONE_CLIENT_ID", NINJA_ONE_CLIENT_ID),
        "refresh_token": refresh_token,
        "scope": NINJA_ONE_AUTH_CODE_SCOPE,
    }

    if not args.pkce:
        form_body["client_secret"] = require_env(
            "NINJA_ONE_CLIENT_SECRET", NINJA_ONE_CLIENT_SECRET
        )

    token_response = request_json(
        f"https://{NINJA_ONE_INSTANCE}/ws/oauth/token",
        method="POST",
        headers={"Accept": "application/json"},
        form_body=form_body,
    )
    validate_token_response(token_response)
    return token_response


def get_api_resource(path, access_token):
    return request_json(
        f"https://{NINJA_ONE_INSTANCE}{path}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
    )


def post_api_resource(path, access_token):
    return request_json(
        f"https://{NINJA_ONE_INSTANCE}{path}",
        method="POST",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
    )


def base64_urlencode(raw_bytes):
    return base64.urlsafe_b64encode(raw_bytes).decode("ascii").rstrip("=")


def generate_pkce_pair():
    verifier = base64_urlencode(secrets.token_bytes(32))
    challenge = base64_urlencode(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def build_authorization_url(
    instance,
    client_id,
    redirect_uri,
    scope,
    state,
    code_challenge=None,
):
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
    }
    if code_challenge:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"

    return f"https://{instance}/ws/oauth/authorize?{urllib.parse.urlencode(params)}"


def exchange_authorization_code(code, redirect_uri, code_verifier=None):
    form_body = {
        "grant_type": "authorization_code",
        "client_id": require_env("NINJA_ONE_CLIENT_ID", NINJA_ONE_CLIENT_ID),
        "code": code,
        "redirect_uri": redirect_uri,
    }

    if code_verifier:
        form_body["code_verifier"] = code_verifier
    else:
        form_body["client_secret"] = require_env(
            "NINJA_ONE_CLIENT_SECRET", NINJA_ONE_CLIENT_SECRET
        )

    auth_response = request_json(
        f"https://{NINJA_ONE_INSTANCE}/ws/oauth/token",
        method="POST",
        headers={"Accept": "application/json"},
        form_body=form_body,
    )

    validate_token_response(auth_response)
    return auth_response


def listen_for_authorization_code(redirect_uri, expected_state, authorization_url):
    parsed = urllib.parse.urlparse(redirect_uri)
    host = parsed.hostname
    if host not in ("localhost", "127.0.0.1"):
        raise RuntimeError(
            "Local callback capture requires a localhost redirect URI. "
            "Use --auth-code for non-local redirects."
        )

    port = parsed.port
    if port is None:
        raise RuntimeError("Redirect URI must include a localhost port.")

    server = HTTPServer((host, port), OAuthCallbackHandler)
    server.expected_state = expected_state
    server.expected_path = parsed.path or "/"
    server.authorization_code = None
    server.oauth_error = None
    server.timeout = 1

    print("Open this URL and sign in as the delegated technician:")
    print(authorization_url)
    print()
    webbrowser.open(authorization_url)

    deadline = time.monotonic() + 300
    while (
        time.monotonic() < deadline
        and not server.authorization_code
        and not server.oauth_error
    ):
        server.handle_request()

    if server.oauth_error:
        raise RuntimeError(f"Authorization failed: {server.oauth_error}")
    if not server.authorization_code:
        raise RuntimeError("Timed out waiting for authorization callback.")
    return server.authorization_code


def get_delegated_access_token(args):
    cache_path = Path(args.token_cache)
    if args.reset_token_cache:
        remove_token_cache(cache_path)

    if not args.no_token_cache and not args.auth_code:
        cache = read_token_cache(cache_path)
        if cache and token_cache_matches(cache, args):
            if cached_access_token_is_valid(cache):
                print(f"Using cached NinjaOne access token from {cache_path}.")
                return cache["access_token"]

            refresh_token = cache.get("refresh_token")
            if refresh_token:
                try:
                    print(f"Refreshing NinjaOne access token using {cache_path}.")
                    token_response = refresh_access_token(refresh_token, args)
                    write_token_cache(
                        cache_path,
                        token_response,
                        args,
                        existing_refresh_token=refresh_token,
                    )
                    return token_response["access_token"]
                except Exception as exc:  # noqa: BLE001
                    print(
                        f"Cached refresh token was rejected; starting browser login. {exc}",
                        file=sys.stderr,
                    )

    state = secrets.token_urlsafe(24)
    code_verifier = None
    code_challenge = None

    if args.pkce:
        code_verifier, code_challenge = generate_pkce_pair()

    if args.auth_code:
        code = args.auth_code
    else:
        authorization_url = build_authorization_url(
            NINJA_ONE_INSTANCE,
            require_env("NINJA_ONE_CLIENT_ID", NINJA_ONE_CLIENT_ID),
            args.redirect_uri,
            NINJA_ONE_AUTH_CODE_SCOPE,
            state,
            code_challenge=code_challenge,
        )
        code = listen_for_authorization_code(
            args.redirect_uri,
            state,
            authorization_url,
        )

    token_response = exchange_authorization_code(code, args.redirect_uri, code_verifier)
    if not args.no_token_cache:
        write_token_cache(cache_path, token_response, args)
        if token_response.get("refresh_token"):
            print(f"Saved NinjaOne refresh token cache to {cache_path}.")
        else:
            print(
                "NinjaOne did not return a refresh token. Confirm that the API app "
                "has Refresh Token grant enabled and that offline_access is in "
                "NINJA_ONE_AUTH_CODE_SCOPE.",
                file=sys.stderr,
            )

    return token_response["access_token"]


def iter_items(response):
    if isinstance(response, list):
        return response

    if not isinstance(response, dict):
        return []

    for key in ("results", "data", "items", "rows", "devices", "users"):
        value = response.get(key)
        if isinstance(value, list):
            return value

    return []


def load_paginated(path, access_token):
    items = []
    after = None

    while True:
        params = {"pageSize": PAGE_SIZE}
        if after is not None:
            params["after"] = after

        separator = "&" if "?" in path else "?"
        response = get_api_resource(
            f"{path}{separator}{urllib.parse.urlencode(params)}", access_token
        )
        page_items = list(iter_items(response))
        items.extend(page_items)

        if len(page_items) < PAGE_SIZE:
            break

        after = page_items[-1].get("id")
        if after is None:
            break

    return items


def display_name(device):
    for key in ("displayName", "systemName", "dnsName", "netbiosName"):
        value = device.get(key)
        if value:
            return str(value)
    return f"Device #{device.get('id', 'unknown')}"


def user_name(user):
    first_name = (user.get("firstName") or "").strip()
    last_name = (user.get("lastName") or "").strip()
    full_name = f"{first_name} {last_name}".strip()
    if full_name:
        return full_name
    return user.get("email") or f"User #{user.get('id', 'unknown')}"


def normalize_text(value):
    return " ".join(str(value or "").casefold().split())


def build_users_by_uid(users):
    users_by_uid = {}
    for user in users:
        uid = user.get("uid")
        if uid:
            users_by_uid[normalize_text(uid)] = user
    return users_by_uid


def format_owner_reference(owner_uid, users_by_uid):
    if not owner_uid:
        return "(none)"

    owner = users_by_uid.get(normalize_text(owner_uid))
    if not owner:
        return str(owner_uid)

    return f"{user_name(owner)} ({owner_uid})"


def find_owner_user(users, owner_name=None, owner_email=None, owner_uid=None):
    if owner_uid:
        matches = [
            user
            for user in users
            if normalize_text(user.get("uid")) == normalize_text(owner_uid)
        ]
        description = f"uid {owner_uid}"
    elif owner_email:
        matches = [
            user
            for user in users
            if normalize_text(user.get("email")) == normalize_text(owner_email)
        ]
        description = f"email {owner_email}"
    else:
        owner_name = owner_name or DEFAULT_OWNER_NAME
        matches = [
            user
            for user in users
            if normalize_text(user_name(user)) == normalize_text(owner_name)
        ]
        description = f"name {owner_name}"

    if not matches:
        raise RuntimeError(f"No technician matched {description}.")
    if len(matches) > 1:
        options = ", ".join(
            f"{user_name(user)} <{user.get('email', '')}>" for user in matches
        )
        raise RuntimeError(f"More than one technician matched {description}: {options}")

    owner = matches[0]
    if not owner.get("uid"):
        raise RuntimeError(f"Matched technician {user_name(owner)} does not have a uid.")

    return owner


def build_assignment_plan(devices, owner_uid):
    to_update = []
    already_owned = []

    for device in devices:
        assigned_owner_uid = device.get("assignedOwnerUid") or device.get("assignedUserUid")
        if normalize_text(assigned_owner_uid) == normalize_text(owner_uid):
            already_owned.append(device)
        else:
            to_update.append(device)

    return AssignmentPlan(
        to_update=to_update,
        already_owned=already_owned,
    )


def set_device_owner(device_id, owner_uid, access_token):
    encoded_owner_uid = urllib.parse.quote(str(owner_uid), safe="")
    post_api_resource(f"/v2/device/{device_id}/owner/{encoded_owner_uid}", access_token)


def print_plan(plan, owner, users_by_uid=None):
    users_by_uid = users_by_uid or {}
    print(f"Owner: {user_name(owner)} <{owner.get('email', '')}> ({owner['uid']})")
    print(f"Devices to update: {len(plan.to_update)}")
    print(f"Devices already assigned to owner: {len(plan.already_owned)}")

    if plan.to_update:
        print()
        print("Devices to update:")
        for device in plan.to_update:
            assigned_owner = format_owner_reference(
                device.get("assignedOwnerUid") or device.get("assignedUserUid"),
                users_by_uid,
            )
            print(
                f"- {device.get('id')} {display_name(device)} "
                f"[{device.get('nodeClass', 'unknown')}] current owner: {assigned_owner}"
            )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Assign all NinjaOne devices to a technician owner. "
            "Runs as a dry run unless --apply is provided."
        )
    )
    owner_group = parser.add_mutually_exclusive_group()
    owner_group.add_argument(
        "--owner-name",
        default=DEFAULT_OWNER_NAME,
        help=f"Technician full name to assign as owner. Defaults to {DEFAULT_OWNER_NAME!r}.",
    )
    owner_group.add_argument("--owner-email", help="Technician email to assign as owner.")
    owner_group.add_argument("--owner-uid", help="Technician user uid to assign as owner.")
    parser.add_argument(
        "--redirect-uri",
        default=NINJA_ONE_REDIRECT_URI,
        help=f"OAuth redirect URI registered in NinjaOne. Defaults to {NINJA_ONE_REDIRECT_URI!r}.",
    )
    parser.add_argument(
        "--auth-code",
        help="Use an already captured OAuth authorization code instead of opening a browser.",
    )
    parser.add_argument(
        "--pkce",
        action="store_true",
        help="Use Authorization Code Flow with PKCE for native apps.",
    )
    parser.add_argument(
        "--token-cache",
        default=str(NINJA_ONE_TOKEN_CACHE),
        help=f"Path for the local delegated OAuth token cache. Defaults to {NINJA_ONE_TOKEN_CACHE}.",
    )
    parser.add_argument(
        "--no-token-cache",
        action="store_true",
        help="Do not read or write the local OAuth token cache.",
    )
    parser.add_argument(
        "--reset-token-cache",
        action="store_true",
        help="Delete the local OAuth token cache before authenticating.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually assign owners. Without this, only prints the planned changes.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        access_token = get_delegated_access_token(args)
        users = iter_items(get_api_resource("/v2/users?includeRoles=true", access_token))
        users_by_uid = build_users_by_uid(users)
        technicians = [user for user in users if user.get("userType") == "TECHNICIAN"]
        owner = find_owner_user(
            technicians,
            owner_name=args.owner_name,
            owner_email=args.owner_email,
            owner_uid=args.owner_uid,
        )
        devices = load_paginated("/v2/devices-detailed", access_token)
        plan = build_assignment_plan(devices, owner["uid"])
        print_plan(plan, owner, users_by_uid)

        if not args.apply:
            print()
            print("Dry run only. Re-run with --apply to assign the listed devices.")
            return 0

        print()
        for device in plan.to_update:
            set_device_owner(device["id"], owner["uid"], access_token)
            print(f"Updated {device.get('id')} {display_name(device)}")

        print(f"Done. Updated {len(plan.to_update)} device(s).")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to assign NinjaOne device owners: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
