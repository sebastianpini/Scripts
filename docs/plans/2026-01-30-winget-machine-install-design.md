# Winget Machine-Scoped Install Script Design

## Goal
Build a PowerShell script that installs one or more Winget packages in machine scope under SYSTEM (RMM-friendly), failing fast if machine scope is not supported for the device architecture. The script should log to a file in the temp directory and emit to stdout/stderr for reliable troubleshooting capture.

## Context & Constraints
- Target OS: Windows 10/11.
- Execution context: SYSTEM (already provided by RMM).
- Input: one or more comma-separated Winget package IDs, optional architecture override.
- Behavior on non-machine scope: fail with a clear error (per-package).
- Winget availability: attempt to install/update App Installer if winget is missing.
- Logging: log file in temp folder + stdout/stderr output.
- Agreements: always accept package/source agreements.
- Exit behavior: throws when all packages fail; partial success is allowed.
- Already-installed packages: treated as a warning, not a failure.

## Architecture
One PowerShell file under `scripts/powershell/winget-machine-install/`:
- `winget-machine-install.ps1` — standalone entry point with all functions inlined for RMM deployment.

Parameters accept environment variable fallbacks (`$env:wingetId`, `$env:architecture`) for RMM tools that inject variables.

### Main Flow
1. Resolve log path and initialize logging.
2. Ensure winget is available (resolve full path under SYSTEM, bootstrap App Installer if missing).
3. Determine device architecture (from parameter, env var, or default `x64`).
4. For each package ID (comma-separated):
   a. Fetch package metadata via `winget show` text output (with timeout).
   b. Parse installer blocks to extract scope and architecture.
   c. Filter installers matching the device architecture.
   d. Validate that a matching installer supports `machine` scope (skip check on timeout).
   e. Install via `winget install --id <id> --source winget --scope machine --accept-package-agreements --accept-source-agreements --disable-interactivity`.
   f. Copy the Start Menu shortcut to the Public Desktop if one was created.
5. Report success/failure counts. Throw only if all packages failed.

## Components

### Logging & Output
- **`Write-Log($Level, $Message)`**
  - Writes timestamped `[Info]`/`[Warning]`/`[Error]` messages to stdout/stderr and appends to a log file.
  - Uses `Write-Output` for Info/Warning, `Write-Error` for Error.
- **`Normalize-WingetOutput($Output, $MaxLines)`**
  - Filters out progress/download lines (KB/MB/GB patterns) and spinner characters.
  - Returns the last N meaningful lines for clean log output.

### Winget Resolution
- **`Get-WingetPath()`**
  - Tries `Get-Command winget.exe`.
  - If missing, checks `Get-AppxPackage -AllUsers Microsoft.DesktopAppInstaller`, sorts by version descending, resolves `InstallLocation\winget.exe`.
  - Returns `$null` if not found.
- **`Initialize-Winget()`** (named `Ensure-Winget` in the module)
  - Calls `Get-WingetPath`. If found, returns path.
  - Otherwise downloads the App Installer MSIX bundle and installs it, then re-checks.
  - Throws if still unavailable.
- **`Invoke-WingetWithTimeout($WingetPath, $ArgsList, $TimeoutSeconds)`**
  - Runs winget via `Start-Process` with stdout/stderr redirection to temp files.
  - Waits up to `$TimeoutSeconds`; kills the process and returns a `TimedOut = $true` result on timeout.
  - Returns a structured object: `Output`, `ExitCode`, `TimedOut`.

### Package Metadata & Scope Validation
- **`Convert-WingetShowTextToPackageInfo($Output)`**
  - Parses `winget show` text output for `Installer:` blocks, extracting `Scope` and `Architecture` per installer.
  - Falls back to regex matching for `Scope:` lines if no installer blocks are found.
  - Returns `[pscustomobject]@{ Installers = @(...) }`.
