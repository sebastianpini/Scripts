# Scripts

A curated list of useful scripts. This README is the customer entry point for setup and common usage. Detailed script documentation uses descriptive filenames so editor tabs are easy to tell apart.

## Quick Start For Customers

Most customers only query one NinjaOne environment. Store those credentials in `env/default.env` and run scripts without an environment argument.

Create your local env file from the committed template:

```bash
cp env/example.env env/default.env
```

Fill `env/default.env` with your NinjaOne API values:

```bash
NINJA_ONE_INSTANCE=eu.ninjarmm.com
NINJA_ONE_CLIENT_ID=
NINJA_ONE_CLIENT_SECRET=
NINJA_ONE_SCOPE="monitoring management"
```

Then run the reports:

```bash
./ninja last-login
./ninja no-login --days 14
./ninja org-summary
```

Do not put API credentials in `~/.zshrc` or paste them into shell history. Real `env/*.env` files are ignored by git.

## Multiple Environments

Ninja employees or testers can keep one env file per NinjaOne environment:

```bash
cp env/example.env env/internal-testing.env
cp env/example.env env/demo-eu.env
cp env/example.env env/demo-ca.env
```

Run against a specific environment by passing it before the script name:

```bash
./ninja demo-eu last-login
./ninja demo-ca org-summary
./ninja internal-testing no-login --days 14
```

The launcher also supports these short aliases:

```text
internal-testing, internal, it
demo-eu, eu
demo-ca, ca
```

And these script names:

```text
last-login
no-login
org-summary
```

## PowerShell

### Winget machine install
Installs a Winget package in machine scope under SYSTEM, with RMM-friendly logging and optional exact-version install.

- Language: PowerShell
- Path: `scripts/powershell/winget-machine-install/`
- Docs: [`WINGET_MACHINE_INSTALL.md`](scripts/powershell/winget-machine-install/WINGET_MACHINE_INSTALL.md)
- Usage: `powershell.exe -ExecutionPolicy Bypass -File scripts/powershell/winget-machine-install/winget-machine-install.ps1 -Id "Microsoft.PowerToys"`
- Prereqs: Winget (App Installer)

## Python

### NinjaOne technician no-login-for-X-days report
Lists NinjaOne technicians who have not logged into the Ninja platform during the last N full days, using local midnight as the cutoff.

- Language: Python
- Path: `scripts/python/ninjaone-technician-inactive-login-report/`
- Docs: [`TECHNICIAN_LOGIN_REPORTS.md`](scripts/python/ninjaone-technician-inactive-login-report/TECHNICIAN_LOGIN_REPORTS.md)
- Usage: `./ninja no-login --days 14`
- Prereqs: Python 3, NinjaOne OAuth client credentials in `env/default.env`

### NinjaOne technician last login report
Lists NinjaOne technicians sorted descending by latest platform login activity.

- Language: Python
- Path: `scripts/python/ninjaone-technician-inactive-login-report/`
- Docs: [`TECHNICIAN_LOGIN_REPORTS.md`](scripts/python/ninjaone-technician-inactive-login-report/TECHNICIAN_LOGIN_REPORTS.md)
- Usage: `./ninja last-login`
- Prereqs: Python 3, NinjaOne OAuth client credentials in `env/default.env`

### NinjaOne organization device summary report
Reports organization counts for total devices, workstations, servers, Apple mobile devices, Android devices, network devices, end users, and used cloud backup storage.

- Language: Python
- Path: `scripts/python/ninjaone-organization-device-summary-report/`
- Docs: [`ORGANIZATION_DEVICE_SUMMARY.md`](scripts/python/ninjaone-organization-device-summary-report/ORGANIZATION_DEVICE_SUMMARY.md)
- Usage: `./ninja org-summary`
- Prereqs: Python 3, NinjaOne OAuth client credentials in `env/default.env`

### Shared NinjaOne Python helper
Provides common NinjaOne OAuth and JSON request helpers used by the Python NinjaOne reports.

- Language: Python
- Path: `scripts/python/_shared/ninja_api.py`
- Docs: [`NINJAONE_SHARED_HELPER.md`](scripts/python/_shared/NINJAONE_SHARED_HELPER.md)

## No Liability / No Warranty
These scripts are provided as-is, without warranty of any kind, express or implied. Use them at your own risk and validate them in a safe test environment before using them in production. The author and contributors are not liable for any damages, data loss, service disruption, security issue, or other consequence resulting from use, misuse, or inability to use these scripts.
