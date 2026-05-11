from core.alert_toasts import queue_toast
import io

import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio, bloque_mc_grid_tarjetas, lista_plegable
from core.export_utils import dataframe_csv_bytes, pdf_output_bytes, safe_text, sanitize_filename_component
from core.utils import ahora, es_control_total, mostrar_dataframe_con_scroll, seleccionar_limite_registros
from core.db_sql import get_facturacion_by_empresa, insert_facturacion
from core.nextgen_sync import _obtener_uuid_paciente, _obtener_uuid_empresa
from core.app_logging import log_event

FPDF_DISPONIBLE = False
try:
    from fpdf import FPDF
    FPDF_DISPONIBLE = True
except ImportError:
    pass  # Intencional: fpdf es opcional para comprobantes


def render_caja(paciente_sel, mi_empresa, user, rol):
    rol_normalizado = str(rol or "").strip().lower()
    if not paciente_sel:
        aviso_sin_paciente()
        return

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Facturacion y caja</h2>
            <p class="mc-hero-text">Cuenta corriente del paciente: practicas, montos, metodo de pago y estado. Exporta CSV o PDF cuando lo necesites.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Nomenclador</span>
                <span class="mc-chip">Cobrado / pendiente</span>
                <span class="mc-chip">Exportacion</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ("Practicas", "Registra nomenclador, monto y estado de cobro."),
            ("Resumen", "Metricas de cobrado y pendiente por paciente."),
            ("Exportar", "Genera CSV o PDF cuando lo necesites."),
        ]
    )
    st.caption(
        "Las metricas usan solo movimientos de este paciente en tu clinica. Registra cada practica con monto y estado; el historial permite PDF por movimiento. "
        "Coordinacion ve abajo la auditoria general de caja."
    )

    # 1. Intentar leer desde PostgreSQL (Hybrid Read)
    fact_empresa = []
    try:
        empresa_uuid = _obtener_uuid_empresa(mi_empresa)
        if empresa_uuid:
            fact_sql = get_facturacion_by_empresa(empresa_uuid)
            if fact_sql:
                for f in fact_sql:
                    dt = pd.to_datetime(f.get("fecha_emision", ""), errors="coerce")
                    paciente_nombre = f.get("pacientes", {}).get("nombre_completo", "N/A") if isinstance(f.get("pacientes"), dict) else "N/A"
                    # Buscar el ID visual del paciente (Nombre - DNI)
                    paciente_visual = paciente_nombre
                    for p in st.session_state.get("pacientes_db", []):
                        if p.startswith(paciente_nombre):
                            paciente_visual = p
                            break
                            
                    try:
                        _monto = float(f.get("monto_total") or 0)
                    except Exception:
                        _monto = 0.0
                    fact_empresa.append({
                        "paciente": paciente_visual,
                        "serv": f.get("concepto", ""),
                        "monto": _monto,
                        "metodo": f.get("observaciones", ""),
                        "estado": f.get("estado", ""),
                        "fecha": dt.strftime("%d/%m/%Y %H:%M") if pd.notnull(dt) else "",
                        "empresa": mi_empresa,
                        "operador": "Sistema",
                        "operador_dni": "S/D",
                        "id_sql": f.get("id")
                    })
    except Exception as e:
        log_event("error_leer_facturacion_sql", str(e))

    # 2. Fallback a JSON si SQL falla o esta vacio
    if not fact_empresa:
        fact_empresa = [f for f in st.session_state.get("facturacion_db", []) if f.get("empresa") == mi_empresa]

    # Cache simple para evitar recálculos innecesarios en reruns
    cache_key_caja = f"_caja_cache_{paciente_sel}_{len(fact_empresa)}"
    if cache_key_caja not in st.session_state:
        fact_paciente = [f for f in fact_empresa if f.get("paciente") == paciente_sel]
        total_cobrado = sum((f.get("monto") or 0) for f in fact_paciente if "Cobrado" in f.get("estado", ""))
        total_pendiente = sum((f.get("monto") or 0) for f in fact_paciente if "Pendiente" in f.get("estado", ""))
        st.session_state[cache_key_caja] = {
            "fact_paciente": fact_paciente,
            "total_cobrado": total_cobrado,
            "total_pendiente": total_pendiente
        }
    
    cached = st.session_state[cache_key_caja]
    fact_paciente = cached["fact_paciente"]
    total_cobrado = cached["total_cobrado"]
    total_pendiente = cached["total_pendiente"]

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Total Cobrado", f"${total_cobrado:,.2f}")
    col_m2.metric("Pendiente de Cobro", f"${total_pendiente:,.2f}")
    col_m3.metric("Practicas Registradas", len(fact_paciente))

    tabs_caja = st.tabs(["💰 Registrar cobro", "📋 Historial del paciente", "📊 Auditoría general"])

    with tabs_caja[0]:
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
        # Validación: monto máximo 500000 (500k) para seguridad
        mon = c2.number_input("Monto a Facturar ($)", min_value=0.0, step=500.0, value=0.0, max_value=500000.0)

        c3, c4 = st.columns(2)
        opciones_pago = [
            "Efectivo", "Mercado Pago / MODO", "Transferencia Bancaria", "Tarjeta", "Link de Pago",
            "Bono / Coseguro", "Cobertura / Obra Social", "Cheque",
        ]
        metodo = c3.selectbox("Metodo de Pago", opciones_pago)
        estado = c4.radio("Estado del Cobro", ["Cobrado", "Pendiente / A Facturar"], horizontal=False)

        if st.form_submit_button("💰 Registrar Cobro / Practica", use_container_width=True, type="primary"):
            # Validación extra de seguridad
            desc_final = practica_manual.strip() if practica_sel == "-- Otro (Especificar manualmente) --" else f"{practica_sel} {('- ' + practica_manual.strip()) if practica_manual.strip() else ''}"
            
            # Validaciones de seguridad
            if not desc_final.strip():
                st.error("⚠️ Descripción vacía. Complete el campo.")
            elif mon <= 0:
                st.error("⚠️ El monto debe ser mayor a $0.")
            elif mon > 500000:
                st.error("⚠️ Monto máximo permitido: $500,000")
            else:
                fecha_str = ahora().strftime("%d/%m/%Y %H:%M")
                
                # 1. Guardar en SQL (Dual-Write)
                try:
                    empresa_uuid = _obtener_uuid_empresa(mi_empresa)
                    _partes_pac = paciente_sel.split(" - ")
                    _dni_pac = _partes_pac[1].strip() if len(_partes_pac) > 1 else ""
                    paciente_uuid = _obtener_uuid_paciente(_dni_pac, empresa_uuid) if empresa_uuid and _dni_pac else None
                    if empresa_uuid and paciente_uuid:
                        datos_sql = {
                            "empresa_id": empresa_uuid,
                            "paciente_id": paciente_uuid,
                            "fecha_emision": ahora().isoformat(),
                            "numero_comprobante": "",
                            "concepto": desc_final.strip(),
                            "monto_total": mon,
                            "estado": estado,
                            "obra_social": "",
                            "observaciones": metodo # Guardamos el método en observaciones
                        }
                        insert_facturacion(datos_sql)
                        log_event("facturacion_sql_insert", f"Paciente: {paciente_uuid}")
                except Exception as e:
                    log_event("error_facturacion_sql", str(e))

                # 2. Guardar en JSON (Legacy)
                if "facturacion_db" not in st.session_state:
                    st.session_state["facturacion_db"] = []
                st.session_state["facturacion_db"].append({
                    "paciente": paciente_sel,
                    "serv": desc_final.strip(),
                    "monto": mon,
                    "metodo": metodo,
                    "estado": estado,
                    "fecha": fecha_str,
                    "empresa": mi_empresa,
                    "operador": user.get("nombre", "Sistema"),
                    "operador_dni": user.get("dni", "S/D"),
                })
                from core.database import _trim_db_list
                _trim_db_list("facturacion_db", 500)
                guardar_datos(spinner=True)
                queue_toast(f"✅ ${mon:,.2f} registrado - {desc_final.strip()[:30]}...")
                st.rerun()

    with tabs_caja[1]:
        st.caption(f"Mostrando movimientos de **{paciente_sel}**")
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
                from core.clinical_exports import _pdf_header_oscuro
                _cobrado = "Cobrado" in mov.get("estado", "")
                _badge_rgb = (13, 90, 80) if _cobrado else (130, 80, 0)
                pdf = FPDF(format="A5")
                pdf.set_margins(12, 10, 12)
                pdf.set_auto_page_break(auto=True, margin=12)
                pdf.add_page()
                _pdf_header_oscuro(
                    pdf, mi_empresa,
                    "RECIBO DE COBRO",
                    subtitulo=safe_text(f"Fecha: {mov['fecha']}  |  Operador: {mov.get('operador','S/D')}"),
                    badge_txt=mov.get("estado", "Cobrado"),
                    badge_rgb=_badge_rgb,
                )
                pdf.ln(2)
                pdf.set_font("Arial", "B", 10)
                pdf.cell(0, 6, safe_text(f"Recibimos de: {mov.get('paciente', '')}"), ln=True)
                pdf.ln(2)
                pdf.set_font("Arial", "", 9)
                pdf.multi_cell(0, 6, safe_text(f"Concepto: {mov['serv']}"))
                pdf.cell(0, 6, safe_text(f"Medio de pago: {mov.get('metodo', 'S/D')}"), ln=True)
                pdf.ln(6)
                pdf.set_fill_color(22, 38, 68)
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Arial", "B", 16)
                pdf.cell(0, 14, safe_text(f"TOTAL: ${mov['monto']:,.2f}"), 1, 1, "C", True)
                pdf.set_text_color(0, 0, 0)
                pdf.ln(8)
                usable = pdf.w - pdf.l_margin - pdf.r_margin
                pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + usable * 0.45, pdf.get_y())
                pdf.set_xy(pdf.l_margin, pdf.get_y() + 1)
                pdf.set_font("Arial", "", 7)
                pdf.cell(0, 4, "Firma / Aclaracion", ln=True)
                return pdf_output_bytes(pdf)

            with st.container(height=480, border=False):
                for i, mov in enumerate(reversed(fact_paciente[-limite:])):
                    with st.container(border=True):
                        col_r1, col_r2 = st.columns([4, 1])
                        with col_r1:
                            st.markdown(f"**{mov['fecha']}** - {mov['serv']}")
                            st.caption(f"{mov.get('estado', 'S/D')} | {mov.get('metodo', 'S/D')} | ${mov['monto']:,.2f}")
                        with col_r2:
                            if FPDF_DISPONIBLE and st.checkbox("PDF", key=f"pdf_mov_{i}", value=False):
                                pdf_bytes = generar_recibo_pdf(mov)
                                st.download_button(
                                    "Descargar PDF",
                                    data=pdf_bytes,
                                    file_name=f"Recibo_{sanitize_filename_component(mov.get('paciente', i+1), 'recibo')}_{i+1}.pdf",
                                    mime="application/pdf",
                                    key=f"pdf_btn_{i}",
                                    use_container_width=True,
                                )
        else:
            st.warning(
                "No hay movimientos de facturacion para este paciente. Registralos en la pestaña **Registrar cobro**."
            )

    with tabs_caja[2]:
        if es_control_total(rol_normalizado):
            st.caption("Vista global de la empresa: busca por texto, acota filas y exporta CSV.")
            df_caja = pd.DataFrame(fact_empresa)
            if not df_caja.empty:
                filtro_caja = st.text_input("Buscar por paciente, practica, fecha o estado", "")
                if filtro_caja:
                    mask = df_caja.astype(str).apply(lambda x: x.str.contains(filtro_caja, case=False, na=False)).any(axis=1)
                    df_caja = df_caja[mask]

                df_mostrar = df_caja.rename(columns={
                    "fecha": "Fecha", "paciente": "Paciente", "serv": "Concepto",
                    "monto": "Monto ($)", "metodo": "Medio de Pago", "estado": "Estado", "operador": "Registro",
                }).drop(columns=["empresa", "operador_dni", "id_sql"], errors='ignore')

                limite_aud = seleccionar_limite_registros(
                    "Filas de caja",
                    len(df_mostrar),
                    key="caja_limite_auditoria",
                    default=100,
                    opciones=(20, 50, 100, 200, 500),
                )
                mostrar_dataframe_con_scroll(df_mostrar.tail(limite_aud).iloc[::-1], height=420)
                csv_data = dataframe_csv_bytes(df_mostrar)
                st.download_button("Descargar CSV de Caja", data=csv_data, file_name=f"Caja_General_{sanitize_filename_component(mi_empresa, 'empresa')}_{ahora().strftime('%d_%m_%Y')}.csv", mime="text/csv", use_container_width=True)
            else:
                bloque_estado_vacio(
                    "Caja sin movimientos",
                    "No hay registros de facturación para esta clínica todavía.",
                    sugerencia="Los movimientos del paciente se cargan en la pestaña Registrar cobro.",
                )
        else:
            st.info("La auditoría general está disponible solo para coordinación y administración.")
