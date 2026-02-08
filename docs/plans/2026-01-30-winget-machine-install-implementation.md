# Winget Machine-Scoped Install Script Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a PowerShell script that installs one or more Winget packages with machine scope under SYSTEM, failing fast if machine scope is unsupported for the device architecture, and logging to temp + stdout/stderr. Copy Start Menu shortcuts to the Public Desktop after install.

**Architecture:** Two-file PowerShell project (`winget-machine-install.ps1` standalone entry point, `winget-machine-install.psm1` module for reuse). All functions inlined in the `.ps1` for single-file RMM deployment. Linear flow per package with per-package error handling, success/failure counting, and architecture-aware scope validation.

**Tech Stack:** PowerShell 5.1+ (Windows 10/11), winget (App Installer).

---

### Task 1: Create project skeleton and script header

**Files:**
- Create: `scripts/powershell/winget-machine-install/winget-machine-install.ps1`

**Step 1: Create script file with versioned header and parameter block**

```powershell
<#
.SYNOPSIS
[Version 1.2.0] Installs a Winget package in machine scope under SYSTEM.
Change Log:
- 1.2.0: Copy Start Menu shortcut to Public Desktop after install.
- 1.1.1: Standardized warning output to [Warning].
- 1.1.0: Single-file packaging.

.DESCRIPTION
Ensures winget is available, validates machine scope support, and installs
with RMM-friendly logging to stdout/stderr and a temp log file.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$Id = $env:wingetId,

    [Parameter(Mandatory = $false)]
    [string]$LogPath,

    [Parameter(Mandatory = $false)]
    [string]$Architecture = $env:architecture
)
```

Note: `-Id` defaults to `$env:wingetId` and `-Architecture` defaults to `$env:architecture` for RMM tools that inject variables.

**Step 2: Commit**

```bash
git add scripts/powershell/winget-machine-install/winget-machine-install.ps1
git commit -m "chore: add skeleton script and readme"
```

---

### Task 2: Add logging and output normalization utilities

**Files:**
- Modify: `scripts/powershell/winget-machine-install/winget-machine-install.ps1`

**Step 1: Add Write-Log function**

```powershell
function Write-Log {
    param(
        [Parameter(Mandatory = $true)][ValidateSet('Info','Warning','Error')][string]$Level,
        [Parameter(Mandatory = $true)][string]$Message
    )

    $line = "$(Get-Date -Format "yyyy-MM-dd HH:mm:ss") [$Level] $Message"
    if ($Level -eq 'Error') {
        Write-Error $line
    } else {
        Write-Output $line
    }
    Add-Content -Path $script:LogPath -Value $line
}
```

Note: Uses `Warning` (not `Warn`) for the validation set to produce standardized `[Warning]` output.

**Step 2: Add Normalize-WingetOutput function**

```powershell
function Normalize-WingetOutput {
    param(
        [Parameter(Mandatory = $true)][string]$Output,
        [Parameter(Mandatory = $false)][int]$MaxLines = 6
    )

    if ([string]::IsNullOrWhiteSpace($Output)) { return "" }

    $lines = $Output -split "\r?\n"
    $filtered = foreach ($line in $lines) {
        $trim = $line.Trim()
        if (-not $trim) { continue }
        if ($trim -match '\b(KB|MB|GB)\b\s*/\s*[\d\.]+') { continue }
        if ($trim -match '^[\s\-\|\\/]+$') { continue }
        $trim
    }

    if (-not $filtered -or $filtered.Count -eq 0) { return "" }

    $tail = $filtered | Select-Object -Last $MaxLines
    return ($tail -join "`n")
}
```

**Step 3: Commit**

```bash
git add scripts/powershell/winget-machine-install/winget-machine-install.ps1
git commit -m "feat: add logging and output normalization"
```

---

### Task 3: Add winget timeout wrapper and resolution

**Files:**
- Modify: `scripts/powershell/winget-machine-install/winget-machine-install.ps1`

**Step 1: Add Invoke-WingetWithTimeout**

```powershell
function Invoke-WingetWithTimeout {
    param(
        [Parameter(Mandatory = $true)][string]$WingetPath,
        [Parameter(Mandatory = $true)][string[]]$ArgsList,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds
    )

    $tmpOut = Join-Path $env:TEMP ("winget-timeout-" + [System.Guid]::NewGuid().ToString("N") + ".log")
    $tmpErr = Join-Path $env:TEMP ("winget-timeout-" + [System.Guid]::NewGuid().ToString("N") + ".err")

    $argString = $ArgsList -join " "
    $process = Start-Process -FilePath $WingetPath -ArgumentList $argString -NoNewWindow -PassThru -RedirectStandardOutput $tmpOut -RedirectStandardError $tmpErr

    $finished = $process.WaitForExit($TimeoutSeconds * 1000)
    if (-not $finished) {
        try { Stop-Process -Id $process.Id -Force } catch {}
        return [pscustomobject]@{ Output = "Timed out after $TimeoutSeconds seconds"; ExitCode = 124; TimedOut = $true }
    }

    $stdout = if (Test-Path $tmpOut) { Get-Content $tmpOut -Raw } else { "" }
    $stderr = if (Test-Path $tmpErr) { Get-Content $tmpErr -Raw } else { "" }
    if ($stderr -and $stderr.Trim().Length -gt 0) { $stdout = $stdout + "`n" + $stderr }

    return [pscustomobject]@{ Output = $stdout; ExitCode = $process.ExitCode; TimedOut = $false }
}
```

**Step 2: Add Get-WingetPath and Initialize-Winget**

```powershell
function Get-WingetPath {
    $cmd = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $apps = Get-AppxPackage -AllUsers -Name "Microsoft.DesktopAppInstaller" -ErrorAction SilentlyContinue
    if ($apps) {
        $app = $apps | Where-Object { $_.InstallLocation } | Sort-Object Version -Descending | Select-Object -First 1
        if ($app -and $app.InstallLocation) {
            $candidate = Join-Path $app.InstallLocation "winget.exe"
            if (Test-Path $candidate) { return $candidate }
        }
    }

    return $null
}

