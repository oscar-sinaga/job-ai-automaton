[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$ApiPort = 8001,
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$Distribution = 'Ubuntu'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'pilot-common.ps1')
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).ProviderPath
$configurationPath = Join-Path $repoRoot '.env.pilot'
$logsPath = Join-Path $repoRoot 'var\logs'
$statePath = Join-Path $logsPath "windows-pilot-$Distribution.json"
$runtimeLog = Join-Path $logsPath 'windows-pilot-start.log'
$wslExecutable = (Get-Command wsl.exe -ErrorAction Stop).Source
if ($ApiPort -eq 5173) { throw 'The API port must differ from the web port 5173.' }
if (-not (Test-Path -LiteralPath $configurationPath -PathType Leaf)) {
    throw 'Missing .env.pilot. Initialize the normal pilot before running this launcher.'
}
if ((Get-Item -LiteralPath $configurationPath).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw 'The pilot configuration must be a regular file.'
}
$logsPath = Initialize-PilotLogs -Repository $repoRoot
$launcherMutex = Enter-PilotMutex -Repository $repoRoot -Distribution $Distribution

function Set-PilotApiPort {
    param([string]$Path, [int]$Port)
    $originalBytes = [IO.File]::ReadAllBytes($Path)
    $hasBom = $originalBytes.Length -ge 3 -and $originalBytes[0] -eq 239 -and $originalBytes[1] -eq 187 -and $originalBytes[2] -eq 191
    $encoding = New-Object Text.UTF8Encoding($hasBom, $true)
    $offset = 0
    if ($hasBom) { $offset = 3 }
    $content = $encoding.GetString($originalBytes, $offset, $originalBytes.Length - $offset)
    $pattern = New-Object Text.RegularExpressions.Regex('(?m)^[ \t]*OSCAR_API_PORT[ \t]*=[^\r\n]*')
    if ($pattern.IsMatch($content)) {
        $updated = $pattern.Replace($content, "OSCAR_API_PORT=$Port")
    } else {
        $newline = "`n"
        if ($content.Contains("`r`n")) { $newline = "`r`n" }
        $separator = ''
        if ($content.Length -gt 0 -and -not $content.EndsWith("`n")) { $separator = $newline }
        $updated = $content + $separator + "OSCAR_API_PORT=$Port" + $newline
    }
    if ($updated -ceq $content) { return }
    $originalAcl = Get-Acl -LiteralPath $Path
    $temporaryPath = Join-Path (Split-Path -Parent $Path) ('.env.pilot.' + [guid]::NewGuid().ToString('N') + '.env.local')
    try {
        $stream = [IO.File]::Open($temporaryPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        $stream.Dispose()
        Set-Acl -LiteralPath $temporaryPath -AclObject $originalAcl
        [IO.File]::WriteAllText($temporaryPath, $updated, $encoding)
        $currentBytes = [IO.File]::ReadAllBytes($Path)
        if ([Convert]::ToBase64String($currentBytes) -cne [Convert]::ToBase64String($originalBytes)) {
            throw 'Configuration changed concurrently; no update was applied.'
        }
        [IO.File]::Replace($temporaryPath, $Path, [NullString]::Value)
        # Reapply the complete descriptor after the replacement's metadata merge,
        # including the original owner/group and inherited access-rule state.
        Set-Acl -LiteralPath $Path -AclObject $originalAcl
    } finally {
        if (Test-Path -LiteralPath $temporaryPath) { Remove-Item -LiteralPath $temporaryPath }
    }
}

try {
Set-PilotApiPort -Path $configurationPath -Port $ApiPort
$repoPathForWsl = $repoRoot.Replace('\', '/')
$repoWslPath = (& $wslExecutable -d $Distribution -- wslpath -a -u $repoPathForWsl 2> (Join-Path $logsPath 'windows-pilot-path.log') | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $repoWslPath.StartsWith('/') -or $repoWslPath -match '[\r\n"]') {
    throw 'Could not resolve the repository path in WSL. See the private path log under var/logs.'
}
$helperWslPath = $repoWslPath.TrimEnd('/') + '/scripts/windows/hold-wsl.py'
$linuxStatePath = $repoWslPath.TrimEnd('/') + "/var/logs/windows-pilot-$Distribution.linux.json"
$helper = $null
if (Test-Path -LiteralPath $statePath) {
    $state = Read-PilotHelperState -Path $statePath
    $helper = Get-OwnedPilotHelper -State $state -HelperPath $helperWslPath -Repository $repoRoot -LinuxStatePath $linuxStatePath -Distribution $Distribution -WslExecutable $wslExecutable
}
if (-not $helper) {
    $ownershipToken = [guid]::NewGuid().ToString('N')
    $commandTail = '-d {0} -- python3 "{1}" --state-file "{2}" --token {3}' -f $Distribution, $helperWslPath, $linuxStatePath, $ownershipToken
    $helper = Start-Process -FilePath $wslExecutable -ArgumentList $commandTail -WindowStyle Hidden -PassThru
    $state = [ordered]@{
        pid = $helper.Id
        startedUtc = $helper.StartTime.ToUniversalTime().ToString('o')
        distribution = $Distribution
        repoRoot = $repoRoot
        helperPath = $helperWslPath
        linuxStatePath = $linuxStatePath
        token = $ownershipToken
    }
    Write-PilotHelperState -Path $statePath -State $state
    Start-Sleep -Milliseconds 700
    $helper.Refresh()
    if ($helper.HasExited) { throw 'The WSL keepalive exited before startup; its state was retained for inspection.' }
}

$pilotArguments = @('-d', $Distribution, '--cd', $repoWslPath, '--', 'python3', 'scripts/pilot.py', 'start')
$previousPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = 'Continue'
    & $wslExecutable @pilotArguments *> $runtimeLog
    $pilotExitCode = $LASTEXITCODE
} finally { $ErrorActionPreference = $previousPreference }
if ($pilotExitCode -ne 0) { throw "Pilot startup failed. Inspect the private log: $runtimeLog" }
if (-not (Get-OwnedPilotHelper -State $state -HelperPath $helperWslPath -Repository $repoRoot -LinuxStatePath $linuxStatePath -Distribution $Distribution -WslExecutable $wslExecutable)) {
    throw 'The WSL keepalive exited during startup. Run the launcher again to recover.'
}
Wait-LocalPilot -ApiPort $ApiPort
Write-Output 'Dashboard: http://127.0.0.1:5173'
Write-Output "Extension API: http://127.0.0.1:$ApiPort/api/v1"
} finally {
    $launcherMutex.ReleaseMutex()
    $launcherMutex.Dispose()
}
