"""Turnos Online - Agenda completa con filtros, edicion y cancelacion."""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from core.alert_toasts import queue_toast
from core.app_logging import log_event
from core.database import guardar_datos
from core.utils import ahora, filtrar_registros_empresa, mostrar_dataframe_con_scroll, seleccionar_limite_registros
from core.view_helpers import bloque_estado_vacio

HORARIOS = [
    '08:00', '08:30', '09:00', '09:30', '10:00', '10:30',
    '11:00', '11:30', '12:00', '12:30',
    '14:00', '14:30', '15:00', '15:30', '16:00', '16:30',
    '17:00', '17:30', '18:00', '18:30',
]


def _today():
    return ahora().date()


def render_turnos_online(mi_empresa, rol):
    st.markdown("""
        <div class="mc-hero">
            <h2 class="mc-hero-title">Turnos Online</h2>
            <p class="mc-hero-text">Agenda profesional completa: crear slots, reservar, cancelar, reprogramar y filtrar.</p>
        </div>
    """, unsafe_allow_html=True)

    if 'turnos_online_db' not in st.session_state:
        st.session_state['turnos_online_db'] = []
    db = st.session_state['turnos_online_db']

    pacientes = filtrar_registros_empresa(st.session_state.get('pacientes_db', []), mi_empresa, rol)
    lista_ids = []
    for p in (pacientes or []):
        lista_ids.append(p.get('id', str(p)) if isinstance(p, dict) else str(p))

    # Obtener lista de profesionales unicos
    profesionales = sorted(set(t.get('profesional', '') for t in db if t.get('profesional')))

    # ================================================================
    # FILTROS
    # ================================================================
    with st.expander("Filtros", expanded=True):
        cols = st.columns(4)
        filtro_prof = cols[0].selectbox("Profesional", ["Todos"] + profesionales)
        filtro_estado = cols[1].selectbox("Estado", ["Todos", "Disponible", "Reservado", "Cancelado"])
        filtro_desde = cols[2].date_input("Desde", _today())
        filtro_hasta = cols[3].date_input("Hasta", _today() + timedelta(days=30))

    # Aplicar filtros
    turnos_filtrados = []
    for t in db:
        if filtro_prof != "Todos" and t.get('profesional') != filtro_prof:
            continue
        if filtro_estado != "Todos" and t.get('estado') != filtro_estado:
            continue
        try:
            tf = datetime.strptime(t['fecha'], '%d/%m/%Y').date()
        except Exception:
            continue
        if tf < filtro_desde or tf > filtro_hasta:
            continue
        turnos_filtrados.append(t)

    # ================================================================
    # TABS
    # ================================================================
    tabs = st.tabs(["Crear slots", "Reservar", "Administrar", "Resumen"])

    # ==================== CREAR SLOTS ====================
    with tabs[0]:
        with st.form("slot_form"):
            st.markdown("##### Nuevo slot")
            c1, c2 = st.columns(2)
            prof = c1.text_input("Profesional *", placeholder="Ej: Dr. Juan Perez")
            fecha = c2.date_input("Fecha", _today() + timedelta(days=1))
            horarios = st.multiselect("Horarios *", HORARIOS, default=HORARIOS[:4])

            if st.form_submit_button("Guardar slots", width="stretch", type="primary"):
                if not prof.strip():
                    st.error("El nombre del profesional es obligatorio.")
                elif not horarios:
                    st.error("Selecciona al menos un horario.")
                else:
                    creados = 0
                    for h in horarios:
                        ya_existe = any(
                            t['profesional'] == prof.strip() and t['fecha'] == fecha.strftime('%d/%m/%Y') and t['horario'] == h
                            for t in db
                        )
                        if not ya_existe:
                            db.append({
                                'profesional': prof.strip(), 'fecha': fecha.strftime('%d/%m/%Y'),
                                'horario': h, 'paciente': '', 'estado': 'Disponible',
                                'empresa': mi_empresa, 'fecha_registro': ahora().isoformat(),
                            })
                            creados += 1
                    if creados:
                        guardar_datos(spinner=True)
                        queue_toast(f"{creados} slots creados.")
                        st.rerun()
                    else:
                        st.warning("Esos slots ya existen.")

        # Mostrar slots creados hoy
        slots_hoy = [t for t in db if t.get('fecha') == _today().strftime('%d/%m/%Y')]
        if slots_hoy:
            with st.expander(f"Slots de hoy ({len(slots_hoy)})", expanded=False):
                for s in slots_hoy:
                    st.caption(f"{s['horario']} - {s['profesional']} - {s['estado']}")

    # ==================== RESERVAR ====================
    with tabs[1]:
        disponibles = [t for t in turnos_filtrados if t.get('estado') == 'Disponible']
        if not disponibles:
            bloque_estado_vacio("Sin slots disponibles", "Sin horarios libres en el filtro actual.",
                                sugerencia="Cambia los filtros o crea slots nuevos.")
        else:
            st.markdown(f"**{len(disponibles)} slots disponibles** segun filtros")
            with st.form("reservar_form"):
                opts = [f'{s["profesional"]} - {s["fecha"]} {s["horario"]}' for s in disponibles]
                sel = st.selectbox("Seleccionar turno", opts)
                idx = opts.index(sel)
                s = disponibles[idx]
                st.info(f"**{s['profesional']}** - {s['fecha']} a las {s['horario']} hs")

                if lista_ids:
                    pac = st.selectbox("Paciente", [''] + lista_ids)
                    if not pac:
                        pac = st.text_input("O ingresa manualmente", placeholder="Nombre del paciente")
                else:
                    pac = st.text_input("Paciente *", placeholder="Nombre del paciente")

                if st.form_submit_button("Reservar", width="stretch", type="primary"):
                    if not pac or (isinstance(pac, str) and not pac.strip()):
                        st.error("Debes indicar el paciente.")
                    else:
                        s['paciente'] = pac.strip() if isinstance(pac, str) else pac
                        s['estado'] = 'Reservado'
                        s['reservado_por'] = st.session_state.get('u_actual', {}).get('nombre', '?')
                        guardar_datos(spinner=True)
                        queue_toast(f"Turno reservado para {pac}.")
                        st.rerun()

    # ==================== ADMINISTRAR ====================
    with tabs[2]:
        if not turnos_filtrados:
            bloque_estado_vacio("Sin resultados", "No hay turnos con esos filtros.")
        else:
            for i, t in enumerate(turnos_filtrados):
                color = {"Disponible": "#059669", "Reservado": "#2563eb", "Cancelado": "#dc2626"}
                bg = {"Disponible": "rgba(5,150,105,0.1)", "Reservado": "rgba(37,99,235,0.1)", "Cancelado": "rgba(220,38,38,0.1)"}
                est = t.get('estado', '')
                with st.container(border=True):
                    cols = st.columns([2, 1, 1, 1.5, 0.5, 0.5])
                    cols[0].markdown(f"**{t.get('profesional','?')}**")
                    cols[1].markdown(f"{t.get('fecha','?')}")
                    cols[2].markdown(f"{t.get('horario','?')} hs")
                    col = color.get(est, "#fff")
                    cols[3].markdown(f"<span style='color:{col}'>{est}</span>", unsafe_allow_html=True)
                    if t.get('paciente'):
                        cols[3].markdown(f"Paciente: {t['paciente']}")
                    else:
                        cols[3].markdown("")

                    # Editar slot (solo disponibles)
                    if est == "Disponible":
                        if cols[4].button("✏️", key=f"ed_{i}"):
                            st.session_state[f"_edit_slot_{i}"] = True
                    if st.session_state.get(f"_edit_slot_{i}"):
                        nuevo_prof = st.text_input("Profesional", t['profesional'], key=f"ep_{i}")
                        nuevo_horario = st.selectbox("Horario", HORARIOS, index=HORARIOS.index(t['horario']) if t['horario'] in HORARIOS else 0, key=f"eh_{i}")
                        if st.button("Guardar cambios", key=f"sv_{i}"):
                            t['profesional'] = nuevo_prof
                            t['horario'] = nuevo_horario
                            guardar_datos(spinner=True)
                            queue_toast("Slot actualizado.")
                            st.session_state.pop(f"_edit_slot_{i}", None)
                            st.rerun()

                    # Eliminar slot
                    if cols[5].button("🗑️", key=f"del_{i}"):
                        db.remove(t)
                        guardar_datos(spinner=True)
                        queue_toast("Slot eliminado.")
                        st.rerun()

                    # Reprogramar (reservados)
                    if est == "Reservado":
                        if st.button("Reprogramar", key=f"rep_{i}"):
                            st.session_state[f"_rep_{i}"] = True
                        if st.session_state.get(f"_rep_{i}"):
                            nueva_fecha = st.date_input("Nueva fecha", _today(), key=f"rf_{i}")
                            nuevo_horario = st.selectbox("Nuevo horario", HORARIOS, key=f"rh_{i}")
                            if st.button("Confirmar reprogramacion", key=f"cf_{i}"):
                                t['fecha'] = nueva_fecha.strftime('%d/%m/%Y')
                                t['horario'] = nuevo_horario
                                guardar_datos(spinner=True)
                                queue_toast("Turno reprogramado.")
                                st.session_state.pop(f"_rep_{i}", None)
                                st.rerun()

                    # Cancelar con confirmacion
                    if est == "Reservado":
                        if st.button("Cancelar turno", key=f"cn_{i}"):
                            st.session_state[f"_cnf_{i}"] = True
                        if st.session_state.get(f"_cnf_{i}"):
                            if st.button(f"Confirmar cancelacion de {t['paciente']}", key=f"cnf_{i}"):
                                t['estado'] = 'Cancelado'
                                t['paciente'] = ''
                                guardar_datos(spinner=True)
                                queue_toast("Turno cancelado.")
                                st.session_state.pop(f"_cnf_{i}", None)
                                st.rerun()

    # ==================== RESUMEN ====================
    with tabs[3]:
        if not db:
            bloque_estado_vacio("Sin datos", "No hay turnos registrados.")
        else:
            total = len(db)
            disponibles = sum(1 for t in db if t.get('estado') == 'Disponible')
            reservados = sum(1 for t in db if t.get('estado') == 'Reservado')
            cancelados = sum(1 for t in db if t.get('estado') == 'Cancelado')

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total slots", total)
            c2.metric("Disponibles", disponibles)
            c3.metric("Reservados", reservados)
            c4.metric("Cancelados", cancelados)

            st.markdown("##### Todos los turnos")
            df = pd.DataFrame(db)
            cols_mostrar = [c for c in ['fecha', 'horario', 'profesional', 'paciente', 'estado'] if c in df.columns]
            df = df[cols_mostrar].rename(columns={
                'fecha': 'Fecha', 'horario': 'Horario', 'profesional': 'Profesional',
                'paciente': 'Paciente', 'estado': 'Estado',
            })
            mostrar_dataframe_con_scroll(df.sort_values(['Fecha', 'Horario'], ascending=False).head(200), height=400)
