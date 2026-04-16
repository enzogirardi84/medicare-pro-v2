"""
Toasts para alertas visibles: solo cuando cambia la «firma» del estado,
así no se repiten en cada rerun de Streamlit.
"""

from __future__ import annotations

import hashlib
from typing import Any

import streamlit as st


def toast_alerta_si_firma_cambia(
    canal: str,
    firma: str,
    mensaje: str | None,
    *,
    icon: str | None = None,
) -> None:
    """
    Actualiza la firma en sesión y muestra st.toast si `mensaje` no está vacío
    y la firma difiere de la última guardada para `canal`.
    """
    key = f"_mc_toast_alert_{canal}"
    prev = st.session_state.get(key)
    if firma == prev:
        return
    st.session_state[key] = firma
    if not mensaje:
        return
    if icon:
        st.toast(mensaje, icon=icon)
    else:
        st.toast(mensaje)


def queue_toast(mensaje: str, icon: str = "✅") -> None:
    """
    Encola un toast para que se muestre en el próximo rerun.
    Útil para reemplazar st.success(...) seguido de st.rerun().
    """
    if "_mc_queued_toasts" not in st.session_state:
        st.session_state["_mc_queued_toasts"] = []
    st.session_state["_mc_queued_toasts"].append((mensaje, icon))


def render_queued_toasts() -> None:
    """
    Muestra los toasts encolados y limpia la cola.
    Debe llamarse al inicio de la app (ej. en main.py).
    """
    if "_mc_queued_toasts" in st.session_state:
        toasts = st.session_state.pop("_mc_queued_toasts")
        for mensaje, icon in toasts:
            st.toast(mensaje, icon=icon)


def firma_alertas_por_ids(rows: list[dict[str, Any]] | list[Any]) -> str:
    if not rows:
        return ""
    out_ids: list[str] = []
    for r in rows:
        if isinstance(r, dict):
            out_ids.append(str(r.get("id") or ""))
        else:
            out_ids.append("")
    out_ids.sort()
    return f"{len(rows)}:" + "|".join(out_ids)


def firma_inventario_alerta(agotados: list[tuple[str, int]], bajos: list[tuple[str, int]]) -> str:
    if not agotados and not bajos:
        return ""
    raw = repr((agotados, bajos))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]


def firma_avisos_sistema(avisos: list[dict[str, Any]]) -> str:
    if not avisos:
        return ""
    raw = "|".join(f"{a.get('nivel', '')}:{a.get('texto', '')}" for a in avisos)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]
