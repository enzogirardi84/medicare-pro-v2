"""Seguridad para operaciones destructivas - auto-backup y confirmacion."""
from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Callable, Optional

import streamlit as st

from core.app_logging import log_event


def auto_backup_antes_de_eliminar(clave_db: str, paciente_sel: str, accion: str):
    """Guarda copia de seguridad antes de eliminar datos."""
    try:
        datos = st.session_state.get(clave_db, [])
        if not datos:
            return
        backup = {
            "timestamp": time.time(),
            "clave_db": clave_db,
            "paciente": paciente_sel,
            "accion": accion,
            "datos": list(datos),
        }
        backups = st.session_state.setdefault("_auto_backups", [])
        backups.append(backup)
        # Mantener solo los ultimos 10 backups
        if len(backups) > 10:
            st.session_state["_auto_backups"] = backups[-10:]
    except Exception as e:
        log_event("seguridad", f"error_auto_backup:{e}")


def confirmar_antes_de_eliminar(clave_db: str, item_idx: int, paciente_sel: str,
                                 mensaje: str = "Confirmar eliminacion",
                                 on_confirm: Optional[Callable] = None) -> bool:
    """Widget de confirmacion para eliminar items."""
    key = f"_del_confirm_{clave_db}_{item_idx}"
    if st.button(f"Eliminar", key=f"_del_btn_{clave_db}_{item_idx}", width="content"):
        st.session_state[key] = True

    if st.session_state.get(key):
        st.warning(mensaje)
        c1, c2 = st.columns(2)
        if c1.button("Confirmar", key=f"_del_yes_{clave_db}_{item_idx}", width="stretch"):
            auto_backup_antes_de_eliminar(clave_db, paciente_sel, "eliminar")
            if on_confirm:
                on_confirm()
            st.session_state.pop(key, None)
            return True
        if c2.button("Cancelar", key=f"_del_no_{clave_db}_{item_idx}", width="stretch"):
            st.session_state.pop(key, None)
    return False


def boton_eliminar_seguro(clave_db: str, item_idx: int, on_confirm: Callable,
                           paciente_sel: str = "",
                           mensaje: str = "Esta accion no se puede deshacer.") -> bool:
    """Boton eliminar con confirmacion en dos pasos."""
    return confirmar_antes_de_eliminar(
        clave_db, item_idx, paciente_sel,
        mensaje=mensaje, on_confirm=on_confirm
    )


def deshacer_ultima_operacion() -> bool:
    """Deshace la ultima operacion destructiva si hay backup."""
    backups = st.session_state.get("_auto_backups", [])
    if not backups:
        st.info("No hay operaciones para deshacer.")
        return False

    ultimo = backups.pop()
    clave = ultimo["clave_db"]
    datos_originales = ultimo["datos"]
    st.session_state[clave] = datos_originales
    st.success(f"Operacion deshecha: {ultimo['accion']} en {clave}")
    log_event("seguridad", f"undo:{ultimo['accion']}:{clave}")
    return True


def render_panel_seguridad():
    """Renderiza panel de seguridad con opcion de deshacer."""
    backups = st.session_state.get("_auto_backups", [])
    if backups:
        with st.expander(f"Protegido por auto-backup ({len(backups)} disponibles)", expanded=False):
            st.caption("Las ultimas 10 operaciones destructivas tienen backup.")
            if st.button("Deshacer ultima operacion", width="stretch"):
                deshacer_ultima_operacion()
                st.rerun()
            for i, b in enumerate(reversed(backups[-5:])):
                fecha = datetime.fromtimestamp(b["timestamp"]).strftime("%H:%M")
                st.caption(f"{fecha} - {b['accion']} en {b['clave_db']} ({b.get('paciente','?')})")
