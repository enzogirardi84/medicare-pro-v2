"""
Franja superior de avisos operativos: cambios del sistema (JSON + secret opcional) e insumos con stock bajo o agotado.

El umbral de «stock bajo» coincide con la vista Inventario (≤10 unidades).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import streamlit as st

from core.alert_toasts import (
    firma_avisos_sistema,
    firma_inventario_alerta,
    toast_alerta_si_firma_cambia,
)
from core.utils import cargar_json_asset
from core.view_helpers import lista_plegable

# Alineado con views/inventario.py (stock crítico listado ahí).
STOCK_BAJO_MAX = 10


def _parse_dia(val: Any) -> date | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _avisos_sistema_desde_json() -> list[dict[str, Any]]:
    try:
        raw = cargar_json_asset("avisos_sistema.json")
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        texto = str(row.get("texto", "") or "").strip()
        if not texto:
            continue
        nivel = str(row.get("nivel", "info") or "info").strip().lower()
        if nivel not in {"info", "warning", "danger"}:
            nivel = "info"
        out.append(
            {
                "texto": texto,
                "nivel": nivel,
                "desde": _parse_dia(row.get("desde")),
                "hasta": _parse_dia(row.get("hasta")),
            }
        )
    return out


def _filtrar_por_fecha(avisos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hoy = date.today()
    ok: list[dict[str, Any]] = []
    for a in avisos:
        d0 = a.get("desde")
        d1 = a.get("hasta")
        if d0 is not None and hoy < d0:
            continue
        if d1 is not None and hoy > d1:
            continue
        ok.append(a)
    return ok


def _aviso_extra_secrets() -> list[dict[str, Any]]:
    try:
        raw = st.secrets.get("MC_AVISO_SISTEMA_EXTRA", "")
    except Exception:
        return []
    if raw is None:
        return []
    texto = str(raw).strip()
    if not texto:
        return []
    return [{"texto": texto, "nivel": "info", "desde": None, "hasta": None}]


def clasificar_inventario_alerta(
    inventario_db: list[Any],
    mi_empresa: str,
    *,
    stock_bajo_max: int = STOCK_BAJO_MAX,
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """
    Devuelve (agotados, bajos) como listas de (nombre_item, stock).
    Agotados: stock <= 0. Bajos: 0 < stock <= stock_bajo_max.
    """
    emp = (mi_empresa or "").strip()
    agotados: list[tuple[str, int]] = []
    bajos: list[tuple[str, int]] = []
    if not emp or not isinstance(inventario_db, list):
        return agotados, bajos
    for row in inventario_db:
        if not isinstance(row, dict):
            continue
        if str(row.get("empresa", "") or "").strip() != emp:
            continue
        item = str(row.get("item", "") or "").strip()
        if not item:
            continue
        try:
            stock = int(row.get("stock", 0) or 0)
        except (TypeError, ValueError):
            stock = 0
        if stock <= 0:
            agotados.append((item, stock))
        elif stock <= stock_bajo_max:
            bajos.append((item, stock))
    agotados.sort(key=lambda x: x[0].lower())
    bajos.sort(key=lambda x: (x[1], x[0].lower()))
    return agotados, bajos


_SESSION_INV_DISMISS = "_mc_inv_dismiss_firma"


def render_alerta_inventario_banda_superior(mi_empresa: str) -> None:
    """
    Alerta de stock (agotado / bajo) en formato compacto al inicio del área principal.
    Ocultar reduce a una franja miniatura; si cambia el inventario (nueva firma), vuelve a mostrarse expandida.
    """
    agotados, bajos = clasificar_inventario_alerta(st.session_state.get("inventario_db") or [], mi_empresa)
    if not agotados and not bajos:
        toast_alerta_si_firma_cambia("insumos_alerta", "", None)
        st.session_state.pop(_SESSION_INV_DISMISS, None)
        return

    na, nb = len(agotados), len(bajos)
    total = na + nb
    f_inv = firma_inventario_alerta(agotados, bajos)
    if na and nb:
        msg_inv = f"Insumos: {na} sin stock, {nb} con stock bajo (≤{STOCK_BAJO_MAX} u.)."
    elif na:
        msg_inv = f"Insumos: {na} ítem(s) sin stock."
    else:
        msg_inv = f"Insumos: {nb} ítem(s) con stock bajo (≤{STOCK_BAJO_MAX} u.)."
    toast_alerta_si_firma_cambia("insumos_alerta", f_inv, msg_inv, icon="📦")

    minificado = st.session_state.get(_SESSION_INV_DISMISS) == f_inv
    if minificado:
        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(
                f"""
                <div class="mc-inv-mini" title="Stock: pulse Mostrar para ampliar">
                    <span class="mc-inv-mini__ico" aria-hidden="true">📦</span>
                    <span class="mc-inv-mini__txt">
                        <strong>Stock</strong> · {na} crít. · {nb} bajo
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c2:
            if st.button("Mostrar", key="mc_inv_expand_from_mini", use_container_width=True):
                st.session_state[_SESSION_INV_DISMISS] = None
                st.rerun()
        return

    res_parts: list[str] = []
    if na:
        res_parts.append(f'<span class="mc-inv-bar__pill mc-inv-bar__pill--danger">{na} sin stock</span>')
    if nb:
        res_parts.append(
            f'<span class="mc-inv-bar__pill mc-inv-bar__pill--warn">{nb} bajo ≤{STOCK_BAJO_MAX}</span>'
        )
    res_html = " ".join(res_parts)

    col_bar, col_hide = st.columns([6, 1])
    with col_bar:
        st.markdown(
            f"""
            <div class="mc-inv-bar mc-inv-bar--slim" role="status" aria-live="polite">
                <div class="mc-inv-bar__strip">
                    <span class="mc-inv-bar__ico" aria-hidden="true">📦</span>
                    <span class="mc-inv-bar__kicker">Stock</span>
                    <div class="mc-inv-bar__summary">{res_html}</div>
                    <span class="mc-inv-bar__hint">Módulo <strong>Inventario</strong></span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_hide:
        if st.button("Ocultar", key="mc_inv_dismiss", help="Minimiza la alerta (se reabre si cambia el stock)", use_container_width=True):
            st.session_state[_SESSION_INV_DISMISS] = f_inv
            st.rerun()

    _h_det = min(340, max(180, 28 * (total + 4)))
    with lista_plegable("Ítems en alerta", count=total, expanded=False, height=_h_det):
        if agotados:
            st.caption("Sin stock (reposición urgente)")
            for n, _s in agotados:
                st.caption(f"· {n}")
        if bajos:
            st.caption(f"Stock bajo (≤{STOCK_BAJO_MAX} u.)")
            for n, s in bajos:
                st.caption(f"· {n} — {s} u.")


def render_franja_avisos_operativos(mi_empresa: str) -> None:
    """Avisos de sistema (JSON / secrets). La alerta de inventario va en `render_alerta_inventario_banda_superior`."""
    avisos = _filtrar_por_fecha(_avisos_sistema_desde_json() + _aviso_extra_secrets())

    f_sys = firma_avisos_sistema(avisos)
    if avisos:
        hay_peligro = any(str(a.get("nivel")) == "danger" for a in avisos)
        hay_warn = any(str(a.get("nivel")) == "warning" for a in avisos)
        if hay_peligro:
            toast_alerta_si_firma_cambia(
                "aviso_sistema",
                f_sys,
                "Aviso crítico del sistema (revisá el mensaje arriba).",
                icon="⛔",
            )
        elif hay_warn:
            toast_alerta_si_firma_cambia(
                "aviso_sistema",
                f_sys,
                "Aviso del sistema (revisá arriba).",
                icon="⚠️",
            )
        else:
            # Solo info en pantalla; sin toast para no saturar al cargar la app.
            toast_alerta_si_firma_cambia("aviso_sistema", f_sys, None)
    else:
        toast_alerta_si_firma_cambia("aviso_sistema", "", None)

    for a in avisos[:6]:
        t = str(a["texto"])
        msg = f"**Aviso del sistema:** {t}"
        nivel = a.get("nivel", "info")
        if nivel == "danger":
            st.error(msg)
        elif nivel == "warning":
            st.warning(msg)
        else:
            st.info(msg)
