from __future__ import annotations
from html import escape

"""Helpers de renderizado de secciones del Historial clÃ­nico.

ExtraÃ­do de views/historial.py.
"""
import base64
from typing import Any, Callable, Dict, List, Optional

import pandas as pd
import streamlit as st
from core.ui_liviano import headers_sugieren_equipo_liviano

from core.app_logging import log_event
from core.utils import mostrar_dataframe_con_scroll
from core.view_helpers import lista_plegable
from views._historial_utils import (
    CLAVES_EXCLUIDAS_GENERICAS,
    COLUMNAS_EXCLUIDAS_TABLA,
)


def _img_movil(data: bytes, caption: str = "", width: int = 260, stretch: bool = False):
    """Muestra imagen con tamaÃ±o reducido en mÃ³vil."""
    es_movil = headers_sugieren_equipo_liviano() or st.session_state.get("mc_liviano_modo") == "on"
    if es_movil:
        if stretch:
            st.image(data, caption=caption, width=200)
        else:
            st.image(data, caption=caption, width=min(width, 200))
    else:
        if stretch:
            st.image(data, caption=caption, use_container_width=True)
        else:
            st.image(data, caption=caption, width=width)


def _ordenar_columnas_tabla(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    prior = [
        "fecha_hora_programada", "fecha", "hora", "fecha_hora", "creado_en",
        "tipo", "categoria_evento", "profesional", "firma", "firmado_por", "estado", "zona",
        "TA", "FC", "FR", "Sat", "Temp", "HGT", "med", "dosis", "ingresos", "egresos", "balance",
    ]
    first = [c for c in prior if c in df.columns]
    rest = [c for c in df.columns if c not in first]
    return df[first + rest]


@st.cache_data(show_spinner=False, ttl=120)
def _preparar_dataframe_seccion(registros: List[Dict[str, Any]], seccion_actual: str) -> pd.DataFrame:
    df = pd.DataFrame(registros).drop(columns=COLUMNAS_EXCLUIDAS_TABLA, errors="ignore")
    if seccion_actual == "Balance Hidrico":
        for col in ["ingresos", "egresos", "balance"]:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: f"{x:.0f} ml" if pd.notna(x) and x != "" else "-")
    elif seccion_actual == "Signos Vitales":
        for col in ["TA", "FC", "FR", "Sat", "Temp", "HGT"]:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: str(x) if x not in (None, "", float("nan")) else "-")
    return _ordenar_columnas_tabla(df)


def _render_seccion_tabla(registros: List[Dict[str, Any]], seccion_actual: str) -> None:
    df = _preparar_dataframe_seccion(registros, seccion_actual)
    with lista_plegable(f"Tabla: {seccion_actual}", count=len(registros), expanded=False, height=520):
        mostrar_dataframe_con_scroll(df, height=496)


def _render_consentimientos(registros: List[Dict[str, Any]], paciente_sel: str) -> None:
    with lista_plegable("Consentimientos (detalle)", count=len(registros), expanded=False, height=520):
        for idx, reg in enumerate(registros):
            with st.container(border=True):
                st.markdown(f"**{reg.get('fecha', 'S/D')}**")
                st.caption(
                    f"Firmante: {reg.get('firmante', 'S/D')} | VÃ­nculo: {reg.get('vinculo', 'S/D')} | "
                    f"DNI: {reg.get('dni_firmante', 'S/D')}"
                )
                if observaciones := reg.get("observaciones"):
                    st.write(observaciones)
                if firma_b64 := reg.get("firma_b64"):
                    try:
                        _img_movil(base64.b64decode(firma_b64), caption="Firma paciente / familiar", width=260)
                    except Exception:
                        log_event("historial_render", "error: No se pudo leer la firma del consentimiento.")
                        st.error("No se pudo leer la firma del consentimiento.")


def _render_estudios(registros: List[Dict[str, Any]], paciente_sel: str) -> None:
    mostrar_adjuntos = st.checkbox("Cargar imÃ¡genes y PDF adjuntos", value=False, key=f"hist_adjuntos_{paciente_sel}")
    with lista_plegable("Estudios en historia", count=len(registros), expanded=False, height=520):
        for idx, est in enumerate(registros):
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
                                key=f"hist_est_pdf_{paciente_sel}_{idx}",
                                width='stretch',
                            )
                        else:
                            _img_movil(archivo, stretch=True)
                    except Exception:
                        log_event("historial_render", "error: No se pudo leer el adjunto.")
                        st.error("No se pudo leer el adjunto.")


