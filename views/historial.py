import base64

import pandas as pd
import streamlit as st

from core.clinical_exports import (
    build_backup_pdf_bytes,
    build_history_pdf_bytes,
    build_patient_excel_bytes,
    collect_patient_sections,
)
from core.utils import mostrar_dataframe_con_scroll


def _limitar_registros(opcion_limite):
    if "10" in opcion_limite:
        return 10
    if "30" in opcion_limite:
        return 30
    if "50" in opcion_limite:
        return 50
    return 200


def _render_lazy_download(container, key_base, prepare_label, download_label, build_fn, file_name, mime, unavailable_message=None):
    cache_key = f"lazy_export_{key_base}"
    payload = st.session_state.get(cache_key)

    if payload:
        container.download_button(
            download_label,
            data=payload,
            file_name=file_name,
            mime=mime,
            key=f"download_{key_base}",
            use_container_width=True,
        )
        if container.button("Actualizar archivo", key=f"refresh_{key_base}", use_container_width=True):
            st.session_state.pop(cache_key, None)
            st.rerun()
        return

    if container.button(prepare_label, key=f"prepare_{key_base}", use_container_width=True):
        with st.spinner("Preparando archivo..."):
            payload = build_fn()
        if payload:
            st.session_state[cache_key] = payload
            st.rerun()
        elif unavailable_message:
            container.info(unavailable_message)
        else:
            container.warning("No se pudo generar el archivo solicitado.")


