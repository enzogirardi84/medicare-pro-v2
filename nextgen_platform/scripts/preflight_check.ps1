$ErrorActionPreference = "Stop"

param(
    [ValidateSet("quick", "full")]
    [string]$Mode = "quick",
    [switch]$StrictGit
)

Write-Host "=== NextGen Preflight Check ($Mode) ==="

function Check-Command($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Host "[FAIL] Missing command: $name"
        return $false
    }
    Write-Host "[OK] $name"
    return $true
}

function Check-PathExists($path) {
    if (-not (Test-Path $path)) {
        Write-Host "[FAIL] Missing file/path: $path"
        return $false
    }
    Write-Host "[OK] Found: $path"
    return $true
}

$ok = $true
$ok = (Check-Command "docker") -and $ok
$ok = (Check-Command "python") -and $ok
$ok = (Check-Command "git") -and $ok
$ok = (Check-Command "k6") -and $ok

if ($Mode -eq "full") {
    $ok = (Check-Command "pip-audit") -and $ok
    $ok = (Check-Command "bandit") -and $ok
}

$ok = (Check-PathExists ".github/workflows/nextgen-pr-gate.yml") -and $ok
$ok = (Check-PathExists ".github/workflows/nextgen-security.yml") -and $ok
$ok = (Check-PathExists "tests/integration/test_api_guardrails_contract.py") -and $ok
$ok = (Check-PathExists "scripts/post_release_aggregate_latency.sh") -and $ok
$ok = (Check-PathExists "scripts/post_release_http_verify.sh") -and $ok
$ok = (Check-PathExists "scripts/run_smoke_suite.ps1") -and $ok
$ok = (Check-PathExists "scripts/run_integration_contracts.ps1") -and $ok

if (-not $ok) {
    Write-Host "Preflight failed: missing required dependencies or files."
    exit 1
}

Write-Host "Checking Docker daemon..."
docker version | Out-Null
Write-Host "[OK] Docker daemon reachable"

if ($StrictGit) {
    $gitChanges = (git status --porcelain)
    if ($gitChanges) {
        Write-Host "[FAIL] Working tree is not clean and -StrictGit is enabled."
        exit 1
    }
    Write-Host "[OK] Working tree clean"
}

if ($Mode -eq "full") {
    Write-Host "Running security tools (full mode)..."
    pip-audit -r requirements-dev.txt
    bandit -q -r apps/api/app
    Write-Host "[OK] Security tools executed"
}

Write-Host "Preflight passed."
