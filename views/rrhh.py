from datetime import datetime, timedelta
from html import escape

import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.export_utils import dataframe_csv_bytes, pdf_output_bytes, safe_text, sanitize_filename_component
from core.view_helpers import bloque_mc_grid_tarjetas, bloque_estado_vacio, lista_plegable
from core.utils import ahora, es_control_total, mostrar_dataframe_con_scroll, seleccionar_limite_registros
from core.db_sql import get_checkins_by_empresa
from core.nextgen_sync import _obtener_uuid_empresa
from core.app_logging import log_event

FPDF_DISPONIBLE = False
try:
    from fpdf import FPDF
    FPDF_DISPONIBLE = True
except ImportError:
    pass


def _obtener_dt(fecha_hora):
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(fecha_hora or "").strip(), fmt)
        except Exception:
            continue
    return datetime.min


def _parsear_duracion(tiempo_str: str) -> float:
    """Parsea '2h 30m' a horas como float. Retorna 0.0 si no se puede."""
    if not isinstance(tiempo_str, str) or "h" not in tiempo_str:
        return 0.0
    partes = [p for p in tiempo_str.replace("h", "").replace("m", "").split() if p.strip().isdigit()]
    if not partes:
        return 0.0
    try:
        h = int(partes[0])
        m = int(partes[1]) if len(partes) > 1 else 0
        return round(h + m / 60.0, 1)
    except (ValueError, IndexError):
        return 0.0


