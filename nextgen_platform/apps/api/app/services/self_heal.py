import asyncio
from datetime import datetime, timezone
import time

from sqlalchemy import text

from app.core.config import settings
from app.core.resilience import RESILIENCE_POLICIES, clear_resilience_policy, set_resilience_policy
from app.infrastructure.cache import redis_client
from app.infrastructure.db import SessionLocal
from app.infrastructure.metrics import self_heal_actions_total, self_heal_dependency_state

_SELF_HEAL_MARKER_KEY = "self_heal:auto_fail_open_active"
_SELF_HEAL_LAST_CHANGE_TS_KEY = "self_heal:last_change_ts"
_state = {
    "enabled": bool(settings.self_heal_enabled),
    "active_fail_open": False,
    "last_run_utc": None,
    "db_ok": None,
    "redis_ok": None,
    "last_action": "none",
    "recovery_streak": 0,
}


def _marker_set(ttl_seconds: int) -> None:
    try:
        redis_client.setex(_SELF_HEAL_MARKER_KEY, max(30, ttl_seconds), "1")
    except Exception:
        pass


def _marker_is_set() -> bool:
    try:
        return redis_client.get(_SELF_HEAL_MARKER_KEY) == "1"
    except Exception:
        return False


def _marker_clear() -> None:
    try:
        redis_client.delete(_SELF_HEAL_MARKER_KEY)
    except Exception:
        pass


def _last_change_ts() -> float:
    try:
        raw = redis_client.get(_SELF_HEAL_LAST_CHANGE_TS_KEY)
        if raw is None:
            return 0.0
        return float(raw)
    except Exception:
        return 0.0


def _set_last_change_ts() -> None:
    try:
        redis_client.set(_SELF_HEAL_LAST_CHANGE_TS_KEY, str(time.time()))
    except Exception:
        pass


def _clear_last_change_ts() -> None:
    try:
        redis_client.delete(_SELF_HEAL_LAST_CHANGE_TS_KEY)
    except Exception:
        pass


def _cooldown_elapsed() -> bool:
    cooldown = max(settings.self_heal_cooldown_seconds, 0)
    if cooldown == 0:
        return True
    last_change = _last_change_ts()
    if last_change <= 0:
        return True
    return (time.time() - last_change) >= cooldown


def _cooldown_remaining_seconds() -> int:
    cooldown = max(settings.self_heal_cooldown_seconds, 0)
    if cooldown == 0:
        return 0
    last_change = _last_change_ts()
    if last_change <= 0:
        return 0
    remaining = cooldown - (time.time() - last_change)
    return max(int(remaining), 0)


def _probe_dependencies() -> tuple[bool, bool]:
    db_ok = False
    redis_ok = False

    db = None
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    finally:
        try:
            if db is not None:
                db.close()
        except Exception:
            pass

    try:
        redis_ok = bool(redis_client.ping())
    except Exception:
        redis_ok = False

    self_heal_dependency_state.labels(dependency="db").set(1 if db_ok else 0)
    self_heal_dependency_state.labels(dependency="redis").set(1 if redis_ok else 0)
    return db_ok, redis_ok