def render_historial(paciente_sel):
    if not paciente_sel:
        return

    detalles = st.session_state["detalles_pacientes_db"].get(paciente_sel, {})
    estado_badge = "[ARCHIVADO DE ALTA]" if detalles.get("estado") == "De Alta" else ""
    st.markdown(
        f"""
        <div class="mc-hero">
            <h2 class="mc-hero-title">Historia clinica digital {estado_badge}</h2>
            <p class="mc-hero-text">Consulta la evolucion completa del paciente por secciones, sin cargar toda la base de golpe. Esta vista esta pensada para rendir mejor con muchos registros.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Paciente: {paciente_sel}</span>
                <span class="mc-chip">DNI: {detalles.get('dni', 'S/D')}</span>
                <span class="mc-chip">Obra social: {detalles.get('obra_social', 'S/D')}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("##### Opciones de visualizacion")
    col_filt1, col_filt2 = st.columns([1, 2])
    opcion_limite = col_filt1.selectbox(
        "Mostrar",
        ["Ultimos 10 registros", "Ultimos 30 registros", "Ultimos 50 registros", "Modo liviano (200 max)"],
    )
    limite = _limitar_registros(opcion_limite)
    col_filt2.info(f"Estas viendo un maximo de {limite} registros por seccion para cuidar rendimiento.")

    st.markdown("##### Exportacion y resguardo")
    col_exp1, col_exp2, col_exp3 = st.columns(3)
    _render_lazy_download(
        col_exp1,
        key_base=f"historial_pdf_{paciente_sel}",
        prepare_label="Preparar historia completa PDF",
        download_label="Descargar historia completa PDF",
        build_fn=lambda: build_history_pdf_bytes(st.session_state, paciente_sel, detalles.get("empresa", "")),
        file_name=f"Historia_Clinica_{paciente_sel.replace(' ', '_')}.pdf",
        mime="application/pdf",
    )
    _render_lazy_download(
        col_exp2,
        key_base=f"historial_excel_{paciente_sel}",
        prepare_label="Preparar historia en Excel",
        download_label="Descargar historia Excel",
        build_fn=lambda: build_patient_excel_bytes(st.session_state, paciente_sel),
        file_name=f"Historia_Clinica_{paciente_sel.replace(' ', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        unavailable_message="Excel no disponible en este equipo.",
    )
    _render_lazy_download(
        col_exp3,
        key_base=f"historial_respaldo_{paciente_sel}",
        prepare_label="Preparar respaldo PDF",
        download_label="Descargar respaldo PDF",
        build_fn=lambda: build_backup_pdf_bytes(st.session_state, paciente_sel, detalles.get("empresa", "")),
        file_name=f"Respaldo_Clinico_{paciente_sel.replace(' ', '_')}.pdf",
        mime="application/pdf",
    )
    st.divider()
    st.markdown(
        """
        <div class="mc-grid-3">
            <div class="mc-card"><h4>Consulta por bloques</h4><p>Cada seccion se abre por separado para evitar colapsos cuando la historia crece.</p></div>
            <div class="mc-card"><h4>Exportacion segura</h4><p>La historia completa y el respaldo se generan en PDF para archivo e impresion.</p></div>
            <div class="mc-card"><h4>Adjuntos opcionales</h4><p>Las imagenes y PDFs clinicos solo se cargan si realmente los queres ver.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    secciones = collect_patient_sections(st.session_state, paciente_sel)
    st.markdown("##### Resumen clinico")
    metric_cols = st.columns(5)
    resumen = list(secciones.items())
    for idx, (nombre, registros) in enumerate(resumen[:5]):
        metric_cols[idx].metric(nombre, len(registros))
    if len(resumen) > 5:
        extra = sum(len(registros) for _, registros in resumen[5:])
        metric_cols[-1].metric("Otros registros", extra)

    seccion_actual = st.selectbox("Seccion de la historia", list(secciones.keys()), key=f"historial_seccion_{paciente_sel}")
    registros = secciones[seccion_actual]

    if not registros:
        st.info("No hay registros cargados en esta seccion.")
        return

    registros_mostrar = registros[-limite:]
    st.caption(f"Mostrando {len(registros_mostrar)} de {len(registros)} registros cargados en esta seccion.")

    if seccion_actual in {
        "Auditoria de Presencia",
        "Materiales Utilizados",
        "Signos Vitales",
        "Control Pediatrico",
        "Balance Hidrico",
    }:
        df = pd.DataFrame(registros_mostrar).drop(
            columns=["paciente", "empresa", "imagen", "base64_foto", "firma_b64", "firma_img"],
            errors="ignore",
        )
        if seccion_actual == "Balance Hidrico":
            for col in ["ingresos", "egresos", "balance"]:
                if col in df.columns:
                    df[col] = df[col].astype(str) + " ml"
        mostrar_dataframe_con_scroll(df.iloc[::-1], height=520)
        return

    if seccion_actual == "Consentimientos":
        with st.container(height=520):
            for idx, reg in enumerate(reversed(registros_mostrar)):
                with st.container(border=True):
                    st.markdown(f"**{reg.get('fecha', 'S/D')}**")
                    st.caption(
                        f"Firmante: {reg.get('firmante', 'S/D')} | Vinculo: {reg.get('vinculo', 'S/D')} | "
                        f"DNI: {reg.get('dni_firmante', 'S/D')}"
                    )
                    if reg.get("observaciones"):
                        st.write(reg.get("observaciones"))
                    if reg.get("firma_b64"):
                        try:
                            st.image(base64.b64decode(reg["firma_b64"]), caption="Firma paciente / familiar", width=260)
                        except Exception:
                            st.error("No se pudo leer la firma del consentimiento.")
        return

    if seccion_actual == "Estudios Complementarios":
        mostrar_adjuntos = st.checkbox("Cargar imagenes y PDF adjuntos", value=False, key=f"adjuntos_{paciente_sel}")
        with st.container(height=520):
            for idx, est in enumerate(reversed(registros_mostrar)):
                with st.container(border=True):
                    st.markdown(f"**{est.get('fecha', '')} - {est.get('tipo', '')}**")
                    st.caption(f"Firmado/cargado por: {est.get('firma', 'S/D')}")
                    if est.get("detalle"):
                        st.write(est["detalle"])
                    if mostrar_adjuntos and est.get("imagen"):
                        try:
                            archivo = base64.b64decode(est["imagen"])
                            if archivo.startswith(b"%PDF") or est.get("extension") == "pdf":
                                st.download_button(
                                    "Descargar PDF adjunto",
                                    data=archivo,
                                    file_name=f"Estudio_{idx + 1}.pdf",
                                    mime="application/pdf",
                                    key=f"hist_est_pdf_{idx}",
                                    use_container_width=True,
                                )
                            else:
                                st.image(archivo, use_container_width=True)
                        except Exception:
                            st.error("No se pudo leer el adjunto.")
        return

    if seccion_actual == "Registro de Heridas":
        mostrar_fotos = st.checkbox("Cargar fotos", value=False, key=f"fotos_{paciente_sel}")
        with st.container(height=520):
            for fh in reversed(registros_mostrar):
                with st.container(border=True):
                    st.markdown(f"**{fh.get('fecha', '')}**")
                    st.caption(f"Registrado por: {fh.get('firma', 'S/D')}")
                    st.write(fh.get("descripcion", "Sin descripcion"))
                    if mostrar_fotos and fh.get("base64_foto"):
                        try:
                            st.image(base64.b64decode(fh["base64_foto"]), use_container_width=True)
                        except Exception:
                            st.error("No se pudo leer la foto.")
        return

    with st.container(height=520):
        for registro in reversed(registros_mostrar):
            with st.container(border=True):
                fecha = registro.get("fecha", registro.get("fecha_hora", "S/D"))
                firma = registro.get("firma", registro.get("firmado_por", registro.get("profesional", "S/D")))
                st.markdown(f"**{fecha}**")
                st.caption(f"Responsable: {firma}")
                if seccion_actual == "Plan Terapeutico":
                    estado = registro.get("estado_receta", registro.get("estado_clinico", "Activa"))
                    origen = registro.get("origen_registro", "")
                    if estado == "Suspendida":
                        st.error(
                            f"Medicacion suspendida | Fecha: {registro.get('fecha_suspension', 'S/D')} | "
                            f"Profesional: {registro.get('profesional_estado', 'S/D')}"
                        )
                    elif estado == "Modificada":
                        st.warning(
                            f"Medicacion modificada | Fecha: {registro.get('fecha_suspension', 'S/D')} | "
                            f"Profesional: {registro.get('profesional_estado', 'S/D')}"
                        )
                    else:
                        st.success("Medicacion activa")
                    if origen:
                        if "papel" in origen.lower():
                            st.info(f"Origen del registro: {origen}")
                        else:
                            st.caption(f"Origen del registro: {origen}")
                    if registro.get("motivo_estado"):
                        st.caption(f"Motivo: {registro.get('motivo_estado')}")
                    if registro.get("firma_b64"):
                        try:
                            st.image(base64.b64decode(registro["firma_b64"]), caption="Firma medica", width=220)
                        except Exception:
                            pass
                    if registro.get("adjunto_papel_b64"):
                        try:
                            st.download_button(
                                "Descargar orden medica adjunta",
                                data=base64.b64decode(registro["adjunto_papel_b64"]),
                                file_name=registro.get("adjunto_papel_nombre", "indicacion_medica.pdf"),
                                mime=registro.get("adjunto_papel_tipo", "application/octet-stream"),
                                key=f"historial_adjunto_receta_{registro.get('fecha', 's_d')}_{registro.get('med', '')[:12]}",
                                use_container_width=True,
                            )
                        except Exception:
                            st.caption("El adjunto cargado no pudo prepararse para descarga.")
                for clave, valor in registro.items():
                    if clave in {
                        "paciente",
                        "empresa",
                        "fecha",
                        "firma",
                        "firmado_por",
                        "firma_b64",
                        "adjunto_papel_b64",
                        "adjunto_papel_tipo",
                    } or valor in [None, ""]:
                        continue
                    st.write(f"**{clave}:** {valor}")
