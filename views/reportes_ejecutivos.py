from datetime import datetime

import streamlit as st

from core.app_logging import log_event
from core.reporte_ejecutivo import generar_reporte_ejecutivo
from core.view_helpers import bloque_estado_vacio


def render_reportes_ejecutivos(mi_empresa, rol):
    st.markdown(
        '<div class="mc-hero"><h2 class="mc-hero-title">Reportes Ejecutivos</h2>'
        '<p class="mc-hero-text">Galería central de reportes exportables para la toma de decisiones.</p></div>',
        unsafe_allow_html=True,
    )

    rol_n = str(rol or "").strip().lower()
    if rol_n not in {"admin", "superadmin"}:
        bloque_estado_vacio(
            "Acceso restringido",
            "Solo administradores pueden acceder a esta sección.",
        )
        return

    r1, r2 = st.columns(2)

    with r1:
        st.markdown("##### Reporte Ejecutivo General")
        st.caption("Resumen de pacientes, facturación, stock bajo y actividad reciente.")
        if st.button("Generar PDF Ejecutivo", key="btn_pdf_ejecutivo", type="primary", use_container_width=True):
            with st.spinner("Generando reporte..."):
                pdf_bytes = generar_reporte_ejecutivo(mi_empresa)
                if pdf_bytes:
                    st.download_button(
                        label="Descargar PDF",
                        data=pdf_bytes,
                        file_name=f"reporte_ejecutivo_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                        mime="application/pdf",
                        key="dl_pdf_ejecutivo",
                        use_container_width=True,
                    )
                    st.success("Reporte listo para descargar.")
                else:
                    st.error("Error al generar el reporte.")

    with r2:
        st.markdown("##### Reporte Financiero")
        st.caption("Dashboard financiero con ingresos, gastos y análisis por obra social.")
        if st.button("Abrir Reporte Financiero", key="btn_financiero", use_container_width=True):
            st.session_state["modulo_actual"] = "Estadisticas"
            st.rerun()

    st.divider()
    r3, r4 = st.columns(2)

    with r3:
        st.markdown("##### Cierre Diario")
        st.caption("Resumen de operaciones del día, ingresos, egresos y movimientos de caja.")
        if st.button("Ir a Cierre Diario", key="btn_cierre", use_container_width=True):
            st.session_state["modulo_actual"] = "Cierre Diario"
            st.rerun()

    with r4:
        st.markdown("##### Reporte de Auditoría")
        st.caption("Traza de eventos del sistema, accesos y cambios críticos.")
        if st.button("Ir a Auditoría", key="btn_auditoria", use_container_width=True):
            st.session_state["modulo_actual"] = "Auditoria"
            st.rerun()

    st.divider()

    st.markdown("##### Exportación de datos")
    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        _exportar_csv_pacientes()
    with col_d2:
        _exportar_csv_agenda()
    with col_d3:
        _exportar_csv_facturacion()

    st.divider()
    st.caption("Los reportes se generan con los datos actuales del sistema.")


def _exportar_csv_pacientes():
    if st.button("Exportar Pacientes (CSV)", use_container_width=True, key="btn_csv_pac"):
        pacientes = st.session_state.get("pacientes_db", [])
        detalles = st.session_state.get("detalles_pacientes_db", {})
        rows = []
        for p in pacientes:
            d = detalles.get(p, {})
            rows.append({
                "paciente": p,
                "dni": d.get("dni", ""),
                "telefono": d.get("telefono", ""),
                "direccion": d.get("direccion", ""),
                "obra_social": d.get("obra_social", ""),
                "estado": d.get("estado", "Activo"),
                "alergias": d.get("alergias", ""),
            })
        if rows:
            import pandas as pd
            import io
            df = pd.DataFrame(rows)
            buf = io.BytesIO()
            df.to_csv(buf, index=False, encoding="utf-8-sig")
            st.download_button("Descargar CSV", data=buf.getvalue(),
                               file_name=f"pacientes_{datetime.now().strftime('%Y%m%d')}.csv",
                               mime="text/csv", key="dl_csv_pac")
        else:
            st.warning("Sin datos de pacientes.")


def _exportar_csv_agenda():
    if st.button("Exportar Agenda (CSV)", use_container_width=True, key="btn_csv_agenda"):
        agenda = st.session_state.get("agenda_db", [])
        if agenda:
            import pandas as pd
            import io
            df = pd.DataFrame(agenda)
            buf = io.BytesIO()
            df.to_csv(buf, index=False, encoding="utf-8-sig")
            st.download_button("Descargar CSV", data=buf.getvalue(),
                               file_name=f"agenda_{datetime.now().strftime('%Y%m%d')}.csv",
                               mime="text/csv", key="dl_csv_agenda")
        else:
            st.warning("Sin datos de agenda.")


def _exportar_csv_facturacion():
    if st.button("Exportar Facturación (CSV)", use_container_width=True, key="btn_csv_fact"):
        facturas = st.session_state.get("facturacion_db", [])
        if facturas:
            import pandas as pd
            import io
            df = pd.DataFrame(facturas)
            buf = io.BytesIO()
            df.to_csv(buf, index=False, encoding="utf-8-sig")
            st.download_button("Descargar CSV", data=buf.getvalue(),
                               file_name=f"facturacion_{datetime.now().strftime('%Y%m%d')}.csv",
                               mime="text/csv", key="dl_csv_fact")
        else:
            st.warning("Sin datos de facturación.")
