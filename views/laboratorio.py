"""Laboratorio (LIS): ordenes, muestras, resultados, catalogo, subida de archivos."""
from __future__ import annotations

import base64
import hashlib
import html
import json
import uuid
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from core.alert_toasts import queue_toast
from core.app_logging import log_event
from core.database import guardar_datos
from core.export_utils import sanitize_filename_component
from core.utils import ahora
from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio

try:
    from fpdf import FPDF
    FPDF_OK = True
except ImportError:
    FPDF_OK = False

_INTRO = """
<div class="mc-hero">
    <h2 class="mc-hero-title">Laboratorio (LIS)</h2>
    <p class="mc-hero-text">Gestion completa: ordenes, muestras, resultados analiticos y catalogo de estudios.</p>
</div>
"""


# ─── helpers ──────────────────────────────────────────────────

def _id_unico() -> str:
    return str(uuid.uuid4())[:12]


def _ahora_iso() -> str:
    return datetime.now().isoformat()


def _init_keys():
    for k in ["lab_categorias", "lab_estudios", "lab_ordenes", "lab_orden_items", "lab_muestras"]:
        if k not in st.session_state or not isinstance(st.session_state[k], list):
            st.session_state[k] = []


def _categorias() -> list:
    return st.session_state.setdefault("lab_categorias", [])


def _estudios() -> list:
    return st.session_state.setdefault("lab_estudios", [])


def _ordenes() -> list:
    return st.session_state.setdefault("lab_ordenes", [])


def _orden_items() -> list:
    return st.session_state.setdefault("lab_orden_items", [])


def _muestras() -> list:
    return st.session_state.setdefault("lab_muestras", [])


def _cat_nombre(cat_id) -> str:
    for c in _categorias():
        if c.get("id") == cat_id:
            return c.get("nombre", "")
    return ""


def _estudio_nombre(eid) -> str:
    for e in _estudios():
        if e.get("id") == eid:
            return e.get("nombre", "")
    return ""


def _flag_desc(flag):
    return {"H": "ALTO", "L": "BAJO", "N": "Normal", "" : ""}.get(flag, flag)


def _valor_dentro_rango(valor_str, estudio) -> str:
    """Retorna flag H/L/N segun rango de referencia."""
    try:
        v = float(valor_str.replace(",", "."))
        t = estudio.get("tipo_valor", "numeric")
        if t != "numeric":
            return ""
        rmin = estudio.get("valor_referencia_min")
        rmax = estudio.get("valor_referencia_max")
        if rmin is not None and rmax is not None:
            if v < float(rmin):
                return "L"
            if v > float(rmax):
                return "H"
        return "N"
    except (ValueError, TypeError):
        return ""


def _sync_categorias_sql():
    try:
        from core.db_sql import get_lab_categorias, insert_lab_categoria
        sql_cats = get_lab_categorias()
        sql_nombres = {c.get("nombre", "").strip().lower() for c in sql_cats}
        for c in _categorias():
            if c.get("nombre", "").strip().lower() not in sql_nombres:
                insert_lab_categoria(c["nombre"], c.get("descripcion", ""))
    except Exception:
        pass


def _sync_estudios_sql():
    try:
        from core.db_sql import get_lab_estudios, insert_lab_estudio
        sql_ests = get_lab_estudios()
        sql_ids = {e.get("nombre", "").strip().lower() for e in sql_ests}
        for e in _estudios():
            if e.get("nombre", "").strip().lower() not in sql_ids:
                insert_lab_estudio(e)
    except Exception:
        pass


# ─── generar PDF de resultados ────────────────────────────────

