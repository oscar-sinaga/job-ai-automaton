function Enter-PilotMutex {
    param([string]$Repository, [string]$Distribution)
    $sha256 = [Security.Cryptography.SHA256]::Create()
    try {
        $identity = $Repository.ToLowerInvariant() + '|' + $Distribution.ToLowerInvariant()
        $hash = [BitConverter]::ToString($sha256.ComputeHash([Text.Encoding]::UTF8.GetBytes($identity))).Replace('-', '')
    } finally { $sha256.Dispose() }
    $mutex = New-Object Threading.Mutex($false, "Local\OSCARPilot-$hash")
    try {
        try { $acquired = $mutex.WaitOne(0) }
        catch [Threading.AbandonedMutexException] { $acquired = $true }
        if (-not $acquired) { throw 'Another launcher is starting or stopping this pilot.' }
        return $mutex
    } catch { $mutex.Dispose(); throw }
}

function Initialize-PilotLogs {
    param([string]$Repository)
    $dataPath = Join-Path $Repository 'var'
    $logsPath = Join-Path $dataPath 'logs'
    foreach ($path in @($dataPath, $logsPath)) {
        if (Test-Path -LiteralPath $path) {
            $item = Get-Item -LiteralPath $path
            if (-not $item.PSIsContainer -or $item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw 'The pilot log directories must be regular directories within this repository.'
            }
        } else { New-Item -ItemType Directory -Path $path | Out-Null }
    }
    return $logsPath
}

function Read-PilotHelperState {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $item = Get-Item -LiteralPath $Path
    if ($item.PSIsContainer -or $item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'The helper state must be a regular file.'
    }
    try { return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json }
    catch { throw 'The helper state is invalid and was left untouched.' }
}

function Write-PilotHelperState {
    param([string]$Path, $State)
    $temporary = Join-Path (Split-Path -Parent $Path) ('.pilot-helper-' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        [IO.File]::WriteAllText($temporary, ($State | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
        if (Test-Path -LiteralPath $Path) { [IO.File]::Replace($temporary, $Path, [NullString]::Value) }
        else { [IO.File]::Move($temporary, $Path) }
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary }
    }
}

function Get-OwnedPilotHelper {
    param($State, [string]$HelperPath, [string]$Repository, [string]$LinuxStatePath, [string]$Distribution, [string]$WslExecutable)
    if (-not $State) { return $null }
    if (
        [string]$State.repoRoot -ine $Repository -or
        [string]$State.distribution -cne $Distribution -or
        [string]$State.helperPath -cne $HelperPath -or
        [string]$State.linuxStatePath -cne $LinuxStatePath -or
        [string]$State.token -notmatch '^[0-9a-f]{32}$'
    ) { throw 'The helper record does not belong to this launcher and was left untouched.' }
    try { $processId = [int]$State.pid }
    catch { throw 'The helper state is invalid and was left untouched.' }
    if ($processId -le 0) { throw 'The helper state is invalid and was left untouched.' }
    $candidate = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if (-not $candidate) { return $null }
    try {
        $record = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction Stop
        if (-not $record -or -not $record.Name) {
            throw 'Process identity is unavailable.'
        }
        if ($record.Name -ine 'wsl.exe') { return $null }
        if (-not $record.CommandLine -or -not $record.ExecutablePath) {
            throw 'Process identity is unavailable.'
        }
        $startedUtc = $candidate.StartTime.ToUniversalTime().ToString('o')
    } catch { throw 'An existing helper could not be verified and was left untouched.' }
    $commandMatch = [regex]::Match([string]$record.CommandLine, '^\s*(?:"[^"]+"|\S+)\s+(?<tail>.*)$')
    $expectedTail = '-d {0} -- python3 "{1}" --state-file "{2}" --token {3}' -f $Distribution, $HelperPath, $LinuxStatePath, [string]$State.token
    if (
        $record.Name -ine 'wsl.exe' -or $record.ExecutablePath -ine $WslExecutable -or
        $startedUtc -cne [string]$State.startedUtc -or -not $commandMatch.Success -or
        $commandMatch.Groups['tail'].Value.Trim() -cne $expectedTail
    ) { return $null } # A positively identified PID reuse is stale; never stop that process.
    return $candidate
}

function Wait-LocalPilot {
    param([int]$ApiPort, [int]$TimeoutSeconds = 30)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/health" -TimeoutSec 3 -ErrorAction Stop
            if ($health.status -ceq 'ok' -and $health.db -ceq 'ok' -and $health.env -ceq 'local') {
                $dashboard = Invoke-WebRequest -Uri 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
                if ([int]$dashboard.StatusCode -eq 200) { return }
            }
        } catch { } # Response bodies and connection details may contain private data.
        if ([DateTime]::UtcNow -ge $deadline) { break }
        Start-Sleep -Milliseconds 500
    } while ($true)
    throw "The containers started, but Windows cannot reach a healthy local API and dashboard. Check ports $ApiPort and 5173."
}
