$ErrorActionPreference = "Stop"

Write-Host "Starting chaos test: temporary events worker outage"

docker compose -f infra/docker/docker-compose.yml stop worker_events
Start-Sleep -Seconds 20
docker compose -f infra/docker/docker-compose.yml start worker_events

Write-Host "Chaos test completed. Verify recovery metrics:"
Write-Host "- outbox_status_count{status='pending|retry'} returns to baseline"
Write-Host "- outbox_failed_total does not grow uncontrollably"
Write-Host "- API readiness remains healthy"