def _generar_pdf_resultados(orden, items):
    if not FPDF_OK:
        return b""
    pdf = FPDF(format="A4")
    pdf.set_margins(12, 10, 12)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Resultados de Laboratorio", align="C")
    pdf.ln(12)
    pdf.set_font("Helvetica", "", 10)
    for label, key in [("Paciente", "paciente"), ("Fecha orden", "fecha_orden"),
                       ("Medico", "medico"), ("Prioridad", "prioridad")]:
        v = str(orden.get(key, "") or "")
        if v:
            pdf.cell(40, 6, label + ":")
            pdf.cell(0, 6, v, ln=True)
    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 9)
    headers = ["Estudio", "Resultado", "Unidad", "Rango ref.", "Flag"]
    widths = [60, 30, 30, 40, 18]
    for h, w in zip(headers, widths):
        pdf.cell(w, 7, h, border=1, align="C")
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for it in items:
        est = it.get("estudio_nombre", "")
        res = it.get("resultado", "")
        uni = it.get("unidad", "")
        ref = it.get("rango_ref", "")
        flag = it.get("flag", "")
        pdf.cell(widths[0], 6, est[:50], border=1)
        pdf.cell(widths[1], 6, res[:20], border=1)
        pdf.cell(widths[2], 6, uni[:20], border=1)
        pdf.cell(widths[3], 6, ref[:30], border=1)
        pdf.cell(widths[4], 6, flag, border=1)
        pdf.ln()
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 5, f"Generado: {_ahora_iso()[:16]}", align="C")
    return pdf.output(dest="S").encode("latin-1", errors="replace")


# ─── main render ──────────────────────────────────────────────

def render_laboratorio(paciente_sel, mi_empresa, user, rol):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    _init_keys()

    st.markdown(_INTRO, unsafe_allow_html=True)

    tabs = st.tabs([
        "Ordenar estudios",
        "Muestras",
        "Cargar resultados",
        "Resultados",
        "Catalogo",
        "Subir archivo",
    ])

    # ── TAB 0: ORDENAR ESTUDIOS ──────────────────────────────
    with tabs[0]:
        _tab_ordenar(paciente_sel, mi_empresa, user)

    # ── TAB 1: MUESTRAS ─────────────────────────────────────
    with tabs[1]:
        _tab_muestras()

    # ── TAB 2: CARGAR RESULTADOS ─────────────────────────────
    with tabs[2]:
        _tab_cargar_resultados()

    # ── TAB 3: RESULTADOS ────────────────────────────────────
    with tabs[3]:
        _tab_resultados(paciente_sel)

    # ── TAB 4: CATALOGO ─────────────────────────────────────
    with tabs[4]:
        _tab_catalogo()

    # ── TAB 5: SUBIR ARCHIVO (legacy) ───────────────────────
    with tabs[5]:
        _tab_subir_archivo(paciente_sel, mi_empresa, user)


# ─── TAB: Ordenar estudios ────────────────────────────────────

