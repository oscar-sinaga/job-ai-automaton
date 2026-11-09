[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$Distribution = 'Ubuntu'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'pilot-common.ps1')
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).ProviderPath
$configurationPath = Join-Path $repoRoot '.env.pilot'
$logsPath = Join-Path $repoRoot 'var\logs'
$statePath = Join-Path $logsPath "windows-pilot-$Distribution.json"
$wslExecutable = (Get-Command wsl.exe -ErrorAction Stop).Source
if (-not (Test-Path -LiteralPath $configurationPath -PathType Leaf)) {
    throw 'Missing .env.pilot. Configuration and existing helpers were left untouched.'
}
$logsPath = Initialize-PilotLogs -Repository $repoRoot
$launcherMutex = Enter-PilotMutex -Repository $repoRoot -Distribution $Distribution
try {
$stopLog = Join-Path $logsPath 'windows-pilot-stop.log'
$repoPathForWsl = $repoRoot.Replace('\', '/')
$repoWslPath = (& $wslExecutable -d $Distribution -- wslpath -a -u $repoPathForWsl 2> (Join-Path $logsPath 'windows-pilot-path.log') | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $repoWslPath.StartsWith('/') -or $repoWslPath -match '[\r\n"]') {
    throw 'Could not resolve the repository path in WSL; services and helpers were left untouched.'
}
$pilotArguments = @('-d', $Distribution, '--cd', $repoWslPath, '--', 'python3', 'scripts/pilot.py', 'stop')
$previousPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = 'Continue'
    & $wslExecutable @pilotArguments *> $stopLog
    $pilotExitCode = $LASTEXITCODE
} finally { $ErrorActionPreference = $previousPreference }
if ($pilotExitCode -ne 0) { throw "Pilot stop failed; keepalive was retained. Inspect the private log: $stopLog" }

if (Test-Path -LiteralPath $statePath) {
    try {
        $state = Read-PilotHelperState -Path $statePath
        $helperPath = $repoWslPath.TrimEnd('/') + '/scripts/windows/hold-wsl.py'
        $linuxStatePath = $repoWslPath.TrimEnd('/') + "/var/logs/windows-pilot-$Distribution.linux.json"
        $candidate = Get-OwnedPilotHelper -State $state -HelperPath $helperPath -Repository $repoRoot -LinuxStatePath $linuxStatePath -Distribution $Distribution -WslExecutable $wslExecutable

        $helperStopArguments = @('-d', $Distribution, '--', 'python3', $helperPath, '--state-file', $linuxStatePath, '--token', [string]$state.token, '--stop')
        $previousPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            & $wslExecutable @helperStopArguments *> (Join-Path $logsPath 'windows-pilot-helper-stop.log')
            $helperExitCode = $LASTEXITCODE
        } finally { $ErrorActionPreference = $previousPreference }
        if ($helperExitCode -ne 0) { throw 'The Linux helper ownership could not be verified.' }
        if ($candidate -and -not $candidate.WaitForExit(5000)) {
            $stillOwned = Get-OwnedPilotHelper -State $state -HelperPath $helperPath -Repository $repoRoot -LinuxStatePath $linuxStatePath -Distribution $Distribution -WslExecutable $wslExecutable
            if ($stillOwned) { Stop-Process -InputObject $stillOwned -ErrorAction Stop }
        }
        Remove-Item -LiteralPath $statePath
    } catch {
        Write-Warning 'The keepalive could not be verified or stopped safely and was left untouched. Persistent data was not removed.'
        return
    }
}
Write-Output 'OSCAR stopped. Database and document volumes were retained.'
} finally {
    $launcherMutex.ReleaseMutex()
    $launcherMutex.Dispose()
}
