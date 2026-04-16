$ErrorActionPreference = "Stop"

param(
    [string]$BaseUrl = "http://localhost:8000",
    # Core = mismo cuatro tests que nextgen-smoke-pr / PR gate smoke. Extended anade scheduler + import CSV (suite completa).
    [switch]$Extended
)

Write-Host "=== NextGen Smoke Suite Runner $(if ($Extended) { '(extended)' } else { '(core)' }) ==="

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

$tests = @(
    "tests/integration/test_auth_contract.py",
    "tests/integration/test_outbox_contract.py",
    "tests/integration/test_system_resilience_contract.py",
    "tests/integration/test_api_guardrails_contract.py"
)
if ($Extended) {
    Write-Host "Extended: adding outbox scheduler + import CSV (matches run_integration_contracts.ps1 full)..."
    $tests += @(
        "tests/integration/test_outbox_scheduler_contract.py",
        "tests/integration/test_import_csv_contract.py"
    )
}

Write-Host "Running smoke suite..."
python -m pytest $tests -q

if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Smoke suite failed."
    exit $LASTEXITCODE
}

Write-Host "[OK] Smoke suite passed."
