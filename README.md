# Winget RMM Machine Install

Installs a Winget package in machine scope under SYSTEM, with RMM-friendly logging and failure on non-machine scope.

## Usage
```powershell
powershell.exe -ExecutionPolicy Bypass -File .\src\winget-machine-install.ps1 -Id "Microsoft.PowerToys"
```

## Parameters
- `-Id` (required): Winget package ID (e.g., `Microsoft.PowerToys`).
- `-LogPath` (optional): Log file path. Defaults to temp directory.

## Manual validation
1) Winget present in PATH; install machine-scoped package.
2) Winget not in PATH but App Installer installed; resolves and installs.
3) Winget missing; App Installer bootstrap succeeds.
4) Package without machine scope; script fails before install.
5) Invalid ID; script fails with clear error.
6) Logs appear in temp and stdout/stderr.
