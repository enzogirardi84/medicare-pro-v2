from __future__ import annotations

"""Funciones de pacientes visibles, alertas clínicas y profesionales.

Extraído de core/utils.py.
"""
from core.norm_empresa import norm_empresa_key
from core.utils_roles import (
    compactar_etiqueta_paciente,
    empresas_clinica_coinciden,
    normalizar_usuario_sistema,
    rol_ve_datos_todas_las_clinicas,
    _roles_usuario_para_filtrado,
    _texto_normalizado,
)

_PACIENTES_SQL_STATUS_KEY = "_mc_pacientes_sql_status"


def mapa_detalles_pacientes(session_state: dict) -> dict:
    m = session_state.get("detalles_pacientes_db")
    if not isinstance(m, dict):
        m = {}
        session_state["detalles_pacientes_db"] = m
    # Si esta vacio, intentar cargar desde SQL
    if not m:
        try:
            from core._db_sql_pacientes import get_pacientes_by_empresa
            from core.nextgen_sync import _obtener_uuid_empresa
            from core.utils_roles import _texto_normalizado
            empresa = session_state.get("u_actual", {}).get("empresa", "")
            if empresa:
                eid = _obtener_uuid_empresa(empresa)
                if eid:
                    pacs = get_pacientes_by_empresa(eid)
                    for p in pacs:
                        nombre = p.get("nombre_completo", p.get("nombre", ""))
                        dni = p.get("dni", "")
                        pid = f"{nombre} - {dni}" if nombre and dni else p.get("id", "")
                        m[pid] = {
                            "dni": dni,
                            "telefono": p.get("telefono", ""),
                            "obra_social": p.get("obra_social", ""),
                            "direccion": p.get("direccion", ""),
                            "estado": p.get("estado", "Activo"),
                            "empresa": empresa,
                            "alergias": p.get("alergias", ""),
                            "patologias": p.get("patologias", ""),
                            "fecha_nacimiento": p.get("fecha_nacimiento", ""),
                        }
        except Exception:
            pass
    return m


def asegurar_detalles_pacientes_en_sesion(session_state: dict) -> dict:
    m = session_state.get("detalles_pacientes_db")
    if not isinstance(m, dict):
        m = {}
        session_state["detalles_pacientes_db"] = m
    return m


def registrar_estado_pacientes_sql(
    session_state: dict,
    *,
    ok: bool,
    empresa: str,
    rows: int = 0,
    error: Exception | None = None,
) -> dict:
    """Deja un diagnostico breve de la lectura SQL de pacientes para la UI."""
    status = {
        "ok": bool(ok),
        "empresa": str(empresa or ""),
        "rows": int(rows or 0),
        "fallback": None if ok else "local",
    }
    if error is not None:
        status["error_type"] = type(error).__name__
        status["error"] = str(error)[:180]
    session_state[_PACIENTES_SQL_STATUS_KEY] = status
    return status


def estado_pacientes_sql(session_state: dict) -> dict:
    status = session_state.get(_PACIENTES_SQL_STATUS_KEY)
    return status if isinstance(status, dict) else {}


_PACIENTE_UI_KEYS_LIMPIAR = frozenset(
    {
        "fecha_vits",
        "hora_vits",
        "conf_borrar_vital",
        "fecha_bal",
        "hora_bal",
        "conf_del_balance",
        "uploader_estudio",
        "mostrar_cam_estudio_form",
        "activar_cam_estudio_form",
        "camara_estudio",
        "conf_del_ultimo_estudio",
        "selector_borrar_estudio",
        "conf_borrar_estudio",
        "tipo_indicacion_receta",
        "hora_inicio_receta",
        "solucion_receta",
        "volumen_receta",
        "dias_infusion_receta",
        "velocidad_receta",
        "hora_inicio_infusion_receta",
        "detalle_infusion_receta",
        "metodo_firma_receta",
        "firma_upload_receta",
        "firma_receta_activa",
        "motivo_cambio_receta",
        "tipo_indicacion_papel_receta",
        "medico_papel_nombre",
        "medico_papel_matricula",
        "dias_papel_receta",
        "hora_papel_receta",
        "detalle_papel_receta",
        "horarios_papel_receta",
        "solucion_papel_receta",
        "volumen_papel_receta",
        "velocidad_papel_receta",
        "detalle_papel_infusion_receta",
        "adjunto_papel_receta",
    }
)

_PACIENTE_UI_PREFIXES_LIMPIAR = (
    "matriz_mar_editor_",
    "motivo_no_realizada_mar_",
    "recetas_editar_sel_",
    "cortina_rapida_",
    "cortina_tabla_editor_",
    "cf_del_est_",
    "del_est_",
    "pdf_est_",
    "mar_ok_",
    "mar_no_",
)


def limpiar_estado_ui_paciente(session_state: dict) -> list[str]:
    """Limpia estado efimero de formularios que no debe cruzar entre pacientes."""
    removidas: list[str] = []
    for clave in list(session_state.keys()):
        clave_txt = str(clave)
        if clave_txt in _PACIENTE_UI_KEYS_LIMPIAR or clave_txt.startswith(_PACIENTE_UI_PREFIXES_LIMPIAR):
            session_state.pop(clave, None)
            removidas.append(clave_txt)
    return removidas


