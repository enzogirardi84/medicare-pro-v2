"""Vigía de Errores — captura centralizada de fallas para diagnóstico directo.

- sys.excepthook + threading.excepthook para errores fatales fuera del loop Streamlit.
- Decorador @resiliente para funciones críticas.
- Buffer en session_state + archivo JSONL local para persistencia entre reruns.
- Integración automática con log_event.
- Opcional: envío a Supabase si está disponible.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import sys
import threading
import traceback
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import streamlit as st

from core.app_logging import log_event
from core.feature_flags import ERROR_TRACKER_ENABLED

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
_MAX_SESSION_BUFFER = 200
_MAX_DISK_LINES = 500
_DISK_FILE = Path(__file__).resolve().parent.parent / ".streamlit" / "data_store" / "app_errors.jsonl"
_SESSION_KEY = "_error_tracker_buffer"
_SESSION_META_KEY = "_error_tracker_meta"

# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _ensure_disk_dir() -> None:
    _DISK_FILE.parent.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_id() -> str:
    return uuid.uuid4().hex[:12]


def _exc_fingerprint(exc_type: str, message: str, module: str) -> str:
    """Hash corto para deduplicar errores idénticos en la misma sesión."""
    raw = f"{exc_type}|{message}|{module}"
    return hashlib.sha256(raw.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def _get_session_buffer() -> deque:
    """Devuelve el deque de errores en session_state (inicializa si hace falta)."""
    if _SESSION_KEY not in st.session_state:
        st.session_state[_SESSION_KEY] = deque(maxlen=_MAX_SESSION_BUFFER)
    return st.session_state[_SESSION_KEY]


def _get_session_meta() -> Dict[str, Any]:
    if _SESSION_META_KEY not in st.session_state:
        st.session_state[_SESSION_META_KEY] = {"initialized": False, "session_start": _now_iso()}
    return st.session_state[_SESSION_META_KEY]


def _append_to_disk(record: Dict[str, Any]) -> None:
    try:
        _ensure_disk_dir()
        with _DISK_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        # Rotar si excede el máximo
        _rotate_disk_if_needed()
    except Exception as e:
        log_event("error_tracker", f"disk_append_falla:{type(e).__name__}:{e}")


def _rotate_disk_if_needed() -> None:
    try:
        if not _DISK_FILE.exists():
            return
        lines = _DISK_FILE.read_text(encoding="utf-8").splitlines()
        if len(lines) > _MAX_DISK_LINES:
            trimmed = lines[-_MAX_DISK_LINES:]
            _DISK_FILE.write_text("\n".join(trimmed) + "\n", encoding="utf-8")
    except Exception:
        pass


def _current_user() -> Optional[str]:
    """Intenta obtener usuario actual desde session_state."""
    try:
        user = st.session_state.get("user")
        if user and isinstance(user, dict):
            return user.get("email") or user.get("username") or user.get("nombre")
    except Exception:
        pass
    return None


def _supabase_insert(record: Dict[str, Any]) -> None:
    """Envío opcional a Supabase (no bloqueante; ignora fallos)."""
    try:
        from core._database_supabase import supabase
        if supabase is None:
            return
        supabase.table("app_error_logs").insert(record).execute()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def report_exception(
    module: str,
    exc_info: Optional[Any] = None,
    context: str = "",
    severity: str = "error",
    user: Optional[str] = None,
) -> Dict[str, Any]:
    """Reporta un error al tracker. Retorna el registro creado.

    Args:
        module: nombre del módulo / función donde ocurrió (ej. "main", "inventario.carga").
        exc_info: excepción activa (sys.exc_info() o una instancia Exception).
        context: descripción breve del contexto operativo.
        severity: "critical", "error", "warning".
        user: override de usuario; si es None se intenta leer de session_state.
    """
    if not ERROR_TRACKER_ENABLED:
        return {}

    try:
        if exc_info is None:
            exc_type, exc_value, exc_tb = sys.exc_info()
        elif isinstance(exc_info, (tuple, list)) and len(exc_info) == 3:
            exc_type, exc_value, exc_tb = exc_info
        elif isinstance(exc_info, BaseException):
            exc_type = type(exc_info)
            exc_value = exc_info
            exc_tb = getattr(exc_info, "__traceback__", None)
        else:
            exc_type, exc_value, exc_tb = type(exc_info), exc_info, None

        type_name = exc_type.__name__ if exc_type else "Unknown"
        message = str(exc_value) if exc_value else "Sin mensaje"
        stack = "".join(traceback.format_exception(exc_type, exc_value, exc_tb)) if exc_type else ""
    except Exception:
        type_name = "Unknown"
        message = str(exc_info) if exc_info else "Sin mensaje"
        stack = traceback.format_exc()

    fingerprint = _exc_fingerprint(type_name, message, module)
    ts = _now_iso()
    record = {
        "id": _short_id(),
        "timestamp": ts,
        "module": module,
        "severity": severity,
        "type": type_name,
        "message": message,
        "stack_trace": stack,
        "context": context,
        "user": user or _current_user() or "anonymous",
        "fingerprint": fingerprint,
        "resolved": False,
        "count": 1,
    }

    # Buffer en memoria (deduplicar)
    buf = _get_session_buffer()
    found = None
    for existing in buf:
        if existing.get("fingerprint") == fingerprint and not existing.get("resolved"):
            found = existing
            break

    if found:
        found["count"] = found.get("count", 1) + 1
        found["last_seen"] = ts
        found["context"] = f"{found.get('context','')}; {context}".strip("; ")
        record = found
    else:
        buf.append(record)

    # Persistencia
    _append_to_disk(record)

    # Log central
    log_event(
        "error_tracker",
        f"[{severity}] {module} | {type_name}: {message} (id={record['id']}, count={record.get('count',1)})",
    )

    # Supabase (fire-and-forget)
    _supabase_insert(record)

    return record


def get_recent_errors(
    limit: int = 50,
    severity: Optional[str] = None,
    module: Optional[str] = None,
    unresolved_only: bool = False,
) -> List[Dict[str, Any]]:
    """Devuelve errores recientes combinando session_state + disco."""
    if not ERROR_TRACKER_ENABLED:
        return []

    # 1. Leer de disco (más antiguo -> más reciente)
    disk_records: List[Dict[str, Any]] = []
    try:
        if _DISK_FILE.exists():
            lines = _DISK_FILE.read_text(encoding="utf-8").splitlines()
            for line in lines:
                if line.strip():
                    try:
                        disk_records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except Exception:
        pass

    # 2. Leer de sesión
    buf = _get_session_buffer()
    session_records = list(buf)

    # 3. Merge y deduplicar por id
    seen = set()
    merged = []
    for rec in disk_records + session_records:
        eid = rec.get("id")
        if eid and eid in seen:
            continue
        seen.add(eid)
        merged.append(rec)

    # 4. Ordenar por timestamp descendente
    merged.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    # 5. Filtros
    filtered = []
    for rec in merged:
        if severity and rec.get("severity") != severity:
            continue
        if module and rec.get("module") != module:
            continue
        if unresolved_only and rec.get("resolved"):
            continue
        filtered.append(rec)
        if len(filtered) >= limit:
            break
    return filtered


def get_summary_stats() -> Dict[str, Any]:
    """Estadísticas rápidas para la UI del Vigía."""
    if not ERROR_TRACKER_ENABLED:
        return {"enabled": False}

    recs = get_recent_errors(limit=9999)
    total = len(recs)
    critical = sum(1 for r in recs if r.get("severity") == "critical")
    unresolved = sum(1 for r in recs if not r.get("resolved"))
    modules = {}
    for r in recs:
        m = r.get("module", "unknown")
        modules[m] = modules.get(m, 0) + (r.get("count", 1))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_count = sum(
        1 for r in recs if r.get("timestamp", "").startswith(today)
    )
    return {
        "enabled": True,
        "total": total,
        "critical": critical,
        "unresolved": unresolved,
        "today": today_count,
        "top_modules": sorted(modules.items(), key=lambda x: x[1], reverse=True)[:5],
    }


def mark_resolved(error_id: str) -> bool:
    """Marca un error como resuelto en session_state + disco."""
    if not ERROR_TRACKER_ENABLED:
        return False

    ok = False
    # Session
    buf = _get_session_buffer()
    for rec in buf:
        if rec.get("id") == error_id:
            rec["resolved"] = True
            rec["resolved_at"] = _now_iso()
            ok = True

    # Disco: reescribir todo (batch pequeño, rara operación)
    try:
        if _DISK_FILE.exists():
            lines = _DISK_FILE.read_text(encoding="utf-8").splitlines()
            new_lines = []
            for line in lines:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("id") == error_id:
                        rec["resolved"] = True
                        rec["resolved_at"] = _now_iso()
                        ok = True
                    new_lines.append(json.dumps(rec, ensure_ascii=False, default=str))
                except json.JSONDecodeError:
                    new_lines.append(line)
            _DISK_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    except Exception as e:
        log_event("error_tracker", f"mark_resolved_falla:{type(e).__name__}:{e}")

    return ok


def clear_all() -> None:
    """Limpia todos los errores de sesión y disco."""
    if _SESSION_KEY in st.session_state:
        st.session_state[_SESSION_KEY] = deque(maxlen=_MAX_SESSION_BUFFER)
    try:
        if _DISK_FILE.exists():
            _DISK_FILE.write_text("", encoding="utf-8")
    except Exception as e:
        log_event("error_tracker", f"clear_all_falla:{type(e).__name__}:{e}")


def export_json() -> str:
    """Exporta todo el historial como JSON string."""
    recs = get_recent_errors(limit=9999)
    return json.dumps(recs, ensure_ascii=False, indent=2, default=str)


def setup_global_hooks() -> None:
    """Instala sys.excepthook y threading.excepthook.

    En Streamlit, la mayoría de excepciones del script son capturadas por el
    runtime de Streamlit. Este hook cubre errores fatales fuera de ese loop
    (imports globales, threads no manejados, etc.).
    """
    if not ERROR_TRACKER_ENABLED:
        return

    if _get_session_meta().get("hooks_installed"):
        return
    _get_session_meta()["hooks_installed"] = True

    original_excepthook = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            original_excepthook(exc_type, exc_value, exc_tb)
            return
        try:
            report_exception(
                module="sys.excepthook",
                exc_info=(exc_type, exc_value, exc_tb),
                severity="critical",
                context="Error fatal no capturado por el runtime de Streamlit",
            )
        except Exception:
            pass
        original_excepthook(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook

    # Threading hook
    try:
        original_threading_excepthook = threading.excepthook

        def _thread_hook(args):
            try:
                report_exception(
                    module=f"thread.{args.thread.name if args.thread else 'unknown'}",
                    exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
                    severity="critical",
                    context="Excepción en thread no manejada",
                )
            except Exception:
                pass
            original_threading_excepthook(args)

        threading.excepthook = _thread_hook
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Decorador
# ---------------------------------------------------------------------------

def resilient(
    module: Optional[str] = None,
    fallback_return: Any = None,
    on_error: Optional[Callable[[BaseException], None]] = None,
    severity: str = "error",
):
    """Decorador para funciones críticas: captura excepción, reporta al tracker,
    retorna fallback_return, y opcionalmente ejecuta on_error.

    Uso:
        @resilient(module="inventario.carga", fallback_return=[])
        def cargar_items():
            ...
    """

    def decorator(fn: Callable) -> Callable:
        mod = module or fn.__module__

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not ERROR_TRACKER_ENABLED:
                return fn(*args, **kwargs)
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                try:
                    report_exception(
                        module=mod,
                        exc_info=exc,
                        context=f"{fn.__name__}({', '.join(str(a) for a in args)})",
                        severity=severity,
                    )
                except Exception:
                    pass
                if on_error:
                    try:
                        on_error(exc)
                    except Exception:
                        pass
                return fallback_return

        return wrapper

    return decorator
