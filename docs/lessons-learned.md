# Lessons Learned

A running log of mistakes made while working on this repo and how to avoid them next time. The same lessons are mirrored in Claude's auto-memory (`~/.claude/projects/-Users-sebastian-Code-Scripts/memory/`) so they apply automatically in future sessions. Edit freely — this file is the human-readable source of truth.

## Process & repo hygiene

### After rename/restructure commits, grep the whole repo for the old name
**Trigger:** Token cache file was renamed to `token.json` in `48f79c1` and the repo was restructured in `cb5d068`. Together they left 4+ stale references that a reviewer caught later: README pointed at the old token cache filename, `ASSIGN_OWNER.md` referenced a nonexistent `env/example.env`, `assign_owner.py`'s own docstring still claimed the old default path, and `last_login.py`'s usage block named the pre-restructure script.

**Rule:** Before committing a rename or restructure, grep the entire repo — not just the directories git diff shows:
```bash
grep -rn "<old-name>" --include='*.md' --include='*.py' --include='*.sh' .
```
Also grep for the *concept*, not just the literal string — e.g. if you renamed `example.env` → `rename_to_default.env`, also grep for `cp env/example` and similar setup commands.

### After path changes, actually run the tests
**Trigger:** All 14 unit tests in `tests/` were broken since the `cb5d068` restructure. Their `SCRIPT_PATH` constants pointed at pre-restructure paths that no longer existed. Tests failed with import errors on every run — but nobody ran them, so nobody noticed.

**Rule:** Right after a restructure or rename, run:
```bash
for t in tests/test_*.py; do python3 "$t"; done
```
The actual fix when this was discovered took 5 minutes (update three SCRIPT_PATH lines). The failure mode was social, not technical.

## Python patterns

### Lazy-import optional 3rd-party dependencies
**Trigger:** `excel_export.py` had `from openpyxl import ...` at top level, and `last_login.py` imported `excel_export` at top level too. Result: `python ninja.py last-login` crashed with `ModuleNotFoundError` if openpyxl wasn't installed — even when the user only wanted console output.

**Rule:** When a feature's dependency isn't in stdlib (`openpyxl`, `pandas`, `requests`, `pillow`, …), put `from <module> import ...` *inside* the function or branch that uses it. The shared module that *only* uses the dep can keep its top-level import — but the *callers* should import the shared module lazily.

### Use `datetime.isoformat(timespec="seconds")` for machine-parsed timestamps
**Trigger:** `last_login.py` originally used `strftime("%Y-%m-%d %H:%M:%S %Z")` → output like `2026-05-18 09:41:22 CEST`. Excel couldn't parse it (space instead of `T`, tz abbreviation instead of numeric offset).

**Rule:** For CSV/XLSX/JSON output, use:
```python
datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().isoformat(timespec="seconds")
# → "2026-05-18T09:41:22+02:00"
```
Strftime is for human-display formats only.

## Architecture

### Target platform is Windows
**Trigger:** The repo originally had a Bash `./ninja` launcher and `lib/run-with-env.sh` as the primary UX. A reviewer flagged it: ~99% of NinjaOne customers run on Windows, so the launcher was unusable for the real user base. We migrated to a cross-platform `ninja.py`.

**Rule:** Default to cross-platform Python for tooling. PowerShell is acceptable for Windows-native ops. Pure Bash launchers as primary UX are wrong target. Use `pathlib.Path`, wrap `chmod` calls in `try/except OSError`, don't rely on shebangs.

### Extract to `_shared/` on the second consumer — not before, not after
**Trigger:** Discussed during this project: OAuth Auth-Code-Flow + token-cache logic lives inline in `assign_owner.py`. Currently the only consumer.

**Rule:** Single-use logic stays inline. When you're about to copy logic into a second file, *that* is the trigger to extract — not later, not earlier. Pre-extraction designs against imaginary needs; post-copy-paste extraction creates two divergent implementations. For the OAuth case specifically: the cache/refresh logic is extractable; browser-login glue (localhost HTTP server, PKCE) stays script-specific.

## Working with code reviewers

### Verify the prescription, trust the diagnosis
**Trigger:** A reviewer suggested fixing the timestamp format with `datetime.isoformat(timespec='seconds', tzdata=tz.datetime.cet)`. The diagnosis (current format isn't valid ISO 8601) was correct. The prescription was hallucinated: `isoformat()` has no `tzdata` argument, and `tz.datetime.cet` isn't a real module. The correct code is `.astimezone().isoformat(timespec="seconds")`.

**Rule:** Treat reviewer feedback as two separate signals:
1. **Diagnosis** ("what's wrong") — usually right, take it seriously.
2. **Prescription** ("here's the fix") — needs verification before pasting.

If a suggested API call refers to module attrs or kwargs you've never seen, grep stdlib docs first. If the reviewer is human, write back the *corrected* fix so they learn too.
