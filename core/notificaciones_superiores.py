"""
Franja superior de avisos operativos: cambios del sistema (JSON + secret opcional) e insumos con stock bajo o agotado.

El umbral de «stock bajo» coincide con la vista Inventario (≤10 unidades).
"""

from __future__ import annotations

from datetime import date, datetime
from html import escape
from typing import Any, Optional, Sequence

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
_MOD_INVENTARIO = "Inventario"


def _navegar_a_modulo_inventario() -> None:
    """Misma idea que al elegir un módulo en la navegación: deja atajo «Anterior»."""
    cur = st.session_state.get("modulo_actual")
    if cur and str(cur) != _MOD_INVENTARIO:
        st.session_state["modulo_anterior"] = cur
    st.session_state["modulo_actual"] = _MOD_INVENTARIO
    st.rerun()


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


def render_alerta_inventario_banda_superior(
    mi_empresa: str,
    menu: Optional[Sequence[str]] = None,
) -> None:
    """
    Alerta de stock (agotado / bajo) en formato compacto al inicio del área principal.
    Ocultar reduce a una franja miniatura; si cambia el inventario (nueva firma), vuelve a mostrarse expandida.

    ``menu``: módulos permitidos para el usuario; si incluye Inventario, se ofrece el botón «Ir a Inventario».
    """
    puede_ir_inventario = bool(menu) and _MOD_INVENTARIO in menu
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
        if puede_ir_inventario:
            c1, c_go, c2 = st.columns([4, 1.35, 1])
        else:
            c1, c2 = st.columns([5, 1])
            c_go = None
        with c1:
            tags = []
            if na:
                tags.append(f'<span class="mc-inv-mini__tag mc-inv-mini__tag--danger">{na} sin stock</span>')
            if nb:
                tags.append(
                    f'<span class="mc-inv-mini__tag mc-inv-mini__tag--warn">{nb} bajo ≤{STOCK_BAJO_MAX}</span>'
                )
            tags_html = "".join(tags)
            st.markdown(
                f"""
                <div class="mc-inv-mini" title="Alerta de inventario: pulse Mostrar para ampliar" role="status">
                    <span class="mc-inv-mini__ico" aria-hidden="true">📦</span>
                    <div class="mc-inv-mini__body">
                        <span class="mc-inv-mini__title">Inventario</span>
                        <div class="mc-inv-mini__tags">{tags_html}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        if c_go is not None:
            with c_go:
                if st.button(
                    "Ir a Inventario",
                    key="mc_inv_go_inventario_mini",
                    help="Abre el módulo Inventario",
                    use_container_width=True,
                ):
                    _navegar_a_modulo_inventario()
        with c2:
            if st.button("Mostrar", key="mc_inv_expand_from_mini", use_container_width=True):
                st.session_state[_SESSION_INV_DISMISS] = None
                st.rerun()
        return

    stat_blocks: list[str] = []
    if na:
        stat_blocks.append(
            f"""
            <div class="mc-inv-stat mc-inv-stat--danger">
                <span class="mc-inv-stat__num">{na}</span>
                <span class="mc-inv-stat__lbl">Sin stock</span>
                <span class="mc-inv-stat__hint">Reposición urgente</span>
            </div>
            """
        )
    if nb:
        stat_blocks.append(
            f"""
            <div class="mc-inv-stat mc-inv-stat--warn">
                <span class="mc-inv-stat__num">{nb}</span>
                <span class="mc-inv-stat__lbl">Stock bajo</span>
                <span class="mc-inv-stat__hint">≤ {STOCK_BAJO_MAX} u.</span>
            </div>
            """
        )
    stats_html = "".join(stat_blocks)
    accent = "mc-inv-alert--mixed" if na and nb else ("mc-inv-alert--critical" if na else "mc-inv-alert--caution")

    if puede_ir_inventario:
        col_bar, col_go, col_hide = st.columns([4.65, 1.45, 1])
    else:
        col_bar, col_hide = st.columns([6, 1])

    with col_bar:
        st.markdown(
            f"""
            <div class="mc-inv-alert {accent}" role="region" aria-label="Alerta de inventario y stock">
                <div class="mc-inv-alert__main">
                    <div class="mc-inv-alert__brand">
                        <span class="mc-inv-alert__ico" aria-hidden="true">📦</span>
                        <div class="mc-inv-alert__titles">
                            <p class="mc-inv-alert__kicker">Inventario</p>
                            <p class="mc-inv-alert__title">Hay insumos que requieren atención</p>
                        </div>
                    </div>
                    <div class="mc-inv-alert__stats">{stats_html}</div>
                </div>
                <p class="mc-inv-alert__foot">
                    Revisá el detalle abajo{puede_ir_inventario and ", o usá el botón «Ir a Inventario»" or ""}.
                    {puede_ir_inventario
                        and " Ahí podés cargar o ajustar existencias."
                        or " Pedí acceso al módulo Inventario si tu rol aún no lo incluye."}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    if puede_ir_inventario:
        with col_go:
            if st.button(
                "Ir a Inventario",
                key="mc_inv_go_inventario",
                help="Cambia al módulo Inventario (atajo «Anterior» disponible)",
                type="primary",
                use_container_width=True,
            ):
                _navegar_a_modulo_inventario()
    with col_hide:
        if st.button("Ocultar", key="mc_inv_dismiss", help="Minimiza la alerta (se reabre si cambia el stock)", use_container_width=True):
            st.session_state[_SESSION_INV_DISMISS] = f_inv
            st.rerun()

    _h_det = min(340, max(180, 28 * (total + 4)))
    with lista_plegable("Detalle de ítems en alerta", count=total, expanded=False, height=_h_det):
        blocks: list[str] = []
        if agotados:
            lis = "".join(f"<li>{escape(n)}</li>" for n, _s in agotados)
            blocks.append(
                f"""
                <div class="mc-inv-detail-block">
                    <p class="mc-inv-detail-block__label mc-inv-detail-block__label--danger">Sin stock</p>
                    <ul class="mc-inv-detail-block__list">{lis}</ul>
                </div>
                """
            )
        if bajos:
            lis = "".join(
                f'<li><span class="mc-inv-detail-block__name">{escape(n)}</span> — {s} u.</li>'
                for n, s in bajos
            )
            blocks.append(
                f"""
                <div class="mc-inv-detail-block">
                    <p class="mc-inv-detail-block__label mc-inv-detail-block__label--warn">Stock bajo (≤ {STOCK_BAJO_MAX} u.)</p>
                    <ul class="mc-inv-detail-block__list">{lis}</ul>
                </div>
                """
            )
        st.markdown('<div class="mc-inv-detail-root">' + "".join(blocks) + "</div>", unsafe_allow_html=True)


def render_franja_avisos_operativos(mi_empresa: str) -> None:
    """Avisos de sistema (JSON / secrets). La alerta de inventario va en `render_alerta_inventario_banda_superior`."""
    avisos = _filtrar_por_fecha(_avisos_sistema_desde_json() + _aviso_extra_secrets())

    f_sys = firma_avisos_sistema(avisos)
    if avisos:
        _niveles = {str(a.get("nivel")) for a in avisos}
        hay_peligro = "danger" in _niveles
        hay_warn = "warning" in _niveles
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
