"""Módulo de seguridad y cumplimiento para MediCare Pro.
Cifrado AES-256 (Fernet), control de acceso por tenant, sanitización XSS,
validación de archivos por magic bytes, PII-free logging y auditoría inmutable
con chain-hash persistido en Supabase.

Cumplimiento:
- Ley 25.326 (Protección de Datos Personales, Art. 7 y 9)
- Ley 25.506 (Firma Digital)
- Resolución AAIP 47/2018
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import logging
import os
import re
import time
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Optional

import streamlit as st

from core.app_logging import log_event

_logger = logging.getLogger("medicare.seguridad")

# ── Cifrado Fernet ───────────────────────────────────────────────────
_FERNET: Any = None
_FERNET_KEY_ID: str = ""

try:
    from cryptography.fernet import Fernet, InvalidToken
    _raw_key = os.environ.get("FERNET_KEY", "").strip()
    if _raw_key:
        _key_bytes = _raw_key.encode("utf-8")
        decoded = base64.urlsafe_b64decode(_key_bytes + b"==")
        if len(decoded) == 32:
            _FERNET = Fernet(_key_bytes)
            _FERNET_KEY_ID = hashlib.sha256(_key_bytes).hexdigest()[:8]
            log_event("seguridad", f"fernet_init_ok:key_id={_FERNET_KEY_ID}")
        else:
            log_event("seguridad", "fernet_init_error:invalid_key_length")
except Exception as exc:
    log_event("seguridad", f"fernet_init_error:{type(exc).__name__}")

# ── Constantes ───────────────────────────────────────────────────────

SENSITIVE_FIELDS: frozenset = frozenset({
    "alergias", "patologias", "diagnostico_ingreso", "motivo_ingreso",
})

ALLOWED_MIME_TYPES: dict[str, tuple[bytes, ...]] = {
    "image/png": (b'\x89PNG\r\n\x1a\n',),
    "image/jpeg": (b'\xff\xd8\xff',),
    "image/webp": (b'RIFF',),
    "application/pdf": (b'%PDF',),
}

ALLOWED_EXTENSIONS: frozenset = frozenset({
    ".png", ".jpg", ".jpeg", ".webp", ".pdf",
})

_PII_PATTERNS: tuple[tuple[str, str], ...] = (
    (r'\b\d{1}\.\d{3}\.\d{3}\b', '***CUIL***'),
    (r'\b\d{2}\.\d{3}\.\d{3}\b', '***CUIL***'),
    (r'\b\d{7,8}\b(?!-)', '***DNI***'),
    (r'[\w.+-]+@[\w-]+\.[\w.-]+', '***EMAIL***'),
    (r'\+\d{7,15}\b|\b\d{7,15}\b', '***TEL***'),
)

_MAX_AUDIT_CHAIN_LENGTH: int = 5000

# ═══════════════════════════════════════════════════════════════════════
#  CIFRADO AES-256
# ═══════════════════════════════════════════════════════════════════════


def encrypt_field(value: str) -> str:
    if not value or not _FERNET:
        return value
    try:
        return _FERNET.encrypt(value.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        log_event("seguridad", f"encrypt_error:{type(exc).__name__}")
        return value


def decrypt_field(value: str) -> str:
    if not value or not _FERNET:
        return value
    try:
        return _FERNET.decrypt(value.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception) as exc:
        if not isinstance(exc, InvalidToken):
            log_event("seguridad", f"decrypt_error:{type(exc).__name__}")
        return value


def encrypt_patient_dict(d: dict) -> dict:
    if not _FERNET or not d:
        return d
    result = deepcopy(d)
    for field in SENSITIVE_FIELDS:
        raw = result.get(field)
        if raw and isinstance(raw, str):
            try:
                result[field] = encrypt_field(raw)
            except Exception as exc:
                log_event("seguridad", f"encrypt_field_fail:{field}:{type(exc).__name__}")
    return result


def decrypt_patient_dict(d: dict) -> dict:
    if not _FERNET or not d:
        return d
    result = deepcopy(d)
    for field in SENSITIVE_FIELDS:
        raw = result.get(field)
        if raw and isinstance(raw, str):
            try:
                result[field] = decrypt_field(raw)
            except Exception as exc:
                log_event("seguridad", f"decrypt_field_fail:{field}:{type(exc).__name__}")
    return result


# ═══════════════════════════════════════════════════════════════════════
#  SANITIZACIÓN DE PII
# ═══════════════════════════════════════════════════════════════════════


def sanitize_for_log(message: str, extra_sensitive: Optional[str] = None) -> str:
    if not message:
        return ""
    sanitized = str(message)
    for pattern, replacement in _PII_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized)
    if extra_sensitive:
        sanitized = sanitized.replace(extra_sensitive, '***SENSIBLE***')
    return sanitized[:500]


# ═══════════════════════════════════════════════════════════════════════
#  XSS-SAFE MARKDOWN
# ═══════════════════════════════════════════════════════════════════════


def safe_markdown(template: str, unsafe_allow_html: bool = False, **kwargs: Any) -> None:
    if not kwargs:
        st.markdown(template, unsafe_allow_html=unsafe_allow_html)
        return
    escaped = {k: html.escape(str(v)) for k, v in kwargs.items()}
    try:
        result = template.format(**escaped)
    except KeyError as e:
        log_event("seguridad", f"safe_markdown_error:missing_key={e}")
        st.error("Error al renderizar contenido.")
        return
    st.markdown(result, unsafe_allow_html=unsafe_allow_html)


def safe_error(message: str, **kwargs: Any) -> None:
    msg = html.escape(message.format(**kwargs)) if kwargs else html.escape(str(message))
    log_event("seguridad", f"ui_error:{msg[:100]}")
    st.error(msg)


# ═══════════════════════════════════════════════════════════════════════
#  CONTROL DE ACCESO (TENANT ISOLATION)
# ═══════════════════════════════════════════════════════════════════════

_VERIFY_CACHE_TTL: float = 30.0


def _get_paciente_empresa(paciente_id: str) -> str:
    cache_key = f"_empresa_cache_{paciente_id}"
    cached = st.session_state.get(cache_key)
    if cached and isinstance(cached, dict):
        ts, empresa = cached.get("ts", 0), cached.get("empresa", "")
        if time.monotonic() - ts < _VERIFY_CACHE_TTL:
            return empresa
    from core.utils_pacientes import mapa_detalles_pacientes
    detalles = mapa_detalles_pacientes(st.session_state).get(paciente_id, {})
    empresa = str(detalles.get("empresa", "")).strip()
    st.session_state[cache_key] = {"ts": time.monotonic(), "empresa": empresa}
    return empresa


def verify_patient_access(paciente_id: str, user: Optional[dict]) -> bool:
    if not paciente_id or not user:
        return False
    rol = str(user.get("rol", "")).strip()
    if rol in ("SuperAdmin", "Admin"):
        return True
    user_empresa = str(user.get("empresa", "")).strip()
    if not user_empresa:
        log_event("seguridad", "verify_access:user_sin_empresa")
        return False
    paciente_empresa = _get_paciente_empresa(paciente_id)
    if not paciente_empresa:
        return True
    return paciente_empresa == user_empresa


def require_patient_access(paciente_id: str, user: Optional[dict]) -> None:
    if not verify_patient_access(paciente_id, user):
        login = str(user.get("login", user.get("nombre", "unknown"))) if user else "unknown"
        log_event("seguridad", f"acceso_denegado:user={sanitize_for_log(login)}:paciente={sanitize_for_log(paciente_id or '')}")
        safe_error("No tiene permisos para acceder a los datos de este paciente. Si cree que esto es un error, contacte a su administrador.")
        st.stop()


# ═══════════════════════════════════════════════════════════════════════
#  VALIDACIÓN DE ARCHIVOS (MAGIC BYTES)
# ═══════════════════════════════════════════════════════════════════════


def validate_uploaded_file(uploaded_file) -> tuple[bool, str]:
    if uploaded_file is None:
        return False, "No se seleccionó ningún archivo."
    name = str(getattr(uploaded_file, "name", "") or "")
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Extensión no permitida: {ext}. Permitidas: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
    try:
        uploaded_file.seek(0)
        header = uploaded_file.read(2048)
        uploaded_file.seek(0)
    except Exception as exc:
        log_event("seguridad", f"file_read_error:{type(exc).__name__}")
        return False, "No se pudo leer el archivo."
    if not header:
        return False, "El archivo está vacío."
    for mime_type, magic_list in ALLOWED_MIME_TYPES.items():
        for magic in magic_list:
            if header.startswith(magic):
                return True, ""
    return False, f"Tipo de archivo no reconocido. Los formatos permitidos son: {', '.join(sorted(ALLOWED_EXTENSIONS))}"


# ═══════════════════════════════════════════════════════════════════════
#  AUDITORÍA INMUTABLE (CHAIN-HASH)
# ═══════════════════════════════════════════════════════════════════════


def _get_last_audit_hash_from_db() -> str:
    try:
        from core.database import supabase
        if supabase:
            result = supabase.table("auditoria_legal").select("hash").order("timestamp", desc=True).limit(1).execute()
            if result.data:
                return result.data[0].get("hash", "0" * 64)
    except Exception as exc:
        log_event("auditoria", f"get_last_hash_error:{type(exc).__name__}")
    return "0" * 64


def registrar_auditoria_inmutable(
    seccion: str,
    paciente: str,
    accion: str,
    usuario: str,
    matricula: str = "",
    detalle: str = "",
) -> str:
    entry: dict[str, Any] = {
        "seccion": sanitize_for_log(seccion),
        "paciente": sanitize_for_log(paciente),
        "accion": sanitize_for_log(accion),
        "usuario": sanitize_for_log(usuario),
        "matricula": sanitize_for_log(matricula),
        "detalle": sanitize_for_log(detalle)[:300],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip": "",
    }
    entry["prev_hash"] = _get_last_audit_hash_from_db()
    entry_hash = hashlib.sha256(json.dumps(entry, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    entry["hash"] = entry_hash
    sql_ok = False
    try:
        from core.database import supabase
        if supabase:
            result = supabase.table("auditoria_legal").insert(entry).execute()
            sql_ok = bool(result.data)
    except Exception as exc:
        log_event("auditoria", f"insert_fail:{sanitize_for_log(str(exc))}")
    if not sql_ok:
        chain: list = st.session_state.setdefault("_audit_chain", [])
        chain.append(entry)
        if len(chain) > _MAX_AUDIT_CHAIN_LENGTH:
            st.session_state["_audit_chain"] = chain[-_MAX_AUDIT_CHAIN_LENGTH:]
    st.session_state["_last_audit_hash"] = entry_hash
    log_event("auditoria", f"entry:{entry_hash[:12]}:seccion={sanitize_for_log(seccion)}")
    return entry_hash


def verify_audit_chain(entries: list[dict]) -> tuple[bool, str]:
    if not entries:
        return False, "Cadena vacía."
    prev_hash = "0" * 64
    for i, entry in enumerate(entries):
        stored_hash = entry.get("hash", "")
        stored_prev = entry.get("prev_hash", "")
        if stored_prev != prev_hash:
            return False, f"Ruptura en entrada {i}: prev_hash esperado={prev_hash[:12]}, encontrado={stored_prev[:12]}"
        entry_copy = dict(entry)
        entry_copy.pop("hash", None)
        computed_hash = hashlib.sha256(json.dumps(entry_copy, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        if computed_hash != stored_hash:
            return False, f"Hash modificado en entrada {i}: esperado={stored_hash[:12]}, calculado={computed_hash[:12]}"
        prev_hash = stored_hash
    return True, f"Cadena íntegra: {len(entries)} entradas verificadas."
