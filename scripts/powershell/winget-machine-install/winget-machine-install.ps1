<#
.SYNOPSIS
[Version 1.3.0] Installs a Winget package in machine scope under SYSTEM.
Change Log:
- 1.3.0: Optional exact-version install + installed-version pinning with end summary.
- 1.2.0: Copy Start Menu shortcut to Public Desktop after install.
- 1.1.1: Standardized warning output to [Warning].
- 1.1.0: Single-file packaging.
Example output:
[Info] Starting winget machine install for Id=Microsoft.PowerShell
[Info] LogPath=C:\Users\...\AppData\Local\Temp\winget-install-Microsoft.PowerShell-20260204-120000.log

.DESCRIPTION
Ensures winget is available, validates machine scope support, and installs
with RMM-friendly logging to stdout/stderr and a temp log file.

.NOTES
Provided AS IS, without warranty of any kind, express or implied, including
merchantability, fitness for a particular purpose, or noninfringement. Use at
your own risk. The author shall not be liable for any claim, damages, or other
liability arising from, out of, or in connection with the script or its use.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$Id = $env:wingetId,

    [Parameter(Mandatory = $false)]
    [string]$Version = $env:wingetVersion,

    [Parameter(Mandatory = $false)]
    [switch]$PinInstalledVersion,

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

function Convert-WingetOutputToText {
    param([Parameter(Mandatory = $true)][object]$Output)

    if ($null -eq $Output) { return "" }
    if ($Output -is [array]) {
        return (($Output | ForEach-Object { [string]$_ }) -join "`n")
    }

    return [string]$Output
}

