import base64
import html
import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio, lista_plegable
from core.clinical_exports import (
    build_backup_pdf_bytes,
    build_history_pdf_bytes,
    build_patient_excel_bytes,
    build_patient_json_bytes,
    collect_patient_sections,
)
from core.utils import ahora, mapa_detalles_pacientes, mostrar_dataframe_con_scroll
from features.historial.fechas import (
    fecha_registro_o_none,
    parse_registro_fecha_hora,
    registro_en_rango_fechas,
    sort_registros_por_fecha,
)

LIMITES_REGISTROS = {
    "Últimos 10 registros": 10,
    "Últimos 30 registros": 30,
    "Últimos 50 registros": 50,
    "Últimos 100 registros": 100,
    "Modo liviano (200 máx)": 200,
}

# Panel con scroll interno (Streamlit): evita que Historial alargue toda la página.
HISTORIAL_PANEL_SCROLL_PX = 680

SECCIONES_TABLA = {
    "Auditoria de Presencia",
    "Visitas y Agenda",
    "Emergencias y Ambulancia",
    "Enfermeria y Plan de Cuidados",
    "Escalas Clinicas",
    "Auditoria Legal",
    "Procedimientos y Evoluciones",
    "Materiales Utilizados",
    "Signos Vitales",
    "Control Pediatrico",
    "Balance Hidrico",
}

COLUMNAS_EXCLUIDAS_TABLA = ["paciente", "empresa", "imagen", "base64_foto", "firma_b64", "firma_img"]

CLAVES_EXCLUIDAS_GENERICAS = {
    "paciente",
    "empresa",
    "fecha",
    "firma",
    "firmado_por",
    "firma_b64",
    "adjunto_papel_b64",
    "adjunto_papel_tipo",
    "adjunto_papel_nombre",
    "_id_local",
    "_fecha_dt",
    "estado_calc",
}


def _resumen_linea_tiempo(seccion: str, reg: Dict[str, Any]) -> str:
    if seccion == "Signos Vitales":
        return f"TA {reg.get('TA', '-')} | FC {reg.get('FC', '-')} | Sat {reg.get('Sat', '-')}%"
    if seccion == "Visitas y Agenda":
        return f"{reg.get('profesional', '-')} | {reg.get('estado', '-')}"
    if seccion == "Balance Hidrico":
        return f"In {reg.get('ingresos', '-')} | Eg {reg.get('egresos', '-')} | Bal {reg.get('balance', '-')}"
    if seccion == "Emergencias y Ambulancia":
        return f"{reg.get('categoria_evento', reg.get('tipo', '-'))} → {reg.get('destino', '-')}"[:120]
    if seccion == "Procedimientos y Evoluciones":
        txt = str(reg.get("texto", reg.get("detalle", "")))[:140]
        return txt or (reg.get("tipo") or "Evolución")
    if seccion == "Estudios Complementarios":
        return f"{reg.get('tipo', '-')} — {str(reg.get('detalle', ''))[:100]}"
    if seccion == "Plan Terapeutico":
        return f"{reg.get('med', '-')} {reg.get('dosis', '')}"[:120]
    if seccion == "Materiales Utilizados":
        return f"{reg.get('material', reg.get('item', '-'))} x{reg.get('cantidad', '')}"
    piezas = [
        str(reg.get("tipo", "")),
        str(reg.get("profesional", "")),
        str(reg.get("titulo", "")),
        str(reg.get("detalle", ""))[:80],
    ]
    t = " | ".join(p for p in piezas if p and p != "None")
    return (t[:160] if t else seccion)[:180]


