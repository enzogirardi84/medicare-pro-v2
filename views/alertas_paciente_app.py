from core.alert_toasts import queue_toast
"""
Panel de alertas desde la app paciente (Supabase tabla alertas_pacientes).
Flujo triage: Rojo / Amarillo / Verde. Estados: Pendiente, En camino, Resuelto.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from core.norm_empresa import norm_empresa_key
from core.database import supabase
from core.utils import es_control_total


def _osm_link(lat: Any, lon: Any) -> str:
    try:
        if lat is None or lon is None:
            return ""
        la, lo = float(lat), float(lon)
        if not (-90 <= la <= 90) or not (-180 <= lo <= 180):
            return ""
        return f"https://www.openstreetmap.org/?mlat={la}&mlon={lo}&zoom=16"
    except (TypeError, ValueError):
        return ""


OPTIONS_ESTADO = ["Pendiente", "En camino", "Resuelto"]
OPTIONS_NIVEL = ["Rojo", "Amarillo", "Verde"]


def _fetch_alertas_filtradas(
    *,
    vista_todas: bool,
    emp_key: str,
    limite: int,
    filtro_estado: List[str],
    filtro_nivel: List[str],
) -> List[Dict[str, Any]]:
    """
    Lee Supabase con límite y, si el triage está acotado, filtra nivel en servidor
    (menos filas transferidas). El estado se refina en Python para respetar filas sin
    campo `estado` (se tratan como Pendiente), igual que antes.
    """
    q = supabase.table("alertas_pacientes").select("*")
    if not vista_todas:
        q = q.eq("empresa", emp_key)
    if filtro_nivel and len(filtro_nivel) < len(OPTIONS_NIVEL):
        q = q.in_("nivel_urgencia", filtro_nivel)
    resp = q.order("fecha_hora", desc=True).limit(int(limite)).execute()
    rows = list(resp.data or [])
    if filtro_estado:
        rows = [r for r in rows if str(r.get("estado") or "Pendiente") in filtro_estado]
    return rows


def _ordenar_filas(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rojo primero, luego Amarillo, Verde; dentro de cada grupo mas reciente primero."""

    def nivel_ord(n: Any) -> int:
        s = str(n or "").strip()
        if s == "Rojo":
            return 0
        if s == "Amarillo":
            return 1
        if s == "Verde":
            return 2
        return 9

    def by_fecha(r: Dict[str, Any]) -> str:
        return str(r.get("fecha_hora") or r.get("created_at") or "")

    buckets: Dict[int, List[Dict[str, Any]]] = {0: [], 1: [], 2: [], 9: []}
    for r in rows:
        buckets[nivel_ord(r.get("nivel_urgencia"))].append(r)
    out: List[Dict[str, Any]] = []
    for b in (0, 1, 2, 9):
        part = sorted(buckets[b], key=by_fecha, reverse=True)
        out.extend(part)
    return out