def set_paciente_actual(session_state: dict, paciente_id: str | None) -> bool:
    """Actualiza el paciente activo y deja trazabilidad del cambio en la UI."""
    paciente_nuevo = str(paciente_id or "").strip()
    if not paciente_nuevo:
        return False

    paciente_actual = session_state.get("paciente_actual")
    if paciente_actual == paciente_nuevo:
        return False

    if paciente_actual:
        session_state["paciente_anterior"] = paciente_actual
    claves_limpiadas = limpiar_estado_ui_paciente(session_state)
    session_state["paciente_actual"] = paciente_nuevo
    session_state["_mc_paciente_cambio"] = {
        "anterior": paciente_actual,
        "actual": paciente_nuevo,
        "ui_limpiada": claves_limpiadas,
    }
    return True


def _clave_paciente_visible(paciente_id: str, dni: str, empresa: str) -> tuple:
    dni_txt = str(dni or "").strip()
    empresa_key = norm_empresa_key(empresa) or ""
    if dni_txt and empresa_key:
        return ("dni_empresa", dni_txt, empresa_key)
    return ("paciente_id", str(paciente_id or "").strip().lower())


def obtener_pacientes_visibles(
    session_state: dict,
    mi_empresa: str,
    rol_actual: str,
    incluir_altas: bool = False,
    busqueda: str = "",
) -> list[tuple]:
    busqueda_norm = _texto_normalizado(busqueda)

    from core.db_sql import get_pacientes_by_empresa
    from core.nextgen_sync import _obtener_uuid_empresa

    pacientes_sql = []
    try:
        empresa_id = _obtener_uuid_empresa(mi_empresa)
        if empresa_id:
            pacs_sql = get_pacientes_by_empresa(empresa_id, busqueda_norm, incluir_altas)
            for p in pacs_sql:
                nombre = p.get("nombre_completo", "")
                dni = p.get("dni", "")
                estado = p.get("estado", "Activo")
                obra_social = p.get("obra_social", "")
                paciente_id_visual = f"{nombre} - {dni}"
                etiqueta = compactar_etiqueta_paciente(paciente_id_visual, estado)
                pacientes_sql.append((paciente_id_visual, etiqueta, dni, obra_social, estado, mi_empresa))
            registrar_estado_pacientes_sql(session_state, ok=True, empresa=mi_empresa, rows=len(pacientes_sql))
        else:
            registrar_estado_pacientes_sql(session_state, ok=False, empresa=mi_empresa, rows=0)
    except Exception as e:
        from core.app_logging import log_event
        log_event("utils", f"Error en lectura SQL de pacientes: {type(e).__name__}: {e}")
        registrar_estado_pacientes_sql(session_state, ok=False, empresa=mi_empresa, rows=0, error=e)

    ts = session_state.get("_ultimo_guardado_ts", 0)
    cache_key = f"_mc_cache_pac_vis_{mi_empresa}_{rol_actual}_{incluir_altas}_{busqueda_norm}"
    cached = session_state.get(cache_key)
    if cached and cached.get("ts") == ts:
        return cached["data"]

    hay_busqueda = bool(busqueda_norm)
    detalles_db = mapa_detalles_pacientes(session_state)
    pacientes_visibles_map = {_clave_paciente_visible(item[0], item[2], item[5]): item for item in pacientes_sql}

    for paciente in session_state.get("pacientes_db", []):
        detalles = detalles_db.get(paciente, {})
        if not isinstance(detalles, dict):
            detalles = {}
        if not rol_ve_datos_todas_las_clinicas(rol_actual):
            if not empresas_clinica_coinciden(detalles.get("empresa", ""), mi_empresa):
                continue
        estado = detalles.get("estado", "Activo")
        if estado != "Activo" and not incluir_altas:
            continue
        dni = str(detalles.get("dni", "") or "")
        obra_social = str(detalles.get("obra_social", "") or "")
        empresa = str(detalles.get("empresa", "") or "")
        etiqueta = compactar_etiqueta_paciente(paciente, estado)
        if hay_busqueda:
            searchable = _texto_normalizado(f"{paciente} {etiqueta} {dni} {obra_social} {empresa} {estado}")
            if busqueda_norm not in searchable:
                continue
        pacientes_visibles_map[_clave_paciente_visible(paciente, dni, empresa)] = (
            paciente, etiqueta, dni, obra_social, estado, empresa,
        )

    pacientes_visibles = list(pacientes_visibles_map.values())
    pacientes_visibles.sort(key=lambda item: (item[1].lower(), item[0].lower()))
    session_state[cache_key] = {"ts": ts, "data": pacientes_visibles}
    return pacientes_visibles


