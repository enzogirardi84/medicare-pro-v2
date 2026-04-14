"""
Franja superior de avisos operativos: cambios del sistema (JSON + secret opcional) e insumos con stock bajo o agotado.

El umbral de «stock bajo» coincide con la vista Inventario (≤10 unidades).
"""

from __future__ import annotations

from datetime import date, datetime
from html import escape
from typing import Any

import streamlit as st

from core.utils import cargar_json_asset

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


def render_franja_avisos_operativos(mi_empresa: str) -> None:
    """Muestra avisos de sistema e inventario debajo del banner crítico de app paciente (si existe)."""
    avisos = _filtrar_por_fecha(_avisos_sistema_desde_json() + _aviso_extra_secrets())
    agotados, bajos = clasificar_inventario_alerta(st.session_state.get("inventario_db") or [], mi_empresa)

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

    if not agotados and not bajos:
        return

    partes: list[str] = []
    if agotados:
        nombres = [escape(n) for n, _ in agotados[:12]]
        suf = f" (+{len(agotados) - 12} más)" if len(agotados) > 12 else ""
        partes.append(
            f'<span style="color:#fecaca;font-weight:700;">Sin stock</span> (reposición urgente): '
            f"{', '.join(nombres)}{suf}"
        )
    if bajos:
        frag = [f"{escape(n)} ({s} u.)" for n, s in bajos[:10]]
        suf = f" (+{len(bajos) - 10} más)" if len(bajos) > 10 else ""
        partes.append(
            f'<span style="color:#fde68a;font-weight:700;">Stock bajo</span> (≤{STOCK_BAJO_MAX} u.): '
            f"{', '.join(frag)}{suf}"
        )
    cuerpo = "<br><br>".join(partes)

    st.markdown(
        f"""
        <div class="mc-strip mc-strip-insumos" style="
            padding: 10px 14px;
            margin-bottom: 12px;
            border-radius: 10px;
            border: 1px solid rgba(251, 191, 36, 0.4);
            background: linear-gradient(135deg, rgba(120, 53, 15, 0.45), rgba(30, 27, 20, 0.88));
            color: #fef3c7;
            font-size: 0.92rem;
        ">
            <div style="font-size:0.68rem; letter-spacing:0.1em; text-transform:uppercase; color:#fcd34d; font-weight:800; margin-bottom:6px;">Insumos e inventario</div>
            <div style="line-height:1.5;">{cuerpo}</div>
            <div style="font-size:0.78rem; color:#d6d3d1; margin-top:8px;">Actualizá existencias en el módulo <b>Inventario</b>.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if len(agotados) + len(bajos) > 4:
        with st.expander("Detalle de ítems en alerta", expanded=False):
            for n, s in agotados:
                st.caption(f"Sin stock: {n}")
            for n, s in bajos:
                st.caption(f"Stock bajo: {n} — {s} u.")