def _render_heridas(registros: List[Dict[str, Any]], paciente_sel: str) -> None:
    mostrar_fotos = st.checkbox("Cargar fotos", value=False, key=f"hist_fotos_{paciente_sel}")
    with lista_plegable("Fotos de heridas", count=len(registros), expanded=False, height=520):
        for idx, fh in enumerate(registros):
            with st.container(border=True):
                st.markdown(f"**{fh.get('fecha', '')}**")
                st.caption(f"Registrado por: {fh.get('firma', 'S/D')}")
                st.write(fh.get("descripcion", "Sin descripciÃ³n"))
                if mostrar_fotos and (foto_b64 := fh.get("base64_foto")):
                    try:
                        _img_movil(base64.b64decode(foto_b64), stretch=True)
                    except Exception:
                        log_event("historial_render", "error: No se pudo leer la foto.")
                        st.error("No se pudo leer la foto.")


def _render_detalles_plan_terapeutico(registro: Dict[str, Any], idx: int, paciente_sel: str) -> None:
    estado = registro.get("estado_receta", registro.get("estado_clinico", "Activa"))
    origen = registro.get("origen_registro", "")
    if estado == "Suspendida":
        log_event("historial_render", "error: Medicacion suspendida")
        st.error(
            f"MedicaciÃ³n suspendida | Fecha: {registro.get('fecha_suspension', 'S/D')} | "
            f"Profesional: {registro.get('profesional_estado', 'S/D')}"
        )
    elif estado == "Modificada":
        st.warning(
            f"MedicaciÃ³n modificada | Fecha: {registro.get('fecha_suspension', 'S/D')} | "
            f"Profesional: {registro.get('profesional_estado', 'S/D')}"
        )
    else:
        st.success("MedicaciÃ³n activa")
    if origen:
        if "papel" in str(origen).lower():
            st.info(f"Origen del registro: {origen}")
        else:
            st.caption(f"Origen del registro: {origen}")
    if motivo := registro.get("motivo_estado"):
        st.caption(f"Motivo: {motivo}")
    if firma_b64 := registro.get("firma_b64"):
        try:
            _img_movil(base64.b64decode(firma_b64), caption="Firma mÃ©dica", width=220)
        except Exception as e:
            log_event("historial_error", f"Error: {e}")
    if adjunto_b64 := registro.get("adjunto_papel_b64"):
        try:
            st.download_button(
                "Descargar orden mÃ©dica adjunta",
                data=base64.b64decode(adjunto_b64),
                file_name=registro.get("adjunto_papel_nombre", "indicacion_medica.pdf"),
                mime=registro.get("adjunto_papel_tipo", "application/octet-stream"),
                key=f"hist_adj_rec_{paciente_sel}_{idx}",
                width='stretch',
            )
        except Exception:
            st.caption("El adjunto cargado no pudo prepararse para descarga.")


def _render_registros_genericos(
    registros: List[Dict[str, Any]],
    seccion_actual: str,
    paciente_sel: str,
) -> None:
    with lista_plegable(f"Registros: {seccion_actual}", count=len(registros), expanded=False, height=520):
        for idx, registro in enumerate(registros):
            with st.container(border=True):
                fecha = registro.get("fecha", registro.get("fecha_hora", "S/D"))
                firma = registro.get("firma", registro.get("firmado_por", registro.get("profesional", "S/D")))
                st.markdown(f"**{fecha}**")
                st.caption(f"Responsable: {firma}")
                if seccion_actual == "Plan Terapeutico":
                    _render_detalles_plan_terapeutico(registro, idx, paciente_sel)
                for clave, valor in registro.items():
                    if clave in CLAVES_EXCLUIDAS_GENERICAS:
                        continue
                    if valor in (None, ""):
                        continue
                    clave_formateada = str(clave).replace("_", " ").capitalize()
                    texto = str(valor)
                    if len(texto) > 1200:
                        texto = texto[:1200] + "â€¦"
                    st.write(f"**{clave_formateada}:** {texto}")


def _render_lazy_download(
    container: st.delta_generator.DeltaGenerator,
    key_base: str,
    prepare_label: str,
    download_label: str,
    build_fn: Callable,
    file_name: str,
    mime: str,
    unavailable_message: Optional[str] = None,
) -> None:
    cache_key = f"lazy_export_{key_base}"
    payload = st.session_state.get(cache_key)
    if payload:
        container.download_button(
            label=download_label,
            data=payload,
            file_name=file_name,
            mime=mime,
            key=f"download_{key_base}",
            width='stretch',
        )
        if container.button("Actualizar archivo", key=f"refresh_{key_base}", width='stretch'):
            st.session_state.pop(cache_key, None)
            st.rerun()
        return
    if container.button(prepare_label, key=f"prepare_{key_base}", width='stretch'):
        with st.spinner("Preparando archivo..."):
            payload = build_fn()
        if payload:
            st.session_state[cache_key] = payload
            st.rerun()
        elif unavailable_message:
            container.info(unavailable_message)
        else:
            container.warning("No se pudo generar el archivo solicitado.")