def _tab_ordenar(paciente_sel, mi_empresa, user):
    st.markdown("##### Nueva orden de laboratorio")

    col_m, col_p = st.columns(2)
    medico = col_m.text_input("Medico solicitante", value=user.get("nombre", ""))
    prioridad = col_p.selectbox("Prioridad", ["Normal", "Urgente"])

    categorias = _categorias()
    estudios = _estudios()

    if not categorias:
        st.info("No hay categorias. Andá a la pestaña Catalogo para crear el catalogo de estudios.")
        return

    cat_nombres = [c["nombre"] for c in categorias]
    cat_sel = st.selectbox("Categoria", cat_nombres)
    cat_id = next((c["id"] for c in categorias if c["nombre"] == cat_sel), None)

    est_en_cat = [e for e in estudios if e.get("categoria_id") == cat_id]
    if not est_en_cat:
        st.info("No hay estudios en esta categoria. Cargalos en Catalogo.")
        est_seleccionados = []
    else:
        est_opts = {e["nombre"]: e for e in est_en_cat}
        est_seleccionados = st.multiselect("Estudios a solicitar", list(est_opts.keys()))

    obs = st.text_area("Observaciones", placeholder="Indicaciones clinicas...")
    obs_val = obs.strip()

    if st.button("Generar orden", type="primary", width="stretch"):
        if not est_seleccionados:
            st.error("Selecciona al menos un estudio.")
        else:
            oid = _id_unico()
            orden = {
                "id": oid,
                "paciente": paciente_sel,
                "medico": medico.strip() or user.get("nombre", ""),
                "prioridad": prioridad,
                "fecha_orden": _ahora_iso(),
                "estado": "pendiente",
                "observaciones": obs_val,
                "empresa": mi_empresa,
                "creado_por": user.get("nombre", ""),
            }
            _ordenes().append(orden)
            for en in est_seleccionados:
                e = est_opts[en]
                _orden_items().append({
                    "id": _id_unico(),
                    "orden_id": oid,
                    "estudio_id": e.get("id"),
                    "estudio_nombre": e["nombre"],
                    "unidad": e.get("unidad", ""),
                    "rango_ref": e.get("valor_referencia_texto", ""),
                    "resultado": "",
                    "flag": "",
                    "estado": "pendiente",
                })
            guardar_datos(spinner=True)
            _sync_categorias_sql()
            _sync_estudios_sql()
            try:
                from core.db_sql import insert_lab_orden
                insert_lab_orden({
                    "paciente_id": paciente_sel,
                    "paciente_nombre": paciente_sel,
                    "medico_solicitante": medico.strip() or user.get("nombre", ""),
                    "prioridad": prioridad.lower(),
                    "observaciones": obs_val,
                    "estado": "pendiente",
                    "empresa": mi_empresa,
                    "created_by": user.get("nombre", ""),
                })
            except Exception:
                pass
            queue_toast(f"Orden generada: {len(est_seleccionados)} estudio(s)")
            st.rerun()

    st.divider()
    st.markdown("##### Ordenes pendientes")
    pendientes = [o for o in _ordenes() if o.get("estado") == "pendiente"]
    if pendientes:
        for o in pendientes:
            items_ord = [it for it in _orden_items() if it.get("orden_id") == o["id"]]
            with st.container(border=True):
                st.markdown(f"**{o.get('fecha_orden', '')[:16]}** - {o.get('paciente', '')}  |  {len(items_ord)} estudio(s)  |  {o.get('medico', '')}")
                for it in items_ord:
                    st.caption(f"  - {it.get('estudio_nombre', '')}")
    else:
        st.caption("Sin ordenes pendientes.")


# ─── TAB: Muestras ────────────────────────────────────────────

def _tab_muestras():
    st.markdown("##### Registrar toma de muestra")

    ordenes_pend = [o for o in _ordenes() if o.get("estado") in ("pendiente", "tomada")]
    if not ordenes_pend:
        st.info("No hay ordenes pendientes de muestra.")
        return

    ord_opts = {f"{o.get('fecha_orden', '')[:16]} - {o.get('paciente', '')} - {o.get('id', '')}" : o for o in ordenes_pend}
    ord_sel = st.selectbox("Seleccionar orden", list(ord_opts.keys()))
    orden = ord_opts[ord_sel]

    with st.container(border=True):
        st.markdown(f"**Paciente:** {orden.get('paciente', '')}")
        st.markdown(f"**Medico:** {orden.get('medico', '')}")
        items_ord = [it for it in _orden_items() if it.get("orden_id") == orden["id"]]
        for it in items_ord:
            st.caption(f"  - {it.get('estudio_nombre', '')}")

    tipo_muestra = st.selectbox("Tipo de muestra", ["Sangre", "Orina", "Heces", "Esputo", "LCR", "Secrecion", "Tejido", "Otro"])
    observaciones_m = st.text_input("Observaciones de la muestra")

    if st.button("Registrar muestra", type="primary"):
        mid = _id_unico()
        cod_barras = f"LAB-{orden['id'][:8]}-{mid[:6]}"
        _muestras().append({
            "id": mid,
            "orden_id": orden["id"],
            "codigo_barras": cod_barras,
            "tipo_muestra": tipo_muestra,
            "fecha_toma": _ahora_iso(),
            "tomada_por": st.session_state.get("u_actual", {}).get("nombre", ""),
            "estado": "tomada",
            "observaciones": observaciones_m.strip(),
        })
        orden["estado"] = "tomada"
        guardar_datos(spinner=True)
        try:
            from core.db_sql import insert_lab_muestra
            insert_lab_muestra({
                "orden_id": orden.get("id_sql"),
                "codigo_barras": cod_barras,
                "tipo_muestra": tipo_muestra,
                "estado": "tomada",
            })
            from core.db_sql import update_lab_orden
            update_lab_orden(orden.get("id_sql"), {"estado": "tomada"})
        except Exception:
            pass
        st.success(f"Muestra registrada. Codigo: **{cod_barras}**")
        st.rerun()

    st.divider()
    st.markdown("##### Muestras registradas")
    todas = _muestras()
    if todas:
        for m in reversed(todas[-20:]):
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                col1.markdown(f"**{m.get('codigo_barras', '')}** - {m.get('tipo_muestra', '')}")
                col2.caption(m.get("fecha_toma", "")[:16] if m.get("fecha_toma") else "")
                ord_rel = next((o for o in _ordenes() if o["id"] == m.get("orden_id")), None)
                if ord_rel:
                    st.caption(f"Paciente: {ord_rel.get('paciente', '')}")
    else:
        st.caption("Sin muestras registradas.")


