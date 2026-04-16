from prometheus_client import Counter, Gauge

outbox_published_total = Counter("outbox_published_total", "Total outbox events published")
outbox_failed_total = Counter("outbox_failed_total", "Total outbox publish failures")
outbox_status_gauge = Gauge("outbox_status_count", "Current outbox events by status", ["status"])

import_jobs_status_gauge = Gauge("import_jobs_status_count", "Current import jobs by status", ["status"])
import_jobs_retried_total = Counter("import_jobs_retried_total", "Total import jobs retried")

cache_events_total = Counter(
    "cache_events_total",
    "Cache events by resource and event type",
    ["resource", "event"],
)

rate_limit_events_total = Counter(
    "rate_limit_events_total",
    "Rate limit events by decision",
    ["decision"],
)

idempotency_events_total = Counter(
    "idempotency_events_total",
    "Idempotency events by operation and result",
    ["operation", "result"],
)

token_revocation_events_total = Counter(
    "token_revocation_events_total",
    "Token revocation events by operation and result",
    ["operation", "result"],
)

resilience_ops_total = Counter(
    "resilience_ops_total",
    "Resilience API operations by operation and outcome",
    ["operation", "outcome"],
)

imports_throttled_total = Counter(
    "imports_throttled_total",
    "Total import requests throttled by tenant guardrail",
)

imports_circuit_open_total = Counter(
    "imports_circuit_open_total",
    "Total import requests blocked by tenant circuit breaker",
)

imports_enqueued_total = Counter(
    "imports_enqueued_total",
    "Total import jobs enqueued by priority tier",
    ["tier"],
)

read_db_fallback_total = Counter(
    "read_db_fallback_total",
    "Total readonly requests that fell back to primary DB",
)

read_db_fallback_reason_total = Counter(
    "read_db_fallback_reason_total",
    "Total readonly fallback events by reason",
    ["reason"],
)

read_db_readonly_requests_total = Counter(
    "read_db_readonly_requests_total",
    "Total requests served through readonly DB dependency",
)

read_db_replica_available = Gauge(
    "read_db_replica_available",
    "Read replica availability state (1=available, 0=unavailable)",
)

api_request_rejections_total = Counter(
    "api_request_rejections_total",
    "Total API requests rejected by safety guardrails",
    ["reason"],
)

api_inflight_requests_gauge = Gauge(
    "api_inflight_requests",
    "Current in-flight API requests guarded by middleware",
)

api_payload_too_large_total = Counter(
    "api_payload_too_large_total",
    "Total payload too large rejections by allowlist status",
    ["allowlisted"],
)

api_error_responses_total = Counter(
    "api_error_responses_total",
    "Total API error responses by code and status",
    ["code", "status"],
)

api_build_info = Gauge(
    "api_build_info",
    "API build information metric (always 1) labeled by version/deploy/sha/environment/region/node",
    ["version", "deploy_id", "git_sha", "environment", "region", "node_id"],
)

self_heal_actions_total = Counter(
    "self_heal_actions_total",
    "Self-heal actions by type and outcome",
    ["action", "outcome"],
)

self_heal_dependency_state = Gauge(
    "self_heal_dependency_state",
    "Self-heal dependency state (1=ok,0=down)",
    ["dependency"],
)