def render_alertas_paciente_app(mi_empresa: str, user: dict, rol: str | None = None) -> None:
    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Alertas app paciente</h2>
            <p class="mc-hero-text">Triage <b>Rojo</b> (riesgo de vida), <b>Amarillo</b> (urgencia), <b>Verde</b> (consulta). Tabla <code>alertas_pacientes</code> en Supabase.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if supabase is None:
        st.warning(
            "Supabase no esta configurado en secrets (**SUPABASE_URL** / **SUPABASE_KEY**). "
            "Este modulo solo funciona con base en la nube."
        )
        return

    emp_key = norm_empresa_key(mi_empresa)
    control = es_control_total(rol)

    vista_todas = False
    if control:
        vista_todas = st.toggle(
            "Ver alertas de todas las clinicas",
            value=False,
            help="Solo roles con control total.",
        )

    if vista_todas:
        st.caption("Modo multi-clinica: columna **empresa** visible.")
    else:
        st.caption(
            f"Clinica en sesion: **{mi_empresa or 'S/D'}** (clave `{emp_key or '—'}`). "
            "La app debe enviar la misma clinica en minusculas."
        )

    filtro_estado = st.multiselect(
        "Filtrar por estado",
        options=OPTIONS_ESTADO,
        default=list(OPTIONS_ESTADO),
        key="mc_alertas_filtro_estado",
    )
    filtro_nivel = st.multiselect(
        "Filtrar por triage",
        options=OPTIONS_NIVEL,
        default=list(OPTIONS_NIVEL),
        key="mc_alertas_filtro_nivel",
    )

    c_ref, c_lim = st.columns([1, 2])
    with c_ref:
        if st.button("Actualizar lista", use_container_width=True, key="mc_alertas_refresh"):
            st.rerun()
    with c_lim:
        limite = st.slider("Maximo de filas", 50, 500, 200, 50, key="mc_alertas_limite")

    if not filtro_estado or not filtro_nivel:
        st.warning("Seleccioná al menos un **estado** y un **nivel de triage**.")
        rows = []
    else:
        try:
            rows = _fetch_alertas_filtradas(
                vista_todas=vista_todas,
                emp_key=emp_key,
                limite=limite,
                filtro_estado=filtro_estado,
                filtro_nivel=filtro_nivel,
            )
        except Exception as exc:
            st.error(
                "No se pudo leer **alertas_pacientes**. Ejecuta `supabase/alertas_pacientes.sql` y despliega la Edge Function **submit-alerta-paciente**."
            )
            with st.expander("Detalle"):
                st.code(f"{type(exc).__name__}: {exc}", language="text")
            return

    rows = _ordenar_filas(rows)

    n_rojo = sum(1 for r in rows if str(r.get("nivel_urgencia")) == "Rojo")
    n_ama = sum(1 for r in rows if str(r.get("nivel_urgencia")) == "Amarillo")
    n_ver = sum(1 for r in rows if str(r.get("nivel_urgencia")) == "Verde")
    n_pend = sum(1 for r in rows if str(r.get("estado")) == "Pendiente")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("En pantalla", len(rows))
    m2.metric("Rojo", n_rojo)
    m3.metric("Amarillo", n_ama)
    m4.metric("Verde", n_ver)
    m5.metric("Pendientes", n_pend)

    if not rows:
        st.info("No hay alertas con estos filtros.")
        return

    df = pd.DataFrame(rows)
    df["mapa"] = [_osm_link(r.get("latitud"), r.get("longitud")) or None for r in rows]
    show_cols = [
        c
        for c in (
            "fecha_hora",
            "nivel_urgencia",
            "estado",
            "empresa",
            "paciente_id",
            "sintoma",
            "latitud",
            "longitud",
            "precision_m",
            "atendido_por",
            "mapa",
        )
        if c in df.columns
    ]
    if not vista_todas and "empresa" in show_cols:
        show_cols.remove("empresa")

    df_kwargs: Dict[str, Any] = {"use_container_width": True, "hide_index": True}
    if "mapa" in show_cols:
        df_kwargs["column_config"] = {
            "mapa": st.column_config.LinkColumn(
                "Mapa",
                help="OpenStreetMap",
                display_text="Abrir mapa",
            )
        }

    st.dataframe(df[show_cols], **df_kwargs)

    try:
        csv_bytes = df[show_cols].to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="Descargar CSV",
            data=csv_bytes,
            file_name="alertas_pacientes_medicare.csv",
            mime="text/csv",
            key="mc_alertas_csv",
        )
    except Exception:
        pass

    st.divider()
    st.markdown("##### Actualizar una alerta")

    labels: List[str] = []
    for r in rows:
        rid = r.get("id", "")
        fh = str(r.get("fecha_hora", ""))[:19]
        niv = r.get("nivel_urgencia", "")
        sint = str(r.get("sintoma", ""))[:40]
        emp_lbl = f" [{r.get('empresa')}]" if vista_todas and r.get("empresa") else ""
        labels.append(f"{fh} | {niv}{emp_lbl} | {sint}… [{str(rid)[:8]}]")

    idx = st.selectbox("Elegi alerta", range(len(rows)), format_func=lambda i: labels[i])
    row = rows[idx]
    rid = row.get("id")

    link = _osm_link(row.get("latitud"), row.get("longitud"))
    if link:
        try:
            st.link_button("Ver mapa (OpenStreetMap)", link)
        except Exception:
            st.markdown(f"[Ver mapa]({link})")

    with st.expander("Detalle JSON", expanded=False):
        st.json(row)

    opts_estado = list(OPTIONS_ESTADO)
    st_actual = str(row.get("estado") or "Pendiente")
    idx_est = opts_estado.index(st_actual) if st_actual in opts_estado else 0
    c1, c2 = st.columns(2)
    with c1:
        nuevo = st.selectbox("Estado operativo", opts_estado, index=idx_est)
    with c2:
        notas = st.text_input("Nota interna", value=str(row.get("notas_equipo") or ""))

    if st.button("Guardar cambios", type="primary"):
        try:
            payload = {
                "estado": nuevo,
                "atendido_por": user.get("nombre", ""),
                "notas_equipo": notas.strip() or None,
            }
            supabase.table("alertas_pacientes").update(payload).eq("id", str(rid)).execute()
            for k in ("_mc_app_alerta_fetch", "_mc_app_alerta_ts", "_mc_app_alerta_emp"):
                st.session_state.pop(k, None)
            queue_toast("Actualizado.")
            st.rerun()
        except Exception as exc:
            st.error(f"No se pudo actualizar: {exc}")
