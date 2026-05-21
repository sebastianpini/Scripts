#!/usr/bin/env python3
"""
Cross-platform launcher for the NinjaOne report scripts.

  python ninja.py <script> [args...]
  python ninja.py <env> <script> [args...]
  python ninja.py envs
  python ninja.py scripts

Loads env/<env>.env (default: env/default.env) into the subprocess
environment, then runs the resolved Python script with any extra args.
"""

import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
ENV_DIR = ROOT_DIR / "env"

SCRIPTS = {
    "last-login": "python/user/last_login.py",
    "org-summary": "python/organization/overview.py",
    "owner-devices": "python/device/assign_owner.py",
}

SCRIPT_DESCRIPTIONS = {
    "last-login": "Technician last login report",
    "org-summary": "Organization device summary report",
    "owner-devices": "Assign all device owners to a technician",
}


def usage():
    script_lines = "\n".join(
        f"  {name:<14} {SCRIPTS[name]:<33} {SCRIPT_DESCRIPTIONS[name]}"
        for name in SCRIPTS
    )
    env_lines = "\n".join(f"  {name}" for name in list_envs()) or "  (none — create env/default.env)"
    print(
        "Usage:\n"
        "  python ninja.py <script> [args...]\n"
        "  python ninja.py <env> <script> [args...]\n"
        "  python ninja.py envs\n"
        "  python ninja.py scripts\n"
        "\n"
        "Default customer setup:\n"
        "  Fill in env/default.env, then run scripts without an environment argument.\n"
        "\n"
        "Environments:\n"
        f"{env_lines}\n"
        "\n"
        "Scripts:\n"
        f"{script_lines}\n"
        "\n"
        "Examples:\n"
        "  python ninja.py last-login\n"
        "  python ninja.py org-summary\n"
        "  python ninja.py owner-devices\n"
        "  python ninja.py owner-devices --apply\n"
        "  python ninja.py demo1 last-login\n"
        "  python ninja.py demo2 org-summary"
    )


def list_envs():
    if not ENV_DIR.is_dir():
        return []
    return sorted(p.stem for p in ENV_DIR.glob("*.env"))


def list_scripts():
    for name in SCRIPTS:
        print(name)


def parse_env_file(path):
    """Parse a Bash-style .env file into a dict.

    Supports KEY=VALUE lines, optional surrounding single/double quotes on the
    value, '#' comments, and blank lines. Does not implement variable
    interpolation or multi-line values — keep env files simple.
    """
    values = {}
    with open(path, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            if key:
                values[key] = value
    return values


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        usage()
        return 0 if argv else 1

    if argv[0] == "envs":
        for name in list_envs():
            print(name)
        return 0

    if argv[0] == "scripts":
        list_scripts()
        return 0

    if argv[0] in SCRIPTS:
        env_name = "default"
        script_name = argv[0]
        script_args = argv[1:]
    else:
        if len(argv) < 2:
            usage()
            return 1
        env_name = argv[0]
        script_name = argv[1]
        script_args = argv[2:]

    if script_name not in SCRIPTS:
        print(f"Unknown script: {script_name}")
        print()
        print("Available scripts:")
        list_scripts()
        return 1

    env_file = ENV_DIR / f"{env_name}.env"
    if not env_file.is_file():
        print(f"Unknown environment: {env_name}")
        print()
        print(f"Expected a file at: {env_file.relative_to(ROOT_DIR)}")
        print("Create it from env/default.env, for example:")
        print(f"  cp env/default.env {env_file.relative_to(ROOT_DIR)}")
        return 1

    env = os.environ.copy()
    env.update(parse_env_file(env_file))

    script_path = ROOT_DIR / SCRIPTS[script_name]
    result = subprocess.run(
        [sys.executable, str(script_path), *script_args],
        env=env,
        cwd=ROOT_DIR,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
