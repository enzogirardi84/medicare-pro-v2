import json
from datetime import datetime, timezone
from typing import Literal

import redis

from app.core.config import settings
from app.infrastructure.cache import redis_client

ResiliencePolicy = Literal["rate_limit_fail_open", "idempotency_fail_open", "token_revocation_fail_open"]
RESILIENCE_POLICIES: tuple[ResiliencePolicy, ...] = (
    "rate_limit_fail_open",
    "idempotency_fail_open",
    "token_revocation_fail_open",
)


def _policy_key(policy: ResiliencePolicy) -> str:
    return f"resilience_policy:{policy}"


def _history_key(tenant_id: str) -> str:
    return f"resilience_history:{tenant_id}"


def _default_policy_value(policy: ResiliencePolicy) -> bool:
    return bool(getattr(settings, policy))


def get_resilience_policy(policy: ResiliencePolicy) -> bool:
    try:
        raw = redis_client.get(_policy_key(policy))
        if raw is None:
            return _default_policy_value(policy)
        return str(raw).strip() in ("1", "true", "True", "yes")
    except redis.RedisError:
        return _default_policy_value(policy)


def set_resilience_policy(policy: ResiliencePolicy, enabled: bool, ttl_seconds: int) -> None:
    redis_client.setex(_policy_key(policy), max(30, ttl_seconds), "1" if enabled else "0")


def clear_resilience_policy(policy: ResiliencePolicy) -> None:
    redis_client.delete(_policy_key(policy))


def append_resilience_history(
    tenant_id: str,
    actor_user_id: str,
    updates: dict[str, bool],
    defaults_restored: list[str],
    ttl_seconds: int,
    effective: dict[str, bool],
    reason: str,
    change_ticket: str | None = None,
    limit: int = 100,
) -> None:
    event = {
        "at": datetime.now(timezone.utc).isoformat(),
        "actor_user_id": actor_user_id,
        "updates": updates,
        "defaults_restored": defaults_restored,
        "ttl_seconds": ttl_seconds,
        "effective": effective,
        "reason": reason,
        "change_ticket": change_ticket,
    }
    key = _history_key(tenant_id)
    redis_client.lpush(key, json.dumps(event, separators=(",", ":")))
    redis_client.ltrim(key, 0, max(1, limit) - 1)
    redis_client.expire(key, 7 * 24 * 3600)


def get_resilience_history(tenant_id: str, limit: int = 20) -> list[dict]:
    try:
        key = _history_key(tenant_id)
        rows = redis_client.lrange(key, 0, max(1, limit) - 1)
        return [json.loads(row) for row in rows]
    except redis.RedisError:
        return []
    except Exception:
        return []
