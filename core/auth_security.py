"""
Controles de seguridad en el flujo de login.

- Límite de intentos fallidos y bloqueo temporal (anti fuerza bruta).
- Estado del bloqueo: solo sesión (navegador), archivo en `.streamlit/`, o tabla Supabase.
- Secrets: MAX_LOGIN_ATTEMPTS (0 = desactivado), LOGIN_LOCKOUT_SECONDS (mín. 30),
  LOGIN_LOCKOUT_PERSIST = session | file | supabase
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import streamlit as st

from core.app_logging import log_event
from core.db_serialize import loads_json_any


def _secret_int(key: str, default: int) -> int:
    try:
        return int(st.secrets.get(key, default))
    except Exception:
        return default


def max_login_attempts() -> int:
    """0 = protección desactivada."""
    n = _secret_int("MAX_LOGIN_ATTEMPTS", 8)
    return max(0, n)


def lockout_segundos() -> int:
    return max(30, _secret_int("LOGIN_LOCKOUT_SECONDS", 300))


def proteccion_login_habilitada() -> bool:
    return max_login_attempts() > 0


def lockout_persist_mode() -> str:
    """session | file | supabase"""
    try:
        v = st.secrets.get("LOGIN_LOCKOUT_PERSIST", "session")
    except Exception:
        return "session"
    s = str(v).strip().lower()
    if s in ("file", "disk", "local"):
        return "file"
    if s in ("supabase", "cloud", "remote"):
        return "supabase"
    return "session"


def _effective_persist_mode() -> str:
    m = lockout_persist_mode()
    if m == "session":
        return "session"
    if m == "file":
        return "file"
    if m == "supabase":
        try:
            from core.database import supabase as sb

            if sb is None:
                log_event("auth", "login_lockout_fallback_no_supabase")
                return "file"
        except Exception:
            return "session"
        return "supabase"
    return "session"


def _clave_login(login_norm: str) -> str:
    s = (login_norm or "").strip().lower()
    return s if s else "(anon)"


def _bundle() -> dict:
    return st.session_state.setdefault("_mc_login_protect", {})


def _lockout_file_path() -> Path:
    root = Path(__file__).resolve().parent.parent / ".streamlit"
    return root / "login_lockout_state.json"


def _file_load_all() -> dict:
    p = _lockout_file_path()
    if not p.exists():
        return {}
    try:
        data = loads_json_any(p.read_bytes())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _file_save_all(data: dict) -> None:
    p = _lockout_file_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(p)
    except Exception:
        log_event("auth", "login_lockout_file_write_fail")


def _remote_row_to_state(row: dict) -> dict:
    if not row:
        return {"fails": 0, "until": 0.0}
    fu = row.get("locked_until")
    until = 0.0
    if fu is not None:
        try:
            until = float(fu)
        except (TypeError, ValueError):
            until = 0.0
    return {"fails": int(row.get("fail_count") or 0), "until": until}


def _persist_get(key: str) -> dict:
    mode = _effective_persist_mode()
    if mode == "file":
        data = _file_load_all()
        b = data.get(key) or {}
        return {"fails": int(b.get("fails") or 0), "until": float(b.get("until") or 0)}
    if mode == "supabase":
        try:
            from core.database import supabase as sb

            r = (
                sb.table("app_login_lockout")
                .select("fail_count, locked_until")
                .eq("login_key", key)
                .limit(1)
                .execute()
            )
            if r.data and len(r.data) > 0:
                return _remote_row_to_state(r.data[0])
        except Exception:
            log_event("auth", "login_lockout_remote_read_fail")
        return {"fails": 0, "until": 0.0}
    return dict(_bundle().get(key) or {})


def _persist_set(key: str, fails: int, until: float) -> None:
    mode = _effective_persist_mode()
    if mode == "file":
        data = _file_load_all()
        if fails <= 0 and until <= 0:
            data.pop(key, None)
        else:
            data[key] = {"fails": fails, "until": until}
        _file_save_all(data)
        return
    if mode == "supabase":
        try:
            from core.database import supabase as sb

            if fails <= 0 and until <= 0:
                sb.table("app_login_lockout").delete().eq("login_key", key).execute()
            else:
                sb.table("app_login_lockout").upsert(
                    {
                        "login_key": key,
                        "fail_count": fails,
                        "locked_until": until if until > 0 else None,
                    },
                    on_conflict="login_key",
                ).execute()
        except Exception:
            log_event("auth", "login_lockout_remote_write_fail")
        return
    b = _bundle()
    if fails <= 0 and until <= 0:
        b.pop(key, None)
    else:
        b[key] = {"fails": fails, "until": until}


def _state_get(key: str) -> dict:
    return _persist_get(key)


def _normalizar_estado_tras_expiracion(key: str, now: float) -> tuple[int, float]:
    """Lee estado; si el bloqueo ya venció, limpia en almacenamiento y devuelve (0, 0)."""
    raw = _state_get(key)
    fails = int(raw.get("fails") or 0)
    until = float(raw.get("until") or 0)
    if until > 0 and until <= now:
        _persist_set(key, 0, 0.0)
        return 0, 0.0
    return fails, until


def puede_intentar_login(login_norm: str) -> tuple[bool, Optional[str]]:
    if not proteccion_login_habilitada():
        return True, None
    key = _clave_login(login_norm)
    now = time.time()
    _fails, until = _normalizar_estado_tras_expiracion(key, now)
    if until > now:
        resta = int(until - now) + 1
        m, s = resta // 60, resta % 60
        msg = f"Demasiados intentos fallidos. Esperá {m} min {s} s antes de volver a probar."
        return False, msg
    return True, None


def registrar_fallo_login(login_norm: str) -> None:
    if proteccion_login_habilitada():
        key = _clave_login(login_norm)
        now = time.time()
        fails, until = _normalizar_estado_tras_expiracion(key, now)
        if until > now:
            return
        fails += 1
        mx = max_login_attempts()
        if fails >= mx:
            new_until = now + lockout_segundos()
            _persist_set(key, 0, new_until)
            log_event("auth", "login_lockout_tras_intentos")
        else:
            _persist_set(key, fails, 0.0)
            log_event("auth", "login_intento_fallido")
    aplicar_jitter_tras_fallo_credenciales()


def aplicar_jitter_tras_fallo_credenciales() -> None:
    """Pausa breve aleatoria tras fallo (mitiga filtrado por tiempos). LOGIN_FAIL_JITTER_MS=0 desactiva."""
    try:
        ms = int(st.secrets.get("LOGIN_FAIL_JITTER_MS", 15))
    except Exception:
        ms = 15
    if ms <= 0:
        return
    import secrets as pysec
    import time as time_mod

    delay_ms = min(30, ms + pysec.randbelow(max(1, ms)))
    time_mod.sleep(delay_ms / 1000.0)


def limpiar_fallos_login(login_norm: str) -> None:
    key = _clave_login(login_norm)
    _persist_set(key, 0, 0.0)
    _bundle().pop(key, None)


def texto_ayuda_proteccion() -> str | None:
    if not proteccion_login_habilitada():
        return None
    mx = max_login_attempts()
    sec = lockout_segundos()
    modo = _effective_persist_mode()
    if modo == "supabase":
        donde = "en el servidor (Supabase), compartido entre sesiones."
    elif modo == "file":
        donde = "en el servidor (archivo), compartido entre sesiones del mismo equipo."
    else:
        donde = "en este navegador."
    return (
        f"Protección activa: tras **{mx}** intentos fallidos con el mismo usuario, "
        f"el acceso se bloquea unos **{sec // 60}** minutos ({donde})"
    )
