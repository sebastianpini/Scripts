# Winget Machine-Scoped Install Script Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a PowerShell script that installs a Winget package with machine scope under SYSTEM, failing fast if machine scope is unsupported, and logging to temp + stdout/stderr.

**Architecture:** Single PowerShell script with helper functions for logging, winget resolution/installation, metadata parsing, scope validation, and install. Linear flow with strict error handling and RMM-friendly output.

**Tech Stack:** PowerShell 5.1+ (Windows 10/11), winget (App Installer).

---

### Task 1: Create project skeleton and basic docs

**Files:**
- Create: `README.md`
- Create: `src/winget-machine-install.ps1`

**Step 1: Create minimal README**

```markdown
# Winget RMM Machine Install

Installs a Winget package in machine scope under SYSTEM, with RMM-friendly logging and failure on non-machine scope.

## Usage
```powershell
powershell.exe -ExecutionPolicy Bypass -File .\src\winget-machine-install.ps1 -Id "Microsoft.PowerToys"
```

## Parameters
- `-Id` (required): Winget package ID (e.g., `Microsoft.PowerToys`).
- `-LogPath` (optional): Log file path. Defaults to temp directory.
```

**Step 2: Create script file with header comment and parameter block**

```powershell
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Id,

    [Parameter(Mandatory = $false)]
    [string]$LogPath
)
```

**Step 3: Commit**

```bash
git add README.md src/winget-machine-install.ps1
git commit -m "chore: add skeleton script and readme"
```

---

### Task 2: Add logging utilities

**Files:**
- Modify: `src/winget-machine-install.ps1`

**Step 1: Add default log path resolution**

```powershell
if (-not $LogPath -or $LogPath.Trim().Length -eq 0) {
    $safeId = $Id -replace '[^a-zA-Z0-9._-]', '_'
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $LogPath = Join-Path -Path $env:TEMP -ChildPath "winget-install-$safeId-$timestamp.log"
}
```

**Step 2: Add Write-Log function**

```powershell
function Write-Log {
    param(
        [Parameter(Mandatory = $true)][ValidateSet('Info','Warn','Error')][string]$Level,
        [Parameter(Mandatory = $true)][string]$Message
    )

    $line = "$(Get-Date -Format "yyyy-MM-dd HH:mm:ss") [$Level] $Message"
    if ($Level -eq 'Error') {
        Write-Error $line
    } else {
        Write-Output $line
    }
    Add-Content -Path $LogPath -Value $line
}
```

**Step 3: Log startup context**

```powershell
Write-Log -Level Info -Message "Starting winget machine install for Id=$Id"
Write-Log -Level Info -Message "LogPath=$LogPath"
Write-Log -Level Info -Message "OS=$([System.Environment]::OSVersion.VersionString)"
Write-Log -Level Info -Message "PowerShell=$($PSVersionTable.PSVersion)"
```

**Step 4: Commit**

```bash
git add src/winget-machine-install.ps1
git commit -m "feat: add logging and startup context"
```

---

### Task 3: Resolve winget and attempt install/update

**Files:**
- Modify: `src/winget-machine-install.ps1`

**Step 1: Add Get-WingetPath helper**

```powershell
function Get-WingetPath {
    $cmd = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $app = Get-AppxPackage -AllUsers -Name "Microsoft.DesktopAppInstaller" -ErrorAction SilentlyContinue
    if ($app -and $app.InstallLocation) {
        $candidate = Join-Path -Path $app.InstallLocation -ChildPath "winget.exe"
        if (Test-Path $candidate) { return $candidate }
    }

    return $null
}
```

**Step 2: Add Ensure-Winget**

```powershell
function Ensure-Winget {
    $path = Get-WingetPath
    if ($path) { return $path }

    Write-Log -Level Warn -Message "winget not found, attempting to install App Installer"

    $tmp = Join-Path -Path $env:TEMP -ChildPath "AppInstaller.msixbundle"
    Invoke-WebRequest -Uri "https://aka.ms/getwinget" -OutFile $tmp
    Add-AppxPackage -Path $tmp

    Start-Sleep -Seconds 2
    $path = Get-WingetPath
    if (-not $path) {
        throw "winget still not available after install attempt"
    }

    return $path
}
```

**Step 3: Commit**

```bash
git add src/winget-machine-install.ps1
git commit -m "feat: resolve winget and attempt install"
```

---

### Task 4: Fetch package metadata and validate scope

**Files:**
- Modify: `src/winget-machine-install.ps1`

**Step 1: Add metadata helper**

```powershell
function Get-WingetPackageInfo {
    param([string]$WingetPath, [string]$Id)

    $output = & $WingetPath show --id $Id --output json 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Log -Level Error -Message "winget show failed: $output"
        throw "winget show failed for Id=$Id"
    }

    try {
        return $output | ConvertFrom-Json
    } catch {
        Write-Log -Level Error -Message "Failed to parse winget JSON output"
        throw
    }
}
```

**Step 2: Add scope validation**

```powershell
function Supports-MachineScope {
    param([object]$PkgInfo)

    if (-not $PkgInfo -or -not $PkgInfo.Installers) { return $false }

    foreach ($installer in $PkgInfo.Installers) {
        if ($installer.Scope -and $installer.Scope.ToString().ToLowerInvariant() -eq "machine") {
            return $true
        }
    }

    return $false
}
```

**Step 3: Commit**

```bash
git add src/winget-machine-install.ps1
git commit -m "feat: parse winget metadata and validate machine scope"
```

---

### Task 5: Install package and wire main flow

**Files:**
- Modify: `src/winget-machine-install.ps1`

**Step 1: Add install helper**

```powershell
function Install-WingetPackage {
    param([string]$WingetPath, [string]$Id)

    $output = & $WingetPath install --id $Id --scope machine --accept-package-agreements --accept-source-agreements 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Log -Level Error -Message "winget install failed: $output"
        throw "winget install failed for Id=$Id"
    }

    Write-Log -Level Info -Message "Install completed successfully"
}
```

**Step 2: Wire the main flow**

```powershell
try {
    $wingetPath = Ensure-Winget
    Write-Log -Level Info -Message "Using winget at $wingetPath"

    $pkg = Get-WingetPackageInfo -WingetPath $wingetPath -Id $Id
    if (-not (Supports-MachineScope -PkgInfo $pkg)) {
        Write-Log -Level Error -Message "Package does not support machine scope"
        throw "Machine scope not supported for Id=$Id"
    }

    Install-WingetPackage -WingetPath $wingetPath -Id $Id
} catch {
    Write-Log -Level Error -Message $_
    throw
}
```

**Step 3: Commit**

```bash
git add src/winget-machine-install.ps1
git commit -m "feat: install flow with scope checks"
```

---

### Task 6: Manual validation notes and usage polish

**Files:**
- Modify: `README.md`

**Step 1: Add manual test checklist**

```markdown
## Manual validation
1) Winget present in PATH; install machine-scoped package.
2) Winget not in PATH but App Installer installed; resolves and installs.
3) Winget missing; App Installer bootstrap succeeds.
4) Package without machine scope; script fails before install.
5) Invalid ID; script fails with clear error.
6) Logs appear in temp and stdout/stderr.
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add manual validation checklist"
```
