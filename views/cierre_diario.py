import base64
from datetime import date

import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.export_utils import pdf_output_bytes, safe_text, sanitize_filename_component
from core.utils import ahora

FPDF_DISPONIBLE = False
try:
    from fpdf import FPDF
    FPDF_DISPONIBLE = True
except ImportError:
    pass


def render_cierre_diario(mi_empresa, user):
    st.subheader("Conciliacion y Cierre Diario de Operaciones")
    st.info("Selecciona un dia para auditar insumos, facturacion y stock sin cargar reportes pesados por defecto.")

    c1_rep, _ = st.columns([1, 2])
    fecha_reporte = c1_rep.date_input("Filtrar por Fecha", value=ahora().date())
    fecha_str = fecha_reporte.strftime("%d/%m/%Y")

    consumos_dia = [c for c in st.session_state.get("consumos_db", []) if c.get("fecha", "").startswith(fecha_str) and c.get("empresa") == mi_empresa]
    facturacion_dia = [f for f in st.session_state.get("facturacion_db", []) if f.get("fecha", "").startswith(fecha_str) and f.get("empresa") == mi_empresa]
    stock_actual = [i for i in st.session_state.get("inventario_db", []) if i.get("empresa") == mi_empresa]

    total_insumos = sum(c.get("cantidad", 0) for c in consumos_dia)
    total_facturado = sum(f.get("monto", 0) for f in facturacion_dia)
    stock_critico = len([s for s in stock_actual if s.get("stock", 0) <= 10])

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Insumos Consumidos", f"{total_insumos} unidades")
    col_m2.metric("Facturado del Dia", f"${total_facturado:,.2f}")
    col_m3.metric("Stock Critico", f"{stock_critico} insumos")

    st.divider()
    st.markdown("##### Navegacion del cierre")
    vista = st.radio(
        "Vista del cierre",
        ["Resumen del Dia", "Insumos", "Facturacion", "Stock", "Archivo de Cierres"],
        horizontal=True,
        label_visibility="collapsed",
        key="cierre_vista_radio",
    )

    if vista == "Resumen del Dia":
        col_r1, col_r2 = st.columns(2)
        with col_r1.container(border=True):
            st.markdown("#### Insumos del dia")
            if consumos_dia:
                st.caption(f"Se registraron {len(consumos_dia)} movimientos de insumos.")
                with st.container(height=340):
                    st.dataframe(
                        pd.DataFrame(consumos_dia).drop(columns="empresa", errors="ignore").tail(100).iloc[::-1],
                        use_container_width=True,
                        hide_index=True,
                    )
            else:
                st.info("No hubo registro de uso de insumos en este dia.")
        with col_r2.container(border=True):
            st.markdown("#### Facturacion del dia")
            if facturacion_dia:
                st.success(f"Total facturado: ${total_facturado:,.2f}")
                with st.container(height=340):
                    st.dataframe(
                        pd.DataFrame(facturacion_dia).drop(columns="empresa", errors="ignore").tail(100).iloc[::-1],
                        use_container_width=True,
                        hide_index=True,
                    )
            else:
                st.info("No hubo facturacion registrada en este dia.")

    elif vista == "Insumos":
        st.markdown(f"#### Insumos consumidos el {fecha_str}")
        if consumos_dia:
            with st.container(height=460, border=True):
                st.dataframe(
                    pd.DataFrame(consumos_dia).drop(columns="empresa", errors="ignore").tail(200).iloc[::-1],
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            st.info("No hubo registro de uso de insumos en este dia.")

    elif vista == "Facturacion":
        st.markdown(f"#### Procedimientos y facturacion del {fecha_str}")
        if facturacion_dia:
            st.success(f"Total facturado en el dia: ${total_facturado:,.2f}")
            with st.container(height=460, border=True):
                st.dataframe(
                    pd.DataFrame(facturacion_dia).drop(columns="empresa", errors="ignore").tail(200).iloc[::-1],
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            st.info("No hubo facturacion registrada en este dia.")

    elif vista == "Stock":
        st.markdown("#### Estado actual de stock")
        if stock_actual:
            with st.container(height=460, border=True):
                st.dataframe(
                    pd.DataFrame(stock_actual).drop(columns="empresa", errors="ignore").head(200),
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            st.info("No hay stock cargado.")

    st.divider()
    if FPDF_DISPONIBLE:
        st.markdown("#### Generar Documento Oficial de Cierre")

        def generar_pdf_cierre(fecha_para_pdf=None):
            fecha_str_pdf = fecha_str if fecha_para_pdf is None else (fecha_para_pdf.strftime("%d/%m/%Y") if isinstance(fecha_para_pdf, date) else str(fecha_para_pdf))
            consumos_pdf = [c for c in st.session_state.get("consumos_db", []) if c.get("fecha", "").startswith(fecha_str_pdf) and c.get("empresa") == mi_empresa]
            facturacion_pdf = [f for f in st.session_state.get("facturacion_db", []) if f.get("fecha", "").startswith(fecha_str_pdf) and f.get("empresa") == mi_empresa]
            total_facturado_pdf = sum(f.get("monto", 0) for f in facturacion_pdf)
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 15)
            pdf.cell(0, 12, safe_text(f"REPORTE DE CIERRE DIARIO - {mi_empresa}"), ln=True, align='C')
            pdf.set_font("Arial", 'I', 10)
            pdf.cell(0, 8, safe_text(f"Fecha auditada: {fecha_str_pdf} | Generado por: {user['nombre']} a las {ahora().strftime('%H:%M')}"), ln=True, align='C')
            pdf.ln(8)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, safe_text("1. INSUMOS CONSUMIDOS EN EL DIA"), ln=True)
            pdf.set_font("Arial", '', 10)
            for c in consumos_pdf[:80]:
                pdf.cell(0, 6, safe_text(f"- {c.get('cantidad')}x {c.get('insumo')} | Paciente: {c.get('paciente')}"), ln=True)
            pdf.ln(5)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, safe_text("2. PROCEDIMIENTOS Y FACTURACION DEL DIA"), ln=True)
            pdf.set_font("Arial", '', 10)
            for f in facturacion_pdf[:80]:
                pdf.cell(0, 6, safe_text(f"- ${f.get('monto')} | {f.get('serv')} | {f.get('paciente')}"), ln=True)
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(0, 10, safe_text(f"TOTAL FACTURADO DEL DIA: ${total_facturado_pdf:,.2f}"), ln=True)
            return pdf_output_bytes(pdf)

        if st.checkbox("Preparar y guardar cierre en PDF", value=False):
            pdf_bytes = generar_pdf_cierre()
            st.download_button("Descargar PDF del cierre", data=pdf_bytes, file_name=f"Cierre_Diario_{sanitize_filename_component(fecha_str.replace('/','-'), 'fecha')}.pdf", mime="application/pdf", use_container_width=True)
            if st.button("Guardar cierre en historial", use_container_width=True, type="primary"):
                b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                st.session_state["reportes_diarios_db"].append({
                    "fecha_reporte": fecha_str,
                    "fecha_generacion": ahora().strftime("%d/%m/%Y %H:%M"),
                    "generado_por": user["nombre"],
                    "empresa": mi_empresa,
                    "pdf_base64": b64_pdf,
                })
                guardar_datos()
                st.success(f"Cierre del dia {fecha_str} guardado exitosamente.")
                st.rerun()

    if vista == "Archivo de Cierres":
        st.divider()
        st.markdown("#### Archivo historico de cierres diarios")
        reportes_mios = [r for r in reversed(st.session_state.get("reportes_diarios_db", [])) if r.get("empresa") == mi_empresa]
        if reportes_mios:
            with st.container(height=460):
                for i, r in enumerate(reportes_mios[:60]):
                    with st.container(border=True):
                        c1_hist, c2_hist = st.columns([4, 1])
                        c1_hist.markdown(f"**Cierre del dia {r['fecha_reporte']}**")
                        c1_hist.caption(f"Generado el {r['fecha_generacion']} por {r['generado_por']}")
                        pdf_bytes = base64.b64decode(r['pdf_base64'])
                        c2_hist.download_button(
                            "Descargar PDF",
                            data=pdf_bytes,
                            file_name=f"Cierre_Diario_{sanitize_filename_component(r['fecha_reporte'].replace('/','-'), 'fecha')}.pdf",
                            mime="application/pdf",
                            key=f"cierre_pdf_{i}",
                            use_container_width=True,
                        )
        else:
            st.info("Aun no hay reportes de cierre diario guardados.")
