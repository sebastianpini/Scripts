# Shared Python Helpers

Reusable Python modules used by scripts in sibling folders.

## NinjaOne API helper
`ninja_api.py` provides common NinjaOne OAuth and JSON request helpers for the NinjaOne reports.

### Environment variables
- `NINJA_ONE_CLIENT_ID` (required): OAuth client ID.
- `NINJA_ONE_CLIENT_SECRET` (required): OAuth client secret.
- `NINJA_ONE_INSTANCE` (optional): NinjaOne instance hostname. Defaults to `eu.ninjarmm.com`.
- `NINJA_ONE_SCOPE` (optional): OAuth scope. Defaults to `monitoring management`.

Scripts that run directly add this folder to `sys.path` before importing `ninja_api`.