def run_self_heal_cycle() -> dict:
    if not settings.self_heal_enabled:
        _state["enabled"] = False
        _state["last_action"] = "disabled"
        return dict(_state)

    _state["enabled"] = True
    _state["last_run_utc"] = datetime.now(timezone.utc).isoformat()
    db_ok, redis_ok = _probe_dependencies()
    _state["db_ok"] = db_ok
    _state["redis_ok"] = redis_ok

    degraded = not db_ok or not redis_ok
    if degraded:
        if _marker_is_set():
            _state["active_fail_open"] = True
            _state["recovery_streak"] = 0
            _state["last_action"] = "already_protected"
            self_heal_actions_total.labels(action="already_protected", outcome="ok").inc()
            return dict(_state)
        if not _cooldown_elapsed():
            _state["active_fail_open"] = bool(_marker_is_set())
            _state["recovery_streak"] = 0
            _state["last_action"] = "cooldown_skip_enable"
            self_heal_actions_total.labels(action="cooldown_skip_enable", outcome="ok").inc()
            return dict(_state)
        ttl_seconds = max(settings.self_heal_policy_ttl_seconds, 30)
        try:
            for policy_name in RESILIENCE_POLICIES:
                set_resilience_policy(policy_name, enabled=True, ttl_seconds=ttl_seconds)
            _marker_set(ttl_seconds=max(ttl_seconds * 2, 60))
            _set_last_change_ts()
            _state["active_fail_open"] = True
            _state["recovery_streak"] = 0
            _state["last_action"] = "enable_fail_open"
            self_heal_actions_total.labels(action="enable_fail_open", outcome="ok").inc()
        except Exception:
            _state["last_action"] = "enable_fail_open_failed"
            self_heal_actions_total.labels(action="enable_fail_open", outcome="error").inc()
        return dict(_state)

    if _marker_is_set():
        _state["recovery_streak"] = int(_state.get("recovery_streak") or 0) + 1
        required = max(settings.self_heal_recovery_streak, 1)
        if _state["recovery_streak"] >= required:
            if not _cooldown_elapsed():
                _state["active_fail_open"] = True
                _state["last_action"] = "cooldown_skip_restore"
                self_heal_actions_total.labels(action="cooldown_skip_restore", outcome="ok").inc()
                return dict(_state)
            try:
                for policy_name in RESILIENCE_POLICIES:
                    clear_resilience_policy(policy_name)
                _marker_clear()
                _set_last_change_ts()
                _state["active_fail_open"] = False
                _state["recovery_streak"] = 0
                _state["last_action"] = "restore_defaults"
                self_heal_actions_total.labels(action="restore_defaults", outcome="ok").inc()
            except Exception:
                _state["last_action"] = "restore_defaults_failed"
                self_heal_actions_total.labels(action="restore_defaults", outcome="error").inc()
        else:
            _state["active_fail_open"] = True
            _state["last_action"] = "recovery_in_progress"
            self_heal_actions_total.labels(action="recovery_in_progress", outcome="ok").inc()
    else:
        _state["active_fail_open"] = False
        _state["recovery_streak"] = 0
        _state["last_action"] = "healthy_no_action"
        self_heal_actions_total.labels(action="healthy_no_action", outcome="ok").inc()

    return dict(_state)


def get_self_heal_status() -> dict:
    status = dict(_state)
    last_change = _last_change_ts()
    cooldown_seconds = max(settings.self_heal_cooldown_seconds, 0)
    cooldown_remaining = _cooldown_remaining_seconds()
    status["marker_active"] = _marker_is_set()
    status["cooldown_seconds"] = cooldown_seconds
    status["cooldown_remaining_seconds"] = cooldown_remaining
    status["last_change_utc"] = (
        datetime.fromtimestamp(last_change, tz=timezone.utc).isoformat() if last_change > 0 else None
    )
    status["next_allowed_action_utc"] = (
        datetime.fromtimestamp(time.time() + cooldown_remaining, tz=timezone.utc).isoformat()
        if cooldown_remaining > 0
        else datetime.now(timezone.utc).isoformat()
    )
    return status


def reset_self_heal_cooldown() -> dict:
    before_remaining = _cooldown_remaining_seconds()
    _clear_last_change_ts()
    _state["last_action"] = "manual_cooldown_reset"
    self_heal_actions_total.labels(action="manual_cooldown_reset", outcome="ok").inc()
    result = get_self_heal_status()
    result["cooldown_reset"] = {
        "before_remaining_seconds": before_remaining,
        "after_remaining_seconds": result.get("cooldown_remaining_seconds", 0),
    }
    return result


def start_self_heal_autopilot() -> None:
    if not settings.self_heal_enabled:
        return

    interval_seconds = max(settings.self_heal_interval_seconds, 5)

    async def _loop() -> None:
        while True:
            run_self_heal_cycle()
            await asyncio.sleep(interval_seconds)

    try:
        loop = asyncio.get_event_loop()
        loop.create_task(_loop())
    except RuntimeError:
        pass
