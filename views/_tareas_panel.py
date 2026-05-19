"""Panel de tareas pendientes por paciente."""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from core.app_logging import log_event
from core.database import guardar_datos
from core.utils import ahora


def render_tareas_panel(paciente_sel):
    """Renderiza el panel de tareas pendientes para un paciente."""
    if not paciente_sel:
        return

    tareas = st.session_state.setdefault("tareas_db", [])
    tareas_pac = [t for t in tareas if t.get("paciente") == paciente_sel]
    tareas_pendientes = [t for t in tareas_pac if not t.get("completada")]
    tareas_completadas = [t for t in tareas_pac if t.get("completada")]

    st.markdown("### 📋 Tareas pendientes")
    
    # Mostrar tareas pendientes
    if tareas_pendientes:
        for i, t in enumerate(tareas_pendientes):
            _key = f"tarea_{id(t)}"
            c1, c2, c3 = st.columns([0.1, 0.7, 0.2])
            _done = c1.checkbox("", key=f"chk_{_key}")
            if _done:
                t["completada"] = True
                t["fecha_completada"] = ahora().strftime("%d/%m/%Y %H:%M")
                guardar_datos(spinner=False)
                st.rerun()
            c2.markdown(f"**{t.get('tarea', '')}**")
            _prio = t.get("prioridad", "normal")
            _chip = {"alta": "🔴", "normal": "🟡", "baja": "🟢"}.get(_prio, "🟡")
            c2.caption(f"{_chip} {t.get('usuario', '')} — {t.get('fecha_creacion', '')}")
            if c3.button("🗑️", key=f"del_{_key}"):
                tareas.remove(t)
                st.session_state["tareas_db"] = tareas
                guardar_datos(spinner=False)
                st.rerun()
    else:
        st.info("Sin tareas pendientes para este paciente.")

    # Formulario para nueva tarea
    with st.expander("➕ Agregar tarea", expanded=False):
        with st.form("nueva_tarea", clear_on_submit=True):
            _tarea = st.text_input("Tarea *", placeholder="Ej: Gestionar turno con cardiología")
            _prio = st.selectbox("Prioridad", ["normal", "alta", "baja"], index=0)
            if st.form_submit_button("Agregar tarea"):
                if _tarea.strip():
                    tareas.append({
                        "paciente": paciente_sel,
                        "tarea": _tarea.strip(),
                        "prioridad": _prio,
                        "completada": False,
                        "fecha_creacion": ahora().strftime("%d/%m/%Y %H:%M"),
                        "usuario": st.session_state.get("u_actual", {}).get("nombre", "Sistema"),
                    })
                    st.session_state["tareas_db"] = tareas
                    guardar_datos(spinner=False)
                    st.success("✅ Tarea agregada")
                    log_event("tareas", f"creada:{paciente_sel}:{_tarea.strip()[:60]}")
                    st.rerun()

    # Mostrar completadas
    if tareas_completadas:
        with st.expander(f"✅ Completadas ({len(tareas_completadas)})", expanded=False):
            for t in tareas_completadas:
                st.caption(f"~~{t.get('tarea', '')}~~ — {t.get('fecha_completada', '')}")
