$ErrorActionPreference = "Stop"

param(
    [string]$BaseUrl = "http://localhost:8000",
    # Mismos cuatro tests que nextgen-pr-gate / run_smoke_suite (core); sin scheduler ni import CSV.
    [switch]$Quick
)

Write-Host "=== NextGen Integration Contracts Runner $(if ($Quick) { '(quick)' } else { '(full)' }) ==="

function Check-Command($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Host "[FAIL] Missing command: $name"
        return $false
    }
    Write-Host "[OK] $name"
    return $true
}

$ok = $true
$ok = (Check-Command "python") -and $ok

if (-not $ok) {
    Write-Host "Missing required dependencies."
    exit 1
}

$env:NEXTGEN_BASE_URL = $BaseUrl.TrimEnd("/")
Write-Host "[OK] NEXTGEN_BASE_URL=$env:NEXTGEN_BASE_URL"

Write-Host "Checking pytest availability..."
python -m pytest --version | Out-Null
Write-Host "[OK] pytest available through python -m pytest"

$fullTests = @(
    "tests/integration/test_auth_contract.py",
    "tests/integration/test_outbox_contract.py",
    "tests/integration/test_outbox_scheduler_contract.py",
    "tests/integration/test_import_csv_contract.py",
    "tests/integration/test_system_resilience_contract.py",
    "tests/integration/test_api_guardrails_contract.py"
)
$quickTests = @(
    "tests/integration/test_auth_contract.py",
    "tests/integration/test_outbox_contract.py",
    "tests/integration/test_system_resilience_contract.py",
    "tests/integration/test_api_guardrails_contract.py"
)
$tests = if ($Quick) { $quickTests } else { $fullTests }

Write-Host "Running integration contracts..."
python -m pytest $tests -q

if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Integration contracts failed."
    exit $LASTEXITCODE
}

Write-Host "[OK] Integration contracts passed."