def obtener_alertas_clinicas(session_state: dict, paciente_sel: str) -> list[dict]:
    if not paciente_sel:
        return []

    ts = session_state.get("_ultimo_guardado_ts", 0)
    cache_key = f"_mc_cache_alertas_{paciente_sel}"
    cached = session_state.get(cache_key)
    if cached and cached.get("ts") == ts:
        return cached["data"]

    detalles = mapa_detalles_pacientes(session_state).get(paciente_sel, {})
    alertas = []

    alergias = str(detalles.get("alergias", "") or "").strip()
    if alergias:
        alertas.append({"nivel": "critica", "titulo": "Alergias registradas", "detalle": alergias})

    patologias = str(detalles.get("patologias", "") or "").strip()
    if patologias:
        alertas.append({"nivel": "media", "titulo": "Patologias y riesgos", "detalle": patologias})

    consentimientos = session_state.get("consentimientos_db", [])
    cons_cache_key = f"_mc_cache_cons_{paciente_sel}"
    cons_cached = session_state.get(cons_cache_key)
    if cons_cached and cons_cached.get("id") == id(consentimientos) and cons_cached.get("len") == len(consentimientos):
        tiene_consentimiento = cons_cached["tiene"]
    else:
        tiene_consentimiento = any(x.get("paciente") == paciente_sel for x in consentimientos)
        session_state[cons_cache_key] = {"id": id(consentimientos), "len": len(consentimientos), "tiene": tiene_consentimiento}

    if not tiene_consentimiento:
        alertas.append({"nivel": "alta", "titulo": "Consentimiento legal pendiente", "detalle": "Todavia no hay un consentimiento domiciliario firmado para este paciente."})

    vitales = session_state.get("vitales_db", [])
    vit_cache_key = f"_mc_cache_vit_ult_{paciente_sel}"
    vit_cached = session_state.get(vit_cache_key)
    if vit_cached and vit_cached.get("id") == id(vitales) and vit_cached.get("len") == len(vitales):
        ultimo_vital = vit_cached["ultimo"]
    else:
        ultimo_vital = None
        for x in reversed(vitales):
            if x.get("paciente") == paciente_sel:
                ultimo_vital = x
                break
        session_state[vit_cache_key] = {"id": id(vitales), "len": len(vitales), "ultimo": ultimo_vital}

    if ultimo_vital:
        def _to_float(v):
            try:
                return None if v in ("", None) else float(v)
            except Exception:
                return None

        sat = _to_float(ultimo_vital.get("Sat"))
        temp = _to_float(ultimo_vital.get("Temp"))
        fc = _to_float(ultimo_vital.get("FC"))
        if sat is not None and sat < 92:
            alertas.append({"nivel": "critica", "titulo": "Desaturacion reciente", "detalle": f"Ultimo SatO2 registrado: {sat:.0f}% | {ultimo_vital.get('fecha', 'S/D')}"})
        if temp is not None and temp >= 38:
            alertas.append({"nivel": "alta", "titulo": "Fiebre registrada", "detalle": f"Ultima temperatura: {temp:.1f} C | {ultimo_vital.get('fecha', 'S/D')}"})
        if fc is not None and (fc > 110 or fc < 50):
            alertas.append({"nivel": "alta", "titulo": "Frecuencia cardiaca fuera de rango", "detalle": f"Ultima FC: {fc:.0f} lpm | {ultimo_vital.get('fecha', 'S/D')}"})

    for indicacion in reversed(session_state.get("indicaciones_db", [])):
        if indicacion.get("paciente") != paciente_sel:
            continue
        estado = str(indicacion.get("estado_receta") or indicacion.get("estado_clinico") or "Activa").strip()
        if estado in {"Suspendida", "Modificada"}:
            fecha_estado = indicacion.get("fecha_estado") or indicacion.get("fecha_suspension") or indicacion.get("fecha", "")
            alertas.append({
                "nivel": "alta" if estado == "Suspendida" else "media",
                "titulo": f"Medicacion {estado.lower()}",
                "detalle": (
                    f"{indicacion.get('med', 'Sin detalle')} | {fecha_estado} | "
                    f"{indicacion.get('profesional_estado', indicacion.get('medico_nombre', 'Sin profesional'))}"
                ),
            })
            if len(alertas) >= 5:
                break

    alertas_result = alertas[:5]
    session_state[cache_key] = {"ts": ts, "data": alertas_result}
    return alertas_result


def obtener_profesionales_visibles(
    session_state: dict,
    mi_empresa: str,
    rol_actual: str,
    roles_validos: list[str] | None = None,
) -> list[dict]:
    roles_validos_normalizados = (
        {str(rol).strip().lower() for rol in roles_validos if rol} if roles_validos else None
    )
    visibles = []
    for username, data in session_state.get("usuarios_db", {}).items():
        if not isinstance(data, dict):
            continue
        data_normalizada = normalizar_usuario_sistema(data)
        roles_usuario = _roles_usuario_para_filtrado(data_normalizada)
        if roles_validos_normalizados and not roles_usuario.intersection(roles_validos_normalizados):
            continue
        if not rol_ve_datos_todas_las_clinicas(rol_actual):
            if not empresas_clinica_coinciden(data_normalizada.get("empresa", ""), mi_empresa):
                continue
        visibles.append({"username": username, **data_normalizada})
    visibles.sort(key=lambda x: (str(x.get("nombre", "")).lower(), str(x.get("username", "")).lower()))
    return visibles