function Initialize-Winget {
    $path = Get-WingetPath
    if ($path) { return $path }

    Write-Log -Level Warning -Message "winget not found, attempting to install App Installer"
    $tmp = Join-Path $env:TEMP "AppInstaller.msixbundle"
    Invoke-WebRequest -Uri "https://aka.ms/getwinget" -OutFile $tmp
    Add-AppxPackage -Path $tmp

    Start-Sleep -Seconds 2
    $path = Get-WingetPath
    if (-not $path) { throw "winget still not available after install attempt" }
    return $path
}
```

Note: `Get-WingetPath` sorts multiple App Installer versions descending and picks the newest. `Initialize-Winget` replaces the earlier `Ensure-Winget` name (the module keeps `Ensure-Winget` for backwards compatibility).

**Step 3: Commit**

```bash
git add scripts/powershell/winget-machine-install/winget-machine-install.ps1
git commit -m "feat: resolve winget with timeout wrapper"
```

---

### Task 4: Fetch package metadata via text output and parse scope/architecture

**Files:**
- Modify: `scripts/powershell/winget-machine-install/winget-machine-install.ps1`

**Step 1: Add Convert-WingetShowTextToPackageInfo**

```powershell
function Convert-WingetShowTextToPackageInfo {
    param([Parameter(Mandatory = $true)][object]$Output)

    $text = if ($Output -is [array]) { $Output -join "`n" } else { [string]$Output }
    $lines = $text -split "`n"
    $installers = @()
    $current = $null

    foreach ($line in $lines) {
        if ($line -match '^\s*Installer:\s*$') {
            if ($current) { $installers += [pscustomobject]$current }
            $current = @{}
            continue
        }
        if ($line -match '^\s*([^:]+):\s*(.+)$') {
            $key = $matches[1].Trim().ToLowerInvariant()
            $value = $matches[2].Trim()
            switch ($key) {
                'scope' { $current['Scope'] = $value }
                'installer architecture' { $current['Architecture'] = $value }
                'architecture' { $current['Architecture'] = $value }
            }
        }
    }

    if ($current) { $installers += [pscustomobject]$current }

    # Fallback: regex scan for Scope lines if no Installer blocks found
    if (-not $installers -or $installers.Count -eq 0) {
        $regexOptions = [System.Text.RegularExpressions.RegexOptions]::IgnoreCase -bor [System.Text.RegularExpressions.RegexOptions]::Multiline
        $matches = [regex]::Matches($text, '^\s*Scope:\s*(\S+)\s*$', $regexOptions)
        foreach ($match in $matches) {
            $installers += [pscustomobject]@{ Scope = $match.Groups[1].Value }
        }
    }

    [pscustomobject]@{ Installers = $installers }
}
```

Note: Uses text output parsing instead of `--output json` because many winget versions do not support the `--output` flag. The parser looks for structured `Installer:` blocks first, then falls back to global `Scope:` regex.

**Step 2: Add Get-WingetPackageInfo with timeout and resilient error handling**

```powershell
function Get-WingetPackageInfo {
    param([string]$WingetPath, [string]$Id)

    Write-Log -Level Info -Message "Running winget show for Id=$Id"
    $showStart = Get-Date
    $textResult = Invoke-WingetWithTimeout -WingetPath $WingetPath -ArgsList @("show", "--id", $Id, "--source", "winget", "--accept-source-agreements", "--disable-interactivity") -TimeoutSeconds 60
    $elapsed = (New-TimeSpan -Start $showStart -End (Get-Date)).TotalSeconds
    Write-Log -Level Info -Message "Completed winget show (elapsed ${elapsed}s)"

    if ($textResult.TimedOut) {
        Write-Log -Level Warning -Message "winget show timed out; skipping machine scope check"
        return [pscustomobject]@{ Installers = @(); SkipScopeCheck = $true }
    }

    if ($textResult.ExitCode -ne 0) {
        $outputText = [string]$textResult.Output
        if ($outputText -match "Found\s+.+\[" -and $outputText -match "Installer:") {
            Write-Log -Level Warning -Message "winget show returned non-zero but output looks valid; continuing"
        } else {
            Write-Log -Level Error -Message "winget show failed: $($textResult.Output)"
            throw "winget show failed for Id=$Id"
        }
    }

    return Convert-WingetShowTextToPackageInfo -Output $textResult.Output
}
```

**Step 3: Commit**

```bash
git add scripts/powershell/winget-machine-install/winget-machine-install.ps1
git commit -m "feat: parse winget text metadata with timeout"
```

---

### Task 5: Add architecture-aware scope validation

**Files:**
- Modify: `scripts/powershell/winget-machine-install/winget-machine-install.ps1`

**Step 1: Add architecture normalization and filtering**

```powershell
function Convert-Architecture {
    param([string]$Architecture)
    if ([string]::IsNullOrWhiteSpace($Architecture)) { return $null }
    $value = $Architecture.Trim().ToLowerInvariant()
    switch ($value) {
        'amd64' { return 'x64' }
        'x64'   { return 'x64' }
        'x86'   { return 'x86' }
        'x32'   { return 'x86' }
        'i386'  { return 'x86' }
        'arm64' { return 'arm64' }
        'aarch64' { return 'arm64' }
        default { return $value }
    }
}