- **`Get-WingetPackageInfo($WingetPath, $Id)`**
  - Runs `winget show --id $Id --source winget --accept-source-agreements --disable-interactivity` with a 60-second timeout.
  - On timeout: returns a stub with `SkipScopeCheck = $true` so installation is still attempted.
  - Tolerates non-zero exit codes when the output looks valid (contains `Found` and `Installer:`).
- **`Convert-Architecture($Architecture)`**
  - Normalizes architecture strings: `amd64`/`x64` → `x64`, `x86`/`x32`/`i386` → `x86`, `aarch64`/`arm64` → `arm64`.
- **`Get-DeviceArchitecture()`**
  - Reads `$env:architecture`, defaults to `x64`.
- **`Get-InstallersForArchitecture($PkgInfo, $Architecture)`**
  - Filters the package's installers to those matching the normalized architecture (or those without an explicit architecture).
- **`Test-MachineScopeForArchitecture($PkgInfo, $Architecture)`**
  - Returns `$true` if any architecture-matching installer has `machine` scope, or if matching installers exist but none specify a scope (implicit machine support).

### Installation
- **`Install-WingetPackage($WingetPath, $Id)`**
  - Runs `winget install --id $Id --source winget --scope machine --accept-package-agreements --accept-source-agreements --disable-interactivity`.
  - Detects "already installed" / "no available upgrade" patterns in the output and treats them as warnings instead of failures.
  - Uses `Normalize-WingetOutput` to clean error output for logging.

### Desktop Shortcut
- **`Get-StartMenuShortcuts()`**
  - Returns all `.lnk` files under `C:\ProgramData\Microsoft\Windows\Start Menu\Programs`.
- **`Find-BestShortcut($Shortcuts, $Id, $InstallStart)`**
  - Filters to shortcuts modified since install start (with 2-minute grace window).
  - Prefers shortcuts whose name matches the package ID; falls back to most recent.
- **`Set-PublicDesktopShortcut($Id, $InstallStart)`**
  - Copies the best-matching Start Menu shortcut to `C:\Users\Public\Desktop`.
  - Skips if the shortcut already exists. Logs warnings on failure (non-fatal).

### Orchestration
- **`Invoke-WingetMachineInstall($Id, $LogPath)`**
  - Entry point. Splits comma-separated IDs, initializes logging, resolves winget.
  - Loops over each package: fetch metadata → validate scope → install → copy shortcut.
  - Tracks success/failure counts per package.
  - Throws only when all packages fail (`$successCount -eq 0`).

## Data Flow & Error Handling
- Inputs: `-Id` (required, comma-separated), `-LogPath` (optional), `-Architecture` (optional).
- Environment variable fallbacks: `$env:wingetId` for Id, `$env:architecture` for Architecture.
- Derived: default log path in `$env:TEMP`.
- Each step logs start/end and failures. Command output is normalized before logging.
- Failure cases:
  - Winget missing after attempted install/update → throws.
  - Winget show times out → scope check skipped, install attempted anyway.
  - Winget show fails with invalid output → throws for that package.
  - Winget show returns non-zero but output looks valid → continues with warning.
  - No machine scope for device architecture → throws for that package.
  - Winget install returns non-zero:
    - "Already installed" / "no upgrade" → warning, counted as success.
    - Other failures → throws for that package.
  - All packages fail → throws.
  - Shortcut copy failure → warning only, non-fatal.

## Testing & Validation
Manual verification scenarios:
1. Winget present in PATH, single package supports machine scope → install succeeds.
2. Comma-separated IDs, mix of valid and invalid → partial success reported.
3. Winget not in PATH but App Installer installed → resolved full path succeeds.
4. Winget missing → App Installer bootstrap → re-check succeeds.
5. Package without machine scope for device architecture → fails with clear error, no install attempt.
6. Invalid package ID → `winget show` failure logged and package skipped.
7. Package already installed → warning logged, counted as success.
8. Winget show times out → scope check skipped, install attempted.
9. Architecture filtering → only installers matching device arch are considered.
10. Desktop shortcut → `.lnk` copied from Start Menu to Public Desktop after install.
11. Logging → temp log file created and stdout/stderr show mirrored messages.

## Open Questions
None.
