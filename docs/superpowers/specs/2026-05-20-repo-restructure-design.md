# Repo Restructure — Design Spec

**Date:** 2026-05-20

## Problem

The `scripts/` subdirectory is redundant because the entire repository is about scripts. This adds an unnecessary layer of indirection. Additionally, `run-with-env.sh` is an internal helper that doesn't belong at the repository root alongside the user-facing `ninja` CLI.

## Goal

A clearly structured repository where every top-level directory has an obvious purpose and nothing is buried under a redundant wrapper folder.

## Target Structure

```
Scripts/
├── ninja                          # user-facing CLI entrypoint (unchanged)
├── README.md
├── pyrightconfig.json
├── env/
├── docs/
├── tests/
├── lib/
│   └── run-with-env.sh            # internal env-loader helper
├── python/
│   ├── _shared/
│   │   ├── ninja_api.py
│   │   ├── excel_export.py
│   │   └── NINJAONE_SHARED_HELPER.md
│   ├── device/
│   │   ├── assign_owner.py
│   │   └── ASSIGN_OWNER.md
│   ├── organization/
│   │   ├── overview.py
│   │   └── OVERVIEW.md
│   └── user/
│       ├── last_login.py
│       └── LAST_LOGIN.md
└── powershell/
    └── winget-machine-install/
        ├── winget-machine-install.ps1
        └── WINGET_MACHINE_INSTALL.md
```

## Changes

### File moves
| From | To |
|------|----|
| `scripts/python/` | `python/` |
| `scripts/powershell/` | `powershell/` |
| `run-with-env.sh` | `lib/run-with-env.sh` |

### Deletions
- `scripts/` directory (empty after moves)
- `scripts/README.md` — content integrated into root `README.md` or dropped if redundant

### Updates required
- `ninja`: script path references `scripts/python/…` → `python/…`; env-loader call `./run-with-env.sh` → `./lib/run-with-env.sh`
- `tests/test_ninja_cli.sh`: any hardcoded paths updated to match new locations
- `README.md`: update any references to `scripts/` paths

## Decisions

- **`ninja` stays at root** — keeps the short `./ninja` invocation without any path prefix.
- **`run-with-env.sh` moves to `lib/`** — it is an implementation detail, not a user-facing tool; `lib/` signals this clearly.
- **Grouped by language** (not domain) at the top level — natural boundary that scales well when new languages are added; the PowerShell script (`winget-machine-install`) has no NinjaOne domain relationship, so domain grouping would require an awkward exception.