function Get-DeviceArchitecture {
    $arch = $env:architecture
    if ([string]::IsNullOrWhiteSpace($arch)) { $arch = "x64" }
    return (Convert-Architecture -Architecture $arch)
}

function Get-InstallersForArchitecture {
    param([object]$PkgInfo, [string]$Architecture)
    $normalizedArch = Convert-Architecture -Architecture $Architecture
    $installers = @()
    foreach ($installer in $PkgInfo.Installers) {
        $installerArch = Convert-Architecture -Architecture $installer.Architecture
        if (-not $installerArch -or $installerArch -eq $normalizedArch) {
            $installers += $installer
        }
    }
    return $installers
}
```

**Step 2: Add Test-MachineScopeForArchitecture**

```powershell
function Test-MachineScopeForArchitecture {
    param([object]$PkgInfo, [string]$Architecture)
    if (-not $PkgInfo -or -not $PkgInfo.Installers) { return $false }
    $matching = Get-InstallersForArchitecture -PkgInfo $PkgInfo -Architecture $Architecture
    if (-not $matching -or $matching.Count -eq 0) { return $false }

    $scopes = $matching | Where-Object { $_.Scope } | ForEach-Object { $_.Scope.ToString().ToLowerInvariant() }
    if ($scopes -contains 'machine') { return $true }
    if (-not $scopes -or $scopes.Count -eq 0) { return $true }  # No scope declared → allow
    return (($scopes | Where-Object { $_ -ne 'user' }).Count -gt 0)
}
```

Note: Replaces the earlier `Supports-MachineScope` with architecture-aware validation. Installers with no explicit scope are treated as implicitly supporting machine scope.

**Step 3: Commit**

```bash
git add scripts/powershell/winget-machine-install/winget-machine-install.ps1
git commit -m "feat: architecture-aware scope validation"
```

---

### Task 6: Add install with already-installed detection

**Files:**
- Modify: `scripts/powershell/winget-machine-install/winget-machine-install.ps1`

**Step 1: Add Install-WingetPackage with already-installed handling**

```powershell
function Install-WingetPackage {
    param([string]$WingetPath, [string]$Id)

    Write-Log -Level Info -Message "Running winget install for Id=$Id"
    $output = & $WingetPath install --id $Id --source winget --scope machine --accept-package-agreements --accept-source-agreements --disable-interactivity 2>&1
    if ($LASTEXITCODE -ne 0) {
        $rawOutput = if ($output -is [array]) { $output -join "`n" } else { [string]$output }
        $cleanOutput = Normalize-WingetOutput -Output $rawOutput
        if ([string]::IsNullOrWhiteSpace($cleanOutput)) { $cleanOutput = $rawOutput }

        $alreadyInstalled =
            ($cleanOutput -match '(?i)already installed') -or
            ($cleanOutput -match '(?i)no available upgrade found') -or
            ($cleanOutput -match '(?i)no newer package versions are available')

        if ($alreadyInstalled) {
            Write-Log -Level Warning -Message "winget install indicates already installed or no upgrade available for Id=$Id. Output: $cleanOutput"
            return
        }

        Write-Log -Level Error -Message "winget install failed: $cleanOutput"
        throw "winget install failed for Id=$Id"
    }

    Write-Log -Level Info -Message "Install completed successfully"
}
```

Note: Uses `--source winget` and `--disable-interactivity` flags. Already-installed states are treated as warnings, not failures, so they count toward `$successCount`.

**Step 2: Commit**

```bash
git add scripts/powershell/winget-machine-install/winget-machine-install.ps1
git commit -m "feat: install with already-installed detection"
```

---

### Task 7: Add Public Desktop shortcut copying

**Files:**
- Modify: `scripts/powershell/winget-machine-install/winget-machine-install.ps1`

**Step 1: Add shortcut discovery and copy functions**

```powershell
function Get-StartMenuShortcuts {
    $path = "C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs"
    if (-not (Test-Path $path)) { return @() }
    return Get-ChildItem -Path $path -Filter "*.lnk" -Recurse -ErrorAction SilentlyContinue
}