# ─── TAB: Cargar resultados ───────────────────────────────────

def _tab_cargar_resultados():
    st.markdown("##### Cargar resultados de analitos")

    ordenes_tomadas = [o for o in _ordenes() if o.get("estado") in ("tomada", "en_proceso")]
    if not ordenes_tomadas:
        st.info("No hay ordenes con muestra tomada pendientes de resultado.")
        return

    ord_opts = {f"{o.get('fecha_orden', '')[:16]} - {o.get('paciente', '')}" : o for o in ordenes_tomadas}
    ord_sel = st.selectbox("Seleccionar orden", list(ord_opts.keys()), key="res_ord_sel")
    orden = ord_opts[ord_sel]
    items_pend = [it for it in _orden_items() if it.get("orden_id") == orden["id"]]

    if not items_pend:
        st.info("Todos los resultados ya fueron cargados para esta orden.")
        return

    st.markdown(f"**Paciente:** {orden.get('paciente', '')} | **Medico:** {orden.get('medico', '')}")
    cambios = False

    for it in items_pend:
        with st.container(border=True):
            st.markdown(f"**{it.get('estudio_nombre', '')}**")
            col1, col2, col3 = st.columns([2, 1, 1])
            rango = it.get("rango_ref", "")
            unidad = it.get("unidad", "")
            key_r = f"res_v_{it['id']}"

            estudio = next((e for e in _estudios() if e.get("id") == it.get("estudio_id")), {})
            tipo = estudio.get("tipo_valor", "numeric")

            if tipo == "numeric":
                valor = col1.text_input("Valor", value=it.get("resultado", ""), key=key_r)
                col2.markdown(f"**Ref:** {rango}" if rango else "")
                col3.markdown(f"**Unidad:** {unidad}" if unidad else "")
            elif tipo == "text":
                valor = col1.text_input("Valor (texto)", value=it.get("resultado", ""), key=key_r)
            elif tipo == "select":
                opts = estudio.get("opciones", [])
                if opts:
                    valor = col1.selectbox("Valor", [""] + opts, key=key_r)
                else:
                    valor = col1.text_input("Valor", value=it.get("resultado", ""), key=key_r)

            if valor and valor != it.get("resultado", ""):
                flag = _valor_dentro_rango(valor, estudio) if tipo == "numeric" else ""
                it["resultado"] = valor
                it["flag"] = flag
                it["estado"] = "completado"
                it["resultado_fecha"] = _ahora_iso()
                it["resultado_por"] = st.session_state.get("u_actual", {}).get("nombre", "")
                cambios = True

                try:
                    from core.db_sql import update_lab_orden_item
                    update_lab_orden_item(it.get("id_sql"), {
                        "resultado_valor": valor,
                        "resultado_flag": flag,
                        "resultado_fecha": _ahora_iso(),
                        "resultado_por": it["resultado_por"],
                        "estado": "completado",
                    })
                except Exception:
                    pass

            if flag == "H":
                col1.warning("ALTO")
            elif flag == "L":
                col1.error("BAJO")

    if cambios:
        orden["estado"] = "en_proceso"
        todos_completos = all(it.get("estado") == "completado" for it in items_pend)
        if todos_completos:
            orden["estado"] = "completada"
        guardar_datos(spinner=True)
        try:
            from core.db_sql import update_lab_orden
            update_lab_orden(orden.get("id_sql"), {"estado": orden["estado"]})
        except Exception:
            pass

    st.divider()
    if st.button("Marcar orden como completada", width="stretch"):
        for it in items_pend:
            if it.get("estado") != "completado":
                it["estado"] = "completado"
        orden["estado"] = "completada"
        guardar_datos(spinner=True)
        st.success("Orden completada.")
        st.rerun()


