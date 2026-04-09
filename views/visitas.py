from datetime import datetime, timedelta
import urllib.parse

import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.utils import (
    ahora,
    calcular_estado_agenda,
    es_control_total,
    filtrar_registros_empresa,
    mostrar_dataframe_con_scroll,
    obtener_direccion_real,
    parse_agenda_datetime,
    seleccionar_limite_registros,
)

GEO_DISPONIBLE = False
try:
    from streamlit_geolocation import streamlit_geolocation

    GEO_DISPONIBLE = True
except ImportError:
    GEO_DISPONIBLE = False


def _agenda_empresa(mi_empresa, rol):
    return filtrar_registros_empresa(st.session_state.get("agenda_db", []), mi_empresa, rol)


def _agenda_paciente(mi_empresa, paciente_sel, rol):
    return [a for a in _agenda_empresa(mi_empresa, rol) if a.get("paciente") == paciente_sel]


def _enriquecer_agenda(items):
    ahora_local = ahora().replace(tzinfo=None)
    enriquecida = []
    for idx, item in enumerate(items):
        registro = dict(item)
        dt = parse_agenda_datetime(item)
        registro["_id_local"] = idx
        registro["_fecha_dt"] = dt
        registro["estado_calc"] = calcular_estado_agenda(item, now=ahora_local)
        enriquecida.append(registro)
    return enriquecida


def _resumen_agenda(items):
    if not items:
        return {"pendientes": 0, "vencidas": 0, "proximas": 0, "profesionales": 0}
    ahora_local = ahora().replace(tzinfo=None)
    proximas_limite = ahora_local + timedelta(hours=48)
    pendientes = sum(1 for x in items if x["estado_calc"] in {"Pendiente", "En curso"})
    vencidas = sum(1 for x in items if x["estado_calc"] == "Vencida")
    proximas = sum(1 for x in items if x["_fecha_dt"] != datetime.min and ahora_local <= x["_fecha_dt"] <= proximas_limite)
    profesionales = len({x.get("profesional", "Sin profesional") for x in items})
    return {
        "pendientes": pendientes,
        "vencidas": vencidas,
        "proximas": proximas,
        "profesionales": profesionales,
    }


