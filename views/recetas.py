from datetime import datetime as _dt, timedelta as _td

from core.alert_toasts import queue_toast
import time as _time

import streamlit as st

from core.anticolapso import anticolapso_activo
from core.database import guardar_datos
from core.utils import (
    ahora,
    cargar_json_asset,
    puede_accion,
)
from views._recetas_utils import (
    FPDF_DISPONIBLE,
    CANVAS_DISPONIBLE,
    nombre_usuario as _nombre_usuario,
)
from views._recetas_mar import (
    render_cortina_mar_hospitalaria as _render_cortina_mar_hospitalaria,
    render_marco_clinico_cortina as _render_marco_clinico_cortina,
)
from views._recetas_indicaciones import (
    resumen_medicacion_activa as _resumen_medicacion_activa,
)
from views._recetas_prescripcion import (
    render_nueva_prescripcion as _render_nueva_prescripcion,
    render_indicacion_papel as _render_indicacion_papel,
)
from views._recetas_turno import (
    render_administracion_turno as _render_administracion_turno,
    render_historial_prescripciones as _render_historial_prescripciones,
)

_RECETAS_SQL_STATUS_KEY = "_mc_recetas_sql_status"


def registrar_estado_recetas_sql(
    session_state: dict,
    *,
    ok: bool,
    paciente: str,
    indicaciones: int = 0,
    administraciones: int = 0,
    error: Exception | None = None,
) -> dict:
    """Deja un diagnostico breve de la lectura SQL de recetas/MAR para la UI."""
    status = {
        "ok": bool(ok),
        "paciente": str(paciente or ""),
        "indicaciones": int(indicaciones or 0),
        "administraciones": int(administraciones or 0),
        "fallback": None if ok else "local",
    }
    if error is not None:
        status["error_type"] = type(error).__name__
        status["error"] = str(error)[:180]
    session_state[_RECETAS_SQL_STATUS_KEY] = status
    return status


def estado_recetas_sql(session_state: dict) -> dict:
    status = session_state.get(_RECETAS_SQL_STATUS_KEY)
    return status if isinstance(status, dict) else {}