# ─── TAB: Resultados ──────────────────────────────────────────

def _tab_resultados(paciente_sel):
    st.markdown(f"##### Resultados de {paciente_sel}")

    ordenes_pac = [o for o in _ordenes() if o.get("paciente") == paciente_sel and o.get("estado") in ("en_proceso", "completada")]
    if not ordenes_pac:
        st.info("No hay resultados para este paciente.")
        return

    for o in reversed(ordenes_pac[-20:]):
        items_ord = [it for it in _orden_items() if it.get("orden_id") == o["id"] and it.get("resultado")]
        if not items_ord:
            continue
        with st.container(border=True):
            st.markdown(f"**{o.get('fecha_orden', '')[:16]}** | {o.get('medico', '')} | {o.get('estado', '')}")
            for it in items_ord:
                flag = it.get("flag", "")
                flag_icon = {"H": " ALTO", "L": " BAJO", "N": ""}.get(flag, "")
                col1, col2, col3 = st.columns([3, 1, 1])
                col1.markdown(f"{it.get('estudio_nombre', '')}")
                col2.markdown(f"**{it.get('resultado', '')}** {flag_icon}")
                col3.markdown(f"{it.get('unidad', '')}")

    # exportar ultima orden como PDF
    ultima = None
    for o in reversed(ordenes_pac):
        items_ult = [it for it in _orden_items() if it.get("orden_id") == o["id"] and it.get("resultado")]
        if items_ult:
            ultima = (o, items_ult)
            break
    if ultima:
        o, items_ult = ultima
        pdf_bytes = _generar_pdf_resultados(o, items_ult)
        if pdf_bytes:
            nf = sanitize_filename_component(f"lab_{paciente_sel}_{datetime.now().strftime('%Y%m%d')}")
            st.download_button("Descargar ultimo resultado PDF", pdf_bytes, f"{nf}.pdf", "application/pdf", width="stretch")


# ─── TAB: Catalogo ────────────────────────────────────────────

