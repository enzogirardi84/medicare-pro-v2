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


def generar_pdf_auditoria_logs(df, nombre_empresa=""):
    """Genera un PDF profesional con el log de auditoria del sistema. v2-force-rebuild"""
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    HEADER_BG = (30, 41, 59)
    HEADER_TEXT = (255, 255, 255)
    ROW_ALT = (241, 245, 249)
    ROW_BASE = (255, 255, 255)
    TEXT_DARK = (15, 23, 42)

    pdf.set_fill_color(*HEADER_BG)
    pdf.rect(10, 10, 277, 20, style="F")
    pdf.set_text_color(*HEADER_TEXT)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_xy(15, 16)
    pdf.cell(0, 8, "Auditoría del Sistema", ln=True)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(15, 23)
    empresa_str = str(nombre_empresa)[:60] if nombre_empresa else ""
    pdf.cell(0, 6, f"Empresa: {empresa_str}  |  Fecha: {ahora().strftime('%d/%m/%Y %H:%M')}", ln=True)

    pdf.set_y(38)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*TEXT_DARK)

    columnas = ["Fecha", "Usuario", "Acción", "Módulo", "Paciente", "Empresa", "Detalle"]
    anchos = [35, 30, 35, 30, 35, 30, 82]

    pdf.set_fill_color(*HEADER_BG)
    pdf.set_text_color(*HEADER_TEXT)
    for col, w in zip(columnas, anchos):
        pdf.cell(w, 8, col, border=1, align="C", fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    for idx, row in df.iterrows():
        fill = ROW_ALT if idx % 2 == 0 else ROW_BASE
        pdf.set_fill_color(*fill)
        pdf.set_text_color(*TEXT_DARK)

        def safe(val, max_len):
            v = str(val) if val is not None else ""
            return (v[: max_len - 3] + "...") if len(v) > max_len else v

        fecha = safe(row.get("F", row.get("fecha", "")), 20)
        usuario = safe(row.get("U", row.get("usuario", "")), 18)
        accion = safe(row.get("A", row.get("accion", "")), 22)
        modulo = safe(row.get("modulo", ""), 18)
        paciente = safe(row.get("paciente", ""), 20)
        empresa = safe(row.get("E", row.get("empresa", "")), 18)
        detalle = safe(row.get("detalle", ""), 55)

        pdf.cell(anchos[0], 7, fecha, border=1, align="C", fill=True)
        pdf.cell(anchos[1], 7, usuario, border=1, align="L", fill=True)
        pdf.cell(anchos[2], 7, accion, border=1, align="L", fill=True)
        pdf.cell(anchos[3], 7, modulo, border=1, align="L", fill=True)
        pdf.cell(anchos[4], 7, paciente, border=1, align="L", fill=True)
        pdf.cell(anchos[5], 7, empresa, border=1, align="L", fill=True)
        pdf.cell(anchos[6], 7, detalle, border=1, align="L", fill=True)
        pdf.ln()

    pdf.set_y(-20)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 10, f"Generado por MediCare Pro  |  {len(df)} registros", align="C")

    return bytes(pdf.output(dest="S"))


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

        pdf_key = f"audit_logs_pdf_{mi_empresa}_{user.get('nombre','')}_{usuario_filtro}_{str(buscar_log or '').strip().lower()}"
        if st.button("Preparar auditoría PDF", width='stretch'):
            pdf_bytes = generar_pdf_auditoria_logs(df_filtrado, mi_empresa)
            st.session_state[pdf_key] = pdf_bytes
        if st.session_state.get(pdf_key):
            nombre_pdf = f"Auditoria_Logs_{sanitize_filename_component(ahora().strftime('%d_%m_%Y_%H%M'), 'logs')}.pdf"
            st.download_button("Descargar auditoría PDF", data=st.session_state[pdf_key], file_name=nombre_pdf, mime="application/pdf", width='stretch')
        return

    # --- Asistencia por profesional ---
    st.subheader("Asistencia por profesional")

    # 1. Hybrid Read: SQL + local fallback + enriquecer nombres
    _checkins_sql = []
    _empresa_uuid = None
    try:
        from core.db_sql import get_checkins_by_empresa
        from core.nextgen_sync import _obtener_uuid_empresa
        _empresa_uuid = _obtener_uuid_empresa(mi_empresa)
    except ImportError:
        _empresa_uuid = None

    _local_checkins = st.session_state.get("checkin_db", [])
    _local_map = {}
    for _lc in _local_checkins:
        _key = (_lc.get("paciente", ""), _lc.get("fecha_hora", "")[:16])
        _local_map[_key] = _lc.get("profesional", "")

    if _empresa_uuid:
        try:
            chk_sql = get_checkins_by_empresa(_empresa_uuid, limit=2000)
            if chk_sql:
                for c in chk_sql:
                    dt = pd.to_datetime(c.get("fecha_hora", ""), errors="coerce")
                    fecha_str = dt.strftime("%d/%m/%Y %H:%M:%S") if pd.notnull(dt) else ""
                    prof_sql = c.get("usuarios", {}).get("nombre", "Desconocido") if isinstance(c.get("usuarios"), dict) else "Desconocido"
                    pac_sql = c.get("pacientes", {}).get("nombre_completo", "N/A") if isinstance(c.get("pacientes"), dict) else "N/A"
                    if prof_sql == "Desconocido" and pac_sql != "N/A":
                        prof_sql = _local_map.get((pac_sql, fecha_str[:16]), prof_sql)
                    _checkins_sql.append({
                        "profesional": prof_sql,
                        "paciente": pac_sql,
                        "fecha_hora": fecha_str,
                        "tipo": c.get("tipo_registro", ""),
                        "gps": f"{c.get('latitud', '')},{c.get('longitud', '')}" if c.get("latitud") else "-",
                    })
        except Exception as e:
            from core.app_logging import log_event
            log_event("auditoria_asistencia_sql", str(e))

    _checkins_todos = _checkins_sql if _checkins_sql else _local_checkins

    # 2. Construir lista de profesionales disponibles
    profesionales_sql = sorted({c["profesional"] for c in _checkins_sql if c.get("profesional") and c["profesional"] != "Desconocido"})
    profesionales_locales = sorted({c.get("profesional", "") for c in _local_checkins if c.get("profesional")})
    profesionales_lista = sorted(set(profesionales_sql + profesionales_locales))

    if not profesionales_lista:
        st.warning("No hay profesionales con registros de asistencia todavia.")
        return

    prof_sel = st.selectbox("Seleccionar Profesional", profesionales_lista, key="prof_rrhh_audit")
    col_r1, col_r2 = st.columns(2)
    fecha_desde = col_r1.date_input("Desde", value=ahora().date().replace(day=1), key="rrhh_desde_audit")
    fecha_hasta = col_r2.date_input("Hasta", value=ahora().date(), key="rrhh_hasta_audit")

    # 3. Filtrar por profesional y fecha
    chks_prof = []
    for c in _checkins_todos:
        if c.get("profesional") != prof_sel:
            continue
        fecha_raw = c.get("fecha_hora", "")
        fecha_dt = pd.to_datetime(fecha_raw, format="%d/%m/%Y %H:%M:%S", errors="coerce")
        if pd.isna(fecha_dt):
            fecha_dt = pd.to_datetime(fecha_raw, format="%d/%m/%Y %H:%M", errors="coerce")
        if pd.notna(fecha_dt) and fecha_desde <= fecha_dt.date() <= fecha_hasta:
            chks_prof.append(c)

    if not chks_prof:
        st.warning(
            f"Sin fichadas para **{prof_sel}** en ese periodo. Amplia fechas o verifica que existan LLEGADA/SALIDA en **Visitas**."
        )
        return

    st.success(f"{len(chks_prof)} registros de asistencia para {prof_sel} en el periodo seleccionado")

    # 4. Dashboard de métricas
    df_chk_raw = pd.DataFrame(chks_prof).copy()
    df_chk_raw["fecha_dt"] = pd.to_datetime(df_chk_raw["fecha_hora"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    df_chk_raw["fecha_dt"] = df_chk_raw["fecha_dt"].fillna(
        pd.to_datetime(df_chk_raw["fecha_hora"], format="%d/%m/%Y %H:%M", errors="coerce")
    )
    df_chk_raw["dia"] = df_chk_raw["fecha_dt"].dt.date
    df_chk_raw["hora"] = df_chk_raw["fecha_dt"].dt.hour
    df_valida = df_chk_raw.dropna(subset=["fecha_dt"]).reset_index(drop=True)

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    _dias_unicos = df_valida["dia"].nunique() if not df_valida.empty else 0
    col_m1.metric("Total fichadas", len(df_valida))
    col_m2.metric("Dias con actividad", _dias_unicos)
    _top_pac = df_valida["paciente"].value_counts().idxmax() if not df_valida.empty and "paciente" in df_valida.columns else "-"
    col_m3.metric("Paciente mas visitado", _top_pac)
    _hora_pico = df_valida["hora"].value_counts().idxmax() if not df_valida.empty else "-"
    col_m4.metric("Hora pico", f"{_hora_pico}:00" if _hora_pico != "-" else "-")

    with st.expander("Distribucion horaria", expanded=False):
        if not df_valida.empty:
            _bins_hora = list(range(0, 25))
            _hist_hora = pd.cut(df_valida["hora"], bins=_bins_hora, right=False, include_lowest=True)
            _dist_hora = _hist_hora.value_counts().sort_index()
            _df_hora = pd.DataFrame({"Hora": [f"{int(b.left):02d}:00-{int(b.right):02d}:00" for b in _dist_hora.index], "Fichadas": _dist_hora.values})
            st.bar_chart(_df_hora.set_index("Hora"))
        else:
            st.info("Sin datos para graficar distribucion horaria.")

    with st.expander("Top pacientes visitados", expanded=False):
        if not df_valida.empty and "paciente" in df_valida.columns:
            _top10 = df_valida["paciente"].value_counts().head(10)
            st.dataframe(_top10.reset_index().rename(columns={"index": "Paciente", "paciente": "Visitas"}), use_container_width=True)

    # 5. Tabla paginada
    df_chk = df_valida.iloc[::-1].reset_index(drop=True) if not df_valida.empty else pd.DataFrame()
    total_chk = len(df_chk)
    limite = st.selectbox("Registros por pagina", [20, 40, 80, 120], index=1, key="audit_chk_limite")
    paginas_chk = max((total_chk - 1) // limite + 1, 1)
    pag_chk = st.number_input("Pagina", min_value=1, max_value=paginas_chk, value=1, step=1, key="audit_chk_pag")
    ini_chk = (int(pag_chk) - 1) * limite
    fin_chk = ini_chk + limite
    df_chk_page = df_chk.iloc[ini_chk:fin_chk]
    st.caption(f"Mostrando {len(df_chk_page)} de {total_chk} fichada(s) en el periodo.")
    with lista_plegable("Asistencia del profesional (tabla)", count=len(df_chk_page), expanded=False, height=460):
        _cols_tabla = [c for c in ["fecha_hora", "paciente", "tipo", "gps"] if c in df_chk_page.columns]
        mostrar_dataframe_con_scroll(df_chk_page[_cols_tabla], height=400)

    # 6. Exportaciones
    col_exp1, col_exp2 = st.columns(2)
    csv_bytes = dataframe_csv_bytes(df_chk[_cols_tabla]) if not df_chk.empty else b""
    col_exp1.download_button(
        "Descargar CSV",
        data=csv_bytes,
        file_name=f"Asistencia_{sanitize_filename_component(prof_sel, 'prof')}_{fecha_desde.strftime('%d%m%Y')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    if FPDF_DISPONIBLE:
        if col_exp2.checkbox("Preparar PDF", value=False, key="audit_pdf_chk"):
            _pdf_data = df_chk[_cols_tabla] if len(df_chk) <= 500 else df_chk.head(500)[_cols_tabla]
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 15)
            pdf.cell(0, 12, safe_text(f"REPORTE ASISTENCIA - {mi_empresa}"), ln=True, align='C')
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, safe_text(f"Profesional: {prof_sel}"), ln=True)
            pdf.set_font("Arial", 'I', 10)
            pdf.cell(0, 8, safe_text(f"Periodo: {fecha_desde.strftime('%d/%m/%Y')} - {fecha_hasta.strftime('%d/%m/%Y')}"), ln=True)
            pdf.ln(10)
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(30, 8, safe_text("Fecha"), border=1)
            pdf.cell(60, 8, safe_text("Paciente"), border=1)
            pdf.cell(35, 8, safe_text("Accion"), border=1)
            pdf.cell(55, 8, safe_text("GPS"), border=1, ln=True)
            pdf.set_font("Arial", '', 9)
            for _, r in _pdf_data.iterrows():
                pdf.cell(30, 8, safe_text(str(r.get("fecha_hora", ""))[:16]), border=1)
                pdf.cell(60, 8, safe_text(str(r.get("paciente", "-"))[:35]), border=1)
                pdf.cell(35, 8, safe_text(str(r.get("tipo", "-"))[:15]), border=1)
                pdf.cell(55, 8, safe_text(str(r.get("gps", "-"))[:30]), border=1, ln=True)
            pdf_bytes = pdf_output_bytes(pdf)
            nombre_pdf = f"Asistencia_{sanitize_filename_component(prof_sel, 'prof')}_{fecha_desde.strftime('%d%m%Y')}.pdf"
            st.download_button("Descargar PDF", data=pdf_bytes, file_name=nombre_pdf, mime="application/pdf", use_container_width=True)
