import streamlit as st

from core.app_logging import log_event
from core.db_sql import get_emergencias_by_paciente
from core.nextgen_sync import _obtener_uuid_paciente, _obtener_uuid_empresa
from core.utils import ahora, mapa_detalles_pacientes
from core.view_helpers import aviso_sin_paciente
from views._emergencias_tabs import (
    _render_tab_registrar,
    _render_tab_panel,
    _render_tab_historial,
)


def render_emergencias(paciente_sel, mi_empresa, user):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    from core.ui_liviano import headers_sugieren_equipo_liviano

    es_movil = headers_sugieren_equipo_liviano() or st.session_state.get("mc_liviano_modo") == "on"

    detalles = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})
    
    # 1. Intentar leer desde PostgreSQL (Hybrid Read)
    eventos = []
    try:
        _partes_em = paciente_sel.split(" - ")
        _dni_em = _partes_em[1].strip() if len(_partes_em) > 1 else ""
        _emp_em = _obtener_uuid_empresa(mi_empresa)
        paciente_uuid = _obtener_uuid_paciente(_dni_em, _emp_em) if _dni_em and _emp_em else None
        if paciente_uuid:
            emergencias_sql = get_emergencias_by_paciente(paciente_uuid)
            if emergencias_sql:
                for e in emergencias_sql:
                    dt = pd.to_datetime(e.get("fecha_llamado", ""), errors="coerce")
                    # Mapear de SQL a formato legacy para la UI
                    eventos.append({
                        "paciente": paciente_sel,
                        "empresa": mi_empresa,
                        "fecha_evento": dt.strftime("%d/%m/%Y") if pd.notnull(dt) else "",
                        "hora_evento": dt.strftime("%H:%M") if pd.notnull(dt) else "",
                        "motivo": e.get("motivo", ""),
                        "prioridad": e.get("prioridad", ""),
                        "estado": e.get("estado", ""),
                        "resolucion": e.get("resolucion", ""),
                        "recursos_asignados": e.get("recursos_asignados", ""),
                        "profesional": e.get("usuarios", {}).get("nombre", "Desconocido") if isinstance(e.get("usuarios"), dict) else "Desconocido",
                        # Campos legacy que quizas no esten en SQL pero la UI espera
                        "triage_grado": "Grado 1 - Rojo" if e.get("prioridad") == "Critica" else "Grado 2 - Amarillo" if e.get("prioridad") == "Alta" else "Grado 3 - Verde",
                        "ambulancia_solicitada": "movil" in e.get("recursos_asignados", "").lower() or "ambulancia" in e.get("recursos_asignados", "").lower(),
                        "categoria_evento": "General",
                        "tipo_evento": "Evento",
                        "tipo_traslado": "Sin traslado confirmado",
                        "destino": "",
                        "matricula": "",
                    })
    except Exception as e:
        log_event("error_leer_emergencias_sql", str(e))

    # 2. Fallback a JSON si SQL falla o esta vacio
    if not eventos:
        eventos = [x for x in st.session_state.get("emergencias_db", []) if x.get("paciente") == paciente_sel]
        
    activos = [x for x in eventos if x.get("triage_grado") in {"Grado 1 - Rojo", "Grado 2 - Amarillo"}]
    traslados = [x for x in eventos if x.get("ambulancia_solicitada")]

    if es_movil:
        m1, m2 = st.columns(2)
        m3, m4 = st.columns(2)
    else:
        m1, m2, m3, m4 = st.columns(4)
    m1.metric("Eventos", len(eventos))
    m2.metric("Criticos activos", len(activos))
    m3.metric("Traslados", len(traslados))
    m4.metric("Ultimo", eventos[-1]["fecha_evento"] if eventos else "—")

    tab_reg, tab_panel, tab_hist = st.tabs(["⚡ Registrar evento", "📋 Panel operativo", "📄 Historial y PDF"])

    with tab_reg:
        _render_tab_registrar(paciente_sel, mi_empresa, user, detalles, es_movil)

    with tab_panel:
        _render_tab_panel(paciente_sel, detalles, eventos, es_movil)

    with tab_hist:
        _render_tab_historial(paciente_sel, mi_empresa, eventos, es_movil)
