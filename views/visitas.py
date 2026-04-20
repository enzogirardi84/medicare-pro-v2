import urllib.parse
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from core.alert_toasts import queue_toast
from core.database import guardar_datos
from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio, lista_plegable
from core.utils import (
    ahora,
    es_control_total,
    mapa_detalles_pacientes,
    normalizar_hora_texto,
    obtener_direccion_real,
    obtener_profesionales_visibles,
    mostrar_dataframe_con_scroll,
    seleccionar_limite_registros,
)
from views._visitas_whatsapp import (
    _armar_mensaje_whatsapp_visita,
    _etiqueta_visita_whatsapp,
    _normalizar_telefono_whatsapp,
    _plantillas_whatsapp_para_empresa,
    _plantillas_whatsapp_store,
    _visitas_para_aviso_whatsapp,
)
from views._visitas_agenda import (
    _agenda_empresa,
    _agenda_paciente,
    _enriquecer_agenda,
    _resumen_agenda,
    _zona_corta,
)
from views._visitas_secciones import (
    _render_fichada_gps,
    _render_agendar_visita,
    _render_whatsapp_agenda,
)

GEO_DISPONIBLE = False
try:
    from streamlit_geolocation import streamlit_geolocation
    GEO_DISPONIBLE = True
except ImportError:
    GEO_DISPONIBLE = False

def render_visitas(paciente_sel, mi_empresa, user, rol):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    nombre_usuario = user.get("nombre", "Profesional sin nombre")

    st.markdown("## Visitas y agenda del paciente")
    st.caption("Fichada con GPS, control de horas de guardia y agendamiento con aviso por WhatsApp.")

    _det_map = mapa_detalles_pacientes(st.session_state)
    estado_pac = _det_map.get(paciente_sel, {}).get("estado", "Activo")
    if estado_pac == "De Alta":
        st.error("Este paciente se encuentra de alta.")
        return

    det = _det_map.get(paciente_sel, {})
    dire_paciente = det.get("direccion", "No registrada")
    tel_paciente = det.get("telefono", "")
    nombre_corto_pac = paciente_sel.split(" (")[0]

    rec_wpp = st.session_state.pop("_wpp_recordatorio_visita", None)
    if rec_wpp and rec_wpp.get("paciente") == paciente_sel:
        st.success("Visita agendada.")
        if rec_wpp.get("tel") and rec_wpp.get("texto"):
            st.link_button(
                "WhatsApp: avisar al paciente sobre esta visita",
                f"https://wa.me/{rec_wpp['tel']}?text={urllib.parse.quote(rec_wpp['texto'])}",
                use_container_width=True,
                type="primary",
            )
        elif not str(tel_paciente or "").strip():
            st.info("Para avisar por WhatsApp, carga el telefono del paciente en Admision.")

    agenda_paciente = _enriquecer_agenda(_agenda_paciente(mi_empresa, paciente_sel, rol))
    resumen = _resumen_agenda(agenda_paciente)
    carga_profesional = sum(
        1
        for x in agenda_paciente
        if x.get("profesional") == nombre_usuario and x["estado_calc"] in {"Pendiente", "En curso", "Vencida"}
    )

    col_r1, col_r2, col_r3, col_r4 = st.columns(4)
    col_r1.metric("Pendientes", resumen["pendientes"])
    col_r2.metric("Vencidas", resumen["vencidas"])
    col_r3.metric("Proximas 48h", resumen["proximas"])
    col_r4.metric("Carga de tu agenda", carga_profesional)

    st.caption(
        "Pendientes / vencidas: turnos activos segun fecha y estado. Proximas 48h: ventana corta para coordinar. "
        "Carga de tu agenda: visitas donde sos el profesional asignado y aun no estan cerradas."
    )

    # ── Indicador de turnos del día ───────────────────────────────────────
    _hoy = ahora().date()
    _turnos_hoy = [
        x for x in agenda_paciente
        if x.get("_fecha_dt") and x["_fecha_dt"] != datetime.min and x["_fecha_dt"].date() == _hoy
    ]
    if _turnos_hoy:
        _prox = min(_turnos_hoy, key=lambda x: x["_fecha_dt"])
        _prox_hora = _prox["_fecha_dt"].strftime("%H:%M")
        _prox_prof = _prox.get("profesional", "S/D")
        st.info(f"📅 **{len(_turnos_hoy)} turno(s) hoy** — próximo a las **{_prox_hora}** con {_prox_prof}")
    else:
        st.caption("📅 Sin turnos agendados para hoy.")

    # ── Alerta de turnos vencidos sin asistencia ──────────────────────────
    _vencidos = [x for x in agenda_paciente if x.get("estado_calc") == "Vencida"]
    if _vencidos:
        st.warning(
            f"⏰ **{len(_vencidos)} turno(s) vencido(s)** sin marcar como realizados o cancelados. "
            "Revisá la agenda y actualizá el estado."
        )

    _render_fichada_gps(paciente_sel, mi_empresa, nombre_usuario)
    _render_agendar_visita(paciente_sel, mi_empresa, user, rol, agenda_paciente, nombre_usuario, nombre_corto_pac, dire_paciente, tel_paciente)
    _render_whatsapp_agenda(paciente_sel, mi_empresa, user, rol, agenda_paciente, nombre_corto_pac, dire_paciente, tel_paciente)

    st.divider()
    st.subheader("Contacto y ubicacion")
    st.markdown(
        """
        <div class="mc-grid-3">
            <div class="mc-card"><h4>GPS legal</h4><p>El fichaje queda asociado a la direccion detectada para mejorar trazabilidad y auditoria.</p></div>
            <div class="mc-card"><h4>Agenda inteligente</h4><p>El sistema remarca pendientes, en curso y vencidas sin expandir listas enormes.</p></div>
            <div class="mc-card"><h4>WhatsApp</h4><p>El aviso con fecha, hora y datos del profesional se arma en la seccion superior de esta misma pantalla.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if dire_paciente and dire_paciente != "No registrada":
        st.info(f"Domicilio: {dire_paciente}")
