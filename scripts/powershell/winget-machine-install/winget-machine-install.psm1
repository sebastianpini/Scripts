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

function Convert-WingetShowTextToPackageInfo {
    param([Parameter(Mandatory = $true)][object]$Output)

    $text = if ($Output -is [array]) { $Output -join "`n" } else { [string]$Output }
    $regexOptions = [System.Text.RegularExpressions.RegexOptions]::IgnoreCase -bor [System.Text.RegularExpressions.RegexOptions]::Multiline
    $matches = [regex]::Matches($text, '^\s*Scope:\s*(\S+)\s*$', $regexOptions)

    $installers = @()
    foreach ($match in $matches) {
        $installers += [pscustomobject]@{ Scope = $match.Groups[1].Value }
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

function Ensure-Winget {
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

    $result = Invoke-Winget -WingetPath $WingetPath -ArgsList @("show", "--id", $Id, "--output", "json")
    $outputText = if ($result.Output -is [array]) { $result.Output -join "`n" } else { [string]$result.Output }

    if ($result.ExitCode -ne 0) {
        if ($outputText -match "Argument name was not recognized.*--output") {
            Write-Log -Level Warning -Message "winget show --output json not supported, falling back to text output"
            $textResult = Invoke-Winget -WingetPath $WingetPath -ArgsList @("show", "--id", $Id)
            if ($textResult.ExitCode -ne 0) {
                Write-Log -Level Error -Message "winget show failed: $($textResult.Output)"
                throw "winget show failed for Id=$Id"
            }
            return Convert-WingetShowTextToPackageInfo -Output $textResult.Output
        }

        Write-Log -Level Error -Message "winget show failed: $($result.Output)"
        throw "winget show failed for Id=$Id"
    }

    try {
        return $outputText | ConvertFrom-Json
    } catch {
        Write-Log -Level Error -Message "Failed to parse winget JSON output"
        throw
    }
}

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

function Install-WingetPackage {
    param([string]$WingetPath, [string]$Id)

    $output = & $WingetPath install --id $Id --scope machine --accept-package-agreements --accept-source-agreements 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Log -Level Error -Message "winget install failed: $output"
        throw "winget install failed for Id=$Id"
    }

    Write-Log -Level Info -Message "Install completed successfully"
}

function Invoke-WingetMachineInstall {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Id,

        [Parameter(Mandatory = $false)]
        [string]$LogPath
    )

    if (-not $LogPath -or $LogPath.Trim().Length -eq 0) {
        $safeId = $Id -replace '[^a-zA-Z0-9._-]', '_'
        $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $LogPath = Join-Path -Path $env:TEMP -ChildPath "winget-install-$safeId-$timestamp.log"
    }

    $script:LogPath = $LogPath

    Write-Log -Level Info -Message "Starting winget machine install for Id=$Id"
    Write-Log -Level Info -Message "LogPath=$LogPath"
    Write-Log -Level Info -Message "OS=$([System.Environment]::OSVersion.VersionString)"
    Write-Log -Level Info -Message "PowerShell=$($PSVersionTable.PSVersion)"

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
}

Export-ModuleMember -Function Get-WingetPath, Ensure-Winget, Get-WingetPackageInfo, Supports-MachineScope, Install-WingetPackage, Invoke-WingetMachineInstall, Convert-WingetShowTextToPackageInfo, Invoke-Winget
