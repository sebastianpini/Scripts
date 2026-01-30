# Scripts

A curated list of useful scripts in this repo.

## PowerShell

### Winget machine install
Installs a Winget package in machine scope under SYSTEM, with RMM-friendly logging and failure on non-machine scope.

- Language: PowerShell
- Path: `scripts/powershell/winget-machine-install/`
- Usage: `powershell.exe -ExecutionPolicy Bypass -File scripts/powershell/winget-machine-install/winget-machine-install.ps1 -Id "Microsoft.PowerToys"`
- Prereqs: Winget (App Installer)
