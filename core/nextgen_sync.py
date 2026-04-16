import hashlib
import uuid
from typing import Any, Dict, Optional
import jwt
import streamlit as st

from core.api_client import post_api
from core.app_logging import log_event
from core.feature_flags import ENABLE_NEXTGEN_API_DUAL_WRITE


def _generate_nextgen_token(empresa: str) -> str:
    """
    Genera un JWT válido para la API NextGen basado en el usuario actual de Streamlit.
    """
    secret = st.secrets.get("NEXTGEN_JWT_SECRET", "change_me_local")
    
    # Generar UUIDs deterministas para el tenant y el usuario basados en sus nombres legacy
    tenant_hash = hashlib.md5(empresa.encode("utf-8")).hexdigest()
    tenant_uuid = str(uuid.UUID(tenant_hash))
    
    user_login = st.session_state.get("u_actual", {}).get("usuario_login", "system")
    user_hash = hashlib.md5(user_login.encode("utf-8")).hexdigest()
    user_uuid = str(uuid.UUID(user_hash))
    
    payload = {
        "sub": user_uuid,
        "tenant_id": tenant_uuid,
        "role": "admin", # Permiso máximo para sincronización dual-write
        "type": "access"
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def sync_paciente_to_nextgen(nombre: str, dni: str, empresa: str) -> None:
    """
    Envía un nuevo paciente a la API NextGen (FastAPI).
    Implementa "fire-and-forget" o dual-write suave: si falla, loguea pero no rompe la app.
    """
    if not ENABLE_NEXTGEN_API_DUAL_WRITE:
        return

    payload = {
        "full_name": nombre.strip(),
        "document_number": str(dni).strip()
    }
    
    # Generamos una idempotency key basada en el DNI para evitar duplicados en reintentos
    idem_key = f"paciente_creacion_{dni.strip()}"
    token = _generate_nextgen_token(empresa)
    
    try:
        resp = post_api(
            "/patients",
            json=payload,
            headers={
                "Idempotency-Key": idem_key,
                "Authorization": f"Bearer {token}"
            },
            timeout=5.0
        )
        if resp.ok:
            log_event("nextgen_sync", f"Paciente {dni} sincronizado con éxito a NextGen API.")
        else:
            log_event("nextgen_sync", f"Error al sincronizar paciente {dni}: {resp.status_code} - {resp.text}")
    except Exception as e:
        log_event("nextgen_sync", f"Excepción al sincronizar paciente {dni} a NextGen: {e}")


def sync_visita_evolucion_to_nextgen(paciente_id: str, nota: str) -> None:
    """
    Envía una nueva evolución/visita a la API NextGen.
    """
    if not ENABLE_NEXTGEN_API_DUAL_WRITE:
        return

    hash_id = hashlib.md5(paciente_id.encode("utf-8")).hexdigest()
    patient_uuid = str(uuid.UUID(hash_id))

    payload = {
        "patient_id": patient_uuid,
        "notes": nota.strip()[:5000]
    }
    
    empresa = st.session_state.get("u_actual", {}).get("empresa", "Clinica Default")
    token = _generate_nextgen_token(empresa)
    
    try:
        resp = post_api(
            "/visits",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0
        )
        if resp.ok:
            log_event("nextgen_sync", f"Evolución para {paciente_id} sincronizada con éxito a NextGen API.")
        else:
            log_event("nextgen_sync", f"Error al sincronizar evolución {paciente_id}: {resp.status_code} - {resp.text}")
    except Exception as e:
        log_event("nextgen_sync", f"Excepción al sincronizar evolución {paciente_id} a NextGen: {e}")
