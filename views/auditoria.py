import base64
import io

import pandas as pd
import streamlit as st

from core.export_utils import dataframe_csv_bytes, pdf_output_bytes, safe_text, sanitize_filename_component
from core.utils import ahora, mostrar_dataframe_con_scroll

FPDF_DISPONIBLE = False
try:
    from fpdf import FPDF
    FPDF_DISPONIBLE = True
except ImportError:
    pass


def render_auditoria(mi_empresa, user):
    st.subheader("Auditoria General de Movimientos")
    st.info("Consulta completa de movimientos del sistema. Visible para SuperAdmin, Coordinador y Administrativo.")

    seccion = st.radio("Seccion", ["Logs del sistema", "Asistencia por profesional"], horizontal=True, label_visibility="collapsed")

    if seccion == "Logs del sistema":
        logs = st.session_state.get("logs_db", [])
        if not logs:
            st.info("Aun no hay registros de auditoria.")
            return

        df_logs = pd.DataFrame(logs)
        col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
        fecha_inicio = col_f1.date_input("Desde", value=ahora().date().replace(day=1), key="log_desde")
        fecha_fin = col_f2.date_input("Hasta", value=ahora().date(), key="log_hasta")

        posibles_usuario = [c for c in ["usuario", "U"] if c in df_logs.columns]
        col_usuario = posibles_usuario[0] if posibles_usuario else None
        usuarios_unicos = sorted(df_logs[col_usuario].astype(str).unique()) if col_usuario else []
        usuario_filtro = col_f3.selectbox("Usuario", ["Todos"] + usuarios_unicos, key="log_usuario")
        buscar_log = st.text_input("Buscar en registros", key="buscar_log")

        col_fecha = "fecha" if "fecha" in df_logs.columns else "F" if "F" in df_logs.columns else None
        df_filtrado = df_logs.copy()

        if col_fecha:
            formato = "%d/%m/%Y" if col_fecha == "F" else None
            df_filtrado["fecha_dt"] = pd.to_datetime(df_filtrado[col_fecha], format=formato, errors="coerce")
            df_filtrado = df_filtrado[(df_filtrado["fecha_dt"].dt.date >= fecha_inicio) & (df_filtrado["fecha_dt"].dt.date <= fecha_fin)]

        if usuario_filtro != "Todos" and col_usuario:
            df_filtrado = df_filtrado[df_filtrado[col_usuario].astype(str) == usuario_filtro]

        if buscar_log:
            mask = df_filtrado.astype(str).apply(lambda x: x.str.contains(buscar_log, case=False, na=False)).any(axis=1)
            df_filtrado = df_filtrado[mask]

        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Total registros", len(df_filtrado))
        col_m2.metric("Usuarios unicos", df_filtrado[col_usuario].nunique() if col_usuario and not df_filtrado.empty else 0)
        ultimo_valor = df_filtrado[col_fecha].iloc[-1] if col_fecha and not df_filtrado.empty else "-"
        col_m3.metric("Ultimo registro", ultimo_valor)

        max_filas = min(1000, max(len(df_filtrado), 1))
        if max_filas <= 50:
            limite = max_filas
            st.caption(f"Mostrando {limite} registros.")
        else:
            limite = st.slider("Filas a mostrar", min_value=50, max_value=max_filas, value=min(200, max_filas), step=50)
        mostrar_dataframe_con_scroll(
            df_filtrado.tail(limite).drop(columns=["fecha_dt"], errors="ignore").iloc[::-1],
            height=460,
        )

        df_descarga = df_filtrado.drop(columns=["fecha_dt"], errors="ignore").copy()
        rename_dict = {"U": "Usuario", "A": "Accion", "F": "Fecha", "H": "Hora", "E": "Empresa"}
        df_descarga = df_descarga.rename(columns=rename_dict)
        nombre_csv = f"Auditoria_Logs_{sanitize_filename_component(ahora().strftime('%d_%m_%Y_%H%M'), 'logs')}.csv"
        st.download_button("Descargar auditoria CSV", data=dataframe_csv_bytes(df_descarga), file_name=nombre_csv, mime="text/csv", use_container_width=True)
        return

    st.subheader("Auditoria de Asistencia por Profesional")
    profesionales_lista = list(set([v.get("nombre", "") for v in st.session_state.get("usuarios_db", {}).values()]))
    profesionales_historicos = list(set([c.get("profesional", "") for c in st.session_state.get("checkin_db", [])]))
    profesionales_lista = sorted([p for p in set(profesionales_lista + profesionales_historicos) if p])

    if not profesionales_lista:
        st.info("No hay profesionales registrados aun.")
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

    st.success(f"{len(chks_prof)} registros de asistencia para {prof_sel} en el periodo seleccionado")

    if chks_prof:
        max_filas = min(500, max(len(chks_prof), 1))
        if max_filas <= 20:
            limite = max_filas
            st.caption(f"Mostrando {limite} registros de asistencia.")
        else:
            limite = st.slider("Filas de asistencia", min_value=20, max_value=max_filas, value=min(120, max_filas), step=20)
        mostrar_dataframe_con_scroll(pd.DataFrame(chks_prof[-limite:]).iloc[::-1], height=420)

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