@st.cache_data(show_spinner=False)
def _actividad_reciente_filas(secciones: Dict[str, List[Dict[str, Any]]], limite: int) -> List[Dict[str, str]]:
    filas: List[Tuple[datetime, str, str, str]] = []
    for nombre_sec, regs in secciones.items():
        for reg in regs:
            dt = parse_registro_fecha_hora(reg)
            if not dt:
                continue
            filas.append(
                (
                    dt,
                    nombre_sec,
                    dt.strftime("%d/%m/%Y %H:%M"),
                    _resumen_linea_tiempo(nombre_sec, reg),
                )
            )
    filas.sort(key=lambda x: x[0], reverse=True)
    out = []
    for _, sec, f_str, res in filas[:limite]:
        out.append({"Fecha": f_str, "Sección": sec, "Resumen": res})
    return out


def _ultimo_evento_global(secciones: Dict[str, List[Dict[str, Any]]]) -> Optional[datetime]:
    ultimo: Optional[datetime] = None
    for regs in secciones.values():
        for reg in regs:
            dt = parse_registro_fecha_hora(reg)
            if dt and (ultimo is None or dt > ultimo):
                ultimo = dt
    return ultimo


def _render_lazy_download(
    container: st.delta_generator.DeltaGenerator,
    key_base: str,
    prepare_label: str,
    download_label: str,
    build_fn: callable,
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


def _ordenar_columnas_tabla(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    prior = [
        "fecha_hora_programada",
        "fecha",
        "hora",
        "fecha_hora",
        "creado_en",
        "tipo",
        "categoria_evento",
        "profesional",
        "firma",
        "firmado_por",
        "estado",
        "zona",
        "TA",
        "FC",
        "FR",
        "Sat",
        "Temp",
        "HGT",
        "med",
        "dosis",
        "ingresos",
        "egresos",
        "balance",
    ]
    first = [c for c in prior if c in df.columns]
    rest = [c for c in df.columns if c not in first]
    return df[first + rest]


@st.cache_data(show_spinner=False)
def _preparar_dataframe_seccion(registros: List[Dict[str, Any]], seccion_actual: str) -> pd.DataFrame:
    df = pd.DataFrame(registros).drop(columns=COLUMNAS_EXCLUIDAS_TABLA, errors="ignore")
    if seccion_actual == "Balance Hidrico":
        for col in ["ingresos", "egresos", "balance"]:
            if col in df.columns:
                df[col] = df[col].astype(str) + " ml"
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
    mostrar_adjuntos = st.checkbox("Cargar imágenes y PDF adjuntos", value=False, key=f"hist_adjuntos_{paciente_sel}")
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
                                use_container_width=True,
                            )
                        else:
                            st.image(archivo, use_container_width=True)
                    except Exception:
                        st.error("No se pudo leer el adjunto.")


def _render_heridas(registros: List[Dict[str, Any]], paciente_sel: str) -> None:
    mostrar_fotos = st.checkbox("Cargar fotos", value=False, key=f"hist_fotos_{paciente_sel}")
    with lista_plegable("Fotos de heridas", count=len(registros), expanded=False, height=520):
        for idx, fh in enumerate(registros):
            with st.container(border=True):
                st.markdown(f"**{fh.get('fecha', '')}**")
                st.caption(f"Registrado por: {fh.get('firma', 'S/D')}")
                st.write(fh.get("descripcion", "Sin descripción"))

                if mostrar_fotos and (foto_b64 := fh.get("base64_foto")):
                    try:
                        st.image(base64.b64decode(foto_b64), use_container_width=True)
                    except Exception:
                        st.error("No se pudo leer la foto.")


def _render_detalles_plan_terapeutico(registro: Dict[str, Any], idx: int, paciente_sel: str) -> None:
    estado = registro.get("estado_receta", registro.get("estado_clinico", "Activa"))
    origen = registro.get("origen_registro", "")

    if estado == "Suspendida":
        st.error(
            f"Medicación suspendida | Fecha: {registro.get('fecha_suspension', 'S/D')} | "
            f"Profesional: {registro.get('profesional_estado', 'S/D')}"
        )
    elif estado == "Modificada":
        st.warning(
            f"Medicación modificada | Fecha: {registro.get('fecha_suspension', 'S/D')} | "
            f"Profesional: {registro.get('profesional_estado', 'S/D')}"
        )
    else:
        st.success("Medicación activa")

    if origen:
        if "papel" in str(origen).lower():
            st.info(f"Origen del registro: {origen}")
        else:
            st.caption(f"Origen del registro: {origen}")

    if motivo := registro.get("motivo_estado"):
        st.caption(f"Motivo: {motivo}")

    if firma_b64 := registro.get("firma_b64"):
        try:
            st.image(base64.b64decode(firma_b64), caption="Firma médica", width=220)
        except Exception as e:

            from core.app_logging import log_event

            log_event('historial_error', f'Error: {e}')

    if adjunto_b64 := registro.get("adjunto_papel_b64"):
        try:
            st.download_button(
                "Descargar orden médica adjunta",
                data=base64.b64decode(adjunto_b64),
                file_name=registro.get("adjunto_papel_nombre", "indicacion_medica.pdf"),
                mime=registro.get("adjunto_papel_tipo", "application/octet-stream"),
                key=f"hist_adj_rec_{paciente_sel}_{idx}",
                use_container_width=True,
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
                        texto = texto[:1200] + "…"
                    st.write(f"**{clave_formateada}:** {texto}")


def _registro_coincide_busqueda(registro: Dict[str, Any], query: str) -> bool:
    q = query.strip().lower()
    if not q:
        return True
    for v in registro.values():
        if v is None:
            continue
        if q in str(v).lower():
            return True
    return False


@st.cache_data(show_spinner=False)
def _busqueda_global_resultados(
    secciones: Dict[str, List[Dict[str, Any]]],
    query: str,
    limite: int,
) -> List[Dict[str, Any]]:
    q = query.strip()
    if not q:
        return []
    out: List[Dict[str, Any]] = []
    for sec, regs in secciones.items():
        for reg in regs:
            if not _registro_coincide_busqueda(reg, q):
                continue
            dt = parse_registro_fecha_hora(reg)
            fe = dt.strftime("%d/%m/%Y %H:%M") if dt else "S/D"
            out.append(
                {
                    "seccion": sec,
                    "fecha": fe,
                    "resumen": _resumen_linea_tiempo(sec, reg)[:220],
                }
            )
            if len(out) >= limite:
                return out
    return out


def _dataframe_seccion_a_csv(registros: List[Dict[str, Any]]) -> Optional[bytes]:
    if not registros:
        return None
    drop_csv = {
        "imagen",
        "base64_foto",
        "firma_b64",
        "adjunto_papel_b64",
        "firma_img",
    }
    try:
        df = pd.DataFrame(registros)
        df = df.drop(columns=["paciente", "empresa"], errors="ignore")
        df = df.drop(columns=[c for c in drop_csv if c in df.columns], errors="ignore")
        return df.to_csv(index=False).encode("utf-8-sig")
    except Exception:
        return None


def _nombre_archivo_seguro(texto: str, max_len: int = 50) -> str:
    t = re.sub(r"[^\w\-]+", "_", str(texto or "").strip(), flags=re.UNICODE)
    return (t or "archivo")[:max_len]


def render_historial(paciente_sel: str) -> None:
    if not paciente_sel:
        aviso_sin_paciente()
        return

    detalles = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})
    estado_badge = "[ARCHIVADO DE ALTA]" if detalles.get("estado") == "De Alta" else ""
    nombre_chip = html.escape(paciente_sel.split(" (")[0])
    dni_chip = html.escape(str(detalles.get("dni", "S/D")))
    os_chip = html.escape(str(detalles.get("obra_social", "S/D")))
    tel_chip = html.escape(str(detalles.get("telefono", "S/D")))
    dom = str(detalles.get("direccion", "")).strip()
    dom_chip = html.escape(dom) if dom and dom != "No registrada" else ""

    chips_extra = ""
    if dom_chip:
        chips_extra = f'<span class="mc-chip">Dom.: {dom_chip[:40]}{"…" if len(dom_chip) > 40 else ""}</span>'

    st.markdown(
        f"""
        <div class="mc-hero">
            <h2 class="mc-hero-title">Historia clínica digital {estado_badge}</h2>
            <p class="mc-hero-text">
                Orden sugerido: exportar o respaldar si lo necesitas, revisar el panorama y la linea de tiempo,
                buscar en toda la historia, y al final abrir cada modulo por seccion para el detalle completo.
                En celular, las tablas anchas se pueden desplazar horizontalmente.
            </p>
            <div class="mc-chip-row">
                <span class="mc-chip">{nombre_chip}</span>
                <span class="mc-chip">DNI: {dni_chip}</span>
                <span class="mc-chip">Obra social: {os_chip}</span>
                <span class="mc-chip">Tel: {tel_chip}</span>
                {chips_extra}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    alergias = str(detalles.get("alergias", "")).strip()
    if alergias:
        st.error(f"Alergias: {alergias}")
    patologias = str(detalles.get("patologias", "")).strip()
    if patologias:
        st.warning(f"Antecedentes / riesgos: {patologias}")

    st.caption(
        "Filtros y límite arriba · exportaciones PDF/Excel/JSON/respaldo · panorama y gráfico · línea de tiempo y búsqueda global · "
        "al final, exploración por sección en franja horizontal (plegable)."
    )

    st.markdown("##### Opciones de visualización")
    col_filt1, col_filt2, col_filt3, col_filt4 = st.columns(4)
    opcion_limite = col_filt1.selectbox("Límite por sección", list(LIMITES_REGISTROS.keys()))
    limite = LIMITES_REGISTROS.get(opcion_limite, 200)
    solo_con_datos = col_filt2.checkbox("Solo secciones con datos", value=True, key=f"hist_solo_datos_{paciente_sel}")
    limite_timeline = col_filt3.selectbox(
        "Eventos en línea de tiempo",
        [15, 25, 40, 60],
        index=1,
        key=f"hist_tl_n_{paciente_sel}",
    )
    col_filt4.info(f"Hasta {limite} ítems al ver una sección.")

    st.markdown("##### Exportación y resguardo")
    r1, r2, r3, r4 = st.columns(4)
    _render_lazy_download(
        r1,
        key_base=f"historial_pdf_{paciente_sel}",
        prepare_label="Preparar historia PDF",
        download_label="Descargar historia PDF",
        build_fn=lambda: build_history_pdf_bytes(st.session_state, paciente_sel, detalles.get("empresa", "")),
        file_name=f"Historia_Clinica_{paciente_sel.replace(' ', '_')}.pdf",
        mime="application/pdf",
    )
    _render_lazy_download(
        r2,
        key_base=f"historial_excel_{paciente_sel}",
        prepare_label="Preparar Excel",
        download_label="Descargar Excel",
        build_fn=lambda: build_patient_excel_bytes(st.session_state, paciente_sel),
        file_name=f"Historia_Clinica_{paciente_sel.replace(' ', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        unavailable_message="Excel no disponible en este equipo.",
    )
    _render_lazy_download(
        r3,
        key_base=f"historial_respaldo_{paciente_sel}",
        prepare_label="Preparar respaldo PDF",
        download_label="Descargar respaldo PDF",
        build_fn=lambda: build_backup_pdf_bytes(st.session_state, paciente_sel, detalles.get("empresa", "")),
        file_name=f"Respaldo_Clinico_{paciente_sel.replace(' ', '_')}.pdf",
        mime="application/pdf",
    )
    _render_lazy_download(
        r4,
        key_base=f"historial_json_{paciente_sel}",
        prepare_label="Preparar JSON",
        download_label="Descargar JSON",
        build_fn=lambda: build_patient_json_bytes(st.session_state, paciente_sel),
        file_name=f"Historia_Clinica_{paciente_sel.replace(' ', '_')}.json",
        mime="application/json",
    )

    st.divider()
    st.markdown(
        """
        <div class="mc-grid-3">
            <div class="mc-card"><h4>Respaldo y filtros</h4><p>PDF, Excel, JSON o respaldo antes de profundizar; limite por seccion y solo modulos con datos.</p></div>
            <div class="mc-card"><h4>Panorama y linea de tiempo</h4><p>Volumen por modulo y mezcla cronologica de eventos con fecha reconocible.</p></div>
            <div class="mc-card"><h4>Busqueda y detalle</h4><p>Texto en toda la historia y luego cada seccion en tabla o ficha segun el tipo de registro.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    secciones = collect_patient_sections(st.session_state, paciente_sel)
    if not any(secciones.values()):
        bloque_estado_vacio(
            "Historia sin registros",
            "No se encontraron registros clínicos agregados para este paciente.",
            sugerencia="Los datos aparecen cuando se usan Clínica, Recetas, Evolución y el resto de módulos.",
        )
        return

    if solo_con_datos:
        secciones = {k: v for k, v in secciones.items() if v}

    if not secciones:
        bloque_estado_vacio(
            "Filtro demasiado estricto",
            "No quedan secciones con datos con el filtro «solo secciones con datos».",
            sugerencia="Desactivá el filtro o registrá información en otros módulos primero.",
        )
        return

    st.caption(
        "Panel con desplazamiento vertical: panorámica, búsqueda global y detalle por sección (scroll interno)."
    )
    with st.container(height=HISTORIAL_PANEL_SCROLL_PX, border=True):
        total_registros = sum(len(v) for v in secciones.values())
        ultimo = _ultimo_evento_global(secciones)

        st.markdown("##### Panorama del paciente")
        m1, m2, m3 = st.columns(3)
        m1.metric("Registros totales", total_registros)
        m2.metric("Secciones con datos", len(secciones))
        m3.metric("Último evento datado", ultimo.strftime("%d/%m/%Y %H:%M") if ultimo else "S/D")
    
        df_cnt = pd.DataFrame([{"Sección": k, "Cantidad": len(v)} for k, v in sorted(secciones.items(), key=lambda x: -len(x[1]))])
        st.caption("Volumen de registros por módulo")
        _n_mod = len(df_cnt)
        _h_bar = min(260, max(120, 32 * _n_mod + 72))
        st.bar_chart(
            df_cnt.set_index("Sección")["Cantidad"],
            use_container_width=True,
            height=_h_bar,
        )
    
        mostrar_tl = st.checkbox(
            "Mostrar línea de tiempo global (mezcla de secciones)",
            value=True,
            key=f"hist_show_tl_{paciente_sel}",
        )
        if mostrar_tl:
            filas_tl = _actividad_reciente_filas(secciones, limite_timeline)
            if filas_tl:
                df_tl = pd.DataFrame(filas_tl)
                altura_tl = min(280, max(168, 36 + len(filas_tl) * 32))
                mostrar_dataframe_con_scroll(df_tl, height=altura_tl)
            else:
                st.caption("No hay registros con fecha reconocible para armar la línea de tiempo.")
    
        st.markdown("##### Búsqueda en toda la historia")
        g_cols = st.columns([2, 1])
        with g_cols[0]:
            q_global = st.text_input(
                "Texto en todas las secciones",
                "",
                key=f"hist_global_q_{paciente_sel}",
                placeholder="Apellido, medicación, tipo de estudio, profesional…",
            )
        with g_cols[1]:
            max_hits = st.selectbox("Máx. resultados", [20, 40, 80], index=0, key=f"hist_global_max_{paciente_sel}")
    
        if q_global.strip():
            hits = _busqueda_global_resultados(secciones, q_global.strip(), max_hits)
            if not hits:
                st.caption("No hay coincidencias en ninguna sección.")
            else:
                conteo_sec = Counter(h["seccion"] for h in hits)
                top_sec, top_n = conteo_sec.most_common(1)[0]
                st.success(
                    f"**{len(hits)}** coincidencia(s) en **{len(conteo_sec)}** sección(es). "
                    f"Mayor densidad: **{top_sec}** ({top_n})."
                )
                if len(conteo_sec) > 1:
                    df_dist = (
                        pd.DataFrame(conteo_sec.most_common(), columns=["Sección", "Coincidencias"])
                        .sort_values("Coincidencias", ascending=False)
                        .set_index("Sección")
                    )
                    st.caption("Coincidencias por módulo")
                    st.bar_chart(df_dist, use_container_width=True, height=min(220, 40 + len(conteo_sec) * 28))

                df_h = pd.DataFrame(hits).rename(
                    columns={"seccion": "Sección", "fecha": "Fecha", "resumen": "Resumen"}
                )
                altura_h = min(280, max(168, 36 + len(hits) * 32))
                mostrar_dataframe_con_scroll(df_h, height=altura_h)
                st.caption(
                    f"Tip: usá «Abrir sección» para ir a **{top_sec}** (más resultados) o elegí otra fila en el selector."
                )
                etiquetas = [f"{i + 1}. {h['seccion']} — {h['fecha']}" for i, h in enumerate(hits)]
                sel_hit = st.selectbox(
                    "Ir a sección del resultado",
                    etiquetas,
                    key=f"hist_global_pick_{paciente_sel}",
                )
                if st.button("Abrir sección y filtrar con esta búsqueda", key=f"hist_global_go_{paciente_sel}", type="primary"):
                    idx = etiquetas.index(sel_hit)
                    destino = hits[idx]["seccion"]
                    st.session_state[f"hist_seccion_radio_{paciente_sel}"] = destino
                    st.session_state[f"hist_buscar_{paciente_sel}_{destino}"] = q_global.strip()
                    st.rerun()
    
        st.divider()
        lista_secciones = list(secciones.keys())
        key_sec = f"hist_seccion_radio_{paciente_sel}"
        if key_sec not in st.session_state:
            st.session_state[key_sec] = lista_secciones[0]
        else:
            _prev = st.session_state[key_sec]
            if _prev not in lista_secciones:
                st.session_state[key_sec] = lista_secciones[0]

        with st.expander("Explorar por sección", expanded=True):
            st.caption(
                "Franja horizontal: en el celular deslizá con el dedo; en PC usá la rueda o la barra inferior. "
                "Podés plegar este bloque para ganar espacio."
            )
            st.markdown(
                '<div class="mc-hist-cortina-mark" aria-hidden="true"></div>',
                unsafe_allow_html=True,
            )
            seccion_actual = st.pills(
                "Elegí una sección",
                lista_secciones,
                selection_mode="single",
                key=key_sec,
                label_visibility="collapsed",
            )
        if not seccion_actual:
            seccion_actual = st.session_state.get(key_sec) or lista_secciones[0]
        registros = secciones.get(seccion_actual, [])
    
        if not registros:
            bloque_estado_vacio(
                "Sección vacía",
                "Esta sección no tiene filas para mostrar.",
                sugerencia="Elegí otra sección en el listado o verificá que existan cargas en ese módulo.",
            )
            return
    
        c_opt1, c_opt2, c_opt3 = st.columns(3)
        usar_fecha = c_opt1.checkbox(
            "Filtrar esta sección por fechas de los registros",
            value=False,
            key=f"hist_use_fecha_{paciente_sel}",
        )
        incluir_sin_fecha = c_opt2.checkbox(
            "Incluir registros sin fecha (si el filtro está activo)",
            value=True,
            key=f"hist_sin_fecha_{paciente_sel}",
        )
        orden_etiqueta = c_opt3.radio(
            "Orden",
            ["Más recientes primero", "Más antiguos primero"],
            horizontal=True,
            key=f"hist_orden_{paciente_sel}",
        )
        recientes_primero = orden_etiqueta.startswith("Más recientes")
    
        hoy = ahora().date()
        default_desde = hoy - timedelta(days=90)
        if usar_fecha:
            rango = st.date_input(
                "Rango (fecha del registro)",
                value=(default_desde, hoy),
                key=f"hist_rango_fecha_{paciente_sel}_{seccion_actual}",
            )
            if isinstance(rango, tuple) and len(rango) == 2:
                d_desde, d_hasta = rango[0], rango[1]
            elif hasattr(rango, "year"):
                d_desde = d_hasta = rango
            else:
                d_desde, d_hasta = default_desde, hoy
            if d_desde > d_hasta:
                d_desde, d_hasta = d_hasta, d_desde
            registros_fecha = [
                r
                for r in registros
                if registro_en_rango_fechas(
                    r, d_desde, d_hasta, incluir_sin_fecha=incluir_sin_fecha
                )
            ]
        else:
            registros_fecha = list(registros)
    
        buscar = st.text_input(
            "Buscar texto en esta sección",
            "",
            key=f"hist_buscar_{paciente_sel}_{seccion_actual}",
            placeholder="Profesional, medicación, detalle, estado…",
        )
        registros_filtrados = [r for r in registros_fecha if _registro_coincide_busqueda(r, buscar)]
        if buscar.strip() and not registros_filtrados:
            bloque_estado_vacio(
                "Sin coincidencias",
                "Ningún registro de esta sección coincide con el texto buscado.",
                sugerencia="Probá otras palabras o limpiá el campo de búsqueda.",
            )
            return
    
        registros_base = registros_filtrados if buscar.strip() else registros_fecha
        if usar_fecha and not registros_base:
            bloque_estado_vacio(
                "Fuera de rango",
                "Ningún registro cae en el rango de fechas indicado.",
                sugerencia="Ampliá las fechas o activá «Incluir registros sin fecha» si corresponde.",
            )
            return
    
        registros_ordenados = sort_registros_por_fecha(
            registros_base, recientes_primero=recientes_primero
        )
        total_registros_seccion = len(registros_ordenados)
        limite_pagina = min(max(int(limite), 1), 500)
        paginas = max((total_registros_seccion - 1) // limite_pagina + 1, 1)
        col_pag1, col_pag2 = st.columns([2, 1])
        col_pag1.caption(f"Tamaño de página: {limite_pagina} registro(s)")
        pagina = col_pag2.number_input(
            "Página de la sección",
            min_value=1,
            max_value=paginas,
            value=1,
            step=1,
            key=f"hist_pag_{paciente_sel}_{_nombre_archivo_seguro(seccion_actual, 24)}",
        )
        inicio = (int(pagina) - 1) * limite_pagina
        fin = inicio + limite_pagina
        registros_mostrar = registros_ordenados[inicio:fin]
    
        st.caption(
            f"Mostrando {len(registros_mostrar)} de {len(registros_base)} registros en «{seccion_actual}»"
            f" (página {int(pagina)}/{paginas})"
            f"{f' (filtrados de {len(registros)})' if (buscar.strip() or usar_fecha) else ''}."
        )
    
        csv_bytes = _dataframe_seccion_a_csv(registros_mostrar)
        if csv_bytes:
            fn = f"Historia_{_nombre_archivo_seguro(paciente_sel.split('(')[0])}_{_nombre_archivo_seguro(seccion_actual, 40)}.csv"
            st.download_button(
                "Descargar esta vista en CSV",
                csv_bytes,
                file_name=fn,
                mime="text/csv; charset=utf-8",
                key=f"hist_csv_vista_{paciente_sel}_{_nombre_archivo_seguro(seccion_actual, 30)}",
            )
    
        if seccion_actual in SECCIONES_TABLA:
            _render_seccion_tabla(registros_mostrar, seccion_actual)
        elif seccion_actual == "Consentimientos":
            _render_consentimientos(registros_mostrar, paciente_sel)
        elif seccion_actual == "Estudios Complementarios":
            _render_estudios(registros_mostrar, paciente_sel)
        elif seccion_actual == "Registro de Heridas":
            _render_heridas(registros_mostrar, paciente_sel)
        else:
            _render_registros_genericos(registros_mostrar, seccion_actual, paciente_sel)
