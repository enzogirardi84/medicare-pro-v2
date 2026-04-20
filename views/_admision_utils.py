"""Helpers de admisión de pacientes. Extraído de views/admision.py."""
from datetime import date, datetime

import streamlit as st

from core.app_logging import log_event
from core.utils import mapa_detalles_pacientes, obtener_pacientes_visibles, empresas_clinica_coinciden

NON_PATIENT_DB_KEYS = {
    "usuarios_db",
    "pacientes_db",
    "detalles_pacientes_db",
    "inventario_db",
    "nomenclador_db",
    "logs_db",
    "reportes_diarios_db",
    "profesionales_red_db",
    "solicitudes_servicios_db",
    "plantillas_whatsapp_db",
}


def _texto_unilinea(valor):
    return " ".join(str(valor or "").strip().split())


def _normalizar_dni(valor):
    return str(valor or "").strip().replace(".", "").replace(" ", "")


def _paciente_id(nombre, dni):
    return f"{_texto_unilinea(nombre)} - {_normalizar_dni(dni)}"


def _nombre_legible(paciente_id):
    partes = str(paciente_id or "").rsplit(" - ", 1)
    return partes[0].strip() if partes else ""


def _parsear_fecha_guardada(valor):
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(valor or "").strip(), formato).date()
        except Exception:
            continue
    return date(1990, 1, 1)


def _normalizar_campos_legajo(nombre, dni, empresa):
    return {
        "nombre": _texto_unilinea(nombre),
        "dni": _normalizar_dni(dni),
        "empresa": _texto_unilinea(empresa),
    }


def _dni_duplicado(dni, excluir_paciente=None):
    dni_limpio = _normalizar_dni(dni)
    for paciente_id, detalles in mapa_detalles_pacientes(st.session_state).items():
        if excluir_paciente and paciente_id == excluir_paciente:
            continue
        if _normalizar_dni(detalles.get("dni", "")) == dni_limpio:
            return True
    return False


def _listar_pacientes_gestion(mi_empresa, rol, busqueda="", incluir_altas=False, empresa_filtro=""):
    pacientes = []
    for paciente_id, _, dni, obra_social, estado, empresa in obtener_pacientes_visibles(
        st.session_state, mi_empresa, rol, incluir_altas=incluir_altas, busqueda=busqueda,
    ):
        if empresa_filtro and not empresas_clinica_coinciden(empresa, empresa_filtro):
            continue
        detalles = mapa_detalles_pacientes(st.session_state).get(paciente_id, {})
        pacientes.append({
            "id": paciente_id,
            "nombre": _nombre_legible(paciente_id),
            "dni": dni,
            "empresa": empresa,
            "obra_social": obra_social,
            "estado": estado,
            "telefono": detalles.get("telefono", ""),
            "direccion": detalles.get("direccion", ""),
        })
    return pacientes


def _existe_dni_en_legajos(dni, mi_empresa, rol, excluir_paciente=None):
    dni_norm = _normalizar_dni(dni)
    if not dni_norm:
        return False
    if _dni_duplicado(dni_norm, excluir_paciente=excluir_paciente):
        return True
    try:
        for item in _listar_pacientes_gestion(mi_empresa, rol, busqueda=dni_norm, incluir_altas=True):
            if excluir_paciente and item["id"] == excluir_paciente:
                continue
            if _normalizar_dni(item.get("dni", "")) == dni_norm:
                return True
    except Exception:
        return False
    return False


def _validar_legajo(nombre, dni, empresa, mi_empresa, rol, excluir_paciente=None):
    campos = _normalizar_campos_legajo(nombre, dni, empresa)
    if not campos["nombre"] or not campos["dni"]:
        return campos, "Nombre y DNI son obligatorios."
    if not campos["empresa"]:
        return campos, "La clinica / empresa es obligatoria."
    if _existe_dni_en_legajos(campos["dni"], mi_empresa, rol, excluir_paciente=excluir_paciente):
        return campos, "Ya existe otro paciente con ese DNI."
    return campos, ""


def _buscar_coincidencias_legajo(busqueda, mi_empresa, rol):
    consulta = _texto_unilinea(busqueda)
    if not consulta:
        return []
    coincidencias = {item["id"]: item for item in _listar_pacientes_gestion(mi_empresa, rol, busqueda=consulta, incluir_altas=True)}
    dni_norm = _normalizar_dni(consulta)
    if dni_norm and dni_norm != consulta:
        for item in _listar_pacientes_gestion(mi_empresa, rol, busqueda="", incluir_altas=True):
            if dni_norm and dni_norm in _normalizar_dni(item.get("dni", "")):
                coincidencias[item["id"]] = item
    return list(coincidencias.values())


def _sincronizar_alta_paciente_best_effort(nombre, dni, empresa):
    try:
        from core.nextgen_sync import sync_paciente_to_nextgen
        sync_paciente_to_nextgen(nombre, dni, empresa)
    except Exception as e:
        log_event("admision", f"alta_sync_error:{type(e).__name__}")


