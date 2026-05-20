# NinjaOne Technician Login Reports

Reports for NinjaOne technician platform login activity.

## No login for X days report
Lists NinjaOne technicians who have not logged into the Ninja platform during the last N full days, using local midnight as the cutoff boundary.

### Usage
Store NinjaOne credentials in `env/default.env` as described in the repository root README. Then run from the repository root:

```bash
./ninja no-login --days 14
```

## Last login report
Lists every NinjaOne user sorted descending by their latest login activity. Users with no login activity are shown as `(never)` at the bottom.

### Usage
Store NinjaOne credentials in `env/default.env` as described in the repository root README. Then run from the repository root:

```bash
./ninja last-login
```

Use `--user-type` to control which users are included (default: `technician`):
```bash
./ninja last-login --user-type technician   # technicians only (default)
./ninja last-login --user-type enduser      # end users only
./ninja last-login --user-type all          # technicians and end users
```

Use `--enabled-only` to exclude disabled users:
```bash
./ninja last-login --enabled-only
```

Use `--csv PATH` to export results to a CSV file:
```bash
./ninja last-login --csv output.csv
```

For multiple environments, pass the environment name before the script name:

```bash
./ninja demo-eu last-login
```

## Environment variables
These variables belong in `env/default.env` or another selected `env/*.env` file, not in `~/.zshrc` or copied into the shell before every run.

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
- Uses `/v2/users?userType=TECHNICIAN&includeRoles=true` (or `END_USER`, or both) depending on `--user-type` (default: `technician`).
- Uses `/v2/activities` with `status=APP_USER_LOGGED_IN` (technicians) or `status=END_USER_LOGGED_IN` (end users) to capture the newest login activity for each user.
- Outputs `Name`, `Email`, `Enabled`, `Admin`, `Roles`, and `Last Login`.
- Sorts by `Last Login` descending, with `(never)` logins last.
- Optionally writes results to a CSV file when `--csv PATH` is provided.
- In `--user-type all` mode, warns to stderr if any users have no `userType` field and will show as `(never)`.

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
Login report for technicians: 42
Name                     Email                                         Enabled Admin Roles                  Last Login
...
Total: 42
```

## No Liability / No Warranty
These scripts are provided as-is, without warranty of any kind, express or implied. Use them at your own risk and validate them in a safe test environment before using them in production. The author and contributors are not liable for any damages, data loss, service disruption, security issue, or other consequence resulting from use, misuse, or inability to use these scripts.
