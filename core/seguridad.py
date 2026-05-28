"""Módulo de seguridad y cumplimiento para MediCare Pro.
Cifrado, control de acceso, XSS prevention, logs inmutables y sanitización.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
from datetime import datetime, timezone
from typing import Optional

import streamlit as st

try:
    from cryptography.fernet import Fernet
    _FERNET = Fernet(os.environ.get("FERNET_KEY", "").encode()) if os.environ.get("FERNET_KEY") else None
except Exception:
    _FERNET = None


# ── Cifrado de campos sensibles ───────────────────────────────────────

def encrypt_field(value: str) -> str:
    if not value or not _FERNET:
        return value
    try:
        return _FERNET.encrypt(value.encode()).decode()
    except Exception:
        return value


def decrypt_field(encrypted: str) -> str:
    if not encrypted or not _FERNET:
        return encrypted
    try:
        return _FERNET.decrypt(encrypted.encode()).decode()
    except Exception:
        return encrypted


# ── Sanitización de PII para logs ─────────────────────────────────────

_PII_PATTERNS = [
    (r'\b\d{7,8}\b', '***DNI***'),          # DNI argentino (7-8 dígitos)
    (r'\b\d{2}\.\d{3}\.\d{3}\b', '***CUIL***'),  # CUIL
    (r'[\w.+-]+@[\w-]+\.[\w.-]+', '***EMAIL***'),  # Email
    (r'\b\d{10,15}\b', '***TEL***'),         # Teléfono
]


def sanitize_for_log(message: str, extra_sensitive: Optional[str] = None) -> str:
    """Reemplaza PII en mensajes de log por placeholders."""
    sanitized = str(message or "")
    for pattern, replacement in _PII_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized)
    if extra_sensitive:
        sanitized = sanitized.replace(extra_sensitive, '***SENSIBLE***')
    return sanitized[:500]


# ── XSS-safe markdown ────────────────────────────────────────────────

def safe_markdown(template: str, unsafe_allow_html: bool = False, **kwargs):
    """Renderiza markdown escapando todos los valores interpolados.
    Usar: safe_markdown("<b>{nombre}</b>", nombre=paciente)
    """
    escaped = {k: html.escape(str(v)) for k, v in kwargs.items()}
    result = template.format(**escaped)
    st.markdown(result, unsafe_allow_html=unsafe_allow_html)


def safe_error(message: str, **kwargs):
    """Muestra st.error() con mensaje escapado."""
    msg = html.escape(message.format(**kwargs)) if kwargs else html.escape(str(message))
    st.error(msg)


# ── Control de acceso por paciente (tenant isolation) ────────────────

def verify_patient_access(paciente_id: str, user: dict) -> bool:
    """Verifica que el usuario tenga permiso para acceder a los datos de este paciente.
    Retorna True si tiene acceso, False si no.
    """
    if not paciente_id or not user:
        return False

    rol = str(user.get("rol", "")).strip()
    if rol in ("SuperAdmin", "Admin"):
        return True

    user_empresa = str(user.get("empresa", "")).strip()
    if not user_empresa:
        return False

    from core.utils_pacientes import mapa_detalles_pacientes
    detalles = mapa_detalles_pacientes(st.session_state).get(paciente_id, {})
    paciente_empresa = str(detalles.get("empresa", "")).strip()

    if not paciente_empresa:
        return True  # sin empresa asignada, acceso permitido

    return paciente_empresa == user_empresa


def require_patient_access(paciente_id: str, user: dict):
    """Verifica acceso y muestra error si no tiene permiso."""
    if not verify_patient_access(paciente_id, user):
        from core.app_logging import log_event
        login = str(user.get("login", user.get("nombre", "unknown")))
        log_event("seguridad", f"acceso_denegado:usuario={sanitize_for_log(login)}:paciente={sanitize_for_log(paciente_id or '')}")
        st.error("No tiene permisos para acceder a los datos de este paciente.")
        st.stop()


# ── Validación de archivos subidos (magic bytes) ─────────────────────

ALLOWED_MIME_TYPES = {
    "image/png": [b'\x89PNG\r\n\x1a\n'],
    "image/jpeg": [b'\xff\xd8\xff'],
    "image/jpg": [b'\xff\xd8\xff'],
    "image/webp": [b'RIFF'],
    "application/pdf": [b'%PDF'],
}

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".pdf"}


def validate_uploaded_file(uploaded_file) -> tuple[bool, str]:
    """Valida tipo MIME por magic bytes y extensión.
    Retorna (ok, mensaje_error).
    """
    if uploaded_file is None:
        return False, "No se seleccionó ningún archivo."

    name = str(getattr(uploaded_file, "name", "") or "")
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Extensión no permitida: {ext}"

    try:
        header = uploaded_file.read(2048)
        uploaded_file.seek(0)
    except Exception:
        return False, "No se pudo leer el archivo."

    if not header:
        return False, "Archivo vacío."

    for mime_type, magic_list in ALLOWED_MIME_TYPES.items():
        for magic in magic_list:
            if header.startswith(magic):
                return True, ""

    return False, f"Tipo de archivo no reconocido. Los formatos permitidos son: {', '.join(sorted(ALLOWED_EXTENSIONS))}"


# ── Logs de auditoría inmutables (chain-hash) ────────────────────────

def registrar_auditoria_inmutable(
    seccion: str,
    paciente: str,
    accion: str,
    usuario: str,
    matricula: str = "",
    detalle: str = "",
) -> str:
    """Registra auditoría con chain-hash para inmutabilidad."""
    from core.app_logging import log_event

    entry = {
        "seccion": sanitize_for_log(seccion),
        "paciente": sanitize_for_log(paciente),
        "accion": sanitize_for_log(accion),
        "usuario": sanitize_for_log(usuario),
        "matricula": sanitize_for_log(matricula),
        "detalle": sanitize_for_log(detalle)[:300],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip": "",  # se puede obtener de st.context.headers si está disponible
    }

    prev_hash = st.session_state.get("_last_audit_hash", "0" * 64)
    entry["prev_hash"] = prev_hash
    entry_hash = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()
    entry["hash"] = entry_hash
    st.session_state["_last_audit_hash"] = entry_hash

    try:
        from core.database import supabase
        if supabase:
            supabase.table("auditoria_legal").insert(entry).execute()
    except Exception as e:
        log_event("auditoria", f"supabase_insert_fail:{sanitize_for_log(str(e))}")

    # Backup en session_state
    if "_audit_chain" not in st.session_state:
        st.session_state["_audit_chain"] = []
    st.session_state["_audit_chain"].append(entry)
    if len(st.session_state["_audit_chain"]) > 1000:
        st.session_state["_audit_chain"] = st.session_state["_audit_chain"][-1000:]

    return entry_hash
