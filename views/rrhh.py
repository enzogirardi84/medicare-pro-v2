import io
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.export_utils import dataframe_csv_bytes, pdf_output_bytes, safe_text, sanitize_filename_component
from core.utils import ahora, es_control_total, mostrar_dataframe_con_scroll, seleccionar_limite_registros

FPDF_DISPONIBLE = False
try:
    from fpdf import FPDF
    FPDF_DISPONIBLE = True
except ImportError:
    pass


def _obtener_dt(fecha_hora):
    try:
        return datetime.strptime(fecha_hora, "%d/%m/%Y %H:%M:%S")
    except Exception:
        try:
            return datetime.strptime(fecha_hora, "%d/%m/%Y %H:%M")
        except Exception:
            return datetime.min


def render_rrhh(mi_empresa, rol, user):
    rol_normalizado = str(rol or "").strip().lower()
    acceso_total = es_control_total(rol_normalizado)
    st.subheader("Control de RRHH y Fichaje Historico")
    st.info("Genera reportes de presentismo, horas trabajadas y movimientos GPS sin cargar tablas gigantes por defecto.")

    col_f1, col_f2 = st.columns(2)
    fecha_inicio = col_f1.date_input("Desde fecha", value=ahora().date() - timedelta(days=30), key="fichajes_desde")
    fecha_fin = col_f2.date_input("Hasta fecha", value=ahora().date(), key="fichajes_hasta")

    fichajes_lista = []
    rastreador_ingresos = {}
    checkins = [c for c in st.session_state.get("checkin_db", []) if c.get("empresa") == mi_empresa or acceso_total]
    checkins_ordenados = sorted(checkins, key=lambda c: _obtener_dt(c.get("fecha_hora", "")))

    usuarios_db = st.session_state.get("usuarios_db", {})
    matriculas = {u_data.get("nombre"): u_data.get("matricula", "S/D") for u_data in usuarios_db.values()}

    for c in checkins_ordenados:
        prof = c.get("profesional", "S/D")
        pac = c.get("paciente", "S/D")
        dt_actual = _obtener_dt(c.get("fecha_hora", ""))
        if dt_actual == datetime.min:
            continue

        fecha_f = dt_actual.strftime("%d/%m/%Y")
        hora_f = dt_actual.strftime("%H:%M")
        accion_raw = c.get("tipo", "")

        if "LLEGADA" in accion_raw.upper():
            accion = "INGRESO"
            rastreador_ingresos[(prof, pac)] = dt_actual
            tiempo_total = "-"
        elif "SALIDA" in accion_raw.upper():
            accion = "EGRESO"
            tiempo_total = "Sin ingreso previo"
            if (prof, pac) in rastreador_ingresos:
                duracion = dt_actual - rastreador_ingresos[(prof, pac)]
                horas = duracion.seconds // 3600
                minutos = (duracion.seconds % 3600) // 60
                tiempo_total = f"{horas}h {minutos:02d}m"
                del rastreador_ingresos[(prof, pac)]
        else:
            accion = "OTRO"
            tiempo_total = "-"

        if fecha_inicio <= dt_actual.date() <= fecha_fin:
            fichajes_lista.append({
                "Fecha": fecha_f,
                "Hora": hora_f,
                "Profesional": prof,
                "Matricula": matriculas.get(prof, "S/D"),
                "Accion": accion,
                "Tiempo Trabajado": tiempo_total,
                "Paciente": pac,
                "GPS": c.get("gps", "-"),
                "fecha_dt": dt_actual,
            })

    if not fichajes_lista:
        st.info("Aun no hay registros de fichajes en ese periodo.")
        return

    df_fichajes = pd.DataFrame(fichajes_lista)
    df_egresos = df_fichajes[df_fichajes["Accion"] == "EGRESO"]
    total_horas = 0.0
    for t in df_egresos["Tiempo Trabajado"]:
        if isinstance(t, str) and "h" in t:
            partes = t.replace("h", "").replace("m", "").split()
            if partes:
                total_horas += int(partes[0]) + (int(partes[1]) if len(partes) > 1 else 0) / 60.0

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("Total Fichajes", len(df_fichajes))
    col_m2.metric("Horas Trabajadas", f"{total_horas:.1f} hs")
    col_m3.metric("Profesionales", df_fichajes["Profesional"].nunique())
    col_m4.metric("Visitas Completadas", len(df_egresos))

    seccion = st.radio("Vista", ["Historico", "Resumen", "Gestion"], horizontal=False, label_visibility="collapsed")

    if seccion == "Historico":
        prof_filtrar = st.selectbox("Filtrar por Profesional", ["Todos"] + sorted(df_fichajes["Profesional"].unique().tolist()))
        df_mostrar = df_fichajes.copy()
        if prof_filtrar != "Todos":
            df_mostrar = df_mostrar[df_mostrar["Profesional"] == prof_filtrar]
        max_historico = min(1000, max(len(df_mostrar), 1))
        if max_historico <= 20:
            limite = max_historico
            st.caption(f"Mostrando {limite} filas historicas.")
        else:
            limite = st.slider("Filas historicas", min_value=20, max_value=max_historico, value=min(120, len(df_mostrar)), step=20)
        mostrar_dataframe_con_scroll(
            df_mostrar.sort_values(by="fecha_dt", ascending=False).drop(columns=["fecha_dt"], errors='ignore').head(limite),
            height=480,
        )

        csv_data = dataframe_csv_bytes(df_mostrar.drop(columns=["fecha_dt"], errors='ignore'))
        st.download_button("Descargar CSV RRHH", data=csv_data, file_name=f"RRHH_{sanitize_filename_component(mi_empresa, 'empresa')}_{fecha_inicio.strftime('%d%m%Y')}_{fecha_fin.strftime('%d%m%Y')}.csv", mime="text/csv", use_container_width=True)

        if FPDF_DISPONIBLE and st.checkbox("Preparar PDF RRHH", value=False):
            pdf = FPDF(orientation='L')
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 12, safe_text(f"REPORTE OFICIAL DE RRHH - {mi_empresa}"), ln=True, align='C')
            pdf.set_font("Arial", '', 11)
            pdf.cell(0, 8, safe_text(f"Periodo: {fecha_inicio.strftime('%d/%m/%Y')} al {fecha_fin.strftime('%d/%m/%Y')}"), ln=True, align='C')
            pdf.ln(8)
            pdf.set_font("Arial", 'B', 9)
            for _, fila in df_mostrar.sort_values(by="fecha_dt", ascending=False).head(200).iterrows():
                pdf.cell(0, 7, safe_text(f"{fila['Fecha']} {fila['Hora']} | {fila['Profesional']} | {fila['Accion']} | {fila['Paciente']} | {fila['Tiempo Trabajado']}"), ln=True)
            pdf_bytes = pdf_output_bytes(pdf)
            st.download_button("Descargar PDF RRHH", data=pdf_bytes, file_name=f"RRHH_{sanitize_filename_component(mi_empresa, 'empresa')}.pdf", mime="application/pdf", use_container_width=True)
        return

    if seccion == "Resumen":
        resumen_rows = []
        for profesional, grupo in df_egresos.groupby("Profesional"):
            horas_totales = 0.0
            for t in grupo["Tiempo Trabajado"]:
                if isinstance(t, str) and "h" in t:
                    partes = t.replace("h", "").replace("m", "").split()
                    if partes:
                        horas_totales += int(partes[0]) + (int(partes[1]) if len(partes) > 1 else 0) / 60.0
            resumen_rows.append({
                "Profesional": profesional,
                "Matricula": grupo["Matricula"].iloc[0] if not grupo.empty else "S/D",
                "Visitas": len(grupo),
                "Horas Totales": round(horas_totales, 1),
            })
        if not resumen_rows:
            st.info("Todavia no hay egresos completos en el periodo para calcular horas trabajadas.")
            return
        resumen_prof = pd.DataFrame(resumen_rows).sort_values(by=["Horas Totales", "Visitas"], ascending=False)
        limite_resumen = seleccionar_limite_registros(
            "Profesionales en resumen",
            len(resumen_prof),
            key=f"rrhh_resumen_{mi_empresa}",
            default=20,
            opciones=(10, 20, 30, 50, 100),
        )
        mostrar_dataframe_con_scroll(resumen_prof.head(limite_resumen), height=400)
        st.success(f"Total horas en el periodo: {resumen_prof['Horas Totales'].sum():.1f} hs")
        return

    st.warning("Solo para correccion de errores. Eliminar un fichaje recalcula automaticamente los tiempos.")
    df_gestion = df_fichajes.sort_values(by="fecha_dt", ascending=False).drop(columns=["fecha_dt"], errors='ignore')
    max_gestion = min(500, max(len(df_gestion), 1))
    if max_gestion <= 20:
        limite = max_gestion
        st.caption(f"Mostrando {limite} filas de gestion.")
    else:
        limite = st.slider("Filas de gestion", min_value=20, max_value=max_gestion, value=min(100, len(df_gestion)), step=20)
    mostrar_dataframe_con_scroll(df_gestion.head(limite), height=420)
    opciones_borrar = [
        (f"{c.get('fecha_hora', '-')} | {c.get('profesional', 'S/D')} | {c.get('tipo', '-')} | Paciente: {c.get('paciente', 'S/D')}", idx)
        for idx, c in enumerate(st.session_state.get("checkin_db", []))
        if c.get("empresa") == mi_empresa or acceso_total
    ]
    if opciones_borrar:
        col_del1, col_del2 = st.columns([3, 1])
        registro_sel = col_del1.selectbox("Seleccionar fichaje a eliminar", options=opciones_borrar, format_func=lambda x: x[0])
        confirmar_borrado = col_del1.checkbox("Confirmar eliminacion del fichaje", key="rrhh_conf_del_fichaje")
        if col_del2.button("Eliminar Fichaje", type="secondary", use_container_width=True, disabled=not confirmar_borrado):
            del st.session_state["checkin_db"][registro_sel[1]]
            guardar_datos()
            st.rerun()