def _tab_catalogo():
    st.markdown("##### Catalogo de estudios")

    seccion = st.radio("Seccion", ["Categorias", "Estudios / analitos"], horizontal=True, label_visibility="collapsed")

    if seccion == "Categorias":
        c_nombre = st.text_input("Nueva categoria", placeholder="Ej: Hematologia, Bioquimica...", key="cat_new")
        c_desc = st.text_input("Descripcion (opcional)", key="cat_desc")
        if st.button("Agregar categoria") and c_nombre.strip():
            cats = _categorias()
            if any(c["nombre"].lower() == c_nombre.strip().lower() for c in cats):
                st.warning("Ya existe.")
            else:
                cats.append({
                    "id": _id_unico(),
                    "nombre": c_nombre.strip().title(),
                    "descripcion": c_desc.strip(),
                })
                guardar_datos(spinner=True)
                _sync_categorias_sql()
                st.rerun()

        cats = _categorias()
        if cats:
            for c in cats:
                st.markdown(f"- **{c['nombre']}** — {c.get('descripcion', '')}")
        else:
            st.caption("Sin categorias.")
        return

    # seccion == "Estudios / analitos"
    cats = _categorias()
    if not cats:
        st.info("Primero crea una categoria.")
        return

    cat_nombres = [c["nombre"] for c in cats]
    cat_sel = st.selectbox("Categoria", cat_nombres, key="est_cat_sel")
    cat_id = next((c["id"] for c in cats if c["nombre"] == cat_sel), None)

    st.markdown("###### Nuevo estudio")
    col1, col2 = st.columns(2)
    nombre_e = col1.text_input("Nombre del estudio", placeholder="Ej: Hemoglobina", key="est_new")
    codigo_e = col2.text_input("Codigo (opcional)", placeholder="LOINC / interno", key="est_code")
    col3, col4 = st.columns(2)
    unidad_e = col3.text_input("Unidad", placeholder="g/dL, mg/dL...", key="est_unit")
    tipo_e = col4.selectbox("Tipo de valor", ["numeric", "text", "select"], key="est_tipo")
    ref_min = ref_max = ref_texto = None
    opciones = []
    if tipo_e == "numeric":
        col5, col6 = st.columns(2)
        ref_min = col5.number_input("Ref. minima", value=0.0, step=0.1, key="est_ref_min")
        ref_max = col6.number_input("Ref. maxima", value=10.0, step=0.1, key="est_ref_max")
        ref_texto = f"{ref_min} - {ref_max} {unidad_e}"
    elif tipo_e == "text":
        ref_texto = st.text_input("Texto de referencia", placeholder="Ej: Negativo, No reactivo", key="est_ref_txt")
    elif tipo_e == "select":
        opcs_str = st.text_input("Opciones (separadas por coma)", placeholder="Positivo, Negativo, Dudoso", key="est_opts")
        opciones = [o.strip() for o in opcs_str.split(",") if o.strip()]

    if st.button("Agregar estudio", key="add_est") and nombre_e.strip():
        ests = _estudios()
        if any(e["nombre"].lower() == nombre_e.strip().lower() for e in ests):
            st.warning("Ya existe.")
        else:
            ests.append({
                "id": _id_unico(),
                "categoria_id": cat_id,
                "nombre": nombre_e.strip().title(),
                "codigo": codigo_e.strip(),
                "unidad": unidad_e.strip(),
                "tipo_valor": tipo_e,
                "valor_referencia_min": float(ref_min) if ref_min is not None else None,
                "valor_referencia_max": float(ref_max) if ref_max is not None else None,
                "valor_referencia_texto": ref_texto or "",
                "opciones": opciones,
            })
            guardar_datos(spinner=True)
            _sync_estudios_sql()
            st.rerun()

    ests_cat = [e for e in _estudios() if e.get("categoria_id") == cat_id]
    if ests_cat:
        df = pd.DataFrame(ests_cat)
        cols_show = [c for c in ["nombre", "codigo", "unidad", "valor_referencia_texto", "tipo_valor"] if c in df.columns]
        st.dataframe(df[cols_show], width='stretch')
    else:
        st.caption("Sin estudios en esta categoria.")


# ─── TAB: Subir archivo (legacy) ──────────────────────────────

