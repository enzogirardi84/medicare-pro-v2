import io

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


def render_caja(paciente_sel, mi_empresa, user, rol):
    rol_normalizado = str(rol or "").strip().lower()
    if not paciente_sel:
        st.info("Selecciona un paciente en el menu lateral para ver su cuenta corriente.")
        return

    st.subheader("Facturacion y Caja Diaria")

    fact_paciente = [
        f for f in st.session_state.get("facturacion_db", [])
        if f.get("paciente") == paciente_sel and f.get("empresa") == mi_empresa
    ]

    total_cobrado = sum(f.get("monto", 0) for f in fact_paciente if "Cobrado" in f.get("estado", ""))
    total_pendiente = sum(f.get("monto", 0) for f in fact_paciente if "Pendiente" in f.get("estado", ""))

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Total Cobrado", f"${total_cobrado:,.2f}")
    col_m2.metric("Pendiente de Cobro", f"${total_pendiente:,.2f}")
    col_m3.metric("Practicas Registradas", len(fact_paciente))

    st.divider()

    with st.form("caja_form", clear_on_submit=True):
        st.markdown("##### Registrar Nuevo Movimiento")
        c1, c2 = st.columns([3, 1])
        practicas_comunes = [
            "Consulta Medica Domiciliaria", "Aplicacion IM/SC", "Curacion de Heridas",
            "Colocacion/Cambio de Sonda", "Control de Signos Vitales",
            "Guardia de Enfermeria (12hs)", "Guardia de Enfermeria (24hs)",
            "Sesion de Kinesiologia", "Insumos Extras", "-- Otro (Especificar manualmente) --",
        ]
        practica_sel = c1.selectbox("Tipo de Servicio / Nomenclador", practicas_comunes)
        practica_manual = c1.text_input("Detalle adicional")
        mon = c2.number_input("Monto a Facturar ($)", min_value=0.0, step=500.0, value=0.0)

        c3, c4 = st.columns(2)
        opciones_pago = [
            "Efectivo", "Mercado Pago / MODO", "Transferencia Bancaria", "Tarjeta", "Link de Pago",
            "Bono / Coseguro", "Cobertura / Obra Social", "Cheque",
        ]
        metodo = c3.selectbox("Metodo de Pago", opciones_pago)
        estado = c4.radio("Estado del Cobro", ["Cobrado", "Pendiente / A Facturar"], horizontal=True)

        if st.form_submit_button("Registrar Cobro / Practica", use_container_width=True, type="primary"):
            desc_final = practica_manual.strip() if practica_sel == "-- Otro (Especificar manualmente) --" else f"{practica_sel} {('- ' + practica_manual.strip()) if practica_manual.strip() else ''}"
            if desc_final.strip() and mon > 0:
                st.session_state["facturacion_db"].append({
                    "paciente": paciente_sel,
                    "serv": desc_final.strip(),
                    "monto": mon,
                    "metodo": metodo,
                    "estado": estado,
                    "fecha": ahora().strftime("%d/%m/%Y %H:%M"),
                    "empresa": mi_empresa,
                    "operador": user["nombre"],
                    "operador_dni": user.get("dni", "S/D"),
                })
                guardar_datos()
                st.success(f"${mon:,.2f} registrado correctamente.")
                st.rerun()
            else:
                st.error("Debe ingresar una descripcion valida y un monto mayor a $0.")

    st.divider()
    st.markdown("#### Historial de Recibos del Paciente")
    if fact_paciente:
        limite = seleccionar_limite_registros(
            "Movimientos a mostrar",
            len(fact_paciente),
            key="caja_limite_recibos",
            default=30,
            opciones=(10, 20, 30, 50, 100, 200),
        )

        def generar_recibo_pdf(mov):
            if not FPDF_DISPONIBLE:
                return b""
            pdf = FPDF(format="A5")
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, safe_text(f"RECIBO - {mi_empresa}"), ln=True, align='C')
            pdf.set_font("Arial", '', 10)
            pdf.cell(0, 6, safe_text(f"Fecha: {mov['fecha']}"), ln=True, align='C')
            pdf.cell(0, 6, safe_text(f"Operador: {mov.get('operador', 'S/D')} (DNI: {mov.get('operador_dni', 'S/D')})"), ln=True, align='C')
            pdf.ln(10)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 8, safe_text(f"Recibimos de: {mov['paciente']}"), ln=True)
            pdf.ln(4)
            pdf.set_font("Arial", '', 11)
            pdf.multi_cell(0, 8, safe_text(f"Concepto: {mov['serv']}"))
            pdf.cell(0, 8, safe_text(f"Medio de pago: {mov.get('metodo', 'S/D')}"), ln=True)
            pdf.cell(0, 8, safe_text(f"Estado: {mov.get('estado', 'Cobrado')}"), ln=True)
            pdf.ln(8)
            pdf.set_fill_color(240, 240, 240)
            pdf.set_font("Arial", 'B', 18)
            pdf.cell(0, 14, safe_text(f"TOTAL: ${mov['monto']:,.2f}"), 1, 1, 'C', True)
            return pdf_output_bytes(pdf)

        with st.container(height=420):
            for i, mov in enumerate(reversed(fact_paciente[-limite:])):
                with st.container(border=True):
                    col_r1, col_r2 = st.columns([4, 1])
                    with col_r1:
                        st.markdown(f"**{mov['fecha']}** - {mov['serv']}")
                        st.caption(f"{mov.get('estado', 'S/D')} | {mov.get('metodo', 'S/D')} | ${mov['monto']:,.2f}")
                    with col_r2:
                        if FPDF_DISPONIBLE and st.checkbox("PDF", key=f"pdf_mov_{i}", value=False):
                            pdf_bytes = generar_recibo_pdf(mov)
                            st.download_button("Descargar PDF", data=pdf_bytes, file_name=f"Recibo_{sanitize_filename_component(mov.get('paciente', i+1), 'recibo')}_{i+1}.pdf", mime="application/pdf", key=f"pdf_btn_{i}", use_container_width=True)
    else:
        st.info("No hay movimientos registrados para este paciente aun.")

    if es_control_total(rol_normalizado):
        st.divider()
        st.markdown("#### Auditoria de Facturacion General")
        df_caja = pd.DataFrame([f for f in st.session_state.get("facturacion_db", []) if f.get("empresa") == mi_empresa])
        if not df_caja.empty:
            filtro_caja = st.text_input("Buscar por paciente, practica, fecha o estado", "")
            if filtro_caja:
                mask = df_caja.astype(str).apply(lambda x: x.str.contains(filtro_caja, case=False, na=False)).any(axis=1)
                df_caja = df_caja[mask]

            df_mostrar = df_caja.rename(columns={
                "fecha": "Fecha", "paciente": "Paciente", "serv": "Concepto",
                "monto": "Monto ($)", "metodo": "Medio de Pago", "estado": "Estado", "operador": "Registro",
            }).drop(columns=["empresa", "operador_dni"], errors='ignore')

            limite = seleccionar_limite_registros(
                "Filas de caja",
                len(df_mostrar),
                key="caja_limite_auditoria",
                default=100,
                opciones=(20, 50, 100, 200, 500),
            )
            mostrar_dataframe_con_scroll(df_mostrar.tail(limite).iloc[::-1], height=400)

            csv_data = dataframe_csv_bytes(df_mostrar)
            st.download_button("Descargar CSV de Caja", data=csv_data, file_name=f"Caja_General_{sanitize_filename_component(mi_empresa, 'empresa')}_{ahora().strftime('%d_%m_%Y')}.csv", mime="text/csv", use_container_width=True)
        else:
            st.info("No hay registros de facturacion aun.")
