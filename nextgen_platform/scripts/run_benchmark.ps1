$ErrorActionPreference = "Stop"

param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$Scenario = "tests/load/k6_mixed_scale.js",
    [string]$OutDir = "benchmark_results"
)

if (!(Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir | Out-Null
}

$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$summary = Join-Path $OutDir "summary-$ts.json"

Write-Host "Running benchmark: $Scenario against $BaseUrl"
k6 run $Scenario --env BASE_URL=$BaseUrl --summary-export $summary

Write-Host "Benchmark summary exported to: $summary"
python scripts/summarize_benchmark.py $summary
