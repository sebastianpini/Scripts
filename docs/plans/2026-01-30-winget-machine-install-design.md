# Winget Machine-Scoped Install Script Design

## Goal
Build a PowerShell script that installs a Winget package in machine scope under SYSTEM (RMM-friendly), failing fast if machine scope is not supported. The script should log to a file in the temp directory and emit to stdout/stderr for reliable troubleshooting capture.

## Context & Constraints
- Target OS: Windows 10/11.
- Execution context: SYSTEM (already provided by RMM).
- Input: Winget package ID only.
- Behavior on non-machine scope: fail with a clear error.
- Winget availability: attempt to install/update App Installer if winget is missing.
- Logging: log file in temp folder + stdout/stderr output.
- Agreements: always accept package/source agreements.
- Exit behavior: default PowerShell behavior (throw on fatal errors).

## Architecture
A single PowerShell script (e.g., `src/winget-machine-install.ps1`) with a linear flow:
1) Resolve log path and initialize logging.
2) Ensure winget is available (and resolve its full path under SYSTEM).
3) Fetch package metadata via `winget show --id <id> --output json`.
4) Validate that `Installers[].Scope` contains `machine`.
5) Install via `winget install --id <id> --scope machine --accept-package-agreements --accept-source-agreements`.

If any step fails, the script logs the reason and throws to propagate a failed run back to the RMM.

## Components
- `Write-Log($Level, $Message)`
  - Writes timestamped messages to stdout/stderr and appends to a log file.
  - Uses `Write-Output` for Info/Warning, `Write-Error` for Error.
- `Ensure-Winget()`
  - Tries `Get-Command winget.exe`.
  - If missing, checks `Get-AppxPackage -AllUsers Microsoft.DesktopAppInstaller` and resolves `InstallLocation\winget.exe`.
  - If still missing, downloads the App Installer MSIX bundle and installs it, then re-checks availability.
- `Get-WingetPackageInfo($Id)`
  - Executes `winget show --id $Id --output json` and parses JSON.
- `Supports-MachineScope($PkgInfo)`
  - Returns true if any installer scope is `machine` (case-insensitive), else false.
- `Install-WingetPackage($Id)`
  - Runs winget install with machine scope and agreement flags.

## Data Flow & Error Handling
- Inputs: `-Id` (required), `-LogPath` (optional).
- Derived: default log path in `C:\Windows\Temp` (or `$env:TEMP` when available).
- Each step logs start/end and failures. Command output is captured and included in logs on error.
- Failure cases:
  - Winget missing after attempted install/update.
  - Winget show fails or returns invalid JSON.
  - No machine scope in metadata.
  - Winget install returns non-zero.

## Testing & Validation
Manual verification scenarios:
1) Winget present in PATH, package supports machine scope → install succeeds.
2) Winget not in PATH but App Installer installed → resolved full path succeeds.
3) Winget missing → App Installer bootstrap → re-check succeeds.
4) Package without machine scope → fails with clear error, no install attempt.
5) Invalid package ID → `winget show` failure logged and exit non-zero.
6) Logging → temp log file created and stdout/stderr show mirrored messages.

## Open Questions
None.
