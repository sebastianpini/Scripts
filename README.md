# Scripts

A curated list of useful scripts. This README is the customer entry point for setup and common usage. Detailed script documentation uses descriptive filenames so editor tabs are easy to tell apart.

## How credentials work

Scripts read NinjaOne credentials from environment variables (`NINJA_ONE_CLIENT_ID`, `NINJA_ONE_CLIENT_SECRET`, etc.). The `ninja.py` launcher loads those variables from a local `env/*.env` file before running the script — so you never have to set them in your shell manually. Running a script directly skips the launcher and reads from whatever environment variables are already set in your shell.

## Quick Start For Customers

Most customers only query one NinjaOne environment. Open `env/default.env` and fill in your NinjaOne API credentials, then run the reports:

```bash
python ninja.py last-login
python ninja.py org-summary
python ninja.py owner-devices
```

On macOS/Linux you can also run `./ninja.py last-login` once you've made the file executable (`chmod +x ninja.py`). On Windows the `python ninja.py …` form is the standard way.

Do not put API credentials in `~/.zshrc` or paste them into shell history. Real `env/*.env` files are ignored by git.

## Multiple Environments

To query a different NinjaOne environment, create a named env file and pass the name before the script:

```bash
cp env/default.env env/demo1.env   # fill in demo1 credentials
cp env/default.env env/demo2.env   # fill in demo2 credentials
```

```bash
python ninja.py demo1 last-login
python ninja.py demo2 org-summary
```

Available script names:

```text
last-login     Technician last login report
org-summary    Organization device summary report
owner-devices  Assign all device owners to a technician
```

## PowerShell

### Winget machine install
Installs a Winget package in machine scope under SYSTEM, with RMM-friendly logging and optional exact-version install.

- Language: PowerShell
- Path: `powershell/winget-machine-install/`
- Docs: [`WINGET_MACHINE_INSTALL.md`](powershell/winget-machine-install/WINGET_MACHINE_INSTALL.md)
- Usage: `powershell.exe -ExecutionPolicy Bypass -File powershell/winget-machine-install/winget-machine-install.ps1 -Id "Microsoft.PowerToys"`
- Prereqs: Winget (App Installer)

## Python

### NinjaOne technician last login report
Lists NinjaOne technicians sorted descending by latest platform login activity.

- Language: Python
- Path: `python/user/`
- Docs: [`LAST_LOGIN.md`](python/user/LAST_LOGIN.md)
- Usage: `python ninja.py last-login`
- Prereqs: Python 3, NinjaOne OAuth client credentials in `env/default.env`

### NinjaOne organization device summary report
Reports organization counts for total devices, workstations, servers, Apple mobile devices, Android devices, network devices, end users, and used cloud backup storage.

- Language: Python
- Path: `python/organization/`
- Docs: [`OVERVIEW.md`](python/organization/OVERVIEW.md)
- Usage: `python ninja.py org-summary`
- Prereqs: Python 3, NinjaOne OAuth client credentials in `env/default.env`

### NinjaOne device owner assignment
Assigns all devices to a technician owner using delegated Authorization Code Flow. It runs as a dry run unless `--apply` is passed.

- Language: Python
- Path: `python/device/`
- Docs: [`ASSIGN_OWNER.md`](python/device/ASSIGN_OWNER.md)
- Usage: `python ninja.py owner-devices` then `python ninja.py owner-devices --apply`
- Prereqs: Python 3, NinjaOne OAuth web or native app credentials in `env/default.env`, `management` scope, and a registered redirect URI
- Token cache: stores delegated access/refresh tokens in `.do_not_push/ninjaone-device-owner-token-cache.json` by default so repeated runs can refresh without another browser login

### Shared NinjaOne Python helper
Provides common NinjaOne OAuth and JSON request helpers used by the Python NinjaOne reports.

- Language: Python
- Path: `python/_shared/ninja_api.py`
- Docs: [`NINJAONE_SHARED_HELPER.md`](python/_shared/NINJAONE_SHARED_HELPER.md)

## No Liability / No Warranty
These scripts are provided as-is, without warranty of any kind, express or implied. Use them at your own risk and validate them in a safe test environment before using them in production. The author and contributors are not liable for any damages, data loss, service disruption, security issue, or other consequence resulting from use, misuse, or inability to use these scripts.
