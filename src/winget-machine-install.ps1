[CmdletBinding()]
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

Write-Log -Level Info -Message "Starting winget machine install for Id=$Id"
Write-Log -Level Info -Message "LogPath=$LogPath"
Write-Log -Level Info -Message "OS=$([System.Environment]::OSVersion.VersionString)"
Write-Log -Level Info -Message "PowerShell=$($PSVersionTable.PSVersion)"

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
