import base64
import json
import random
import zlib
from typing import Any

import redis

from app.core.config import settings
from app.infrastructure.metrics import cache_events_total

redis_client = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_timeout=max(settings.redis_socket_timeout_ms, 1) / 1000.0,
    socket_connect_timeout=max(settings.redis_socket_connect_timeout_ms, 1) / 1000.0,
)


def _list_cache_version_key(resource: str, tenant_id: str) -> str:
    return f"list_cache_version:{resource}:{tenant_id}"


def get_resource_list_cache_version(resource: str, tenant_id: str) -> str:
    try:
        version = redis_client.get(_list_cache_version_key(resource, tenant_id))
        if version is None:
            return "1"
        return version
    except redis.RedisError:
        cache_events_total.labels(resource=resource, event="error_version").inc()
        return "1"


def list_cache_key(resource: str, tenant_id: str, params_hash: str, version: str) -> str:
    return f"list_cache:{resource}:{tenant_id}:v{version}:{params_hash}"


def invalidate_resource_list_cache(resource: str, tenant_id: str) -> None:
    try:
        redis_client.incr(_list_cache_version_key(resource, tenant_id))
        cache_events_total.labels(resource=resource, event="invalidate").inc()
    except redis.RedisError:
        cache_events_total.labels(resource=resource, event="error_invalidate").inc()


def _cache_build_lock_key(key: str) -> str:
    return f"cache_build_lock:{key}"


def try_acquire_cache_build_lock(key: str) -> bool:
    try:
        return bool(redis_client.set(_cache_build_lock_key(key), "1", nx=True, ex=settings.list_cache_build_lock_seconds))
    except redis.RedisError:
        return False


def release_cache_build_lock(key: str) -> None:
    try:
        redis_client.delete(_cache_build_lock_key(key))
    except redis.RedisError:
        pass


def set_json_cache(key: str, value: Any, ttl_seconds: int, resource: str) -> None:
    try:
        payload = json.dumps(value, separators=(",", ":"))
        ttl_with_jitter = ttl_seconds + random.randint(0, max(settings.list_cache_ttl_jitter_seconds, 0))
        if len(payload.encode("utf-8")) >= settings.list_cache_compress_min_bytes:
            compressed = zlib.compress(payload.encode("utf-8"), level=6)
            encoded = base64.b64encode(compressed).decode("ascii")
            redis_client.setex(key, ttl_with_jitter, f"z:{encoded}")
            cache_events_total.labels(resource=resource, event="write_compressed").inc()
            return
        redis_client.setex(key, ttl_with_jitter, f"p:{payload}")
        cache_events_total.labels(resource=resource, event="write_plain").inc()
    except redis.RedisError:
        cache_events_total.labels(resource=resource, event="error_write").inc()


def get_json_cache(key: str, resource: str) -> Any | None:
    try:
        raw_value = redis_client.get(key)
        if not raw_value:
            cache_events_total.labels(resource=resource, event="miss").inc()
            return None
        if raw_value.startswith("z:"):
            compressed = base64.b64decode(raw_value[2:].encode("ascii"))
            cache_events_total.labels(resource=resource, event="hit_compressed").inc()
            return json.loads(zlib.decompress(compressed).decode("utf-8"))
        if raw_value.startswith("p:"):
            cache_events_total.labels(resource=resource, event="hit_plain").inc()
            return json.loads(raw_value[2:])
        # Compatibilidad con claves antiguas sin prefijo.
        cache_events_total.labels(resource=resource, event="hit_legacy").inc()
        return json.loads(raw_value)
    except redis.RedisError:
        cache_events_total.labels(resource=resource, event="error_read").inc()
        return None
    except Exception:
        cache_events_total.labels(resource=resource, event="error_decode").inc()
        return None