function Invoke-Winget {
    param(
        [Parameter(Mandatory = $true)][string]$WingetPath,
        [Parameter(Mandatory = $true)][string[]]$ArgsList
    )

    $output = & $WingetPath @ArgsList 2>&1
    [pscustomobject]@{
        Output = $output
        ExitCode = $LASTEXITCODE
    }
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

    $outputText = Convert-WingetOutputToText -Output $textResult.Output
    if ($textResult.ExitCode -ne 0) {
        if ($outputText -match "Found\s+.+\[" -and $outputText -match "Installer:") {
            Write-Log -Level Warning -Message "winget show returned non-zero exit code but output looks valid; continuing"
        } else {
            $cleanOutput = Normalize-WingetOutput -Output $outputText
            if ([string]::IsNullOrWhiteSpace($cleanOutput)) { $cleanOutput = $outputText }
            Write-Log -Level Error -Message "winget show failed: $cleanOutput"
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

function Get-PerPackageOptionMap {
    param(
        [Parameter(Mandatory = $true)][string[]]$Ids,
        [Parameter(Mandatory = $false)][string]$RawValue,
        [Parameter(Mandatory = $true)][string]$OptionName
    )

    $map = @{}
    if ([string]::IsNullOrWhiteSpace($RawValue)) { return $map }

    $values = $RawValue -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    if (-not $values -or $values.Count -eq 0) { return $map }

    if ($values.Count -ne $Ids.Count) {
        throw "$OptionName count ($($values.Count)) must match Id count ($($Ids.Count))"
    }

    for ($i = 0; $i -lt $Ids.Count; $i++) {
        $map[$Ids[$i]] = $values[$i]
    }

    return $map
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
    param(
        [string]$WingetPath,
        [string]$Id,
        [string]$Version
    )

    $argsList = @("install", "--id", $Id, "--source", "winget", "--scope", "machine", "--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity")
    if (-not [string]::IsNullOrWhiteSpace($Version)) {
        Write-Log -Level Info -Message "Running winget install for Id=$Id Version=$Version"
        $argsList += @("--version", $Version)
    } else {
        Write-Log -Level Info -Message "Running winget install for Id=$Id"
    }

    $result = Invoke-Winget -WingetPath $WingetPath -ArgsList $argsList
    if ($result.ExitCode -ne 0) {
        $rawOutput = Convert-WingetOutputToText -Output $result.Output
        $cleanOutput = Normalize-WingetOutput -Output $rawOutput
        if ([string]::IsNullOrWhiteSpace($cleanOutput)) { $cleanOutput = $rawOutput }

        $alreadyInstalled =
            ($cleanOutput -match '(?i)already installed') -or
            ($cleanOutput -match '(?i)no available upgrade found') -or
            ($cleanOutput -match '(?i)no newer package versions are available')

        if ($alreadyInstalled) {
            Write-Log -Level Warning -Message "winget install indicates already installed or no upgrade available for Id=$Id. Output: $cleanOutput"
            return [pscustomobject]@{
                Status = "AlreadyInstalled"
            }
        }

        Write-Log -Level Error -Message "winget install failed: $cleanOutput"
        throw "winget install failed for Id=$Id"
    }

    Write-Log -Level Info -Message "Install completed successfully"
    return [pscustomobject]@{
        Status = "Installed"
    }
}

function Convert-WingetPinListToPackagePin {
    param(
        [Parameter(Mandatory = $true)][object]$Output,
        [Parameter(Mandatory = $true)][string]$Id
    )

    $text = Convert-WingetOutputToText -Output $Output
    if ([string]::IsNullOrWhiteSpace($text)) { return $null }

    $lines = $text -split "\r?\n"
    foreach ($line in $lines) {
        $trim = $line.Trim()
        if (-not $trim) { continue }
        if ($trim -match '^(Name|[-]+)\s*$') { continue }

        $parts = $trim -split '\s{2,}'
        if ($parts.Count -lt 4) { continue }

        $idIndex = [array]::IndexOf($parts, $Id)
        if ($idIndex -lt 0) { continue }
        if (($idIndex + 2) -ge $parts.Count) { continue }

        $name = if ($idIndex -gt 0) { ($parts[0..($idIndex - 1)] -join ' ') } else { "" }
        $version = $parts[$idIndex + 1]
        $source = $parts[$idIndex + 2]
        $pinType = if (($idIndex + 3) -lt $parts.Count) { ($parts[($idIndex + 3)..($parts.Count - 1)] -join ' ') } else { "" }

        return [pscustomobject]@{
            Name = $name
            Id = $Id
            Version = $version
            Source = $source
            PinType = $pinType
        }
    }

    return $null
}

function Test-WingetPinUnsupported {
    param([Parameter(Mandatory = $true)][string]$OutputText)

    return (
        ($OutputText -match '(?i)\bpin\b.+(not recognized|unrecognized|unknown)') -or
        ($OutputText -match '(?i)(no command named|invalid command).*pin') -or
        ($OutputText -match '(?i)command line alias .* was not found')
    )
}

function Test-WingetNoMatch {
    param([Parameter(Mandatory = $true)][string]$OutputText)

    return (
        ($OutputText -match '(?i)no (installed )?package found') -or
        ($OutputText -match '(?i)no package found matching input criteria') -or
        ($OutputText -match '(?i)no pinned package found')
    )
}

function Get-WingetPackagePin {
    param(
        [Parameter(Mandatory = $true)][string]$WingetPath,
        [Parameter(Mandatory = $true)][string]$Id
    )

    $result = Invoke-Winget -WingetPath $WingetPath -ArgsList @("pin", "list", "--id", $Id, "--exact", "--accept-source-agreements", "--disable-interactivity")
    $outputText = Convert-WingetOutputToText -Output $result.Output

    if ($result.ExitCode -ne 0) {
        if (Test-WingetPinUnsupported -OutputText $outputText) {
            throw "winget pin commands are not supported by the installed App Installer version"
        }
        if (Test-WingetNoMatch -OutputText $outputText) {
            return $null
        }

        $cleanOutput = Normalize-WingetOutput -Output $outputText
        if ([string]::IsNullOrWhiteSpace($cleanOutput)) { $cleanOutput = $outputText }
        Write-Log -Level Error -Message "winget pin list failed: $cleanOutput"
        throw "winget pin list failed for Id=$Id"
    }

    return Convert-WingetPinListToPackagePin -Output $result.Output -Id $Id
}

function Remove-WingetPackagePin {
    param(
        [Parameter(Mandatory = $true)][string]$WingetPath,
        [Parameter(Mandatory = $true)][string]$Id
    )

    Write-Log -Level Info -Message "Removing existing pin for Id=$Id"
    $result = Invoke-Winget -WingetPath $WingetPath -ArgsList @("pin", "remove", "--id", $Id, "--exact", "--accept-source-agreements", "--disable-interactivity")
    if ($result.ExitCode -ne 0) {
        $outputText = Convert-WingetOutputToText -Output $result.Output
        if (Test-WingetPinUnsupported -OutputText $outputText) {
            throw "winget pin commands are not supported by the installed App Installer version"
        }
        if (Test-WingetNoMatch -OutputText $outputText) {
            return
        }

        $cleanOutput = Normalize-WingetOutput -Output $outputText
        if ([string]::IsNullOrWhiteSpace($cleanOutput)) { $cleanOutput = $outputText }
        Write-Log -Level Error -Message "winget pin remove failed: $cleanOutput"
        throw "winget pin remove failed for Id=$Id"
    }
}

function Set-WingetPackagePin {
    param(
        [Parameter(Mandatory = $true)][string]$WingetPath,
        [Parameter(Mandatory = $true)][string]$Id
    )

    $existingPin = Get-WingetPackagePin -WingetPath $WingetPath -Id $Id
    if ($existingPin) {
        Remove-WingetPackagePin -WingetPath $WingetPath -Id $Id
    }

    Write-Log -Level Info -Message "Pinning installed version for Id=$Id"
    $result = Invoke-Winget -WingetPath $WingetPath -ArgsList @("pin", "add", "--id", $Id, "--exact", "--installed", "--accept-source-agreements", "--disable-interactivity")
    if ($result.ExitCode -ne 0) {
        $outputText = Convert-WingetOutputToText -Output $result.Output
        if (Test-WingetPinUnsupported -OutputText $outputText) {
            throw "winget pin commands are not supported by the installed App Installer version"
        }

        $cleanOutput = Normalize-WingetOutput -Output $outputText
        if ([string]::IsNullOrWhiteSpace($cleanOutput)) { $cleanOutput = $outputText }
        Write-Log -Level Error -Message "winget pin add failed: $cleanOutput"
        throw "winget pin add failed for Id=$Id"
    }

    $pin = Get-WingetPackagePin -WingetPath $WingetPath -Id $Id
    if (-not $pin) {
        throw "winget pin add completed but no pin entry was found for Id=$Id"
    }

    Write-Log -Level Info -Message "Pin applied: Version=$($pin.Version) Type=$($pin.PinType)"
    return [pscustomobject]@{
        Status = $(if ($existingPin) { "Updated" } else { "Added" })
        Version = $pin.Version
        PinType = $pin.PinType
    }
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
        return [pscustomobject]@{
            Status = "PublicDesktopMissing"
        }
    }

    $shortcuts = Get-StartMenuShortcuts
    if (-not $shortcuts -or $shortcuts.Count -eq 0) {
        Write-Log -Level Warning -Message "No Start Menu shortcuts found to copy"
        return [pscustomobject]@{
            Status = "NoStartMenuShortcuts"
        }
    }

    $match = Find-BestShortcut -Shortcuts $shortcuts -Id $Id -InstallStart $InstallStart
    if (-not $match) {
        Write-Log -Level Warning -Message "No suitable Start Menu shortcut found for Id=$Id"
        return [pscustomobject]@{
            Status = "NotFound"
        }
    }

    $dest = Join-Path -Path $publicDesktop -ChildPath $match.Name
    if (Test-Path $dest) {
        Write-Log -Level Info -Message "Public Desktop shortcut already exists: $dest"
        return [pscustomobject]@{
            Status = "AlreadyExists"
        }
    }

    try {
        Copy-Item -Path $match.FullName -Destination $dest -Force
        Write-Log -Level Info -Message "Copied shortcut to Public Desktop: $dest"
        return [pscustomobject]@{
            Status = "Copied"
        }
    } catch {
        Write-Log -Level Warning -Message "Failed to copy shortcut to Public Desktop: $_"
        return [pscustomobject]@{
            Status = "CopyFailed"
        }
    }
}

function Format-SummaryValue {
    param([Parameter(Mandatory = $true)][string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) { return "n/a" }
    return $Value
}

function Write-ExecutionSummary {
    param(
        [Parameter(Mandatory = $true)][object[]]$Results,
        [Parameter(Mandatory = $true)][int]$SuccessCount,
        [Parameter(Mandatory = $true)][int]$FailureCount
    )

    Write-Log -Level Info -Message "Completed. Successes=$SuccessCount Failures=$FailureCount"

    foreach ($result in $Results) {
        $requestedVersion = if ([string]::IsNullOrWhiteSpace($result.RequestedVersion)) { "latest" } else { $result.RequestedVersion }
        $pinSummary = $result.PinStatus
        if (-not [string]::IsNullOrWhiteSpace($result.PinVersion)) {
            $pinSummary = $pinSummary + ":" + $result.PinVersion
        }
        if (-not [string]::IsNullOrWhiteSpace($result.PinType)) {
            $pinSummary = $pinSummary + ":" + $result.PinType
        }

        $message = "Summary Id=$($result.Id); RequestedVersion=$requestedVersion; ScopeCheck=$(Format-SummaryValue -Value $result.ScopeCheck); Install=$(Format-SummaryValue -Value $result.InstallStatus); Pin=$(Format-SummaryValue -Value $pinSummary); Shortcut=$(Format-SummaryValue -Value $result.ShortcutStatus)"
        if (-not [string]::IsNullOrWhiteSpace($result.Error)) {
            $message = "$message; Error=$($result.Error)"
        }

        Write-Log -Level Info -Message $message
    }
}

function Invoke-WingetMachineInstall {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Id,

        [Parameter(Mandatory = $false)]
        [string]$Version,

        [Parameter(Mandatory = $false)]
        [switch]$PinInstalledVersion,

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
    $versionMap = Get-PerPackageOptionMap -Ids $ids -RawValue $Version -OptionName "Version"

    Write-Log -Level Info -Message "Starting winget machine install for Ids=$($ids -join ', ')"
    Write-Log -Level Info -Message "LogPath=$LogPath"
    Write-Log -Level Info -Message "OS=$([System.Environment]::OSVersion.VersionString)"
    Write-Log -Level Info -Message "PowerShell=$($PSVersionTable.PSVersion)"
    if ($PinInstalledVersion) {
        Write-Log -Level Info -Message "Installed-version pinning enabled"
        if ($ids.Count -gt 1) {
            Write-Log -Level Warning -Message "PinInstalledVersion is intended for single-app runs. A pin will be applied to each package ID provided."
        }
    }

    $wingetPath = Initialize-Winget
    Write-Log -Level Info -Message "Using winget at $wingetPath"

    $deviceArch = Get-DeviceArchitecture
    Write-Log -Level Info -Message "Device architecture: $deviceArch"

    $successCount = 0
    $failureCount = 0
    $results = @()

    foreach ($pkgId in $ids) {
        $requestedVersion = if ($versionMap.ContainsKey($pkgId)) { $versionMap[$pkgId] } else { "" }
        $result = [ordered]@{
            Id = $pkgId
            RequestedVersion = $requestedVersion
            ScopeCheck = "Pending"
            InstallStatus = "NotAttempted"
            PinStatus = $(if ($PinInstalledVersion) { "Pending" } else { "NotRequested" })
            PinVersion = ""
            PinType = ""
            ShortcutStatus = "NotAttempted"
            Error = ""
        }

        Write-Log -Level Info -Message "Processing Id=$pkgId"

        try {
            $installStart = Get-Date
            $pkg = Get-WingetPackageInfo -WingetPath $wingetPath -Id $pkgId

            if ($pkg -and $pkg.SkipScopeCheck -eq $true) {
                Write-Log -Level Warning -Message "Skipping machine scope check due to winget show timeout for Id=$pkgId"
                $result.ScopeCheck = "SkippedTimeout"
            } else {
                $archInstallers = Get-InstallersForArchitecture -PkgInfo $pkg -Architecture $deviceArch
                Write-Log -Level Info -Message "Matching installers for ${deviceArch}: $($archInstallers.Count)"
                if (-not (Test-MachineScopeForArchitecture -PkgInfo $pkg -Architecture $deviceArch)) {
                    $result.ScopeCheck = "Rejected"
                    Write-Log -Level Error -Message "Package does not support machine scope for architecture $deviceArch"
                    throw "Machine scope not supported for Id=$pkgId on architecture $deviceArch"
                }
                $result.ScopeCheck = "Validated"
                Write-Log -Level Info -Message "Machine scope supported, starting install"
            }

            $installResult = Install-WingetPackage -WingetPath $wingetPath -Id $pkgId -Version $requestedVersion
            $result.InstallStatus = $installResult.Status

            $shortcutResult = Set-PublicDesktopShortcut -Id $pkgId -InstallStart $installStart
            $result.ShortcutStatus = $shortcutResult.Status

            if ($PinInstalledVersion) {
                $pinResult = Set-WingetPackagePin -WingetPath $wingetPath -Id $pkgId
                $result.PinStatus = $pinResult.Status
                $result.PinVersion = $pinResult.Version
                $result.PinType = $pinResult.PinType
            }
            Write-Log -Level Info -Message "Id=$pkgId completed successfully"
            $successCount += 1
        } catch {
            $failureCount += 1
            $result.Error = $_.ToString()
            if ($result.InstallStatus -eq "NotAttempted") {
                $result.InstallStatus = "Failed"
            }
            if ($PinInstalledVersion -and $result.PinStatus -eq "Pending") {
                $result.PinStatus = "NotAttempted"
            }
            if ($result.ShortcutStatus -eq "NotAttempted") {
                $result.ShortcutStatus = "NotAttempted"
            }
            Write-Log -Level Error -Message "Id=$pkgId failed: $_"
        }

        $results += [pscustomobject]$result
    }

    Write-ExecutionSummary -Results $results -SuccessCount $successCount -FailureCount $failureCount

    if ($successCount -eq 0) {
        throw "All package installs failed"
    }
}

Invoke-WingetMachineInstall -Id $Id -Version $Version -PinInstalledVersion:$PinInstalledVersion -LogPath $LogPath
exit 0