def render_visitas(paciente_sel, mi_empresa, user, rol):
    if not paciente_sel:
        st.info("Selecciona un paciente en el menu lateral para gestionar sus visitas y turnos.")
        return

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Visitas y agenda del paciente</h2>
            <p class="mc-hero-text">Desde esta pantalla podes fichar llegada o salida con GPS, controlar la guardia del dia y manejar una agenda operativa sin cargar historiales infinitos.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Fichaje GPS</span>
                <span class="mc-chip">Agenda inteligente</span>
                <span class="mc-chip">Acciones rapidas</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    estado_pac = st.session_state["detalles_pacientes_db"].get(paciente_sel, {}).get("estado", "Activo")
    if estado_pac == "De Alta":
        st.error("Este paciente se encuentra de alta.")
        return

    det = st.session_state["detalles_pacientes_db"].get(paciente_sel, {})
    dire_paciente = det.get("direccion", "No registrada")
    tel_paciente = det.get("telefono", "")

    agenda_paciente = _enriquecer_agenda(_agenda_paciente(mi_empresa, paciente_sel, rol))
    resumen = _resumen_agenda(agenda_paciente)
    carga_profesional = sum(1 for x in agenda_paciente if x.get("profesional") == user["nombre"] and x["estado_calc"] in {"Pendiente", "En curso", "Vencida"})

    col_r1, col_r2, col_r3, col_r4 = st.columns(4)
    col_r1.metric("Pendientes", resumen["pendientes"])
    col_r2.metric("Vencidas", resumen["vencidas"])
    col_r3.metric("Proximas 48h", resumen["proximas"])
    col_r4.metric("Carga de tu agenda", carga_profesional)

    st.subheader("Fichada Legal de Visita (GPS Real)")
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
                    st.session_state["checkin_db"].append(
                        {
                            "paciente": paciente_sel,
                            "profesional": user["nombre"],
                            "fecha_hora": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                            "tipo": f"LLEGADA en: {direccion_real} (Lat: {lat_str})",
                            "empresa": mi_empresa,
                        }
                    )
                    guardar_datos()
                    st.success("Llegada registrada.")
                    st.rerun()
                if col_out.button("Fichar SALIDA", use_container_width=True):
                    st.session_state["checkin_db"].append(
                        {
                            "paciente": paciente_sel,
                            "profesional": user["nombre"],
                            "fecha_hora": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                            "tipo": f"SALIDA de: {direccion_real} (Lat: {lat_str})",
                            "empresa": mi_empresa,
                        }
                    )
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
        c
        for c in st.session_state.get("checkin_db", [])
        if c.get("paciente") == paciente_sel and c.get("profesional") == user["nombre"] and c.get("fecha_hora", "").startswith(hoy_str)
    ]
    if fichadas_hoy:
        fichadas_hoy = sorted(fichadas_hoy, key=lambda x: pd.to_datetime(x["fecha_hora"], format="%d/%m/%Y %H:%M:%S", errors="coerce"))
        llegada_time = None
        ahora_naive = ahora().replace(tzinfo=None)
        for f in fichadas_hoy:
            dt = pd.to_datetime(f["fecha_hora"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
            if pd.isna(dt):
                dt = pd.to_datetime(f["fecha_hora"], format="%d/%m/%Y %H:%M", errors="coerce")
            if pd.isna(dt):
                continue
            dt = dt.to_pydatetime()
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
    else:
        st.info("Aun no tienes fichadas hoy para este paciente.")

    st.divider()
    st.subheader("Agendar Proxima Visita")
    with st.form("agenda_form", clear_on_submit=True):
        c1_ag, c2_ag = st.columns(2)
        fecha_ag = c1_ag.date_input("Fecha programada", value=ahora().date())
        hora_ag_str = c2_ag.text_input("Hora aproximada (HH:MM)", value=ahora().strftime("%H:%M"))
        profesionales = [
            v["nombre"]
            for _, v in st.session_state["usuarios_db"].items()
            if es_control_total(rol) or v.get("empresa") == mi_empresa
        ]
        idx_prof = profesionales.index(user["nombre"]) if user["nombre"] in profesionales else 0
        prof_ag = st.selectbox("Asignar Profesional", profesionales, index=idx_prof)
        if st.form_submit_button("Agendar Visita", use_container_width=True, type="primary"):
            hora_limpia = hora_ag_str.strip() if ":" in hora_ag_str else ahora().strftime("%H:%M")
            st.session_state["agenda_db"].append(
                {
                    "paciente": paciente_sel,
                    "profesional": prof_ag,
                    "fecha": fecha_ag.strftime("%d/%m/%Y"),
                    "hora": hora_limpia,
                    "empresa": mi_empresa,
                    "estado": "Pendiente",
                }
            )
            guardar_datos()
            st.success("Turno agendado correctamente.")
            st.rerun()

    if agenda_paciente:
        st.divider()
        st.markdown("#### Agenda inteligente")
        df_agenda = pd.DataFrame(agenda_paciente)
        df_agenda["Fecha y Hora"] = df_agenda["_fecha_dt"].apply(lambda x: x.strftime("%d/%m/%Y %H:%M") if x.year > 1900 else "Sin fecha")
        df_agenda["Profesional"] = df_agenda["profesional"].fillna("Sin profesional")
        df_agenda["Estado"] = df_agenda["estado_calc"]

        c_f1, c_f2 = st.columns(2)
        profesionales_disp = ["Todos"] + sorted(df_agenda["Profesional"].dropna().unique().tolist())
        estados_disp = ["Todos", "Pendiente", "En curso", "Vencida", "Realizada", "Cancelada"]
        filtro_prof = c_f1.selectbox("Filtrar por profesional", profesionales_disp, key=f"agenda_prof_{paciente_sel}")
        filtro_estado = c_f2.selectbox("Filtrar por estado", estados_disp, key=f"agenda_estado_{paciente_sel}")

        df_filtrado = df_agenda.copy()
        if filtro_prof != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Profesional"] == filtro_prof]
        if filtro_estado != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Estado"] == filtro_estado]

        col_g1, col_g2 = st.columns([1.1, 1])
        with col_g1:
            st.caption("Estado de la agenda del paciente")
            estado_chart = df_agenda.groupby("Estado").size().reset_index(name="Visitas")
            if not estado_chart.empty:
                st.bar_chart(estado_chart.set_index("Estado")["Visitas"], use_container_width=True)
        with col_g2:
            st.caption("Carga por profesional")
            prof_chart = df_agenda.groupby("Profesional").size().reset_index(name="Visitas").sort_values("Visitas", ascending=False)
            if not prof_chart.empty:
                st.bar_chart(prof_chart.set_index("Profesional")["Visitas"], use_container_width=True)

        c_a1, c_a2 = st.columns([2, 1])
        opciones_accion = [f"{x['Fecha y Hora']} | {x['Profesional']} | {x['Estado']}" for _, x in df_filtrado.sort_values("_fecha_dt").iterrows()]
        seleccion = c_a1.selectbox("Accion rapida sobre una visita", ["Sin cambios"] + opciones_accion, key=f"agenda_accion_sel_{paciente_sel}")
        accion = c_a2.selectbox("Accion", ["Marcar realizada", "Cancelar"], key=f"agenda_accion_tipo_{paciente_sel}")
        if st.button("Aplicar cambio de agenda", use_container_width=True, key=f"agenda_apply_{paciente_sel}"):
            if seleccion != "Sin cambios":
                objetivo = next(
                    (
                        x
                        for x in agenda_paciente
                        if f"{x['_fecha_dt'].strftime('%d/%m/%Y %H:%M') if x['_fecha_dt'].year > 1900 else 'Sin fecha'} | {x.get('profesional', 'Sin profesional')} | {x['estado_calc']}" == seleccion
                    ),
                    None,
                )
                if objetivo:
                    for item in st.session_state["agenda_db"]:
                        if (
                            item.get("paciente") == objetivo.get("paciente")
                            and item.get("profesional") == objetivo.get("profesional")
                            and item.get("fecha") == objetivo.get("fecha")
                            and item.get("hora") == objetivo.get("hora")
                        ):
                            item["estado"] = "Realizada" if accion == "Marcar realizada" else "Cancelada"
                            break
                    guardar_datos()
                    st.success("Agenda actualizada correctamente.")
                    st.rerun()

        limite = seleccionar_limite_registros(
            "Visitas a mostrar",
            len(df_filtrado),
            key=f"agenda_limit_{paciente_sel}",
            default=20,
            opciones=(10, 20, 30, 50, 80, 120),
        )
        cols_visibles = ["Fecha y Hora", "Profesional", "Estado", "fecha", "hora"]
        df_render = df_filtrado.sort_values("_fecha_dt", ascending=False)[cols_visibles].rename(columns={"fecha": "Fecha", "hora": "Hora"})
        mostrar_dataframe_con_scroll(df_render.head(limite), height=360)

    st.divider()
    st.subheader("Contacto y Ubicacion")
    st.markdown(
        """
        <div class="mc-grid-3">
            <div class="mc-card"><h4>GPS legal</h4><p>El fichaje queda asociado a la direccion detectada para mejorar trazabilidad y auditoria.</p></div>
            <div class="mc-card"><h4>Agenda inteligente</h4><p>El sistema remarca pendientes, en curso y vencidas sin expandir listas enormes.</p></div>
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
        if agenda_paciente:
            agenda_ordenada = sorted(agenda_paciente, key=lambda x: x["_fecha_dt"], reverse=True)
            ultima_visita = agenda_ordenada[0]
            mensaje_base = (
                f"Hola {nombre_corto}, me comunico desde {mi_empresa} para confirmarte que el dia "
                f"{ultima_visita.get('fecha', '')} a las {ultima_visita.get('hora', '')} hs estare pasando por tu domicilio "
                "para realizar la visita correspondiente. Saludos."
            )
        else:
            mensaje_base = f"Hola {nombre_corto}, me comunico desde {mi_empresa} para coordinar tu proxima visita de internacion domiciliaria."
        link_wpp = f"https://api.whatsapp.com/send?phone={tel_limpio}&text={urllib.parse.quote(mensaje_base)}"
        st.link_button("Enviar mensaje por WhatsApp", link_wpp, use_container_width=True)
    else:
        st.warning("Este paciente no tiene un numero de telefono registrado.")
