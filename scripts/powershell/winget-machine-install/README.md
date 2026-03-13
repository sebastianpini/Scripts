# Winget RMM Machine Install

Installs a Winget package in machine scope under SYSTEM, with RMM-friendly logging, optional exact-version install, optional installed-version pinning, and failure on non-machine scope.

## Usage
```powershell
powershell.exe -ExecutionPolicy Bypass -File .\winget-machine-install.ps1 -Id "Microsoft.PowerToys"
```

Pin the installed version so future `winget upgrade <id>` and `winget upgrade --all` runs skip it:
```powershell
powershell.exe -ExecutionPolicy Bypass -File .\winget-machine-install.ps1 -Id "Microsoft.PowerToys" -PinInstalledVersion
```
Use `-PinInstalledVersion` only for single-app runs. The script supports multiple IDs, but the pin switch applies to every package in the list.

Install a specific version and pin that installed version:
```powershell
powershell.exe -ExecutionPolicy Bypass -File .\winget-machine-install.ps1 -Id "Microsoft.PowerToys" -Version "0.89.0" -PinInstalledVersion
```

## Parameters
- `-Id` (required): Winget package ID (e.g., `Microsoft.PowerToys`).
- `-Version` (optional): Exact Winget package version to install. For multiple IDs, pass a comma-separated version list in the same order.
- `-PinInstalledVersion` (optional): Adds or refreshes a Winget pin for the installed version after install completes. Intended for single-app runs.
- `-LogPath` (optional): Log file path. Defaults to temp directory.

## Manual validation
1) Winget present in PATH; install machine-scoped package.
2) Winget not in PATH but App Installer installed; resolves and installs.
3) Winget missing; App Installer bootstrap succeeds.
4) Package without machine scope; script fails before install.
5) Invalid ID; script fails with clear error.
6) `-PinInstalledVersion` adds a gating pin and end summary reports the pinned version.
7) `-Version` installs the requested version and end summary reports install/pin/shortcut outcomes.
8) Logs appear in temp and stdout/stderr.
