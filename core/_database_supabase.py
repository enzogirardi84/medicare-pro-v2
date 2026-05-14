"""Conexión a Supabase, reintentos y operaciones de carga/guardado en nube.

Extraído de core/database.py.
"""
import hashlib
import os
import time
from urllib.parse import urlparse

import streamlit as st

from core.app_logging import log_event
from core.db_serialize import compress_payload, decompress_payload, dumps_db_sorted, loads_db_payload

try:
    from supabase import create_client
    try:
        from supabase import APIError as _SupabaseAPIError
    except ImportError:
        _SupabaseAPIError = Exception
except ImportError:
    create_client = None
    _SupabaseAPIError = Exception

PAYLOAD_ALERTA_BYTES = 9 * 1024 * 1024


def _proxy_env_loopback_blackhole_activo() -> bool:
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "all_proxy"):
        raw = str(os.environ.get(key, "") or "").strip()
        if not raw:
            continue
        try:
            parsed = urlparse(raw)
        except Exception:
            continue
        host = str(parsed.hostname or "").strip().lower()
        if host in {"127.0.0.1", "localhost", "::1"} and parsed.port == 9:
            return True
    return False


@st.cache_resource
def init_supabase():
    if create_client is None:
        log_event("db", "supabase_client_not_installed")
        return None
    try:
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")
    except Exception as e:
        log_event("db", f"supabase_secrets_error:{type(e).__name__}")
        return None
    if not url or "tu-proyecto-aqui" in url or not key:
        log_event("db", "supabase_secrets_empty_or_placeholder")
        return None
    options = None
    if _proxy_env_loopback_blackhole_activo():
        try:
            import httpx
            from supabase.lib.client_options import SyncClientOptions
            options = SyncClientOptions(
                httpx_client=httpx.Client(
                    trust_env=False,
                    follow_redirects=True,
                    http2=True,
                    timeout=5.0,
                )
            )
            log_event("db", "supabase_proxy_bypass:loopback_port_9")
        except Exception as e:
            log_event("db", f"supabase_proxy_bypass_error:{type(e).__name__}")
    try:
        client = create_client(url, key, options=options)
        log_event("db", "supabase_init_ok")
        return client
    except _SupabaseAPIError as e:
        log_event("db", f"supabase_init_apierror:{type(e).__name__}")
        return None
    except Exception as e:
        log_event("db", f"supabase_init_exception:{type(e).__name__}")
        return None


supabase = init_supabase()


def _supabase_execute_with_retry(op_name: str, fn, attempts: int = 3, base_delay: float = 0.35):
    try:
        from core.feature_flags import SUPABASE_RETRY_ATTEMPTS, SUPABASE_RETRY_BASE_DELAY_SEGUNDOS
        attempts = int(SUPABASE_RETRY_ATTEMPTS or attempts)
        base_delay = float(SUPABASE_RETRY_BASE_DELAY_SEGUNDOS or base_delay)
    except Exception as _exc:
        import logging
        logging.getLogger("database.supabase").debug(f"fallo_cargar_feature_flags:{type(_exc).__name__}")
    last_error = None
    tries = max(1, int(attempts or 1))
    for intento in range(1, tries + 1):
        try:
            return fn()
        except (TimeoutError, ConnectionError, OSError) as e:
            last_error = e
            if intento >= tries:
                log_event("db", f"{op_name}_timeout_finalizado:{type(e).__name__}:{e}")
                break
            try:
                espera = max(0.05, min(0.5, float(base_delay) * (1.5 ** (intento - 1))))
            except Exception:
                espera = 0.15
            log_event("db", f"{op_name}_retry_timeout:{intento}/{tries}:{type(e).__name__}")
            time.sleep(espera)
        except _SupabaseAPIError as e:
            last_error = e
            err_msg = str(getattr(e, "message", e))[:200]
            if intento >= tries:
                log_event("db", f"{op_name}_apierror_finalizado:{type(e).__name__}:{err_msg}")
                break
            try:
                espera = max(0.05, min(0.5, float(base_delay) * (1.5 ** (intento - 1))))
            except Exception:
                espera = 0.15
            log_event("db", f"{op_name}_retry_apierror:{intento}/{tries}:{err_msg}")
            time.sleep(espera)
        except Exception as e:
            last_error = e
            if intento >= tries:
                break
            try:
                espera = max(0.05, min(0.5, float(base_delay) * (1.5 ** (intento - 1))))
            except Exception:
                espera = 0.15
            log_event("db", f"{op_name}_retry:{intento}/{tries}:{type(e).__name__}")
            time.sleep(espera)
    raise last_error


def _payload_muy_grande(serializado_o_bytes) -> bool:
    if isinstance(serializado_o_bytes, bytes):
        return len(serializado_o_bytes) >= PAYLOAD_ALERTA_BYTES
    return len(serializado_o_bytes.encode("utf-8")) >= PAYLOAD_ALERTA_BYTES


def _fijar_cache_y_hash(data: dict) -> bytes | None:
    if not isinstance(data, dict):
        return None
    pb, _ = dumps_db_sorted(data)
    st.session_state["_db_cache"] = loads_db_payload(pb)
    st.session_state["_db_cache_hash"] = hashlib.sha256(pb).hexdigest()
    st.session_state["_db_cache_ts"] = time.monotonic()
    st.session_state["_guardar_datos_pendiente"] = False
    return pb


def _cargar_supabase_monolito():
    response = _supabase_execute_with_retry(
        "cargar_monolito",
        lambda: supabase.table("medicare_db").select("datos").eq("id", 1).execute(),
    )
    if response.data:
        raw = response.data[0]["datos"]
        return decompress_payload(raw) if isinstance(raw, dict) else raw
    return None


def _cargar_supabase_tenant(tenant_key: str):
    r = _supabase_execute_with_retry(
        "cargar_tenant",
        lambda: supabase.table("medicare_db")
        .select("datos")
        .eq("tenant_key", tenant_key)
        .limit(1)
        .execute(),
    )
    if r.data and len(r.data) > 0:
        raw = r.data[0].get("datos")
        return decompress_payload(raw) if isinstance(raw, dict) else raw
    return None


def _upsert_supabase_monolito(data: dict):
    tbl = supabase.table("medicare_db")
    payload = compress_payload(data)
    try:
        _supabase_execute_with_retry(
            "upsert_monolito",
            lambda: tbl.upsert({"id": 1, "datos": payload}, on_conflict="id").execute(),
        )
    except TypeError:
        _supabase_execute_with_retry("upsert_monolito", lambda: tbl.upsert({"id": 1, "datos": payload}).execute())


def _upsert_supabase_tenant(tenant_key: str, data: dict):
    tbl = supabase.table("medicare_db")
    payload = compress_payload(data)
    try:
        _supabase_execute_with_retry(
            "upsert_tenant",
            lambda: tbl.upsert({"tenant_key": tenant_key, "datos": payload}, on_conflict="tenant_key").execute(),
        )
    except TypeError:
        _supabase_execute_with_retry(
            "upsert_tenant",
            lambda: tbl.upsert({"tenant_key": tenant_key, "datos": payload}).execute(),
        )