def render_recetas(paciente_sel, mi_empresa, user, rol=None):
    if not paciente_sel:
        st.info("Selecciona un paciente en el menu lateral.")
        return

    from core.ui_liviano import headers_sugieren_equipo_liviano

    es_movil = headers_sugieren_equipo_liviano() or st.session_state.get("mc_liviano_modo") == "on"
    rol = rol or user.get("rol", "")
    nombre_usuario = _nombre_usuario(user)
    puede_prescribir = puede_accion(rol, "recetas_prescribir")
    puede_cargar_papel = puede_accion(rol, "recetas_cargar_papel")
    puede_registrar_dosis = puede_accion(rol, "recetas_registrar_dosis")
    puede_cambiar_estado = puede_accion(rol, "recetas_cambiar_estado")

    st.markdown("## Recetas y administración")
    st.caption(f"Profesional en sesión: **{nombre_usuario}**")

    _resumen_medicacion_activa(paciente_sel, mi_empresa)

    try:
        vademecum_base = cargar_json_asset("vademecum.json")
    except Exception:
        vademecum_base = ["Medicamento 1", "Medicamento 2"]

    if puede_prescribir:
        _render_nueva_prescripcion(paciente_sel, mi_empresa, user, rol, nombre_usuario, es_movil, vademecum_base)

    if puede_cargar_papel:
        _render_indicacion_papel(paciente_sel, mi_empresa, user, rol, nombre_usuario, es_movil)

    st.divider()

    # --- LECTURA DESDE POSTGRESQL (con fallback a session_state) ---
    from core.nextgen_sync import _obtener_uuid_paciente, _obtener_uuid_empresa

    recs_todas = []
    admin_hoy = []
    fecha_hoy = ahora().strftime("%d/%m/%Y")
    uso_sql_recetas = False
    _RECETAS_SQL_TTL = 30

    try:
        partes = paciente_sel.split(" - ")
        if len(partes) > 1:
            dni = partes[1].strip()
            empresa = st.session_state.get("u_actual", {}).get("empresa", "Clinica General")
            empresa_id = _obtener_uuid_empresa(empresa)
            if empresa_id:
                pac_uuid = _obtener_uuid_paciente(dni, empresa_id)
                if pac_uuid:
                    _ck = f"_rx_sql_{pac_uuid}"
                    if st.session_state.pop("_rx_sql_invalidar", False):
                        st.session_state.pop(_ck, None)
                    _cached = st.session_state.get(_ck, {})
                    _cache_age = _time.monotonic() - _cached.get("ts", 0)
                    if _cache_age < _RECETAS_SQL_TTL and _cached.get("fecha") == fecha_hoy:
                        inds_sql = _cached["inds"]
                        adms_sql = _cached["adms"]
                    else:
                        from core.database import supabase
                        if supabase is None:
                            raise RuntimeError("Supabase no inicializado")
                        fecha_hoy_iso = ahora().strftime("%Y-%m-%d")
                        res_ind = supabase.table("indicaciones").select("*").eq("paciente_id", pac_uuid).order("fecha_indicacion", desc=True).execute()
                        inds_sql = res_ind.data if res_ind and res_ind.data else []
                        res_adm = supabase.table("administracion_med").select("*").eq("paciente_id", pac_uuid).gte("fecha_registro", f"{fecha_hoy_iso}T00:00:00").lte("fecha_registro", f"{fecha_hoy_iso}T23:59:59").execute()
                        adms_sql = res_adm.data if res_adm and res_adm.data else []
                        st.session_state[_ck] = {"ts": _time.monotonic(), "fecha": fecha_hoy, "inds": inds_sql, "adms": adms_sql}
                    uso_sql_recetas = True
                    registrar_estado_recetas_sql(
                        st.session_state,
                        ok=True,
                        paciente=paciente_sel,
                        indicaciones=len(inds_sql),
                        administraciones=len(adms_sql),
                    )
                    for ind in inds_sql:
                        extra = ind.get("datos_extra", {}) or {}
                        recs_todas.append({
                            "_sql_id": ind.get("id", ""),
                            "paciente": paciente_sel,
                            "med": ind.get("medicamento", ""),
                            "fecha": ind.get("fecha_indicacion", "")[:16].replace("T", " ") if ind.get("fecha_indicacion") else "",
                            "estado_receta": ind.get("estado", "Activa"),
                            "estado_clinico": ind.get("estado", "Activa"),
                            "via": ind.get("via_administracion", ""),
                            "frecuencia": ind.get("frecuencia", ""),
                            "tipo_indicacion": ind.get("tipo_indicacion", ""),
                            "dias_duracion": extra.get("dias_duracion", 7),
                            "medico_nombre": extra.get("medico_nombre", ""),
                            "medico_matricula": extra.get("medico_matricula", ""),
                            "firma_b64": extra.get("firma_b64", ""),
                            "hora_inicio": extra.get("hora_inicio", ""),
                            "horarios_programados": extra.get("horarios_programados", []),
                            "solucion": extra.get("solucion", ""),
                            "volumen_ml": extra.get("volumen_ml", 0),
                            "velocidad_ml_h": extra.get("velocidad_ml_h", None),
                            "alternar_con": extra.get("alternar_con", ""),
                            "detalle_infusion": extra.get("detalle_infusion", ""),
                            "plan_hidratacion": extra.get("plan_hidratacion", []),
                        })
                    for adm in adms_sql:
                        extra = adm.get("datos_extra", {}) or {}
                        admin_hoy.append({
                            "paciente": paciente_sel, "fecha": fecha_hoy,
                            "med": extra.get("medicamento", ""),
                            "horario_programado": adm.get("horario_programado", ""),
                            "hora": extra.get("hora_real_administracion", adm.get("hora_real_administracion", "")),
                            "estado": adm.get("estado", ""),
                            "motivo": adm.get("motivo_no_realizada", ""),
                            "firma": extra.get("firma", ""),
                            "matricula_profesional": extra.get("matricula_profesional", ""),
                            "usuario_login": extra.get("usuario_login", ""),
                        })
                else:
                    registrar_estado_recetas_sql(st.session_state, ok=False, paciente=paciente_sel)
            else:
                registrar_estado_recetas_sql(st.session_state, ok=False, paciente=paciente_sel)
        else:
            registrar_estado_recetas_sql(st.session_state, ok=False, paciente=paciente_sel)
    except Exception as e:
        from core.app_logging import log_event
        log_event("recetas_sql", f"error_lectura:{type(e).__name__}")
        registrar_estado_recetas_sql(st.session_state, ok=False, paciente=paciente_sel, error=e)

    if not uso_sql_recetas:
        recs_todas = [r for r in st.session_state.get("indicaciones_db", []) if r.get("paciente") == paciente_sel]
        admin_hoy = [
            a for a in st.session_state.get("administracion_med_db", [])
            if a.get("paciente") == paciente_sel and a.get("fecha") == fecha_hoy
        ]
        sql_status = estado_recetas_sql(st.session_state)
        if sql_status and not sql_status.get("ok"):
            st.caption("Modo local/cache activo para recetas y administracion. La lectura SQL no respondio en esta vista.")

    # --- Auto-marcar como Completada las indicaciones cuyo ciclo vencio ---
    _hoy = _dt.now().date()
    for r in recs_todas:
        if r.get("estado_receta", "Activa") != "Activa":
            continue
        try:
            _dur = int(r.get("dias_duracion", 0) or 0)
            if _dur <= 0:
                continue
            _fecha_str = str(r.get("fecha", ""))[:10]
            _inicio = _dt.strptime(_fecha_str, "%d/%m/%Y").date() if "/" in _fecha_str else _dt.fromisoformat(_fecha_str).date()
            if (_inicio + _td(days=_dur)) < _hoy:
                r["estado_receta"] = "Completada"
                r["estado_clinico"] = "Completada"
                _sql_id = r.get("_sql_id", "")
                if _sql_id:
                    try:
                        from core._db_sql_clinico import update_estado_indicacion
                        update_estado_indicacion(_sql_id, "Completada")
                    except Exception:
                        pass
        except Exception:
            pass

    recs_activas = [r for r in recs_todas if r.get("estado_receta", "Activa") == "Activa"]

    if recs_activas:
        _render_administracion_turno(
            paciente_sel, mi_empresa, user, nombre_usuario, es_movil,
            recs_activas, admin_hoy, fecha_hoy, puede_registrar_dosis, puede_cambiar_estado,
        )
    else:
        st.markdown(
            """
            <div class="mc-rx-callout-care" style="border-color:rgba(148,163,184,0.2);background:linear-gradient(90deg,rgba(30,41,59,0.5),rgba(15,23,42,0.4));">
                <span class="mc-rx-callout-ico" aria-hidden="true">📋</span>
                <p>
                    <strong>Sin indicaciones activas</strong> para este paciente. Cuando el médico prescriba o cargues una orden en papel,
                    aparecerá aquí la administración del turno con el mismo estándar de trazabilidad.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    _render_historial_prescripciones(paciente_sel, mi_empresa, user, es_movil, recs_todas)
