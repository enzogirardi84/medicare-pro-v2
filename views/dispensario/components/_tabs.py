"""Todas las tabs del modulo APS. Extraidas de views/dispensario_aps.py"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import streamlit as st

from core.app_logging import log_event
from core.database import guardar_datos
from core.utils import puede_accion
from views._aps_pdf import FPDF_DISPONIBLE, generar_pdf_historial_paciente, generar_pdf_reporte_aps
from views.dispensario.components._helpers import (
    guardar_directo, header_paciente,
    input_paciente_volatil, calcular_edad, ya_entrego_mes,
    calcular_edad_gestacional, get_paciente_id_visual,
)


def tab_panel_diario(paciente_sel, user, centro_salud_id=None):
    """Panel diario con metricas y sala de espera."""
    st.subheader("Panel Diario APS")
    atenciones = st.session_state.get("atenciones_aps_db", [])
    entregas = st.session_state.get("entregas_aps_db", [])
    epi = st.session_state.get("epidemiologia_aps_db", [])
    turnos = st.session_state.get("turnos_aps_db", [])
    hoy_iso = date.today().isoformat()

    en_espera = [t for t in turnos if isinstance(t, dict) and t.get("estado") == "en_espera"]
    pacientes_hoy = len({a.get("paciente_id") for a in atenciones if isinstance(a, dict) and str(a.get("fecha_atencion", ""))[:10] == hoy_iso})
    medicacion_hoy = sum(1 for e in entregas if isinstance(e, dict) and str(e.get("fecha_entrega", ""))[:10] == hoy_iso)
    alertas_epi = sum(1 for ep in epi if isinstance(ep, dict) and ep.get("estado") in ("Pendiente", "En seguimiento"))

    col1, col2 = st.columns(2)
    col1.metric("Pacientes hoy", pacientes_hoy)
    col1.metric("Medicacion hoy", medicacion_hoy)
    col2.metric("Alertas epi.", alertas_epi)
    col2.metric("En sala de espera", len(en_espera))

    for t in en_espera:
        prio = t.get("prioridad", "Normal")
        color = "🔴" if prio == "Urgente" else "🟡" if prio == "Preferencial" else "🟢"
        with st.container(border=True):
            ca, cb, cc = st.columns([3, 2, 1])
            ca.write(f"{color} **{t.get('paciente_id', '-')}**\n{t.get('motivo', '-')}")
            cb.caption(f"Llegada: {str(t.get('hora_llegada', ''))[:16]}")
            if cc.button("Atender", key=f"atender_{t.get('id_turno', 'x')}"):
                t["estado"] = "atendido"
                guardar_directo()
                st.rerun()


def tab_pacientes_familia(paciente_sel, user, centro_salud_id):
    """Gestion de pacientes y nucleo familiar."""
    st.subheader("Pacientes y Nucleo Familiar")
    tab_buscar, tab_grupo = st.tabs(["Busqueda", "Gestion de Nucleo Familiar"])
    with tab_buscar:
        busqueda = st.text_input("Buscar por DNI o Nombre", key="aps_buscar_pac")
        from views.dispensario.components._helpers import buscar_pacientes_por_texto
        resultados = buscar_pacientes_por_texto(busqueda) if busqueda else []
        if resultados:
            for p in resultados[:20]:
                st.write(f"- {p.get('nombre', '?')} (DNI: {p.get('dni', '?')})")
    with tab_grupo:
        st.info("Gestion de grupos familiares - seccion en construccion.")


def tab_ficha_aps(paciente_sel, user, centro_salud_id):
    """Ficha de paciente con datos completos."""
    st.subheader("Ficha del Paciente")
    if not paciente_sel:
        return input_paciente_volatil(paciente_sel)
    header_paciente(paciente_sel, user)
    if st.button("Ver historial completo", width='stretch'):
        st.session_state["_aps_tab"] = "historial"
        st.rerun()


def tab_turnos(paciente_sel, user, centro_salud_id):
    """Gestion de turnos."""
    st.subheader("Turnos")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Registrar llegada (demanda espontanea)", use_container_width=True):
            if paciente_sel:
                pid = get_paciente_id_visual(paciente_sel)
                turnos_db = st.session_state.setdefault("turnos_aps_db", [])
                turnos_db.append({"id_turno": f"esp-{datetime.now().strftime('%Y%m%d%H%M%S')}", "paciente_id": pid,
                                  "tipo_turno": "Demanda espontanea", "estado": "en_espera",
                                  "hora_llegada": datetime.now().isoformat(), "prioridad": "Normal"})
                guardar_directo()
                st.rerun()
    with col2:
        if st.button("Programar turno", use_container_width=True):
            st.info("Formulario de programacion - proximamente.")


def tab_historial_aps(paciente_sel, user, centro_salud_id):
    """Historial del paciente en el dispensario."""
    st.subheader("Historial APS")
    if not paciente_sel:
        return st.info("Seleccione un paciente.")
    from datetime import date as dt_date
    fd = st.date_input("Desde", value=dt_date.today() - timedelta(days=30), key="aps_hist_desde")
    fh = st.date_input("Hasta", value=dt_date.today(), key="aps_hist_hasta")
    pid = get_paciente_id_visual(paciente_sel)
    todos = []
    for key in ["atenciones_aps_db", "entregas_aps_db", "epidemiologia_aps_db", "visitas_domiciliarias_aps_db"]:
        for r in st.session_state.get(key, []):
            if isinstance(r, dict) and r.get("paciente_id") == pid:
                todos.append(r)
    st.caption(f"{len(todos)} registros encontrados.")
    if todos and FPDF_DISPONIBLE:
        pdf = generar_pdf_historial_paciente(pid, todos, str(fd), str(fh), centro_salud_id)
        if pdf:
            st.download_button("Descargar PDF", pdf, f"historial_aps_{pid}.pdf", "application/pdf")


def tab_nueva_atencion(paciente_sel, user, centro_salud_id):
    """Registrar nueva atencion APS."""
    st.subheader("Nueva Atencion")
    pid, pdata = input_paciente_volatil(paciente_sel)
    if not pid:
        return
    motivo = st.text_area("Motivo de consulta", key="aps_atencion_motivo")
    if st.button("Guardar atencion", type="primary", use_container_width=True):
        st.session_state.setdefault("atenciones_aps_db", []).append({
            "paciente_id": pid, "motivo_consulta": motivo,
            "fecha_atencion": datetime.now().isoformat(), "created_at": datetime.now().isoformat(),
            "registrado_por": user.get("nombre", "Sistema"),
        })
        guardar_directo()
        st.rerun()


def tab_control_nino_embarazo(paciente_sel, user, centro_salud_id):
    """Control de nino sano y embarazo."""
    st.subheader("Control Ninez y Embarazo")
    if not paciente_sel:
        return input_paciente_volatil(paciente_sel)
    pid = get_paciente_id_visual(paciente_sel)
    tipo = st.selectbox("Tipo de control", ["Ninez", "Embarazo", "Puerperio"], key="aps_control_tipo")
    if tipo == "Embarazo":
        fum = st.date_input("Fecha de ultima menstruacion (FUM)", key="aps_fum")
        if fum:
            sg = calcular_edad_gestacional(fum.isoformat())
            if sg is not None:
                st.metric("Edad gestacional", f"{sg} semanas")
    if st.button("Guardar control", type="primary", use_container_width=True):
        st.session_state.setdefault("pediatria_aps_db", []).append({
            "paciente_id": pid, "tipo_control": tipo, "fecha_control": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
        })
        guardar_directo()
        st.rerun()


def tab_farmacia(paciente_sel, user, centro_salud_id):
    """Farmacia, leche e insumos."""
    st.subheader("Farmacia")
    if not paciente_sel:
        return input_paciente_volatil(paciente_sel)
    pid = get_paciente_id_visual(paciente_sel)
    entregas_db = st.session_state.setdefault("entregas_aps_db", [])
    medicamento = st.text_input("Medicamento / Insumo", key="aps_farma_med")
    cantidad = st.number_input("Cantidad", min_value=1, value=1, key="aps_farma_cant")
    if st.button("Registrar entrega", type="primary", use_container_width=True):
        if ya_entrego_mes(pid, "farmacia_aps", entregas_db):
            st.warning("Este paciente ya retiro medicacion este mes.")
        else:
            entregas_db.append({"paciente_id": pid, "tipo_entrega": "farmacia_aps", "medicamento": medicamento,
                                "cantidad": cantidad, "fecha_entrega": datetime.now().isoformat(),
                                "created_at": datetime.now().isoformat(), "centro_salud_id": centro_salud_id})
            guardar_directo()
            st.rerun()


def tab_trabajo_social(paciente_sel, user, centro_salud_id):
    """Registro de trabajo social."""
    st.subheader("Trabajo Social")
    pid, _ = input_paciente_volatil(paciente_sel)
    if not pid:
        return
    intervencion = st.text_area("Intervencion realizada", key="aps_ts_intervencion")
    if st.button("Guardar", type="primary", use_container_width=True):
        st.session_state.setdefault("trabajo_social_aps_db", []).append({
            "paciente_id": pid, "intervencion": intervencion,
            "fecha_registro": datetime.now().isoformat(), "created_at": datetime.now().isoformat(),
        })
        guardar_directo()
        st.rerun()


def tab_epidemiologia(paciente_sel, user, centro_salud_id):
    """Registro de epidemiologia."""
    st.subheader("Epidemiologia")
    pid, _ = input_paciente_volatil(paciente_sel)
    if not pid:
        return
    enf = st.text_area("Enfermedades / seguimiento", key="aps_epi_enf")
    if st.button("Guardar", type="primary", use_container_width=True):
        st.session_state.setdefault("epidemiologia_aps_db", []).append({
            "paciente_id": pid, "enfermedades_seguimiento": [enf],
            "fecha_registro": datetime.now().isoformat(), "created_at": datetime.now().isoformat(),
        })
        guardar_directo()
        st.rerun()


def tab_visitas(paciente_sel, user, centro_salud_id):
    """Registro de visitas domiciliarias."""
    st.subheader("Visitas Domiciliarias")
    pid, _ = input_paciente_volatil(paciente_sel)
    if not pid:
        return
    observaciones = st.text_area("Observaciones de la visita", key="aps_visita_obs")
    if st.button("Guardar visita", type="primary", use_container_width=True):
        st.session_state.setdefault("visitas_domiciliarias_aps_db", []).append({
            "paciente_id": pid, "observaciones": observaciones,
            "fecha_visita": datetime.now().isoformat(), "created_at": datetime.now().isoformat(),
        })
        guardar_directo()
        st.rerun()


def tab_reportes(paciente_sel, user, centro_salud_id):
    """Reportes APS."""
    st.subheader("Reportes APS")
    fd = st.date_input("Desde", value=date.today(), key="aps_rep_desde")
    fh = st.date_input("Hasta", value=date.today(), key="aps_rep_hasta")
    tipo_reporte = st.selectbox("Tipo de reporte", ["Atenciones", "Entregas", "Epidemiologia", "Visitas"], key="aps_rep_tipo")
    if st.button("Generar reporte", use_container_width=True):
        key_map = {"Atenciones": "atenciones_aps_db", "Entregas": "entregas_aps_db",
                   "Epidemiologia": "epidemiologia_aps_db", "Visitas": "visitas_domiciliarias_aps_db"}
        registros = [r for r in st.session_state.get(key_map[tipo_reporte], []) if isinstance(r, dict)]
        if registros and FPDF_DISPONIBLE:
            pdf = generar_pdf_reporte_aps(f"Reporte {tipo_reporte}", registros, f"{fd} a {fh}", centro_salud_id)
            if pdf:
                st.download_button("Descargar PDF", pdf, f"reporte_aps_{tipo_reporte}.pdf", "application/pdf")
