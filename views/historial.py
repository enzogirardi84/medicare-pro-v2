import base64
from typing import Optional, Dict, Any, List

import pandas as pd
import streamlit as st

from core.clinical_exports import (
    build_backup_pdf_bytes,
    build_history_pdf_bytes,
    build_patient_excel_bytes,
    collect_patient_sections,
)
from core.utils import mostrar_dataframe_con_scroll

# --- Constantes ---
LIMITES_REGISTROS = {
    "Últimos 10 registros": 10,
    "Últimos 30 registros": 30,
    "Últimos 50 registros": 50,
    "Modo liviano (200 máx)": 200,
}

SECCIONES_TABLA = {
    "Auditoria de Presencia",
    "Materiales Utilizados",
    "Signos Vitales",
    "Control Pediatrico",
    "Balance Hidrico",
}

COLUMNAS_EXCLUIDAS_TABLA = ["paciente", "empresa", "imagen", "base64_foto", "firma_b64", "firma_img"]
CLAVES_EXCLUIDAS_GENERICAS = {
    "paciente", "empresa", "fecha", "firma", "firmado_por", 
    "firma_b64", "adjunto_papel_b64", "adjunto_papel_tipo", "adjunto_papel_nombre"
}


# --- Funciones Auxiliares ---
def _render_lazy_download(
    container: st.delta_generator.DeltaGenerator,
    key_base: str,
    prepare_label: str,
    download_label: str,
    build_fn: callable,
    file_name: str,
    mime: str,
    unavailable_message: Optional[str] = None
) -> None:
    """Renderiza botones de descarga de forma perezosa (lazy load) para mejorar el rendimiento."""
    cache_key = f"lazy_export_{key_base}"
    payload = st.session_state.get(cache_key)

    if payload:
        container.download_button(
            label=download_label,
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


# --- Renderizadores de Secciones (Modularización) ---
def _render_seccion_tabla(registros: List[Dict[str, Any]], seccion_actual: str) -> None:
    df = pd.DataFrame(registros).drop(columns=COLUMNAS_EXCLUIDAS_TABLA, errors="ignore")
    if seccion_actual == "Balance Hidrico":
        for col in ["ingresos", "egresos", "balance"]:
            if col in df.columns:
                df[col] = df[col].astype(str) + " ml"
    mostrar_dataframe_con_scroll(df.iloc[::-1], height=520)


def _render_consentimientos(registros: List[Dict[str, Any]]) -> None:
    with st.container(height=520):
        for reg in reversed(registros):
            with st.container(border=True):
                st.markdown(f"**{reg.get('fecha', 'S/D')}**")
                st.caption(
                    f"Firmante: {reg.get('firmante', 'S/D')} | Vínculo: {reg.get('vinculo', 'S/D')} | "
                    f"DNI: {reg.get('dni_firmante', 'S/D')}"
                )
                if observaciones := reg.get("observaciones"):
                    st.write(observaciones)
                if firma_b64 := reg.get("firma_b64"):
                    try:
                        st.image(base64.b64decode(firma_b64), caption="Firma paciente / familiar", width=260)
                    except Exception:
                        st.error("No se pudo leer la firma del consentimiento.")


def _render_estudios(registros: List[Dict[str, Any]], paciente_sel: str) -> None:
    mostrar_adjuntos = st.checkbox("Cargar imágenes y PDF adjuntos", value=False, key=f"adjuntos_{paciente_sel}")
    with st.container(height=520):
        for idx, est in enumerate(reversed(registros)):
            with st.container(border=True):
                st.markdown(f"**{est.get('fecha', '')} - {est.get('tipo', '')}**")
                st.caption(f"Firmado/cargado por: {est.get('firma', 'S/D')}")
                if detalle := est.get("detalle"):
                    st.write(detalle)
                
                if mostrar_adjuntos and (imagen := est.get("imagen")):
                    try:
                        archivo = base64.b64decode(imagen)
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


def _render_heridas(registros: List[Dict[str, Any]], paciente_sel: str) -> None:
    mostrar_fotos = st.checkbox("Cargar fotos", value=False, key=f"fotos_{paciente_sel}")
    with st.container(height=520):
        for fh in reversed(registros):
            with st.container(border=True):
                st.markdown(f"**{fh.get('fecha', '')}**")
                st.caption(f"Registrado por: {fh.get('firma', 'S/D')}")
                st.write(fh.get("descripcion", "Sin descripción"))
                
                if mostrar_fotos and (foto_b64 := fh.get("base64_foto")):
                    try:
                        st.image(base64.b64decode(foto_b64), use_container_width=True)
                    except Exception:
                        st.error("No se pudo leer la foto.")


def _render_registros_genericos(registros: List[Dict[str, Any]], seccion_actual: str) -> None:
    with st.container(height=520):
        for registro in reversed(registros):
            with st.container(border=True):
                fecha = registro.get("fecha", registro.get("fecha_hora", "S/D"))
                firma = registro.get("firma", registro.get("firmado_por", registro.get("profesional", "S/D")))
                st.markdown(f"**{fecha}**")
                st.caption(f"Responsable: {firma}")
                
                if seccion_actual == "Plan Terapeutico":
                    _render_detalles_plan_terapeutico(registro)
                
                for clave, valor in registro.items():
                    if clave not in CLAVES_EXCLUIDAS_GENERICAS and valor not in (None, ""):
                        # Formatea la clave para que se vea mejor (ej: "presion_arterial" -> "Presion arterial")
                        clave_formateada = str(clave).replace('_', ' ').capitalize()
                        st.write(f"**{clave_formateada}:** {valor}")


def _render_detalles_plan_terapeutico(registro: Dict[str, Any]) -> None:
    estado = registro.get("estado_receta", registro.get("estado_clinico", "Activa"))
    origen = registro.get("origen_registro", "")
    
    if estado == "Suspendida":
        st.error(f"Medicación suspendida | Fecha: {registro.get('fecha_suspension', 'S/D')} | Profesional: {registro.get('profesional_estado', 'S/D')}")
    elif estado == "Modificada":
        st.warning(f"Medicación modificada | Fecha: {registro.get('fecha_suspension', 'S/D')} | Profesional: {registro.get('profesional_estado', 'S/D')}")
    else:
        st.success("Medicación activa")
        
    if origen:
        if "papel" in origen.lower():
            st.info(f"Origen del registro: {origen}")
        else:
            st.caption(f"Origen del registro: {origen}")
            
    if motivo := registro.get("motivo_estado"):
        st.caption(f"Motivo: {motivo}")
        
    if firma_b64 := registro.get("firma_b64"):
        try:
            st.image(base64.b64decode(firma_b64), caption="Firma médica", width=220)
        except Exception:
            pass
            
    if adjunto_b64 := registro.get("adjunto_papel_b64"):
        try:
            st.download_button(
                "Descargar orden médica adjunta",
                data=base64.b64decode(adjunto_b64),
                file_name=registro.get("adjunto_papel_nombre", "indicacion_medica.pdf"),
                mime=registro.get("adjunto_papel_tipo", "application/octet-stream"),
                key=f"historial_adjunto_receta_{registro.get('fecha', 's_d')}_{registro.get('med', '')[:12]}",
                use_container_width=True,
            )
        except Exception:
            st.caption("El adjunto cargado no pudo prepararse para descarga.")


# --- Función Principal ---
def render_historial(paciente_sel: str) -> None:
    if not paciente_sel:
        return

    detalles = st.session_state.get("detalles_pacientes_db", {}).get(paciente_sel, {})
    estado_badge = "[ARCHIVADO DE ALTA]" if detalles.get("estado") == "De Alta" else ""
    
    st.markdown(
        f"""
        <div class="mc-hero">
            <h2 class="mc-hero-title">Historia clínica digital {estado_badge}</h2>
            <p class="mc-hero-text">Consulta la evolución completa del paciente por secciones, sin cargar toda la base de golpe. Esta vista está pensada para rendir mejor con muchos registros.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Paciente: {paciente_sel}</span>
                <span class="mc-chip">DNI: {detalles.get('dni', 'S/D')}</span>
                <span class="mc-chip">Obra social: {detalles.get('obra_social', 'S/D')}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("##### Opciones de visualización")
    col_filt1, col_filt2 = st.columns([1, 2])
    opcion_limite = col_filt1.selectbox("Mostrar", list(LIMITES_REGISTROS.keys()))
    limite = LIMITES_REGISTROS.get(opcion_limite, 200)
    col_filt2.info(f"Estás viendo un máximo de {limite} registros por sección para cuidar el rendimiento.")

    st.markdown("##### Exportación y resguardo")
    col_exp1, col_exp2, col_exp3 = st.columns(3)
    
    _render_lazy_download(
        col_exp1,
        key_base=f"historial_pdf_{paciente_sel}",
        prepare_label="Preparar historia completa PDF",
        download_label="Descargar historia completa PDF",
        build_fn=lambda: build_history_pdf_bytes(st.session_state, paciente_sel, detalles.get("empresa", "")),
        file_name=f"Historia_Clinica_{paciente_sel.replace(' ', '_')}.pdf",
        mime="application/pdf",
        unavailable_message="Historia clinica PDF no disponible en este equipo. Instala reportlab para habilitarla.",
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
            <div class="mc-card"><h4>Consulta por bloques</h4><p>Cada sección se abre por separado para evitar colapsos cuando la historia crece.</p></div>
            <div class="mc-card"><h4>Exportación segura</h4><p>La historia completa y el respaldo se generan en PDF para archivo e impresión.</p></div>
            <div class="mc-card"><h4>Adjuntos opcionales</h4><p>Las imágenes y PDFs clínicos solo se cargan si realmente los querés ver.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    secciones = collect_patient_sections(st.session_state, paciente_sel)
    if not secciones:
        st.warning("No se encontraron registros para este paciente.")
        return

    st.markdown("##### Resumen clínico")
    metric_cols = st.columns(5)
    resumen = list(secciones.items())
    
    for idx, (nombre, registros_sec) in enumerate(resumen[:5]):
        metric_cols[idx].metric(nombre, len(registros_sec))
    if len(resumen) > 5:
        extra = sum(len(registros_sec) for _, registros_sec in resumen[5:])
        metric_cols[-1].metric("Otros registros", extra)

    seccion_actual = st.selectbox("Sección de la historia", list(secciones.keys()), key=f"historial_seccion_{paciente_sel}")
    registros = secciones.get(seccion_actual, [])

    if not registros:
        st.info("No hay registros cargados en esta sección.")
        return

    registros_mostrar = registros[-limite:]
    st.caption(f"Mostrando {len(registros_mostrar)} de {len(registros)} registros cargados en esta sección.")

    # Enrutador de secciones
    if seccion_actual in SECCIONES_TABLA:
        _render_seccion_tabla(registros_mostrar, seccion_actual)
    elif seccion_actual == "Consentimientos":
        _render_consentimientos(registros_mostrar)
    elif seccion_actual == "Estudios Complementarios":
        _render_estudios(registros_mostrar, paciente_sel)
    elif seccion_actual == "Registro de Heridas":
        _render_heridas(registros_mostrar, paciente_sel)
    else:
        _render_registros_genericos(registros_mostrar, seccion_actual)
