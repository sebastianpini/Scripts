# NinjaOne Technician Inactive Login Report

Lists NinjaOne technicians who have not logged into the Ninja platform during the last N full days, using local midnight as the cutoff boundary.

## Usage
```bash
export NINJA_ONE_INSTANCE="eu.ninjarmm.com"
export NINJA_ONE_CLIENT_ID="your-client-id"
export NINJA_ONE_CLIENT_SECRET="your-client-secret"
python3 ./technician_inactive_login_report.py --days 14
```

## Environment variables
- `NINJA_ONE_INSTANCE` (required): NinjaOne instance hostname, for example `eu.ninjarmm.com`.
- `NINJA_ONE_CLIENT_ID` (required): OAuth client ID.
- `NINJA_ONE_CLIENT_SECRET` (required): OAuth client secret.
- `NINJA_ONE_SCOPE` (optional): OAuth scope. Defaults to `monitoring management`.

## Behavior
- Uses local midnight for the cutoff date. Example: `--days 14` means `00:00:00` local time 14 days ago.
- Uses `/v2/users?userType=TECHNICIAN&includeRoles=true` to load technicians.
- Uses `/v2/activities` with `after=<cutoff>` to identify active technicians.
- Uses `/v2/activities` with `before=<cutoff>` to fetch the last older login for inactive technicians.
- Outputs `Name`, `Email`, `Admin`, `Roles`, and `Last Login`.

## Example
```text
Cutoff: 2026-04-09 00:00:00 CEST
Inactive enabled technicians with no Ninja platform login in the last 14 day(s): 387
Name                     Email                                         Admin Roles                  Last Login
...
Total: 387
```
