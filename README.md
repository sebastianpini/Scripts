# Scripts

A curated list of useful scripts in this repo. For full details, see each script's README in its folder.

## Environment Files

Store local NinjaOne credentials in gitignored env files under `env/`.

Create one file per environment from the committed template:

```bash
cp env/example.env env/internal-testing.env
cp env/example.env env/demo-eu.env
cp env/example.env env/demo-ca.env
```

Fill each file with that environment's values. The scripts expect the same variable names in every file:

```bash
NINJA_ONE_INSTANCE=eu.ninjarmm.com
NINJA_ONE_CLIENT_ID=
NINJA_ONE_CLIENT_SECRET=
NINJA_ONE_SCOPE="monitoring management"
```

For NinjaOne scripts, use the short launcher:

```bash
./ninja eu last-login
./ninja ca org-summary
./ninja it no-login --days 14
```

The launcher supports these environment aliases:

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

You can also run any command with a specific environment:

```bash
./run-with-env.sh demo-eu python3 scripts/python/ninjaone-technician-inactive-login-report/technician_last_login_report.py
./run-with-env.sh demo-ca python3 scripts/python/ninjaone-organization-device-summary-report/organization_device_summary_report.py
```

## PowerShell

### Winget machine install
Installs a Winget package in machine scope under SYSTEM, with RMM-friendly logging and optional exact-version install.

- Language: PowerShell
- Path: `scripts/powershell/winget-machine-install/`
- Usage: `powershell.exe -ExecutionPolicy Bypass -File scripts/powershell/winget-machine-install/winget-machine-install.ps1 -Id "Microsoft.PowerToys"`
- Prereqs: Winget (App Installer)

## Python

### NinjaOne technician no-login-for-X-days report
Lists NinjaOne technicians who have not logged into the Ninja platform during the last N full days, using local midnight as the cutoff.

- Language: Python
- Path: `scripts/python/ninjaone-technician-inactive-login-report/`
- Usage: `python3 scripts/python/ninjaone-technician-inactive-login-report/technician_no_login_for_x_days_report.py --days 14`
- Prereqs: Python 3, NinjaOne OAuth client credentials via `NINJA_ONE_CLIENT_ID` and `NINJA_ONE_CLIENT_SECRET`

### NinjaOne technician last login report
Lists NinjaOne technicians sorted descending by latest platform login activity.

- Language: Python
- Path: `scripts/python/ninjaone-technician-inactive-login-report/`
- Usage: `python3 scripts/python/ninjaone-technician-inactive-login-report/technician_last_login_report.py`
- Prereqs: Python 3, NinjaOne OAuth client credentials via `NINJA_ONE_CLIENT_ID` and `NINJA_ONE_CLIENT_SECRET`

### NinjaOne organization device summary report
Reports organization counts for total devices, workstations, servers, Apple mobile devices, Android devices, network devices, end users, and used cloud backup storage.

- Language: Python
- Path: `scripts/python/ninjaone-organization-device-summary-report/`
- Usage: `python3 scripts/python/ninjaone-organization-device-summary-report/organization_device_summary_report.py`
- Prereqs: Python 3, NinjaOne OAuth client credentials via `NINJA_ONE_CLIENT_ID` and `NINJA_ONE_CLIENT_SECRET`

### Shared NinjaOne Python helper
Provides common NinjaOne OAuth and JSON request helpers used by the Python NinjaOne reports.

- Language: Python
- Path: `scripts/python/_shared/ninja_api.py`

## No Liability / No Warranty
These scripts are provided as-is, without warranty of any kind, express or implied. Use them at your own risk and validate them in a safe test environment before using them in production. The author and contributors are not liable for any damages, data loss, service disruption, security issue, or other consequence resulting from use, misuse, or inability to use these scripts.