function Find-BestShortcut {
    param([object[]]$Shortcuts, [string]$Id, [datetime]$InstallStart)
    $graceStart = $InstallStart.AddMinutes(-2)
    $recent = $Shortcuts | Where-Object { $_.LastWriteTime -ge $graceStart }
    $normalizedId = $Id.ToLowerInvariant()
    $nameMatches = $recent | Where-Object {
        $_.BaseName.ToLowerInvariant().Contains($normalizedId) -or $_.Name.ToLowerInvariant().Contains($normalizedId)
    }
    $candidates = if ($nameMatches -and $nameMatches.Count -gt 0) { $nameMatches } else { $recent }
    if ($candidates -and $candidates.Count -gt 0) {
        return ($candidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1)
    }
    return $null
}

function Set-PublicDesktopShortcut {
    param([string]$Id, [datetime]$InstallStart)
    $publicDesktop = "C:\\Users\\Public\\Desktop"
    if (-not (Test-Path $publicDesktop)) {
        Write-Log -Level Warning -Message "Public Desktop not found"; return
    }
    $shortcuts = Get-StartMenuShortcuts
    if (-not $shortcuts -or $shortcuts.Count -eq 0) {
        Write-Log -Level Warning -Message "No Start Menu shortcuts found"; return
    }
    $match = Find-BestShortcut -Shortcuts $shortcuts -Id $Id -InstallStart $InstallStart
    if (-not $match) {
        Write-Log -Level Warning -Message "No suitable shortcut found for Id=$Id"; return
    }
    $dest = Join-Path $publicDesktop $match.Name
    if (Test-Path $dest) {
        Write-Log -Level Info -Message "Public Desktop shortcut already exists: $dest"; return
    }
    try {
        Copy-Item -Path $match.FullName -Destination $dest -Force
        Write-Log -Level Info -Message "Copied shortcut to Public Desktop: $dest"
    } catch {
        Write-Log -Level Warning -Message "Failed to copy shortcut: $_"
    }
}
```

Note: Shortcut matching uses a 2-minute grace window before install start to handle clock skew. Prefers name-matched shortcuts over recency alone. All failures are non-fatal warnings.

**Step 2: Commit**

```bash
git add scripts/powershell/winget-machine-install/winget-machine-install.ps1
git commit -m "feat: copy Start Menu shortcut to Public Desktop"
```

---

### Task 8: Wire main orchestration flow with multi-package support

**Files:**
- Modify: `scripts/powershell/winget-machine-install/winget-machine-install.ps1`

**Step 1: Add Invoke-WingetMachineInstall orchestrator**

```powershell
function Invoke-WingetMachineInstall {
    param(
        [Parameter(Mandatory = $true)][string]$Id,
        [Parameter(Mandatory = $false)][string]$LogPath
    )

    if ([string]::IsNullOrWhiteSpace($LogPath)) {
        $safeId = $Id -replace '[^a-zA-Z0-9._-]', '_'
        $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $LogPath = Join-Path $env:TEMP "winget-install-$safeId-$timestamp.log"
    }
    $script:LogPath = $LogPath

    $ids = $Id -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    if (-not $ids) { throw "No package IDs provided" }

    Write-Log -Level Info -Message "Starting winget machine install for Ids=$($ids -join ', ')"
    Write-Log -Level Info -Message "LogPath=$LogPath"
    Write-Log -Level Info -Message "OS=$([System.Environment]::OSVersion.VersionString)"
    Write-Log -Level Info -Message "PowerShell=$($PSVersionTable.PSVersion)"

    $wingetPath = Initialize-Winget
    Write-Log -Level Info -Message "Using winget at $wingetPath"

    $deviceArch = Get-DeviceArchitecture
    Write-Log -Level Info -Message "Device architecture: $deviceArch"

    $successCount = 0
    $failureCount = 0

    foreach ($pkgId in $ids) {
        Write-Log -Level Info -Message "Processing Id=$pkgId"
        try {
            $installStart = Get-Date
            $pkg = Get-WingetPackageInfo -WingetPath $wingetPath -Id $pkgId

            if ($pkg -and $pkg.SkipScopeCheck -eq $true) {
                Write-Log -Level Warning -Message "Skipping scope check (timeout) for Id=$pkgId"
            } else {
                if (-not (Test-MachineScopeForArchitecture -PkgInfo $pkg -Architecture $deviceArch)) {
                    throw "Machine scope not supported for Id=$pkgId on architecture $deviceArch"
                }
                Write-Log -Level Info -Message "Machine scope supported, starting install"
            }

            Install-WingetPackage -WingetPath $wingetPath -Id $pkgId
            Set-PublicDesktopShortcut -Id $pkgId -InstallStart $installStart
            $successCount += 1
        } catch {
            $failureCount += 1
            Write-Log -Level Error -Message "Id=$pkgId failed: $_"
        }
    }

    Write-Log -Level Info -Message "Completed. Successes=$successCount Failures=$failureCount"
    if ($successCount -eq 0) { throw "All package installs failed" }
}

