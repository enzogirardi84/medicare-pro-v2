from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "medicare-nextgen-api"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/medicare_nextgen"
    read_database_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change_me_local"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14
    enable_metrics: bool = True
    outbox_auto_flush_enabled: bool = True
    outbox_auto_flush_interval_seconds: int = 20
    outbox_flush_batch_size: int = 200
    list_cache_ttl_seconds: int = 20
    list_cache_compress_min_bytes: int = 1024
    list_cache_ttl_jitter_seconds: int = 5
    list_cache_build_lock_seconds: int = 5
    list_cache_wait_on_lock_ms: int = 50
    redis_socket_timeout_ms: int = 200
    redis_socket_connect_timeout_ms: int = 200
    db_pool_size: int = 40
    db_max_overflow: int = 80
    db_pool_timeout_seconds: int = 30
    db_pool_recycle_seconds: int = 1800
    db_statement_timeout_ms: int = 5000
    read_db_fail_open: bool = True
    read_db_healthcheck_interval_seconds: int = 5
    import_max_pending_per_tenant: int = 20
    import_priority_tenant_ids: str = ""
    import_priority_high: int = 9
    import_priority_default: int = 1
    import_circuit_breaker_threshold: int = 10
    import_circuit_breaker_window_seconds: int = 60
    import_circuit_breaker_open_seconds: int = 120
    rate_limit_burst_window_seconds: int = 10
    rate_limit_burst_multiplier: float = 0.5
    rate_limit_burst_min_requests: int = 10
    rate_limit_fail_open: bool = True
    idempotency_fail_open: bool = True
    token_revocation_fail_open: bool = True
    resilience_rollback_max_index: int = 20
    api_max_request_body_bytes: int = 5_000_000
    api_max_inflight_requests: int = 500
    api_inflight_acquire_timeout_ms: int = 25
    api_reserved_inflight_for_priority: int = 50
    api_priority_paths: str = "/health,/live,/ready,/metrics,/v1/auth"
    api_request_timeout_ms: int = 8000
    api_priority_request_timeout_ms: int = 3000
    api_retry_after_busy_seconds: int = 1
    api_retry_after_timeout_seconds: int = 2
    api_payload_reject_threshold: int = 8
    api_payload_reject_window_seconds: int = 60
    api_payload_reject_block_seconds: int = 120
    api_payload_guard_ip_allowlist: str = "127.0.0.1,::1"
    self_heal_enabled: bool = True
    self_heal_interval_seconds: int = 30
    self_heal_policy_ttl_seconds: int = 180
    self_heal_recovery_streak: int = 2
    self_heal_cooldown_seconds: int = 120
    deploy_id: str = "local"
    git_sha: str = "unknown"
    region: str = "local"
    node_id: str = "local-node"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
