#!/usr/bin/env python3
"""
Shared NinjaOne API authentication and JSON request helpers.

Configure credentials with NINJA_ONE_CLIENT_ID, NINJA_ONE_CLIENT_SECRET, and
optional NINJA_ONE_INSTANCE/NINJA_ONE_SCOPE environment variables.
"""

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request


NINJA_ONE_INSTANCE = os.getenv("NINJA_ONE_INSTANCE", "eu.ninjarmm.com")
NINJA_ONE_CLIENT_ID = os.getenv("NINJA_ONE_CLIENT_ID")
NINJA_ONE_CLIENT_SECRET = os.getenv("NINJA_ONE_CLIENT_SECRET")
NINJA_ONE_SCOPE = os.getenv("NINJA_ONE_SCOPE", "monitoring management")


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
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {exc.reason}: {error_body}") from exc


def get_access_token():
    auth_response = request_json(
        f"https://{NINJA_ONE_INSTANCE}/oauth/token",
        method="POST",
        headers={"Accept": "application/json"},
        form_body={
            "grant_type": "client_credentials",
            "client_id": require_env("NINJA_ONE_CLIENT_ID", NINJA_ONE_CLIENT_ID),
            "client_secret": require_env(
                "NINJA_ONE_CLIENT_SECRET",
                NINJA_ONE_CLIENT_SECRET,
            ),
            "scope": NINJA_ONE_SCOPE,
        },
    )

    access_token = auth_response.get("access_token")
    if not access_token:
        raise RuntimeError("OAuth response did not contain an access token.")

    return access_token


def get_api_resource(path, access_token):
    return request_json(
        f"https://{NINJA_ONE_INSTANCE}{path}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
    )
