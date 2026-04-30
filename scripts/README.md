# Scripts Index

This folder contains the script implementations. Use the repository root [`README.md`](../README.md) for customer setup, NinjaOne credential handling, and common launcher usage.

## PowerShell

| Script | Purpose | Documentation |
| --- | --- | --- |
| `powershell/winget-machine-install/winget-machine-install.ps1` | Installs a Winget package in machine scope under SYSTEM. | [`WINGET_MACHINE_INSTALL.md`](powershell/winget-machine-install/WINGET_MACHINE_INSTALL.md) |

## Python

| Script | Purpose | Documentation |
| --- | --- | --- |
| `python/ninjaone-technician-inactive-login-report/technician_no_login_for_x_days_report.py` | Lists NinjaOne technicians with no platform login in the last N full days. | [`TECHNICIAN_LOGIN_REPORTS.md`](python/ninjaone-technician-inactive-login-report/TECHNICIAN_LOGIN_REPORTS.md) |
| `python/ninjaone-technician-inactive-login-report/technician_last_login_report.py` | Lists NinjaOne technicians by latest platform login activity. | [`TECHNICIAN_LOGIN_REPORTS.md`](python/ninjaone-technician-inactive-login-report/TECHNICIAN_LOGIN_REPORTS.md) |
| `python/ninjaone-organization-device-summary-report/organization_device_summary_report.py` | Reports NinjaOne organization device, user, and backup storage counts. | [`ORGANIZATION_DEVICE_SUMMARY.md`](python/ninjaone-organization-device-summary-report/ORGANIZATION_DEVICE_SUMMARY.md) |
| `python/_shared/ninja_api.py` | Shared NinjaOne OAuth and JSON request helper for Python reports. | [`NINJAONE_SHARED_HELPER.md`](python/_shared/NINJAONE_SHARED_HELPER.md) |

## No Liability / No Warranty

These scripts are provided as-is, without warranty of any kind, express or implied. Use them at your own risk and validate them in a safe test environment before using them in production. The author and contributors are not liable for any damages, data loss, service disruption, security issue, or other consequence resulting from use, misuse, or inability to use these scripts.