def _sincronizar_edicion_paciente_sql_best_effort(detalle_anterior, detalle_nuevo, nombre_nuevo):
    try:
        from core.db_sql import get_empresa_by_nombre, get_paciente_by_dni_empresa, update_paciente_by_id

        empresa_origen = _texto_unilinea(detalle_anterior.get("empresa", ""))
        empresa_destino = _texto_unilinea(detalle_nuevo.get("empresa", ""))
        dni_origen = _normalizar_dni(detalle_anterior.get("dni", ""))
        dni_destino = _normalizar_dni(detalle_nuevo.get("dni", ""))

        empresa_sql_origen = get_empresa_by_nombre(empresa_origen) if empresa_origen else None
        empresa_sql_destino = (
            get_empresa_by_nombre(empresa_destino)
            if empresa_destino and empresa_destino != empresa_origen
            else empresa_sql_origen
        )

        paciente_sql = None
        if empresa_sql_origen and dni_origen:
            paciente_sql = get_paciente_by_dni_empresa(empresa_sql_origen.get("id", ""), dni_origen)
        if paciente_sql is None and empresa_sql_destino and dni_destino:
            paciente_sql = get_paciente_by_dni_empresa(empresa_sql_destino.get("id", ""), dni_destino)
        if not paciente_sql:
            return False

        payload = {
            "nombre_completo": nombre_nuevo,
            "dni": dni_destino,
            "estado": detalle_nuevo.get("estado", "Activo"),
        }
        if empresa_sql_destino and empresa_sql_destino.get("id"):
            payload["empresa_id"] = empresa_sql_destino["id"]

        updated = update_paciente_by_id(paciente_sql.get("id", ""), payload)
        return updated is not None
    except Exception as e:
        log_event("admision", f"edit_sync_error:{type(e).__name__}")
        return False


def _sincronizar_eliminacion_paciente_sql_best_effort(detalle_paciente):
    try:
        from core.db_sql import delete_paciente_by_id, get_empresa_by_nombre, get_paciente_by_dni_empresa

        empresa_txt = _texto_unilinea(detalle_paciente.get("empresa", ""))
        dni_txt = _normalizar_dni(detalle_paciente.get("dni", ""))
        empresa_sql = get_empresa_by_nombre(empresa_txt) if empresa_txt else None
        if not empresa_sql or not dni_txt:
            return False
        paciente_sql = get_paciente_by_dni_empresa(empresa_sql.get("id", ""), dni_txt)
        if not paciente_sql:
            return False
        return delete_paciente_by_id(paciente_sql.get("id", ""))
    except Exception as e:
        log_event("admision", f"delete_sync_error:{type(e).__name__}")
        return False


def _iterar_tablas_paciente():
    for clave, registros in st.session_state.items():
        if not clave.endswith("_db") or clave in NON_PATIENT_DB_KEYS or not isinstance(registros, list):
            continue
        yield clave, registros


def _resumen_impacto_paciente(paciente_id):
    resumen = {}
    for clave, registros in _iterar_tablas_paciente():
        cantidad = sum(
            1 for registro in registros if isinstance(registro, dict) and registro.get("paciente") == paciente_id
        )
        if cantidad:
            resumen[clave] = cantidad
    return dict(sorted(resumen.items(), key=lambda item: (-item[1], item[0])))


def _renombrar_referencias_paciente(paciente_anterior, paciente_nuevo):
    total_actualizado = 0
    for _, registros in _iterar_tablas_paciente():
        for registro in registros:
            if isinstance(registro, dict) and registro.get("paciente") == paciente_anterior:
                registro["paciente"] = paciente_nuevo
                total_actualizado += 1
    if st.session_state.get("paciente_actual") == paciente_anterior:
        st.session_state["paciente_actual"] = paciente_nuevo
    for clave in [k for k in st.session_state if k.startswith("lazy_export_")]:
        st.session_state.pop(clave, None)
    return total_actualizado


def _eliminar_referencias_paciente(paciente_id):
    resumen = {}
    for clave, registros in list(_iterar_tablas_paciente()):
        nuevos_registros = []
        eliminados = 0
        for registro in registros:
            if isinstance(registro, dict) and registro.get("paciente") == paciente_id:
                eliminados += 1
                continue
            nuevos_registros.append(registro)
        if eliminados:
            st.session_state[clave] = nuevos_registros
            resumen[clave] = eliminados
    if st.session_state.get("paciente_actual") == paciente_id:
        st.session_state.pop("paciente_actual", None)
    for clave in [k for k in st.session_state if k.startswith("lazy_export_")]:
        st.session_state.pop(clave, None)
    return dict(sorted(resumen.items(), key=lambda item: (-item[1], item[0])))


def _dataframe_pacientes(registros):
    import pandas as pd
    filas = []
    for item in registros:
        filas.append({
            "Paciente": item["nombre"],
            "DNI": item["dni"],
            "Clinica": item["empresa"],
            "Obra social": item["obra_social"] or "S/D",
            "Estado": item["estado"],
            "Telefono": item["telefono"] or "S/D",
            "Direccion": item["direccion"] or "S/D",
        })
    return pd.DataFrame(filas)
