"""Windows functions are tested with synthetic process/HTTP responses, never WSL."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh")
pytestmark = pytest.mark.skipif(
    sys.platform != "win32" or not POWERSHELL, reason="Windows PowerShell launcher functions"
)


def powershell_json(body):
    common = str(ROOT / "scripts/windows/pilot-common.ps1").replace("'", "''")
    result = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"$ErrorActionPreference = 'Stop'; . '{common}'; {body}",
        ],
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("identity", ["owned", "reused_pid", "unverifiable"])
def test_helper_reuse_recovers_only_proven_stale_windows_pid(identity):
    result = powershell_json(
        r"""
        $script:identity = 'IDENTITY'
        $started = [DateTime]::Parse('2026-01-01T00:00:00Z').ToUniversalTime()
        $state = [pscustomobject]@{
            pid = 4242; startedUtc = $started.ToString('o'); distribution = 'Ubuntu-Fixture';
            repoRoot = 'C:\fixture'; helperPath = '/fixture/scripts/windows/hold-wsl.py';
            linuxStatePath = '/fixture/var/logs/state.linux.json'; token = ('a' * 32)
        }
        function Get-Process { param($Id, $ErrorAction)
            [pscustomobject]@{ Id = 4242; StartTime = $started }
        }
        function Get-CimInstance { param($ClassName, $Filter, $ErrorAction)
            if ($script:identity -eq 'unverifiable') { throw 'synthetic access failure' }
            $name = 'wsl.exe'
            if ($script:identity -eq 'reused_pid') { $name = 'unrelated.exe' }
            [pscustomobject]@{
                Name = $name; ExecutablePath = 'C:\fixture\wsl.exe';
                CommandLine = ('"C:\fixture\wsl.exe" -d Ubuntu-Fixture -- python3 ' +
                    '"/fixture/scripts/windows/hold-wsl.py" --state-file ' +
                    '"/fixture/var/logs/state.linux.json" --token ' + ('a' * 32))
            }
        }
        function Stop-Process { throw 'No process may be stopped by this test' }
        try {
            $arguments = @{
                State = $state; HelperPath = $state.helperPath; Repository = $state.repoRoot
                LinuxStatePath = $state.linuxStatePath; Distribution = $state.distribution
                WslExecutable = 'C:\fixture\wsl.exe'
            }
            $helper = Get-OwnedPilotHelper @arguments
            @{ reusable = [bool]$helper; refused_unknown = $false } | ConvertTo-Json -Compress
        } catch { @{ reusable = $false; refused_unknown = $true } | ConvertTo-Json -Compress }
    """.replace("IDENTITY", identity)
    )
    assert result == {
        "reusable": identity == "owned",
        "refused_unknown": identity == "unverifiable",
    }


@pytest.mark.parametrize("response", ["healthy", "db_unhealthy", "wrong_mode", "dashboard_bad"])
def test_readiness_requires_windows_api_and_dashboard(response):
    result = powershell_json(
        r"""
        $script:response = 'RESPONSE'
        $script:apiUrl = ''
        function Invoke-RestMethod { param($Uri, $TimeoutSec, $ErrorAction)
            $script:apiUrl = $Uri
            $db = 'ok'; $mode = 'local'
            if ($script:response -eq 'db_unhealthy') { $db = 'error' }
            if ($script:response -eq 'wrong_mode') { $mode = 'simulation' }
            [pscustomobject]@{ status = 'ok'; db = $db; env = $mode }
        }
        function Invoke-WebRequest {
            param($Uri, [switch]$UseBasicParsing, $TimeoutSec, $ErrorAction)
            $status = 200
            if ($script:response -eq 'dashboard_bad') { $status = 503 }
            [pscustomobject]@{ StatusCode = $status }
        }
        try {
            Wait-LocalPilot -ApiPort 8123 -TimeoutSeconds 0
            @{ ready = $true; api_url = $script:apiUrl } | ConvertTo-Json -Compress
        } catch { @{ ready = $false; api_url = $script:apiUrl } | ConvertTo-Json -Compress }
    """.replace("RESPONSE", response)
    )
    assert result["ready"] == (response == "healthy")
    assert result["api_url"] == "http://127.0.0.1:8123/health"


def test_atomic_windows_state_round_trip_uses_only_fixture_directory(tmp_path):
    state = str(tmp_path / "fixture.json").replace("'", "''")
    result = powershell_json(f"""
        $path = '{state}'
        Write-PilotHelperState -Path $path -State @{{ pid = 1; token = 'fixture-first' }}
        Write-PilotHelperState -Path $path -State @{{ pid = 2; token = 'fixture-second' }}
        $state = Read-PilotHelperState -Path $path
        $temporary = @(Get-ChildItem -LiteralPath (Split-Path -Parent $path) -Filter '*.tmp' -Force)
        @{{ pid = $state.pid; temporary_count = $temporary.Count }} | ConvertTo-Json -Compress
    """)
    assert result == {"pid": 2, "temporary_count": 0}


def test_port_change_preserves_other_values_bom_and_acl(tmp_path):
    script = str(ROOT / "scripts/windows/start-pilot.ps1").replace("'", "''")
    path = str(tmp_path / "synthetic.cfg").replace("'", "''")
    result = powershell_json(f"""
        $errors = $null; $tokens = $null
        $ast = [Management.Automation.Language.Parser]::ParseFile(
            '{script}', [ref]$tokens, [ref]$errors)
        $definition = $ast.Find({{
            param($node)
            $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
                $node.Name -eq 'Set-PilotApiPort'
        }}, $true)
        . ([ScriptBlock]::Create($definition.Extent.Text))
        $path = '{path}'
        $original = "OSCAR_ENV=local`r`nOSCAR_API_KEY=synthetic-app-key`r`nOSCAR_API_PORT=8001`r`n"
        [IO.File]::WriteAllText($path, $original, [Text.UTF8Encoding]::new($true))
        $beforeAcl = Get-Acl -LiteralPath $path
        $beforeRules = $beforeAcl.Access | ConvertTo-Json -Depth 5 -Compress
        Set-PilotApiPort -Path $path -Port 8123
        $after = [IO.File]::ReadAllText($path)
        $bytes = [IO.File]::ReadAllBytes($path)
        $afterAcl = Get-Acl -LiteralPath $path
        $afterRules = $afterAcl.Access | ConvertTo-Json -Depth 5 -Compress
        $sections = [Security.AccessControl.AccessControlSections]::Access -bor
            [Security.AccessControl.AccessControlSections]::Owner -bor
            [Security.AccessControl.AccessControlSections]::Group
        @{{
            expected_text = ($after -ceq $original.Replace('8001', '8123'))
            same_acl = ($afterAcl.Owner -ceq $beforeAcl.Owner -and
                $afterAcl.Group -ceq $beforeAcl.Group -and
                $afterAcl.AreAccessRulesProtected -eq $beforeAcl.AreAccessRulesProtected -and
                $afterRules -ceq $beforeRules)
            has_bom = ($bytes[0] -eq 239 -and $bytes[1] -eq 187 -and $bytes[2] -eq 191)
            acl_diagnostic = @{{
                same_owner = ($afterAcl.Owner -ceq $beforeAcl.Owner)
                same_group = ($afterAcl.Group -ceq $beforeAcl.Group)
                same_protection = ($afterAcl.AreAccessRulesProtected -eq
                    $beforeAcl.AreAccessRulesProtected)
                same_rules = ($afterRules -ceq $beforeRules)
                same_descriptor = ($beforeAcl.GetSecurityDescriptorSddlForm($sections) -ceq
                    $afterAcl.GetSecurityDescriptorSddlForm($sections))
            }}
        }} | ConvertTo-Json -Compress
    """)
    diagnostic = result.pop("acl_diagnostic")
    assert result == {"expected_text": True, "same_acl": True, "has_bom": True}, diagnostic