def _generar_pdf_rrhh(mi_empresa, user, fecha_inicio, fecha_fin, df_mostrar, total_horas, total_visitas):
    """Genera PDF profesional con resumen y detalle de fichajes."""
    if not FPDF_DISPONIBLE:
        return b""
    pdf = FPDF()
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=True, margin=15)

    # ── Pagina 1: Resumen + Tabla profesional ──
    pdf.add_page()
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 12, safe_text(f"REPORTE DE RRHH - {mi_empresa}"), ln=True, align="C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 7, safe_text(f"Periodo: {fecha_inicio.strftime('%d/%m/%Y')} al {fecha_fin.strftime('%d/%m/%Y')}"), ln=True, align="C")
    pdf.cell(0, 7, safe_text(f"Generado: {ahora().strftime('%d/%m/%Y %H:%M')} por {user.get('nombre', 'Sistema')}"), ln=True, align="C")
    pdf.ln(6)

    # Metricas
    n_prof = df_mostrar["Profesional"].nunique() if not df_mostrar.empty else 0
    n_ingresos = len(df_mostrar[df_mostrar["Accion"] == "INGRESO"])
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 8, "RESUMEN GENERAL", ln=True)
    pdf.set_fill_color(22, 38, 68)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "", 10)
    col_w = pdf.w / 5
    headers = ["Fichajes", "Horas", "Profesionales", "Visitas", "Ingresos"]
    vals = [len(df_mostrar), f"{total_horas:.1f} hs", n_prof, total_visitas, n_ingresos]
    for i, (h, v) in enumerate(zip(headers, vals)):
        pdf.cell(col_w, 10, f"{h}: {v}", border=1, align="C", fill=True)
    pdf.ln(12)
    pdf.set_text_color(0, 0, 0)

    # Tabla resumen por profesional
    if not df_mostrar.empty:
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 8, "RESUMEN POR PROFESIONAL", ln=True)
        pdf.set_font("Arial", "B", 9)
        pdf.set_fill_color(15, 30, 60)
        pdf.set_text_color(255, 255, 255)
        col_prof = 60
        col_matr = 25
        col_vis = 25
        col_horas = 25
        col_prom = 25
        total_w = col_prof + col_matr + col_vis + col_horas + col_prom
        x_start = (pdf.w - total_w) / 2
        pdf.set_x(x_start)
        pdf.cell(col_prof, 7, "Profesional", border=1, fill=True, align="C")
        pdf.cell(col_matr, 7, "Matr.", border=1, fill=True, align="C")
        pdf.cell(col_vis, 7, "Visitas", border=1, fill=True, align="C")
        pdf.cell(col_horas, 7, "Horas", border=1, fill=True, align="C")
        pdf.cell(col_prom, 7, "Hs/Vis", border=1, fill=True, align="C")
        pdf.ln()
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", "", 8)

        df_eg = df_mostrar[df_mostrar["Accion"] == "EGRESO"]
        for prof, grupo in df_eg.groupby("Profesional"):
            hh = sum(_parsear_duracion(t) for t in grupo["Tiempo Trabajado"])
            n_vis = len(grupo)
            prom = round(hh / n_vis, 2) if n_vis > 0 else 0
            mat = grupo["Matricula"].iloc[0] if not grupo.empty else "S/D"
            pdf.set_x(x_start)
            pdf.cell(col_prof, 6, safe_text(prof[:28]), border=1)
            pdf.cell(col_matr, 6, safe_text(str(mat)[:10]), border=1, align="C")
            pdf.cell(col_vis, 6, str(n_vis), border=1, align="C")
            pdf.cell(col_horas, 6, f"{hh:.1f}", border=1, align="C")
            pdf.cell(col_prom, 6, f"{prom:.2f}", border=1, align="C")
            pdf.ln()
            if pdf.get_y() > 250:
                pdf.add_page()

    # ── Pagina 2+: Detalle de fichajes ──
    if pdf.get_y() > 220:
        pdf.add_page()
    pdf.ln(4)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 8, "DETALLE DE FICHAJES", ln=True)
    pdf.set_font("Arial", "B", 8)
    pdf.set_fill_color(15, 30, 60)
    pdf.set_text_color(255, 255, 255)
    cols_det = {"Fecha": 22, "Hora": 14, "Profesional": 48, "Matr.": 16, "Accion": 18, "Paciente": 48, "Tiempo": 18, "GPS": 30}
    for c, w in cols_det.items():
        pdf.cell(w, 6, c, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 7)
    for _, fila in df_mostrar.sort_values(by="fecha_dt", ascending=False).head(500).iterrows():
        if pdf.get_y() > 265:
            pdf.add_page()
            pdf.set_font("Arial", "B", 8)
            pdf.set_fill_color(15, 30, 60)
            pdf.set_text_color(255, 255, 255)
            for c, w in cols_det.items():
                pdf.cell(w, 5, c, border=1, fill=True, align="C")
            pdf.ln()
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Arial", "", 7)
        pdf.cell(cols_det["Fecha"], 5, safe_text(str(fila.get("Fecha", ""))[:10]), border=1)
        pdf.cell(cols_det["Hora"], 5, safe_text(str(fila.get("Hora", ""))[:5]), border=1)
        pdf.cell(cols_det["Profesional"], 5, safe_text(str(fila.get("Profesional", ""))[:24]), border=1)
        pdf.cell(cols_det["Matr."], 5, safe_text(str(fila.get("Matricula", ""))[:8]), border=1, align="C")
        pdf.cell(cols_det["Accion"], 5, safe_text(str(fila.get("Accion", ""))[:10]), border=1, align="C")
        pdf.cell(cols_det["Paciente"], 5, safe_text(str(fila.get("Paciente", ""))[:24]), border=1)
        pdf.cell(cols_det["Tiempo"], 5, safe_text(str(fila.get("Tiempo Trabajado", ""))[:8]), border=1, align="C")
        pdf.cell(cols_det["GPS"], 5, safe_text(str(fila.get("GPS", ""))[:15]), border=1)
        pdf.ln()
    return pdf_output_bytes(pdf)


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
    total_horas = sum(_parsear_duracion(t) for t in df_egresos["Tiempo Trabajado"])

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
        df_hist = df_mostrar.sort_values(by="fecha_dt", ascending=False).drop(columns=["fecha_dt"], errors="ignore").head(limite)
        with lista_plegable("Historico de fichajes", count=len(df_hist), expanded=False, height=520):
            mostrar_dataframe_con_scroll(df_hist, height=460)

        csv_data = dataframe_csv_bytes(df_mostrar.drop(columns=["fecha_dt"], errors='ignore'))
        st.download_button("Descargar CSV RRHH", data=csv_data, file_name=f"RRHH_{sanitize_filename_component(mi_empresa, 'empresa')}_{fecha_inicio.strftime('%d%m%Y')}_{fecha_fin.strftime('%d%m%Y')}.csv", mime="text/csv", width='stretch')

        if FPDF_DISPONIBLE and st.checkbox("Preparar PDF RRHH", value=False):
            pdf = _generar_pdf_rrhh(mi_empresa, user, fecha_inicio, fecha_fin, df_mostrar, total_horas, len(df_egresos))
            st.download_button("Descargar PDF RRHH", data=pdf, file_name=f"RRHH_{sanitize_filename_component(mi_empresa, 'empresa')}_{fecha_inicio.strftime('%d%m%Y')}_{fecha_fin.strftime('%d%m%Y')}.pdf", mime="application/pdf", width='stretch')

    elif seccion == "Resumen":
        resumen_rows = []
        for profesional, grupo in df_egresos.groupby("Profesional"):
            hh = sum(_parsear_duracion(t) for t in grupo["Tiempo Trabajado"])
            resumen_rows.append({
                "Profesional": profesional,
                "Matricula": grupo["Matricula"].iloc[0] if not grupo.empty else "S/D",
                "Visitas": len(grupo),
                "Horas Totales": round(hh, 1),
                "Prom. hs/visita": round(hh / len(grupo), 2) if len(grupo) > 0 else 0,
            })
        if not resumen_rows:
            st.info("Todavia no hay egresos completos en el periodo para calcular horas trabajadas.")
            return
        resumen_prof = pd.DataFrame(resumen_rows).sort_values(by=["Horas Totales", "Visitas"], ascending=False)
        c_r1, c_r2 = st.columns([2, 1])
        with c_r1:
            limite_resumen = seleccionar_limite_registros(
                "Profesionales en resumen", len(resumen_prof),
                key=f"rrhh_resumen_{mi_empresa}", default=20,
                opciones=(10, 20, 30, 50, 100),
            )
            df_res = resumen_prof.head(limite_resumen)
            with lista_plegable("Resumen por profesional", count=len(df_res), expanded=False, height=440):
                mostrar_dataframe_con_scroll(df_res, height=380)
            st.success(f"Total horas en el periodo: {resumen_prof['Horas Totales'].sum():.1f} hs")
        with c_r2:
            st.markdown("##### Horas por profesional")
            _chart_df = resumen_prof.head(15).copy()
            if not _chart_df.empty and _chart_df["Horas Totales"].sum() > 0:
                import altair as alt
                _chart = alt.Chart(_chart_df).mark_bar(cornerRadiusEnd=4).encode(
                    x=alt.X("Horas Totales:Q", title="Hs"),
                    y=alt.Y("Profesional:N", sort="-x", title=None),
                    tooltip=["Profesional:N", "Horas Totales:Q", "Visitas:Q"],
                ).configure_axis(labelFontSize=11, titleFontSize=12).configure_view(strokeWidth=0)
                st.altair_chart(_chart, width="stretch")

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
        if col_del2.button("Eliminar Fichaje", type="secondary", width='stretch', disabled=not confirmar_borrado):
            del st.session_state["checkin_db"][registro_sel[1]]
            guardar_datos(spinner=True)
            st.rerun()
