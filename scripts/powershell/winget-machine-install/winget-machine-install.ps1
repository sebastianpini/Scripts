<#
.SYNOPSIS
[Version 1.2.0] Installs a Winget package in machine scope under SYSTEM.
Change Log:
- 1.2.0: Copy Start Menu shortcut to Public Desktop after install.
- 1.1.1: Standardized warning output to [Warning].
- 1.1.0: Single-file packaging.
Example output:
[Info] Starting winget machine install for Id=Microsoft.PowerShell
[Info] LogPath=C:\Users\...\AppData\Local\Temp\winget-install-Microsoft.PowerShell-20260204-120000.log

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

function Invoke-WingetWithTimeout {
    param(
        [Parameter(Mandatory = $true)][string]$WingetPath,
        [Parameter(Mandatory = $true)][string[]]$ArgsList,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds
    )

    $tmpOut = Join-Path -Path $env:TEMP -ChildPath ("winget-timeout-" + [System.Guid]::NewGuid().ToString("N") + ".log")
    $tmpErr = Join-Path -Path $env:TEMP -ChildPath ("winget-timeout-" + [System.Guid]::NewGuid().ToString("N") + ".err")

    $argString = $ArgsList -join " "
    $process = Start-Process -FilePath $WingetPath -ArgumentList $argString -NoNewWindow -PassThru -RedirectStandardOutput $tmpOut -RedirectStandardError $tmpErr

    $finished = $process.WaitForExit($TimeoutSeconds * 1000)
    if (-not $finished) {
        try { Stop-Process -Id $process.Id -Force } catch {}
        return [pscustomobject]@{
            Output = "Timed out after $TimeoutSeconds seconds"
            ExitCode = 124
            TimedOut = $true
        }
    }

    $stdout = if (Test-Path $tmpOut) { Get-Content -Path $tmpOut -Raw } else { "" }
    $stderr = if (Test-Path $tmpErr) { Get-Content -Path $tmpErr -Raw } else { "" }
    if ($stderr -and $stderr.Trim().Length -gt 0) {
        $stdout = $stdout + "`n" + $stderr
    }

    return [pscustomobject]@{
        Output = $stdout
        ExitCode = $process.ExitCode
        TimedOut = $false
    }
}

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

    if (-not $installers -or $installers.Count -eq 0) {
        $regexOptions = [System.Text.RegularExpressions.RegexOptions]::IgnoreCase -bor [System.Text.RegularExpressions.RegexOptions]::Multiline
        $matches = [regex]::Matches($text, '^\s*Scope:\s*(\S+)\s*$', $regexOptions)
        foreach ($match in $matches) {
            $installers += [pscustomobject]@{ Scope = $match.Groups[1].Value }
        }
    }

    [pscustomobject]@{ Installers = $installers }
}

function Get-WingetPath {
    $cmd = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $apps = Get-AppxPackage -AllUsers -Name "Microsoft.DesktopAppInstaller" -ErrorAction SilentlyContinue
    if ($apps) {
        $app = $apps | Where-Object { $_.InstallLocation } | Sort-Object Version -Descending | Select-Object -First 1
        if ($app -and $app.InstallLocation) {
            $candidate = Join-Path -Path $app.InstallLocation -ChildPath "winget.exe"
            if (Test-Path $candidate) { return $candidate }
        }
    }

    return $null
}