Invoke-WingetMachineInstall -Id $Id -LogPath $LogPath
exit 0
```

Note: Each package is processed independently with its own try/catch. Partial success (some packages installed, some failed) is allowed — the script only throws if all packages fail.

**Step 2: Commit**

```bash
git add scripts/powershell/winget-machine-install/winget-machine-install.ps1
git commit -m "feat: multi-package orchestration with per-package error handling"
```

---

### Task 9: Create module variant

**Files:**
- Create: `scripts/powershell/winget-machine-install/winget-machine-install.psm1`

**Step 1: Create module with exported functions**

Copy all helper functions into the module. Key differences from `.ps1`:
- No `param()` block or script header.
- `Initialize-Winget` is named `Ensure-Winget` in the module.
- Uses a simpler `Invoke-Winget` (direct call, no timeout) instead of `Invoke-WingetWithTimeout`.
- `Get-WingetPackageInfo` tries `--output json` first, falls back to text parsing.
- `Export-ModuleMember` exports all public functions.

**Step 2: Commit**

```bash
git add scripts/powershell/winget-machine-install/winget-machine-install.psm1
git commit -m "feat: add module variant for testing and reuse"
```

---

### Task 10: Manual validation and polish

**Verification scenarios:**
1. Single package, machine scope supported → installs successfully.
2. Comma-separated IDs, mix of valid/invalid → partial success reported.
3. Winget not in PATH but App Installer present → resolves path and installs.
4. Winget missing entirely → bootstraps App Installer, then installs.
5. Package without machine scope for device arch → fails with clear error.
6. Invalid package ID → `winget show` failure logged, package skipped.
7. Package already installed → warning logged, counted as success.
8. Winget show timeout → scope check skipped, install attempted.
9. Architecture filtering → correct installer subset validated.
10. Desktop shortcut → `.lnk` copied to Public Desktop after install.
11. Logging → temp log file + stdout/stderr mirrored messages.
