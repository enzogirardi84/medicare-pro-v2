import pandas as pd
import streamlit as st
from datetime import datetime

from fpdf import FPDF

from core.export_utils import dataframe_csv_bytes, sanitize_filename_component
from core.view_helpers import bloque_mc_grid_tarjetas, lista_plegable
from core.utils import mostrar_dataframe_con_scroll, seleccionar_limite_registros


def _texto_filtro_registro(reg):
    piezas = [
        str(reg.get("paciente", "") or ""),
        str(reg.get("accion", "") or ""),
        str(reg.get("actor", "") or ""),
        str(reg.get("detalle", "") or ""),
        str(reg.get("referencia", "") or ""),
        str(reg.get("modulo", "") or ""),
        str(reg.get("criticidad", "") or ""),
    ]
    return " | ".join(piezas).lower()


def _clave_orden_desc(reg):
    iso = str(reg.get("fecha_iso", "") or "").strip()
    if iso:
        return iso
    fecha = str(reg.get("fecha", "") or "").strip()
    return fecha


def _safe_pdf_text(text, max_len=80):
    """Trunca y limpia texto para evitar errores de encoding en FPDF."""
    if text is None:
        return ""
    text = str(text)
    # FPDF usa latin-1 por defecto; reemplazamos caracteres no soportados
    try:
        text.encode("latin-1")
    except UnicodeEncodeError:
        text = text.encode("latin-1", "replace").decode("latin-1")
    if len(text) > max_len:
        text = text[: max_len - 3] + "..."
    return text


def generar_pdf_auditoria_legal(df, nombre_empresa=""):
    """Genera un PDF profesional con el registro de auditoría legal."""
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Colores corporativos oscuros
    HEADER_BG = (30, 41, 59)       # slate-800
    HEADER_TEXT = (255, 255, 255)  # white
    ROW_ALT = (241, 245, 249)        # slate-100
    ROW_BASE = (255, 255, 255)       # white
    BORDER = (148, 163, 184)         # slate-400
    TEXT_DARK = (15, 23, 42)         # slate-900

    # Encabezado
    pdf.set_fill_color(*HEADER_BG)
    pdf.rect(10, 10, 277, 20, style="F")
    pdf.set_text_color(*HEADER_TEXT)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_xy(15, 16)
    pdf.cell(0, 8, "Auditoría Legal", ln=True)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(15, 23)
    empresa_str = _safe_pdf_text(nombre_empresa, 60)
    pdf.cell(0, 6, f"Empresa: {empresa_str}  |  Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)

    # Tabla
    pdf.set_y(38)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*TEXT_DARK)

    columnas = ["Fecha", "Paciente", "Modulo", "Accion", "Actor", "Criticidad", "Detalle"]
    anchos = [30, 40, 30, 35, 35, 25, 82]

    # Encabezado de tabla
    pdf.set_fill_color(*HEADER_BG)
    pdf.set_text_color(*HEADER_TEXT)
    for col, w in zip(columnas, anchos):
        pdf.cell(w, 8, col, border=1, align="C", fill=True)
    pdf.ln()

    # Filas
    pdf.set_font("Helvetica", "", 8)
    for idx, row in df.iterrows():
        fill = ROW_ALT if idx % 2 == 0 else ROW_BASE
        pdf.set_fill_color(*fill)
        pdf.set_text_color(*TEXT_DARK)

        fecha = _safe_pdf_text(row.get("fecha", ""), 18)
        paciente = _safe_pdf_text(row.get("paciente", ""), 25)
        modulo = _safe_pdf_text(row.get("modulo", ""), 20)
        accion = _safe_pdf_text(row.get("accion", ""), 25)
        actor = _safe_pdf_text(row.get("actor", ""), 25)
        criticidad = _safe_pdf_text(row.get("criticidad", ""), 15)
        detalle = _safe_pdf_text(row.get("detalle", ""), 55)

        # Color de criticidad
        criticidad_raw = str(row.get("criticidad", "")).lower()
        if "alta" in criticidad_raw or "critica" in criticidad_raw:
            pdf.set_text_color(220, 38, 38)
        elif "media" in criticidad_raw:
            pdf.set_text_color(234, 179, 8)
        else:
            pdf.set_text_color(*TEXT_DARK)

        pdf.cell(anchos[0], 7, fecha, border=1, align="C", fill=True)
        pdf.cell(anchos[1], 7, paciente, border=1, align="L", fill=True)
        pdf.cell(anchos[2], 7, modulo, border=1, align="L", fill=True)
        pdf.cell(anchos[3], 7, accion, border=1, align="L", fill=True)
        pdf.cell(anchos[4], 7, actor, border=1, align="L", fill=True)
        pdf.cell(anchos[5], 7, criticidad, border=1, align="C", fill=True)
        pdf.set_text_color(*TEXT_DARK)
        pdf.cell(anchos[6], 7, detalle, border=1, align="L", fill=True)
        pdf.ln()

    # Pie de pagina
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 10, f"Generado por MediCare Pro  |  {len(df)} registros", align="C")

    return bytes(pdf.output(dest="S"))