function Initialize-Winget {
    $path = Get-WingetPath
    if ($path) { return $path }

    Write-Log -Level Warning -Message "winget not found, attempting to install App Installer"

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

function Get-WingetPackageInfo {
    param([string]$WingetPath, [string]$Id)

    Write-Log -Level Info -Message "Running winget show for Id=$Id"
    $showStart = Get-Date
    $textResult = Invoke-WingetWithTimeout -WingetPath $WingetPath -ArgsList @("show", "--id", $Id, "--source", "winget", "--accept-source-agreements", "--disable-interactivity") -TimeoutSeconds 60
    $showEnd = Get-Date
    $elapsed = New-TimeSpan -Start $showStart -End $showEnd
    Write-Log -Level Info -Message "Completed winget show text at $showEnd (elapsed $($elapsed.TotalSeconds)s)"

    if ($textResult.TimedOut) {
        Write-Log -Level Warning -Message "winget show text timed out; skipping machine scope check"
        return [pscustomobject]@{
            Installers = @()
            SkipScopeCheck = $true
        }
    }

    if ($textResult.ExitCode -ne 0) {
        $outputText = [string]$textResult.Output
        if ($outputText -match "Found\s+.+\[" -and $outputText -match "Installer:") {
            Write-Log -Level Warning -Message "winget show returned non-zero exit code but output looks valid; continuing"
        } else {
            Write-Log -Level Error -Message "winget show failed: $($textResult.Output)"
            throw "winget show failed for Id=$Id"
        }
    }

    return Convert-WingetShowTextToPackageInfo -Output $textResult.Output
}

function Convert-Architecture {
    param([string]$Architecture)

    if ([string]::IsNullOrWhiteSpace($Architecture)) { return $null }
    $value = $Architecture.ToString().Trim().ToLowerInvariant()

    switch ($value) {
        'amd64' { return 'x64' }
        'x64' { return 'x64' }
        'x86' { return 'x86' }
        'x32' { return 'x86' }
        'i386' { return 'x86' }
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
    param(
        [Parameter(Mandatory = $true)][object]$PkgInfo,
        [Parameter(Mandatory = $true)][string]$Architecture
    )

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

function Test-MachineScopeForArchitecture {
    param(
        [Parameter(Mandatory = $true)][object]$PkgInfo,
        [Parameter(Mandatory = $true)][string]$Architecture
    )

    if (-not $PkgInfo -or -not $PkgInfo.Installers) { return $false }

    $matching = Get-InstallersForArchitecture -PkgInfo $PkgInfo -Architecture $Architecture
    if (-not $matching -or $matching.Count -eq 0) { return $false }

    $scopes = $matching |
        Where-Object { $_.Scope } |
        ForEach-Object { $_.Scope.ToString().ToLowerInvariant() }

    if ($scopes -contains 'machine') { return $true }
    if (-not $scopes -or $scopes.Count -eq 0) { return $true }

    return (($scopes | Where-Object { $_ -ne 'user' }).Count -gt 0)
}

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

function Get-StartMenuShortcuts {
    $path = "C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs"
    if (-not (Test-Path $path)) { return @() }
    return Get-ChildItem -Path $path -Filter "*.lnk" -Recurse -ErrorAction SilentlyContinue
}

function Find-BestShortcut {
    param(
        [Parameter(Mandatory = $true)][object[]]$Shortcuts,
        [Parameter(Mandatory = $true)][string]$Id,
        [Parameter(Mandatory = $true)][datetime]$InstallStart
    )

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
    param(
        [Parameter(Mandatory = $true)][string]$Id,
        [Parameter(Mandatory = $true)][datetime]$InstallStart
    )

    $publicDesktop = "C:\\Users\\Public\\Desktop"
    if (-not (Test-Path $publicDesktop)) {
        Write-Log -Level Warning -Message "Public Desktop not found at $publicDesktop"
        return
    }

    $shortcuts = Get-StartMenuShortcuts
    if (-not $shortcuts -or $shortcuts.Count -eq 0) {
        Write-Log -Level Warning -Message "No Start Menu shortcuts found to copy"
        return
    }

    $match = Find-BestShortcut -Shortcuts $shortcuts -Id $Id -InstallStart $InstallStart
    if (-not $match) {
        Write-Log -Level Warning -Message "No suitable Start Menu shortcut found for Id=$Id"
        return
    }

    $dest = Join-Path -Path $publicDesktop -ChildPath $match.Name
    if (Test-Path $dest) {
        Write-Log -Level Info -Message "Public Desktop shortcut already exists: $dest"
        return
    }

    try {
        Copy-Item -Path $match.FullName -Destination $dest -Force
        Write-Log -Level Info -Message "Copied shortcut to Public Desktop: $dest"
    } catch {
        Write-Log -Level Warning -Message "Failed to copy shortcut to Public Desktop: $_"
    }
}

function Invoke-WingetMachineInstall {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Id,

        [Parameter(Mandatory = $false)]
        [string]$LogPath
    )

    if ([string]::IsNullOrWhiteSpace($LogPath)) {
        $safeId = $Id -replace '[^a-zA-Z0-9._-]', '_'
        $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $LogPath = Join-Path -Path $env:TEMP -ChildPath "winget-install-$safeId-$timestamp.log"
    }

    $script:LogPath = $LogPath

    $ids = $Id -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    if (-not $ids) {
        throw "No package IDs provided"
    }

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
                Write-Log -Level Warning -Message "Skipping machine scope check due to winget show timeout for Id=$pkgId"
            } else {
                $archInstallers = Get-InstallersForArchitecture -PkgInfo $pkg -Architecture $deviceArch
                Write-Log -Level Info -Message "Matching installers for ${deviceArch}: $($archInstallers.Count)"
                if (-not (Test-MachineScopeForArchitecture -PkgInfo $pkg -Architecture $deviceArch)) {
                    Write-Log -Level Error -Message "Package does not support machine scope for architecture $deviceArch"
                    throw "Machine scope not supported for Id=$pkgId on architecture $deviceArch"
                }
                Write-Log -Level Info -Message "Machine scope supported, starting install"
            }

            Install-WingetPackage -WingetPath $wingetPath -Id $pkgId
            Set-PublicDesktopShortcut -Id $pkgId -InstallStart $installStart
            Write-Log -Level Info -Message "Id=$pkgId completed successfully"
            $successCount += 1
        } catch {
            $failureCount += 1
            Write-Log -Level Error -Message "Id=$pkgId failed: $_"
        }
    }

    Write-Log -Level Info -Message "Completed. Successes=$successCount Failures=$failureCount"

    if ($successCount -eq 0) {
        throw "All package installs failed"
    }
}

Invoke-WingetMachineInstall -Id $Id -LogPath $LogPath
exit 0
