import io
from datetime import datetime, timedelta
from html import escape

import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.export_utils import dataframe_csv_bytes, pdf_output_bytes, safe_text, sanitize_filename_component
from core.view_helpers import bloque_mc_grid_tarjetas, lista_plegable
from core.utils import ahora, es_control_total, mostrar_dataframe_con_scroll, seleccionar_limite_registros
from core.db_sql import get_checkins_by_empresa
from core.nextgen_sync import _obtener_uuid_empresa
from core.app_logging import log_event

FPDF_DISPONIBLE = False
try:
    from fpdf import FPDF
    FPDF_DISPONIBLE = True
except ImportError:
    pass  # Intencional: fpdf es opcional para PDFs


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
    emp_e = escape(str(mi_empresa or ""))
    st.markdown(
        f"""
        <div class="mc-hero">
            <h2 class="mc-hero-title">RRHH y fichajes</h2>
            <p class="mc-hero-text">Presentismo y duracion de visitas desde check-in para {emp_e}. Rangos de fecha y limites de filas para equipos lentos.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Fichajes</span>
                <span class="mc-chip">Duraciones</span>
                <span class="mc-chip">Exportar</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ("Historico", "Fichajes filtrados por fechas con CSV y PDF opcional."),
            ("Resumen", "Horas y visitas agrupadas por profesional."),
            ("Gestion", "Correccion puntual: borrar un fichaje mal cargado."),
        ]
    )
    st.info("Genera reportes de presentismo, horas trabajadas y movimientos GPS sin cargar tablas gigantes por defecto.")
    st.caption(
        "Ajusta **Desde** / **Hasta** primero; si no hay datos, amplia el rango o confirma que existan LLEGADA/SALIDA en check-in. "
        "Las horas se estiman al cerrar cada visita con EGRESO."
    )

    col_f1, col_f2 = st.columns(2)
    fecha_inicio = col_f1.date_input("Desde fecha", value=ahora().date() - timedelta(days=30), key="fichajes_desde")
    fecha_fin = col_f2.date_input("Hasta fecha", value=ahora().date(), key="fichajes_hasta")
    st.caption(
        "El rango **Desde / Hasta** se mantiene mientras la sesión siga abierta (hasta Cerrar sesión)."
    )

    fichajes_lista = []
    rastreador_ingresos = {}
    
    # 1. Intentar leer desde PostgreSQL (Hybrid Read)
    checkins = []
    try:
        empresa_uuid = _obtener_uuid_empresa(mi_empresa)
        if empresa_uuid:
            chk_sql = get_checkins_by_empresa(empresa_uuid, limit=2000)
            if chk_sql:
                for c in chk_sql:
                    dt = pd.to_datetime(c.get("fecha_hora", ""), errors="coerce")
                    checkins.append({
                        "empresa": mi_empresa,
                        "profesional": c.get("usuarios", {}).get("nombre", "Desconocido") if isinstance(c.get("usuarios"), dict) else "Desconocido",
                        "paciente": c.get("pacientes", {}).get("nombre_completo", "N/A") if isinstance(c.get("pacientes"), dict) else "N/A",
                        "fecha_hora": dt.strftime("%d/%m/%Y %H:%M:%S") if pd.notnull(dt) else "",
                        "tipo": c.get("tipo_registro", ""),
                        "gps": f"{c.get('latitud', '')},{c.get('longitud', '')}" if c.get("latitud") else "-",
                        "id_sql": c.get("id")
                    })
    except Exception as e:
        log_event("error_leer_checkins_sql", str(e))

    # 2. Fallback a JSON si SQL falla o esta vacio
    if not checkins:
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
        st.warning(
            "No hay fichajes en el periodo elegido para esta clinica (o sin datos aun). Proba ampliar las fechas o revisar que el equipo registre llegadas y salidas en **Visitas**."
        )
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
    st.caption("Historico: fila a fila. Resumen: totales por profesional. Gestion: solo para corregir errores de carga.")

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
        df_hist = df_mostrar.sort_values(by="fecha_dt", ascending=False).drop(columns=["fecha_dt"], errors="ignore").head(limite)
        with lista_plegable("Histórico de fichajes", count=len(df_hist), expanded=False, height=520):
            mostrar_dataframe_con_scroll(df_hist, height=460)

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
                    partes = [p.strip() for p in t.replace("h", "").replace("m", "").split() if p.strip().isdigit()]
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
        df_res = resumen_prof.head(limite_resumen)
        with lista_plegable("Resumen por profesional", count=len(df_res), expanded=False, height=440):
            mostrar_dataframe_con_scroll(df_res, height=380)
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
    df_g = df_gestion.head(limite)
    with lista_plegable("Gestión de fichajes (corrección)", count=len(df_g), expanded=False, height=460):
        mostrar_dataframe_con_scroll(df_g, height=400)
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
            guardar_datos(spinner=True)
            st.rerun()
