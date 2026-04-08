from datetime import datetime
import urllib.parse

import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.utils import ahora, obtener_direccion_real

GEO_DISPONIBLE = False
try:
    from streamlit_geolocation import streamlit_geolocation
    GEO_DISPONIBLE = True
except ImportError:
    GEO_DISPONIBLE = False


def _parse_fecha(fecha_str):
    try:
        return datetime.strptime(fecha_str, "%d/%m/%Y %H:%M:%S")
    except Exception:
        try:
            return datetime.strptime(fecha_str, "%d/%m/%Y %H:%M")
        except Exception:
            return datetime.min


def render_visitas(paciente_sel, mi_empresa, user, rol):
    if not paciente_sel:
        st.info("Selecciona un paciente en el menu lateral para gestionar sus visitas y turnos.")
        return

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Visitas y agenda del paciente</h2>
            <p class="mc-hero-text">Desde esta pantalla podes fichar llegada o salida con GPS, revisar la guardia del dia y programar la proxima visita sin cargar pasos innecesarios.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">1. Activar GPS</span>
                <span class="mc-chip">2. Fichar llegada o salida</span>
                <span class="mc-chip">3. Agendar nueva visita</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Fichada Legal de Visita (GPS Real)")
    estado_pac = st.session_state["detalles_pacientes_db"].get(paciente_sel, {}).get("estado", "Activo")
    if estado_pac == "De Alta":
        st.error("Este paciente se encuentra de alta.")
        return

    det = st.session_state["detalles_pacientes_db"].get(paciente_sel, {})
    dire_paciente = det.get("direccion", "No registrada")
    tel_paciente = det.get("telefono", "")

    if GEO_DISPONIBLE:
        st.info("Para fichar llegada o salida, activa la ubicacion solo cuando la necesites.")
        activar_gps = st.checkbox("Activar GPS y obtener mi ubicacion")
        if activar_gps:
            loc = streamlit_geolocation()
            lat = loc.get("latitude") if loc and loc.get("latitude") is not None else None
            lon = loc.get("longitude") if loc and loc.get("longitude") is not None else None
            if lat is not None and lon is not None:
                lat_str = f"{float(lat):.5f}"
                lon_str = f"{float(lon):.5f}"
                direccion_real = obtener_direccion_real(lat_str, lon_str)
                st.success(f"Estas fisicamente en: {direccion_real}")
                col_in, col_out = st.columns(2)
                if col_in.button("Fichar LLEGADA", use_container_width=True, type="primary"):
                    st.session_state["checkin_db"].append({
                        "paciente": paciente_sel,
                        "profesional": user["nombre"],
                        "fecha_hora": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                        "tipo": f"LLEGADA en: {direccion_real} (Lat: {lat_str})",
                        "empresa": mi_empresa,
                    })
                    guardar_datos()
                    st.success("Llegada registrada.")
                    st.rerun()
                if col_out.button("Fichar SALIDA", use_container_width=True):
                    st.session_state["checkin_db"].append({
                        "paciente": paciente_sel,
                        "profesional": user["nombre"],
                        "fecha_hora": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                        "tipo": f"SALIDA de: {direccion_real} (Lat: {lat_str})",
                        "empresa": mi_empresa,
                    })
                    guardar_datos()
                    st.success("Salida registrada.")
                    st.rerun()
            else:
                st.warning("Buscando senal GPS. Asegurate de permitir ubicacion.")
    else:
        st.error("Libreria de geolocalizacion no disponible.")

    st.divider()
    st.markdown("#### Control de Horas de Guardia (Hoy)")
    hoy_str = ahora().strftime("%d/%m/%Y")
    fichadas_hoy = [
        c for c in st.session_state.get("checkin_db", [])
        if c.get("paciente") == paciente_sel and c.get("profesional") == user["nombre"] and c.get("fecha_hora", "").startswith(hoy_str)
    ]
    if fichadas_hoy:
        fichadas_hoy = sorted(fichadas_hoy, key=lambda x: _parse_fecha(x["fecha_hora"]))
        llegada_time = None
        ahora_naive = ahora().replace(tzinfo=None)
        for f in fichadas_hoy:
            dt = _parse_fecha(f["fecha_hora"])
            if "LLEGADA" in f["tipo"].upper():
                llegada_time = dt
            elif "SALIDA" in f["tipo"].upper() and llegada_time:
                duracion = dt - llegada_time
                horas, rem = divmod(duracion.seconds, 3600)
                minutos, _ = divmod(rem, 60)
                st.success(f"Turno completado: {llegada_time.strftime('%H:%M')} -> {dt.strftime('%H:%M')} ({horas}h {minutos}m)")
                llegada_time = None
        if llegada_time:
            duracion_actual = ahora_naive - llegada_time
            horas, rem = divmod(duracion_actual.seconds, 3600)
            minutos, _ = divmod(rem, 60)
            st.warning(f"Guardia en curso desde las {llegada_time.strftime('%H:%M')} -> {horas}h {minutos}m")
            if st.button("Actualizar cronometro", use_container_width=True):
                st.rerun()
    else:
        st.info("Aun no tienes fichadas hoy para este paciente.")

    st.divider()
    st.subheader("Agendar Proxima Visita")
    with st.form("agenda_form", clear_on_submit=True):
        c1_ag, c2_ag = st.columns(2)
        fecha_ag = c1_ag.date_input("Fecha programada", value=ahora().date())
        hora_ag_str = c2_ag.text_input("Hora aproximada (HH:MM)", value=ahora().strftime("%H:%M"))
        profesionales = [v["nombre"] for _, v in st.session_state["usuarios_db"].items() if v.get("empresa") == mi_empresa or rol == "SuperAdmin"]
        idx_prof = profesionales.index(user["nombre"]) if user["nombre"] in profesionales else 0
        prof_ag = st.selectbox("Asignar Profesional", profesionales, index=idx_prof)
        if st.form_submit_button("Agendar Visita", use_container_width=True, type="primary"):
            hora_limpia = hora_ag_str.strip() if ":" in hora_ag_str else ahora().strftime("%H:%M")
            st.session_state["agenda_db"].append({
                "paciente": paciente_sel,
                "profesional": prof_ag,
                "fecha": fecha_ag.strftime("%d/%m/%Y"),
                "hora": hora_limpia,
                "empresa": mi_empresa,
                "estado": "Pendiente",
            })
            guardar_datos()
            st.success("Turno agendado correctamente.")
            st.rerun()

    agenda_mia = [a for a in st.session_state.get("agenda_db", []) if a.get("empresa") == mi_empresa and a.get("paciente") == paciente_sel]
    if agenda_mia:
        st.caption("Proximas visitas agendadas")
        limite = min(50, len(agenda_mia))
        with st.container(height=280, border=True):
            df_agenda = pd.DataFrame(agenda_mia[-limite:]).drop(columns=["empresa", "paciente"], errors='ignore').iloc[::-1]
            st.dataframe(df_agenda, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Contacto y Ubicacion")
    st.markdown(
        """
        <div class="mc-grid-3">
            <div class="mc-card"><h4>GPS legal</h4><p>El fichaje queda asociado a la direccion detectada para mejorar trazabilidad y auditoria.</p></div>
            <div class="mc-card"><h4>Agenda simple</h4><p>La proxima visita se guarda sin cargar toda la agenda completa en pantalla.</p></div>
            <div class="mc-card"><h4>Contacto rapido</h4><p>El acceso a WhatsApp usa un mensaje prearmado para ahorrar tiempo operativo.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if dire_paciente and dire_paciente != "No registrada":
        st.info(f"Domicilio: {dire_paciente}")

    if tel_paciente:
        nombre_corto = paciente_sel.split(" (")[0]
        tel_limpio = "".join(filter(str.isdigit, str(tel_paciente)))
        if tel_limpio and not tel_limpio.startswith("54"):
            tel_limpio = "549" + tel_limpio
        if agenda_mia:
            ultima_visita = agenda_mia[-1]
            mensaje_base = f"Hola {nombre_corto}, me comunico desde {mi_empresa} para confirmarte que el dia {ultima_visita.get('fecha', '')} a las {ultima_visita.get('hora', '')} hs estare pasando por tu domicilio para realizar la visita correspondiente. Saludos."
        else:
            mensaje_base = f"Hola {nombre_corto}, me comunico desde {mi_empresa} para coordinar tu proxima visita de internacion domiciliaria."
        link_wpp = f"https://api.whatsapp.com/send?phone={tel_limpio}&text={urllib.parse.quote(mensaje_base)}"
        st.link_button("Enviar mensaje por WhatsApp", link_wpp, use_container_width=True)
    else:
        st.warning("Este paciente no tiene un numero de telefono registrado.")