def _tab_subir_archivo(paciente_sel, mi_empresa, user):
    st.markdown("##### Subir resultado completo (PDF/imagen)")
    st.caption("Para resultados ya emitidos por el laboratorio externo.")

    if "laboratorio_db" not in st.session_state:
        st.session_state["laboratorio_db"] = []
    lab_db = st.session_state["laboratorio_db"]
    lab_paciente = [r for r in lab_db if r.get("paciente") == paciente_sel]

    with st.form("lab_form_upload", clear_on_submit=True):
        c1, c2 = st.columns(2)
        tipo_estudio = c1.text_input("Tipo de estudio", placeholder="Ej: Analisis clinico, Perfil hepatico...")
        fecha = c2.date_input("Fecha del analisis", value=ahora().date())
        medico = st.text_input("Medico solicitante", placeholder="Opcional")
        archivo = st.file_uploader("Subir resultado (PDF, imagen)", type=["pdf", "png", "jpg", "jpeg"])
        observaciones = st.text_area("Notas", placeholder="Comentarios sobre el resultado...")

        if st.form_submit_button("Guardar estudio", width="stretch", type="primary"):
            if not tipo_estudio.strip():
                st.error("El tipo de estudio es obligatorio.")
            elif archivo is None:
                st.error("Debe adjuntar el archivo.")
            else:
                archivo_b64 = base64.b64encode(archivo.getvalue()).decode()
                lab_db.append({
                    "paciente": paciente_sel,
                    "tipo_estudio": tipo_estudio.strip(),
                    "fecha": fecha.strftime("%d/%m/%Y"),
                    "medico_solicitante": medico.strip(),
                    "observaciones": observaciones.strip(),
                    "archivo_b64": archivo_b64,
                    "archivo_tipo": archivo.type or "",
                    "archivo_nombre": archivo.name,
                    "visto": False,
                    "empresa": mi_empresa,
                    "registrado_por": user.get("nombre", "Sistema"),
                    "fecha_registro": _ahora_iso(),
                    "id": f"lab_{int(datetime.now().timestamp())}",
                })
                guardar_datos(spinner=True)
                queue_toast(f"Estudio {tipo_estudio.strip()} guardado.")
                st.rerun()

    if lab_paciente:
        for i, r in enumerate(reversed(lab_paciente)):
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 1, 1])
                col1.markdown(f"**{r.get('tipo_estudio','?')}** — {r.get('fecha','')}")
                col2.markdown("Visto" if r.get("visto") else "Pendiente")
                col3.caption(f"Dr. {r['medico_solicitante']}" if r.get("medico_solicitante") else "")
                if r.get("archivo_b64"):
                    at = r.get("archivo_tipo", "application/octet-stream")
                    an = r.get("archivo_nombre", "resultado")
                    ab = r["archivo_b64"]
                    st.markdown(f'<a href="data:{html.escape(at)};base64,{html.escape(ab)}" download="{html.escape(an)}" target="_blank">Ver archivo</a>', unsafe_allow_html=True)
                cols_btn = st.columns(3)
                pdf_bytes = _generar_pdf_lab_legacy(r)
                if pdf_bytes and cols_btn[0].download_button("PDF", pdf_bytes, f"lab_{r.get('tipo_estudio','r')}.pdf", "application/pdf", key=f"lp_{i}", width="content"):
                    pass
                if not r.get("visto") and cols_btn[1].button("Visto", key=f"lv_{i}", width="content"):
                    r["visto"] = True
                    guardar_datos(spinner=True)
                    st.rerun()
                if cols_btn[2].button("Eliminar", key=f"ld_{i}", width="content"):
                    lab_db.remove(r)
                    guardar_datos(spinner=True)
                    st.rerun()
    else:
        bloque_estado_vacio("Sin estudios", "No hay resultados de laboratorio subidos para este paciente.")


def _generar_pdf_lab_legacy(registro):
    if not FPDF_OK:
        return b""
    try:
        pdf = FPDF(format="A4")
        pdf.set_margins(15, 10, 15)
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 12, "Resultado de Laboratorio", align="C")
        pdf.ln(14)
        pdf.set_font("Helvetica", "", 10)
        for label, key in [("Paciente", "paciente"), ("Tipo de estudio", "tipo_estudio"),
                           ("Fecha del analisis", "fecha"), ("Medico solicitante", "medico_solicitante"),
                           ("Observaciones", "observaciones")]:
            val = str(registro.get(key, "") or "")
            if val:
                pdf.set_font("Helvetica", "B", 9)
                pdf.cell(42, 6, label + ":")
                pdf.set_font("Helvetica", "", 9)
                pdf.multi_cell(0, 6, val)
                pdf.ln(2)
        pdf.ln(10)
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(0, 5, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')} | ID: {registro.get('id','')}", align="C")
        return pdf.output(dest="S").encode("latin-1", errors="replace")
    except Exception as e:
        log_event("lab", f"error_pdf:{e}")
        return b""
