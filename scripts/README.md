# Scripts

A curated list of useful scripts in this repo.

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
