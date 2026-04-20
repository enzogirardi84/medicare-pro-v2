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


def mapa_detalles_pacientes(session_state) -> dict:
    m = session_state.get("detalles_pacientes_db")
    return m if isinstance(m, dict) else {}


def asegurar_detalles_pacientes_en_sesion(session_state) -> dict:
    m = session_state.get("detalles_pacientes_db")
    if not isinstance(m, dict):
        m = {}
        session_state["detalles_pacientes_db"] = m
    return m


def _clave_paciente_visible(paciente_id, dni, empresa):
    dni_txt = str(dni or "").strip()
    empresa_key = norm_empresa_key(empresa) or ""
    if dni_txt and empresa_key:
        return ("dni_empresa", dni_txt, empresa_key)
    return ("paciente_id", str(paciente_id or "").strip().lower())


def obtener_pacientes_visibles(session_state, mi_empresa, rol_actual, incluir_altas=False, busqueda=""):
    busqueda_norm = str(busqueda or "").strip().lower()

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
    except Exception as e:
        from core.app_logging import log_event
        log_event("utils", f"Error en lectura SQL de pacientes: {type(e).__name__}: {e}")

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
            searchable = f"{paciente} {etiqueta} {dni} {obra_social} {empresa} {estado}".lower()
            if busqueda_norm not in searchable:
                continue
        pacientes_visibles_map[_clave_paciente_visible(paciente, dni, empresa)] = (
            paciente, etiqueta, dni, obra_social, estado, empresa,
        )

    pacientes_visibles = list(pacientes_visibles_map.values())
    pacientes_visibles.sort(key=lambda item: (item[1].lower(), item[0].lower()))
    session_state[cache_key] = {"ts": ts, "data": pacientes_visibles}
    return pacientes_visibles


def obtener_alertas_clinicas(session_state, paciente_sel):
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


def obtener_profesionales_visibles(session_state, mi_empresa, rol_actual, roles_validos=None):
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
