# Winget RMM Machine Install

Installs a Winget package in machine scope under SYSTEM, with RMM-friendly logging and failure on non-machine scope.

## Usage
```powershell
powershell.exe -ExecutionPolicy Bypass -File .\src\winget-machine-install.ps1 -Id "Microsoft.PowerToys"
```

## Parameters
- `-Id` (required): Winget package ID (e.g., `Microsoft.PowerToys`).
- `-LogPath` (optional): Log file path. Defaults to temp directory.
