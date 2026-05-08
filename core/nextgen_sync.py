import hashlib
import time
import uuid
from typing import Any, Dict, Optional
import jwt
import streamlit as st

from core.api_client import post_api
from core.app_logging import log_event
from core.empresa_config import empresa_uuid_configurada
from core.feature_flags import ENABLE_NEXTGEN_API_DUAL_WRITE
from core.db_sql import upsert_paciente, insert_evolucion, insert_indicacion, insert_administracion

def _generate_nextgen_token(empresa: str) -> str:
    """
    Genera un JWT válido para la API NextGen basado en el usuario actual de Streamlit.
    """
    secret = st.secrets.get("NEXTGEN_JWT_SECRET", "")
    if not secret:
        log_event("nextgen_sync", "NEXTGEN_JWT_SECRET no configurado en secrets — usando fallback inseguro solo para dev.")
        secret = "change_me_local_dev_only"
    
    # Generar UUIDs deterministas para el tenant y el usuario basados en sus nombres legacy
    tenant_hash = hashlib.sha256(empresa.encode("utf-8")).hexdigest()
    tenant_uuid = str(uuid.UUID(tenant_hash[:32]))
    
    user_login = st.session_state.get("u_actual", {}).get("usuario_login", "system")
    user_hash = hashlib.sha256(user_login.encode("utf-8")).hexdigest()
    user_uuid = str(uuid.UUID(user_hash[:32]))
    
    user_role = st.session_state.get("u_actual", {}).get("rol", "nurse")
    payload = {
        "sub": user_uuid,
        "tenant_id": tenant_uuid,
        "role": user_role,
        "type": "access"
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _extraer_dni(paciente_id: str) -> str:
    """Extrae DNI del formato 'Nombre Apellido - DNI'. Retorna '' si no es parseable."""
    if not paciente_id or " - " not in str(paciente_id):
        return ""
    partes = str(paciente_id).rsplit(" - ", 1)
    dni = partes[1].strip() if len(partes) == 2 else ""
    return dni if dni.isdigit() else ""


def _obtener_uuid_empresa(nombre_empresa: str) -> str:
    """Busca el UUID de la empresa en SQL. Maneja su propio caché a prueba de fallos temporales."""
    cache_key = f"_cache_uuid_empresa_{nombre_empresa}"

    # 1. Revisar si tenemos un caché válido (menos de 1 hora = 3600s)
    if cache_key in st.session_state:
        cached_data = st.session_state[cache_key]
        if time.monotonic() - cached_data["ts"] < 3600:
            return cached_data["uuid"]

    from core.database import supabase

    empresa_configurada = empresa_uuid_configurada(nombre_empresa)

    if not supabase:
        return empresa_configurada or None

    try:
        res = supabase.table("empresas").select("id").eq("nombre", nombre_empresa).limit(1).execute()
        if res.data:
            resultado = res.data[0]["id"]
            # 2. Guardar en caché SOLO si la consulta a la BD fue exitosa
            st.session_state[cache_key] = {"uuid": resultado, "ts": time.monotonic()}
            return resultado
    except Exception as e:
        log_event("db_error", f"Fallo al obtener UUID de empresa (no se guardará en caché): {e}")
        # Al no guardar en st.session_state, el sistema volverá a intentar en la próxima acción
    return empresa_configurada or None


def _obtener_uuid_paciente(dni: str, empresa_id: str) -> str:
    """Busca el UUID del paciente en SQL. Maneja su propio cache a prueba de fallos temporales."""
    cache_key = f"_cache_uuid_paciente_{dni}_{empresa_id}"

    # 1. Revisar cache valido (menos de 1 hora)
    if cache_key in st.session_state:
        cached_data = st.session_state[cache_key]
        if time.monotonic() - cached_data["ts"] < 3600:
            return cached_data["uuid"]

    from core.database import supabase
    if not supabase:
        return None

    try:
        res = supabase.table("pacientes").select("id").eq("dni", dni).eq("empresa_id", empresa_id).limit(1).execute()
        if res.data:
            resultado = res.data[0]["id"]
            # 2. Guardar en cache SOLO si la consulta fue exitosa
            st.session_state[cache_key] = {"uuid": resultado, "ts": time.monotonic()}
            return resultado
    except Exception as e:
        log_event("db_error", f"Fallo al obtener UUID de paciente (no se guardara en cache): {e}")

    return None


def sync_paciente_to_nextgen(nombre: str, dni: str, empresa: str) -> None:
    """
    DUAL-WRITE: Guarda el paciente tanto en la nueva BD SQL como en la API NextGen.
    """
    # 1. Guardar en la nueva base de datos PostgreSQL (Silencioso, no rompe la app si falla)
    try:
        empresa_id = _obtener_uuid_empresa(empresa)
        if empresa_id:
            datos_paciente = {
                "empresa_id": empresa_id,
                "nombre_completo": nombre.strip(),
                "dni": str(dni).strip(),
                "estado": "Activo"
            }
            upsert_paciente(datos_paciente)
            log_event("sql_sync", f"Paciente {dni} guardado en PostgreSQL.")
    except Exception as e:
        log_event("sql_sync", f"Error al guardar paciente {dni} en PostgreSQL: {e}")

    # 2. Guardar en la API NextGen (Código original)
    if not ENABLE_NEXTGEN_API_DUAL_WRITE:
        return

    payload = {
        "full_name": nombre.strip(),
        "document_number": str(dni).strip()
    }
    
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
    DUAL-WRITE: Guarda la evolución tanto en la nueva BD SQL como en la API NextGen.
    """
    # Resolver UUID real del paciente (consulta BD, no MD5)
    pac_uuid = None
    dni = _extraer_dni(paciente_id)
    empresa = st.session_state.get("u_actual", {}).get("empresa", "Clinica General")
    if dni:
        try:
            empresa_id = _obtener_uuid_empresa(empresa)
            if empresa_id:
                pac_uuid = _obtener_uuid_paciente(dni, empresa_id)
        except Exception as e:
            log_event("sql_sync", f"Error al resolver UUID de paciente {paciente_id}: {e}")

    # 1. Guardar en la nueva base de datos PostgreSQL
    if pac_uuid:
        try:
            datos_evolucion = {
                "paciente_id": pac_uuid,
                "nota": nota.strip(),
                "firma_medico": st.session_state.get("u_actual", {}).get("nombre", "Sistema"),
                "plantilla": "Libre"
            }
            insert_evolucion(datos_evolucion)
            log_event("sql_sync", f"Evolución guardada en PostgreSQL para {dni}.")
        except Exception as e:
            log_event("sql_sync", f"Error al guardar evolución en PostgreSQL: {e}")

    # 2. Guardar en la API NextGen
    if not ENABLE_NEXTGEN_API_DUAL_WRITE:
        return

    if not pac_uuid:
        log_event("nextgen_sync", f"No se pudo resolver UUID para {paciente_id}, omitiendo sync a NextGen API.")
        return

    payload = {
        "patient_id": pac_uuid,
        "notes": nota.strip()[:5000]
    }

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


def sync_receta_to_sql(paciente_id: str, medicamento: str, via: str, frecuencia: str, tipo: str, datos_completos: dict = None) -> None:
    """
    DUAL-WRITE: Guarda la indicación en la nueva BD SQL, incluyendo datos complejos en JSONB.
    """
    dni = _extraer_dni(paciente_id)
    if not dni:
        return
    try:
        empresa = st.session_state.get("u_actual", {}).get("empresa", "Clinica General")
        empresa_id = _obtener_uuid_empresa(empresa)
        if empresa_id:
            pac_uuid = _obtener_uuid_paciente(dni, empresa_id)
            if pac_uuid:
                datos_indicacion = {
                    "paciente_id": pac_uuid,
                    "tipo_indicacion": tipo,
                    "medicamento": medicamento,
                    "via_administracion": via,
                    "frecuencia": frecuencia,
                    "estado": "Activa",
                    "datos_extra": datos_completos or {}
                }
                insert_indicacion(datos_indicacion)
                log_event("sql_sync", f"Indicación guardada en PostgreSQL para {dni}.")
    except Exception as e:
        log_event("sql_sync", f"Error al guardar indicación en PostgreSQL: {e}")


def sync_administracion_to_sql(paciente_id: str, medicamento: str, horario: str, estado: str, motivo: str, datos_completos: dict = None) -> None:
    """
    DUAL-WRITE: Guarda el registro de administración (MAR) en la nueva BD SQL.
    """
    dni = _extraer_dni(paciente_id)
    if not dni:
        return
    try:
        empresa = st.session_state.get("u_actual", {}).get("empresa", "Clinica General")
        empresa_id = _obtener_uuid_empresa(empresa)
        if empresa_id:
            pac_uuid = _obtener_uuid_paciente(dni, empresa_id)
            if pac_uuid:
                datos_admin = {
                    "paciente_id": pac_uuid,
                    "horario_programado": horario,
                    "estado": estado,
                    "motivo_no_realizada": motivo,
                    "datos_extra": datos_completos or {}
                }
                insert_administracion(datos_admin)
                log_event("sql_sync", f"Administración guardada en PostgreSQL para {dni}.")
    except Exception as e:
        log_event("sql_sync", f"Error al guardar administración en PostgreSQL: {e}")
