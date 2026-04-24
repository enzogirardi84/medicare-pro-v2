import base64
import io
from html import escape

import pandas as pd
import streamlit as st

from core.export_utils import dataframe_csv_bytes, pdf_output_bytes, safe_text, sanitize_filename_component
from core.view_helpers import bloque_mc_grid_tarjetas, lista_plegable
from core.utils import ahora, mostrar_dataframe_con_scroll

FPDF_DISPONIBLE = False
try:
    from fpdf import FPDF
    FPDF_DISPONIBLE = True
except ImportError:
    pass  # Intencional: fpdf es opcional para PDFs


def _texto_busqueda_log(reg):
    return " | ".join(
        [
            str(reg.get("usuario", reg.get("U", "")) or ""),
            str(reg.get("accion", reg.get("A", "")) or ""),
            str(reg.get("detalle", reg.get("D", "")) or ""),
            str(reg.get("fecha", reg.get("F", "")) or ""),
            str(reg.get("hora", reg.get("H", "")) or ""),
        ]
    ).lower()


def render_auditoria(mi_empresa, user):
    emp_e = escape(str(mi_empresa or ""))
    st.markdown(
        f"""
        <div class="mc-hero">
            <h2 class="mc-hero-title">Auditoria de movimientos</h2>
            <p class="mc-hero-text">Logs del sistema y asistencia por profesional para {emp_e}. Filtros por fecha, usuario y texto; descarga CSV cuando haga falta.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Logs</span>
                <span class="mc-chip">Asistencia</span>
                <span class="mc-chip">Exportacion</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ("Logs", "Accesos y acciones del sistema con filtro por fecha y usuario."),
            ("Asistencia", "Fichadas del check-in por profesional y periodo."),
            ("CSV / PDF", "Descarga de logs en CSV; PDF opcional en asistencia."),
        ]
    )
    st.info("Consulta completa de movimientos del sistema. Visible para SuperAdmin, Coordinador y perfiles con acceso de gestion.")
    st.caption(
        "Elegi la seccion abajo: **Logs** son eventos de login y uso; **Asistencia** cruza profesional con fichadas de **Visitas**."
    )

    seccion = st.radio("Seccion", ["Logs del sistema", "Asistencia por profesional"], horizontal=False, label_visibility="collapsed")

    if seccion == "Logs del sistema":
        # 1. Intentar leer de PostgreSQL (Hybrid Read)
        logs_empresa = []
        try:
            from core.db_sql import get_auditoria_by_empresa
            from core.nextgen_sync import _obtener_uuid_empresa
            
            empresa_uuid = _obtener_uuid_empresa(mi_empresa)
            if empresa_uuid:
                logs_sql = get_auditoria_by_empresa(empresa_uuid, limit=1000)
                if logs_sql:
                    for log in logs_sql:
                        dt = pd.to_datetime(log.get("fecha_evento", ""), errors="coerce")
                        logs_empresa.append({
                            "fecha": dt.strftime("%d/%m/%Y %H:%M:%S") if pd.notnull(dt) else "",
                            "modulo": log.get("modulo", ""),
                            "usuario": log.get("usuarios", {}).get("nombre", "Desconocido") if isinstance(log.get("usuarios"), dict) else "Desconocido",
                            "paciente": log.get("pacientes", {}).get("nombre_completo", "N/A") if isinstance(log.get("pacientes"), dict) else "N/A",
                            "accion": log.get("accion", ""),
                            "detalle": log.get("detalle", "")
                        })
        except Exception as e:
            from core.app_logging import log_event
            log_event("error_leer_auditoria_sql", str(e))

        # 2. Fallback a JSON si SQL falla o esta vacio
        if not logs_empresa:
            logs = st.session_state.get("auditoria_legal_db", [])
            for r in reversed(logs):
                if r.get("empresa") == mi_empresa or r.get("empresa") == "":
                    logs_empresa.append({
                        "fecha": r.get("fecha", ""),
                        "modulo": r.get("modulo", ""),
                        "usuario": r.get("actor", r.get("profesional", "")),
                        "paciente": r.get("paciente", "N/A"),
                        "accion": r.get("accion", ""),
                        "detalle": r.get("detalle", "")
                    })

        if not logs_empresa:
            st.warning(
                "Todavia no hay registros de auditoría. Los eventos aparecen cuando el equipo usa el sistema con normalidad."
            )
            return

        df_logs = pd.DataFrame(logs_empresa)
        col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
        fecha_inicio = col_f1.date_input("Desde", value=ahora().date().replace(day=1), key="log_desde")
        fecha_fin = col_f2.date_input("Hasta", value=ahora().date(), key="log_hasta")

        posibles_usuario = [c for c in ["usuario", "U"] if c in df_logs.columns]
        col_usuario = posibles_usuario[0] if posibles_usuario else None
        usuarios_unicos = sorted(df_logs[col_usuario].astype(str).unique()) if col_usuario else []
        usuario_filtro = col_f3.selectbox("Usuario", ["Todos"] + usuarios_unicos, key="log_usuario")
        buscar_log = st.text_input("Buscar en registros", key="buscar_log")

        col_fecha = "fecha" if "fecha" in df_logs.columns else "F" if "F" in df_logs.columns else None
        registros_filtrados = list(logs_empresa)
        if col_fecha:
            filtro_fechas = []
            for r in registros_filtrados:
                fecha_raw = str(r.get(col_fecha, "") or "").strip()
                dt = pd.to_datetime(fecha_raw, format="%d/%m/%Y" if col_fecha == "F" else None, errors="coerce")
                if pd.notna(dt) and fecha_inicio <= dt.date() <= fecha_fin:
                    filtro_fechas.append(r)
            registros_filtrados = filtro_fechas

        if usuario_filtro != "Todos" and col_usuario:
            registros_filtrados = [r for r in registros_filtrados if str(r.get(col_usuario, "")) == usuario_filtro]

        if buscar_log:
            b = str(buscar_log).strip().lower()
            registros_filtrados = [r for r in registros_filtrados if b in _texto_busqueda_log(r)]

        df_filtrado = pd.DataFrame(registros_filtrados)

        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Total registros", len(df_filtrado))
        col_m2.metric("Usuarios unicos", df_filtrado[col_usuario].nunique() if col_usuario and not df_filtrado.empty else 0)
        ultimo_valor = df_filtrado[col_fecha].iloc[-1] if col_fecha and not df_filtrado.empty else "-"
        col_m3.metric("Ultimo registro", ultimo_valor)

        total = len(df_filtrado)
        if total == 0:
            st.info("Sin resultados para el filtro actual.")
            return
        limite = st.selectbox("Eventos por página", [50, 100, 200, 400], index=1, key="audit_log_limite")
        paginas = max((total - 1) // limite + 1, 1)
        pagina = st.number_input("Página logs", min_value=1, max_value=paginas, value=1, step=1)
        inicio = (int(pagina) - 1) * limite
        fin = inicio + limite
        df_pagina = df_filtrado.iloc[::-1].iloc[inicio:fin]
        st.caption(f"Mostrando {len(df_pagina)} de {total} registro(s) filtrado(s).")
        with lista_plegable("Log de auditoría (tabla)", count=len(df_pagina), expanded=False, height=500):
            mostrar_dataframe_con_scroll(
                df_pagina.drop(columns=["fecha_dt"], errors="ignore"),
                height=440,
            )

        csv_key = f"audit_logs_csv_{mi_empresa}_{user.get('nombre','')}_{usuario_filtro}_{str(buscar_log or '').strip().lower()}"
        if st.button("Preparar auditoría CSV", use_container_width=True):
            df_descarga = df_filtrado.drop(columns=["fecha_dt"], errors="ignore").copy()
            rename_dict = {"U": "Usuario", "A": "Accion", "F": "Fecha", "H": "Hora", "E": "Empresa"}
            df_descarga = df_descarga.rename(columns=rename_dict)
            st.session_state[csv_key] = dataframe_csv_bytes(df_descarga)
        if st.session_state.get(csv_key):
            nombre_csv = f"Auditoria_Logs_{sanitize_filename_component(ahora().strftime('%d_%m_%Y_%H%M'), 'logs')}.csv"
            st.download_button("Descargar auditoria CSV", data=st.session_state[csv_key], file_name=nombre_csv, mime="text/csv", use_container_width=True)
        return

    st.subheader("Auditoria de Asistencia por Profesional")
    profesionales_lista = list(set([v.get("nombre", "") for v in st.session_state.get("usuarios_db", {}).values()]))
    profesionales_historicos = list(set([c.get("profesional", "") for c in st.session_state.get("checkin_db", [])]))
    profesionales_lista = sorted([p for p in set(profesionales_lista + profesionales_historicos) if p])

    if not profesionales_lista:
        st.warning("No hay nombres de profesionales en usuarios ni en fichadas de check-in todavia.")
        return

    prof_sel = st.selectbox("Seleccionar Profesional", profesionales_lista, key="prof_rrhh_audit")
    col_r1, col_r2 = st.columns(2)
    fecha_rrhh_desde = col_r1.date_input("Desde", value=ahora().date().replace(day=1), key="rrhh_desde_audit")
    fecha_rrhh_hasta = col_r2.date_input("Hasta", value=ahora().date(), key="rrhh_hasta_audit")

    chks_prof = []
    for c in st.session_state.get("checkin_db", []):
        if c.get("profesional") != prof_sel:
            continue
        fecha_raw = c.get("fecha_hora", "")
        fecha_dt = pd.to_datetime(fecha_raw, format="%d/%m/%Y %H:%M:%S", errors="coerce")
        if pd.isna(fecha_dt):
            fecha_dt = pd.to_datetime(fecha_raw, format="%d/%m/%Y %H:%M", errors="coerce")
        if pd.notna(fecha_dt) and fecha_rrhh_desde <= fecha_dt.date() <= fecha_rrhh_hasta:
            chks_prof.append(c)

    if chks_prof:
        st.success(f"{len(chks_prof)} registros de asistencia para {prof_sel} en el periodo seleccionado")
    else:
        st.warning(
            f"Sin fichadas para **{prof_sel}** en ese periodo. Amplia fechas o verifica que existan LLEGADA/SALIDA en **Visitas**."
        )

    if chks_prof:
        df_chk = pd.DataFrame(chks_prof).iloc[::-1].reset_index(drop=True)
        total_chk = len(df_chk)
        limite = st.selectbox("Registros asistencia por página", [20, 40, 80, 120], index=1, key="audit_chk_limite")
        paginas_chk = max((total_chk - 1) // limite + 1, 1)
        pag_chk = st.number_input("Página asistencia", min_value=1, max_value=paginas_chk, value=1, step=1)
        ini_chk = (int(pag_chk) - 1) * limite
        fin_chk = ini_chk + limite
        df_chk_page = df_chk.iloc[ini_chk:fin_chk]
        st.caption(f"Mostrando {len(df_chk_page)} de {total_chk} fichada(s) en el período.")
        with lista_plegable("Asistencia del profesional (tabla)", count=len(df_chk_page), expanded=False, height=460):
            mostrar_dataframe_con_scroll(df_chk_page, height=400)

        if FPDF_DISPONIBLE and st.checkbox("Preparar PDF de asistencia", value=False):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 15)
            pdf.cell(0, 12, safe_text(f"REPORTE RRHH - {mi_empresa}"), ln=True, align='C')
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, safe_text(f"Profesional: {prof_sel}"), ln=True)
            pdf.set_font("Arial", 'I', 10)
            pdf.cell(0, 8, safe_text(f"Periodo: {fecha_rrhh_desde.strftime('%d/%m/%Y')} - {fecha_rrhh_hasta.strftime('%d/%m/%Y')}"), ln=True)
            pdf.ln(10)
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(30, 8, safe_text("Fecha"), border=1)
            pdf.cell(45, 8, safe_text("Paciente"), border=1)
            pdf.cell(35, 8, safe_text("Accion"), border=1)
            pdf.cell(40, 8, safe_text("GPS"), border=1)
            pdf.cell(40, 8, safe_text("Duracion"), border=1, ln=True)
            pdf.set_font("Arial", '', 9)
            for c in reversed(chks_prof[-200:]):
                pdf.cell(30, 8, safe_text(c.get("fecha_hora", "")[:16]), border=1)
                pdf.cell(45, 8, safe_text(str(c.get("paciente", "-"))[:25]), border=1)
                pdf.cell(35, 8, safe_text(str(c.get("tipo", "-"))[:15]), border=1)
                pdf.cell(40, 8, safe_text(str(c.get("gps", "-"))[:25]), border=1)
                pdf.cell(40, 8, safe_text("-"), border=1, ln=True)

            pdf_bytes = pdf_output_bytes(pdf)
            nombre_pdf = f"Asistencia_{sanitize_filename_component(prof_sel, 'profesional')}_{fecha_rrhh_desde.strftime('%d%m%Y')}.pdf"
            st.download_button("Descargar reporte asistencia PDF", data=pdf_bytes, file_name=nombre_pdf, mime="application/pdf", use_container_width=True)
