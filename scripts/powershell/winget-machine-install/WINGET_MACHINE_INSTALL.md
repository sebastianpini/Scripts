# Winget RMM Machine Install

Installs a Winget package in machine scope under SYSTEM, with RMM-friendly logging, optional exact-version install, and failure on non-machine scope.

## NinjaOne setup
Create NinjaOne custom fields and map them to dynamic script variables before using this script in automation:
- `wingetId` for `-Id`
- `wingetVersion` for `-Version`
- `architecture` for `-Architecture`

## Usage
```powershell
powershell.exe -ExecutionPolicy Bypass -File .\winget-machine-install.ps1 -Id "Microsoft.PowerToys"
```

Install a specific version:
```powershell
powershell.exe -ExecutionPolicy Bypass -File .\winget-machine-install.ps1 -Id "Microsoft.PowerToys" -Version "0.89.0"
```

## Parameters
- `-Id` (required): Winget package ID (e.g., `Microsoft.PowerToys`). In NinjaOne, set this up as custom field `wingetId`.
- `-Version` (optional): Exact Winget package version to install. For multiple IDs, pass a comma-separated version list in the same order. In NinjaOne, set this up as custom field `wingetVersion`.
- `-Architecture` (optional): Target architecture override. In NinjaOne, set this up as custom field `architecture`.
- `-LogPath` (optional): Log file path. Defaults to temp directory. This is not read from a NinjaOne custom field.

## Manual validation
1) Winget present in PATH; install machine-scoped package.
2) Winget not in PATH but App Installer installed; resolves and installs.
3) Winget missing; App Installer bootstrap succeeds.
4) Package without machine scope; script fails before install.
5) Invalid ID; script fails with clear error.
6) `-Version` installs the requested version and end summary reports install/shortcut outcomes.
7) Logs appear in temp and stdout/stderr.

## No Liability / No Warranty
This script is provided as-is, without warranty of any kind, express or implied. Use it at your own risk and validate it in a safe test environment before using it in production. The author and contributors are not liable for any damages, data loss, service disruption, security issue, or other consequence resulting from use, misuse, or inability to use this script.
