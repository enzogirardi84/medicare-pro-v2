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


def _chips_inventario_html(na: int, nb: int) -> str:
    """Chips compactos (mejor en móvil que cajas altas)."""
    parts: list[str] = []
    if na:
        parts.append(
            f'<span class="mc-inv-chip mc-inv-chip--danger" title="Ítems sin stock — reposición urgente">'
            f'<span class="mc-inv-chip__dot" aria-hidden="true"></span>'
            f'<span class="mc-inv-chip__n">{na}</span>'
            f'<span class="mc-inv-chip__txt">sin stock</span>'
            f'<span class="mc-inv-chip__hint">urgente</span>'
            f"</span>"
        )
    if nb:
        parts.append(
            f'<span class="mc-inv-chip mc-inv-chip--warn" title="Stock bajo (≤ {STOCK_BAJO_MAX} u.)">'
            f'<span class="mc-inv-chip__dot" aria-hidden="true"></span>'
            f'<span class="mc-inv-chip__n">{nb}</span>'
            f'<span class="mc-inv-chip__txt">bajos</span>'
            f'<span class="mc-inv-chip__hint">≤{STOCK_BAJO_MAX} u.</span>'
            f"</span>"
        )
    return "".join(parts)


def _render_tarjeta_alerta_inventario_markdown(accent: str, chips_html: str, foot_html: str) -> None:
    """Solo `st.markdown`: los estilos de `assets/style.css` aplican (st.html suele aislar y verse “plano”)."""
    body = (
        f'<div class="mc-inv-alert mc-inv-alert--compact {accent}" role="region" aria-label="Alerta de inventario y stock">'
        '<div class="mc-inv-alert__main">'
        '<div class="mc-inv-alert__brand">'
        '<span class="mc-inv-alert__ico" aria-hidden="true">📦</span>'
        '<div class="mc-inv-alert__titles">'
        '<p class="mc-inv-alert__kicker">Inventario</p>'
        '<p class="mc-inv-alert__title">Atención: faltantes o stock bajo</p>'
        "</div></div>"
        f'<div class="mc-inv-chips">{chips_html}</div>'
        "</div>"
        f'<p class="mc-inv-alert__foot mc-inv-alert__foot--compact">{foot_html}</p>'
        "</div>"
    )
    st.markdown(body, unsafe_allow_html=True)


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
            c1, c_go, c2 = st.columns([2.6, 2.4, 1.6])
        else:
            c1, c2 = st.columns([4, 2])
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
                    "📦 Inventario",
                    key="mc_inv_go_inventario_mini",
                    help="Abre el módulo Inventario",
                    type="primary",
                    use_container_width=True,
                ):
                    _navegar_a_modulo_inventario()
        with c2:
            if st.button("Mostrar", key="mc_inv_expand_from_mini", use_container_width=True):
                st.session_state[_SESSION_INV_DISMISS] = None
                st.rerun()
        return

    chips_html = _chips_inventario_html(na, nb)
    accent = "mc-inv-alert--mixed" if na and nb else ("mc-inv-alert--critical" if na else "mc-inv-alert--caution")

    if puede_ir_inventario:
        foot_plain = (
            "Expandí el detalle abajo o entrá a Inventario con el botón. "
            "Ajustá existencias o ingresá mercadería ahí."
        )
    else:
        foot_plain = "Expandí el detalle abajo. Si no ves el módulo Inventario, pedí acceso según tu rol."
    foot_html = escape(foot_plain)

    _render_tarjeta_alerta_inventario_markdown(accent, chips_html, foot_html)

    # Ancla para CSS: centrar y limitar ancho de la fila de botones en escritorio/tablet
    st.markdown('<div class="mc-inv-after-card" aria-hidden="true"></div>', unsafe_allow_html=True)

    if puede_ir_inventario:
        b1, b2 = st.columns(2)
        with b1:
            if st.button(
                "📦 Inventario",
                key="mc_inv_go_inventario",
                help="Abre el módulo Inventario (atajo «Anterior» disponible)",
                type="primary",
                use_container_width=True,
            ):
                _navegar_a_modulo_inventario()
        with b2:
            if st.button(
                "Ocultar",
                key="mc_inv_dismiss",
                help="Minimiza la alerta (se reabre si cambia el stock)",
                type="secondary",
                use_container_width=True,
            ):
                st.session_state[_SESSION_INV_DISMISS] = f_inv
                st.rerun()
    else:
        if st.button(
            "Ocultar",
            key="mc_inv_dismiss",
            help="Minimiza la alerta (se reabre si cambia el stock)",
            type="secondary",
            use_container_width=True,
        ):
            st.session_state[_SESSION_INV_DISMISS] = f_inv
            st.rerun()

    _h_det = min(280, max(160, 22 * (total + 3)))
    with lista_plegable("Lista de ítems", count=total, expanded=False, height=_h_det):
        # Listas Markdown (sin HTML): dentro del expander + contenedor con scroll el HTML
        # a veces se muestra como texto/código; Markdown nativo es estable en todos los hosts.
        if agotados:
            st.markdown(
                '<p class="mc-inv-md-sec mc-inv-md-sec--danger">Sin stock · reposición urgente</p>',
                unsafe_allow_html=True,
            )
            st.markdown("\n".join(f"- {escape(n)}" for n, _s in agotados))
        if agotados and bajos:
            st.divider()
        if bajos:
            st.markdown(
                f'<p class="mc-inv-md-sec mc-inv-md-sec--warn">Stock bajo (≤ {STOCK_BAJO_MAX} u.)</p>',
                unsafe_allow_html=True,
            )
            st.markdown(
                "\n".join(f"- **{escape(n)}** — {s} u." for n, s in bajos),
            )


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
