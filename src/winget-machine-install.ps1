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
