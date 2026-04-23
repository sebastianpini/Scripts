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

### NinjaOne technician inactive login report
Lists NinjaOne technicians who have not logged into the Ninja platform during the last N full days, using local midnight as the cutoff.

- Language: Python
- Path: `scripts/python/ninjaone-technician-inactive-login-report/`
- Usage: `python3 scripts/python/ninjaone-technician-inactive-login-report/technician_inactive_login_report.py --days 14`
- Prereqs: Python 3, NinjaOne OAuth client credentials via `NINJA_ONE_INSTANCE`, `NINJA_ONE_CLIENT_ID`, and `NINJA_ONE_CLIENT_SECRET`
