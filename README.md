# Scripts

A curated list of useful scripts in this repo. For full details, see each script's README in its folder.

## PowerShell

### Winget machine install
Installs a Winget package in machine scope under SYSTEM, with RMM-friendly logging, optional exact-version install, and optional installed-version pinning.

- Language: PowerShell
- Path: `scripts/powershell/winget-machine-install/`
- Usage: `powershell.exe -ExecutionPolicy Bypass -File scripts/powershell/winget-machine-install/winget-machine-install.ps1 -Id "Microsoft.PowerToys" -PinInstalledVersion`
- Prereqs: Winget (App Installer)