def render_auditoria_legal(mi_empresa, user):
    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Auditoria legal central</h2>
            <p class="mc-hero-text">Concentra eventos clinicos y documentales con valor legal: medicacion, consentimientos, emergencias, escalas y cuidados.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Trazabilidad</span>
                <span class="mc-chip">Actor y matricula</span>
                <span class="mc-chip">Paciente</span>
                <span class="mc-chip">Fecha y hora</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ("Eventos", "Altas sensibles: equipo, medicacion, consentimientos, emergencias, clinicas."),
            ("Filtros", "Texto libre y paciente para acotar antes de exportar."),
            ("CSV", "Descarga completa del conjunto filtrado."),
        ]
    )
    st.caption(
        "Los registros se generan al usar modulos con auditoria (Recetas, Evolucion, Equipo, Clinicas, etc.). Ajusta el limite de filas si la lista es larga."
    )

    registros = list(st.session_state.get("auditoria_legal_db", []) or [])
    if not registros:
        st.warning(
            "Todavia no hay eventos en la auditoria legal. Apareceran cuando el equipo registre acciones auditadas (evoluciones, recetas, usuarios, suspension de clinicas, etc.)."
        )
        return

    filtro = st.text_input("Buscar por paciente, accion, actor o detalle")
    pacientes = sorted({str(r.get("paciente", "") or "").strip() for r in registros if str(r.get("paciente", "") or "").strip()})
    paciente_sel = st.selectbox("Paciente", ["Todos"] + pacientes)
    if paciente_sel != "Todos":
        registros = [r for r in registros if str(r.get("paciente", "") or "").strip() == paciente_sel]

    if filtro:
        f_low = str(filtro).strip().lower()
        registros = [r for r in registros if f_low in _texto_filtro_registro(r)]
        if not registros:
            st.warning("No hay coincidencias con la busqueda. Proba otro texto o limpia el filtro.")
            return

    if not registros:
        st.info("No hay eventos para el filtro seleccionado.")
        return

    registros = sorted(registros, key=_clave_orden_desc, reverse=True)
    total_filtrado = len(registros)

    limite = seleccionar_limite_registros(
        "Eventos por página",
        total_filtrado,
        key=f"auditoria_legal_{mi_empresa}_{user.get('nombre', '')}",
        default=50,
    )
    paginas = max((total_filtrado - 1) // max(limite, 1) + 1, 1)
    pagina = st.number_input("Página", min_value=1, max_value=paginas, value=1, step=1)
    inicio = (int(pagina) - 1) * limite
    fin = inicio + limite
    pagina_regs = registros[inicio:fin]
    st.caption(f"Mostrando {len(pagina_regs)} de {total_filtrado} evento(s) filtrado(s).")

    df_page = pd.DataFrame(pagina_regs)
    with lista_plegable("Eventos de auditoría legal", count=len(df_page), expanded=False, height=500):
        mostrar_dataframe_con_scroll(df_page, height=440)

    filtro_key = f"{paciente_sel}|{str(filtro or '').strip().lower()}|{total_filtrado}"
    cache_key = "auditoria_legal_pdf"
    if st.button("Preparar PDF auditoría legal", use_container_width=True):
        pdf_bytes = generar_pdf_auditoria_legal(pd.DataFrame(registros), mi_empresa)
        st.session_state[cache_key] = pdf_bytes

    if cache_key in st.session_state and st.session_state[cache_key]:
        st.download_button(
            label="Descargar PDF",
            data=st.session_state[cache_key],
            file_name=f"auditoria_legal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)
