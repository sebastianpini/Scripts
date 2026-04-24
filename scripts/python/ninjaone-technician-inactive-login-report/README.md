# NinjaOne Technician Login Reports

Reports for NinjaOne technician platform login activity.

## No login for X days report
Lists NinjaOne technicians who have not logged into the Ninja platform during the last N full days, using local midnight as the cutoff boundary.

### Usage
```bash
export NINJA_ONE_INSTANCE="eu.ninjarmm.com"
export NINJA_ONE_CLIENT_ID="your-client-id"
export NINJA_ONE_CLIENT_SECRET="your-client-secret"
python3 ./technician_no_login_for_x_days_report.py --days 14
```

## Last login report
Lists every NinjaOne technician sorted descending by their latest `APP_USER_LOGGED_IN` activity. Technicians with no login activity are shown as `(never)` at the bottom.

### Usage
```bash
export NINJA_ONE_INSTANCE="eu.ninjarmm.com"
export NINJA_ONE_CLIENT_ID="your-client-id"
export NINJA_ONE_CLIENT_SECRET="your-client-secret"
python3 ./technician_last_login_report.py
```

Use `--enabled-only` to exclude disabled technicians:
```bash
python3 ./technician_last_login_report.py --enabled-only
```

## Environment variables
- `NINJA_ONE_CLIENT_ID` (required): OAuth client ID.
- `NINJA_ONE_CLIENT_SECRET` (required): OAuth client secret.
- `NINJA_ONE_INSTANCE` (optional): NinjaOne instance hostname. Defaults to `eu.ninjarmm.com`.
- `NINJA_ONE_SCOPE` (optional): OAuth scope. Defaults to `monitoring management`.

## No login for X days report behavior
- Uses local midnight for the cutoff date. Example: `--days 14` means `00:00:00` local time 14 days ago.
- Uses `/v2/users?userType=TECHNICIAN&includeRoles=true` to load technicians.
- Uses `/v2/activities` with `after=<cutoff>` to identify active technicians.
- Uses `/v2/activities` with `before=<cutoff>` to fetch the last older login for inactive technicians.
- Outputs `Name`, `Email`, `Enabled`, `Admin`, `Roles`, and `Last Login`.

## Last login report behavior
- Uses `/v2/users?userType=TECHNICIAN&includeRoles=true` to load technicians.
- Uses `/v2/activities` with `status=APP_USER_LOGGED_IN` to capture the newest login activity for each technician.
- Outputs `Name`, `Email`, `Enabled`, `Admin`, `Roles`, and `Last Login`.
- Sorts by `Last Login` descending, with `(never)` logins last.

## No login for X days report example
```text
Cutoff: 2026-04-09 00:00:00 CEST
Inactive enabled technicians with no Ninja platform login in the last 14 day(s): 387
Name                     Email                                         Enabled Admin Roles                  Last Login
...
Total: 387
```

## Last login report example
```text
Technician last login report for all technicians: 42
Name                     Email                                         Enabled Admin Roles                  Last Login
...
Total: 42
```
