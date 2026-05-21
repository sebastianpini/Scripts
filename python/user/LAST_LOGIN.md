# NinjaOne Last Login Report

## Last login report
Lists every NinjaOne user sorted descending by their latest login activity. Users with no login activity are shown as `(never)` at the bottom.

### Usage
Store NinjaOne credentials in `env/default.env` as described in the repository root README. Then run from the repository root:

```bash
python ninja.py last-login
```

Use `--user-type` to control which users are included (default: `technician`):
```bash
python ninja.py last-login --user-type technician   # technicians only (default)
python ninja.py last-login --user-type enduser      # end users only
python ninja.py last-login --user-type all          # technicians and end users
```

Use `--enabled-only` to exclude disabled users:
```bash
python ninja.py last-login --enabled-only
```

Use `--csv PATH` to export results to a CSV file:
```bash
python ninja.py last-login --csv /Users/sebastian/Desktop/last_login_report.csv
```

Use `--xlsx PATH` to export results to a formatted Excel file (auto-fitted columns, filterable table):
```bash
python ninja.py last-login --xlsx /Users/sebastian/Desktop/last_login_report.xlsx
```

Both flags can be combined:
```bash
python ninja.py last-login --user-type all --enabled-only --xlsx /Users/sebastian/Desktop/last_login_report.xlsx
```

For multiple environments, pass the environment name before the script name:

```bash
python ninja.py demo-eu last-login
```

## Environment variables
These variables belong in `env/default.env` or another selected `env/*.env` file, not in `~/.zshrc` or copied into the shell before every run.

- `NINJA_ONE_CLIENT_ID` (required): OAuth client ID.
- `NINJA_ONE_CLIENT_SECRET` (required): OAuth client secret.
- `NINJA_ONE_INSTANCE` (optional): NinjaOne instance hostname. Defaults to `eu.ninjarmm.com`.
- `NINJA_ONE_SCOPE` (optional): OAuth scope. Defaults to `monitoring management`.

## Behavior
- Uses `/v2/users?userType=TECHNICIAN&includeRoles=true` (or `END_USER`, or both) depending on `--user-type` (default: `technician`).
- Uses `/v2/activities` with `status=APP_USER_LOGGED_IN` (technicians) or `status=END_USER_LOGGED_IN` (end users) to capture the newest login activity for each user.
- Outputs `Name`, `Email`, `Type`, `Enabled`, `Admin`, `Roles`, and `Last Login`.
- Sorts by `Last Login` descending, with `(never)` logins last.
- Optionally writes results to a CSV file when `--csv PATH` is provided.
- Optionally writes results to a formatted Excel file when `--xlsx PATH` is provided (auto-fitted column widths, filterable Excel table, frozen header row).
- In `--user-type all` mode, warns to stderr if any users have no `userType` field and will show as `(never)`.

## Example
```text
Login report for technicians: 42
Name                     Email                              Type        Enabled Admin Roles        Last Login
------------------------ ---------------------------------- ----------- ------- ----- ---------- -------------------------
Jane Smith               jane.smith@example.com             Technician  Yes     Yes   IT Admin   2026-05-18T09:41:22+02:00
John Doe                 john.doe@example.com               Technician  Yes     No    Helpdesk   2026-03-02T14:07:55+01:00
...
Total: 42
```

## No Liability / No Warranty
This script is provided as-is, without warranty of any kind, express or implied. Use it at your own risk and validate it in a safe test environment before using it in production. The author and contributors are not liable for any damages, data loss, service disruption, security issue, or other consequence resulting from use, misuse, or inability to use this script.
