"""Secciones UI de visitas. Extraído de views/visitas.py."""
import urllib.parse
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from core.alert_toasts import queue_toast
from core.database import guardar_datos
from core.view_helpers import bloque_estado_vacio
from core.utils import (
    ahora,
    mostrar_dataframe_con_scroll,
    normalizar_hora_texto,
    obtener_direccion_real,
    obtener_profesionales_visibles,
    seleccionar_limite_registros,
    es_control_total,
)
from views._visitas_whatsapp import (
    _armar_mensaje_whatsapp_visita,
    _etiqueta_visita_whatsapp,
    _normalizar_telefono_whatsapp,
    _plantillas_whatsapp_para_empresa,
    _plantillas_whatsapp_store,
    _visitas_para_aviso_whatsapp,
)
from views._visitas_agenda import _agenda_empresa, _zona_corta

GEO_DISPONIBLE = False
try:
    from streamlit_geolocation import streamlit_geolocation
    GEO_DISPONIBLE = True
except ImportError:
    pass


def _render_fichada_gps(paciente_sel, mi_empresa, nombre_usuario):
    """Sección: Fichada Legal de Visita (GPS Real) + Control de Horas."""
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
                    try:
                        from core.db_sql import insert_checkin
                        from core.nextgen_sync import _obtener_uuid_empresa, _obtener_uuid_paciente
                        empresa_id = _obtener_uuid_empresa(mi_empresa)
                        if empresa_id:
                            pac_uuid = None
                            partes = paciente_sel.split(" - ")
                            if len(partes) > 1:
                                pac_uuid = _obtener_uuid_paciente(partes[1].strip(), empresa_id)
                            from core.database import supabase
                            usr_id = None
                            if supabase:
                                res_usr = supabase.table("usuarios").select("id").eq("nombre", nombre_usuario).eq("empresa_id", empresa_id).limit(1).execute()
                                if res_usr.data:
                                    usr_id = res_usr.data[0]["id"]
                            datos_sql = {
                                "empresa_id": empresa_id,
                                "usuario_id": usr_id,
                                "paciente_id": pac_uuid,
                                "fecha_hora": ahora().isoformat(),
                                "tipo_registro": "LLEGADA",
                                "latitud": float(lat),
                                "longitud": float(lon),
                                "direccion_estimada": direccion_real,
                                "observaciones": ""
                            }
                            insert_checkin(datos_sql)
                    except Exception as e:
                        from core.app_logging import log_event
                        log_event("visitas_sql", f"error_dual_write_checkin_in:{type(e).__name__}")
                    if "checkin_db" not in st.session_state or not isinstance(st.session_state["checkin_db"], list):
                        st.session_state["checkin_db"] = []
                    st.session_state["checkin_db"].append({
                        "paciente": paciente_sel,
                        "profesional": nombre_usuario,
                        "fecha_hora": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                        "tipo": f"LLEGADA en: {direccion_real} (Lat: {lat_str})",
                        "empresa": mi_empresa,
                        "gps": f"{lat_str},{lon_str}"
                    })
                    from core.database import _trim_db_list
                    _trim_db_list("checkin_db", 1000)
                    guardar_datos(spinner=True)
                    queue_toast("Llegada registrada.")
                    st.rerun()
                if col_out.button("Fichar SALIDA", use_container_width=True):
                    try:
                        from core.db_sql import insert_checkin
                        from core.nextgen_sync import _obtener_uuid_empresa, _obtener_uuid_paciente
                        empresa_id = _obtener_uuid_empresa(mi_empresa)
                        if empresa_id:
                            pac_uuid = None
                            partes = paciente_sel.split(" - ")
                            if len(partes) > 1:
                                pac_uuid = _obtener_uuid_paciente(partes[1].strip(), empresa_id)
                            from core.database import supabase
                            usr_id = None
                            if supabase:
                                res_usr = supabase.table("usuarios").select("id").eq("nombre", nombre_usuario).eq("empresa_id", empresa_id).limit(1).execute()
                                if res_usr.data:
                                    usr_id = res_usr.data[0]["id"]
                            datos_sql = {
                                "empresa_id": empresa_id,
                                "usuario_id": usr_id,
                                "paciente_id": pac_uuid,
                                "fecha_hora": ahora().isoformat(),
                                "tipo_registro": "SALIDA",
                                "latitud": float(lat),
                                "longitud": float(lon),
                                "direccion_estimada": direccion_real,
                                "observaciones": ""
                            }
                            insert_checkin(datos_sql)
                    except Exception as e:
                        from core.app_logging import log_event
                        log_event("visitas_sql", f"error_dual_write_checkin_out:{type(e).__name__}")
                    if "checkin_db" not in st.session_state or not isinstance(st.session_state["checkin_db"], list):
                        st.session_state["checkin_db"] = []
                    st.session_state["checkin_db"].append({
                        "paciente": paciente_sel,
                        "profesional": nombre_usuario,
                        "fecha_hora": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                        "tipo": f"SALIDA de: {direccion_real} (Lat: {lat_str})",
                        "empresa": mi_empresa,
                        "gps": f"{lat_str},{lon_str}"
                    })
                    from core.database import _trim_db_list
                    _trim_db_list("checkin_db", 1000)
                    guardar_datos(spinner=True)
                    queue_toast("Salida registrada.")
                    st.rerun()
            else:
                st.warning("Buscando senal GPS. Asegurate de permitir ubicacion.")
    else:
        st.error("Libreria de geolocalizacion no disponible.")

    st.divider()
    st.markdown("#### Control de Horas de Guardia (Hoy)")
    hoy_str = ahora().strftime("%d/%m/%Y")
    fichadas_hoy = []
    try:
        from core.db_sql import get_checkins_by_empresa
        from core.nextgen_sync import _obtener_uuid_empresa
        empresa_uuid = _obtener_uuid_empresa(mi_empresa)
        if empresa_uuid:
            chk_sql = get_checkins_by_empresa(empresa_uuid, limit=500)
            if chk_sql:
                for c in chk_sql:
                    dt = pd.to_datetime(c.get("fecha_hora", ""))
                    if pd.notnull(dt) and dt.strftime("%d/%m/%Y") == hoy_str:
                        paciente_nombre = c.get("pacientes", {}).get("nombre_completo", "N/A") if isinstance(c.get("pacientes"), dict) else "N/A"
                        prof_nombre = c.get("usuarios", {}).get("nombre", "Desconocido") if isinstance(c.get("usuarios"), dict) else "Desconocido"
                        if paciente_sel.startswith(paciente_nombre) and prof_nombre == nombre_usuario:
                            fichadas_hoy.append({
                                "paciente": paciente_sel,
                                "profesional": nombre_usuario,
                                "fecha_hora": dt.strftime("%d/%m/%Y %H:%M:%S"),
                                "tipo": c.get("tipo_registro", ""),
                                "empresa": mi_empresa,
                            })
    except Exception as e:
        from core.app_logging import log_event
        log_event("visitas_sql", f"error_lectura_checkins:{type(e).__name__}")
    if not fichadas_hoy:
        fichadas_hoy = [
            c for c in st.session_state.get("checkin_db", [])
            if c.get("paciente") == paciente_sel and c.get("profesional") == nombre_usuario and c.get("fecha_hora", "").startswith(hoy_str)
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
        bloque_estado_vacio(
            "Sin fichadas hoy",
            "Todavía no hay llegadas ni salidas registradas hoy para este paciente.",
            sugerencia="Usá Fichar LLEGADA/SALIDA cuando corresponda (con ubicación si aplica).",
        )


def _render_agendar_visita(paciente_sel, mi_empresa, user, rol, agenda_paciente, nombre_usuario, nombre_corto_pac, dire_paciente, tel_paciente):
    """Sección: Agendar Próxima Visita."""
    st.divider()
    st.subheader("Agendar Proxima Visita")
    profesionales = sorted({
        str(v.get("nombre", "")).strip()
        for v in obtener_profesionales_visibles(
            st.session_state, mi_empresa, rol,
            roles_validos=["Operativo", "Enfermeria", "Medico", "Coordinador", "SuperAdmin"],
        )
        if str(v.get("nombre", "")).strip()
    })
    if not profesionales and user.get("nombre"):
        profesionales = [nombre_usuario]
    if not profesionales:
        bloque_estado_vacio(
            "Sin profesionales para asignar",
            "No hay profesionales visibles con permisos para visitas.",
            sugerencia="Revisá Mi Equipo y roles (Operativo, Enfermería, Médico, Coordinador).",
        )
    else:
        ofrecer_wpp_tras_agendar = st.checkbox(
            "Al agendar una visita nueva, ofrecer recordatorio para WhatsApp",
            value=True,
            key=f"wpp_tras_agendar_{paciente_sel}",
        )
        with st.form("agenda_form", clear_on_submit=True):
            c1_ag, c2_ag = st.columns(2)
            fecha_ag = c1_ag.date_input("Fecha programada", value=ahora().date())
            hora_ag = c2_ag.time_input(
                "Hora aproximada (HH:MM)",
                value=ahora().replace(second=0, microsecond=0).time(),
                step=300,
            )
            idx_prof = profesionales.index(nombre_usuario) if nombre_usuario in profesionales else 0
            prof_ag = st.selectbox("Asignar Profesional", profesionales, index=idx_prof)
            if st.form_submit_button("Agendar Visita", use_container_width=True, type="primary"):
                hora_limpia = normalizar_hora_texto(hora_ag.strftime("%H:%M"), default=ahora().strftime("%H:%M"))
                fecha_ag_str = fecha_ag.strftime("%d/%m/%Y")
                fecha_hora_programada = datetime.combine(fecha_ag, hora_ag).strftime("%Y-%m-%d %H:%M:%S")
                conflicto = next(
                    (
                        item for item in _agenda_empresa(mi_empresa, rol)
                        if item.get("profesional") == prof_ag
                        and item.get("fecha") == fecha_ag_str
                        and normalizar_hora_texto(item.get("hora", ""), default="") == hora_limpia
                        and item.get("estado", "Pendiente") not in {"Cancelada", "Realizada"}
                        and item.get("paciente") != paciente_sel
                    ),
                    None,
                )
                if conflicto:
                    st.error(f"{prof_ag} ya tiene una visita activa en ese horario con {conflicto.get('paciente', 'otro paciente')}.")
                else:
                    if "agenda_db" not in st.session_state or not isinstance(st.session_state["agenda_db"], list):
                        st.session_state["agenda_db"] = []
                    st.session_state["agenda_db"].append({
                        "paciente": paciente_sel,
                        "profesional": prof_ag,
                        "fecha": fecha_ag_str,
                        "fecha_programada": fecha_ag_str,
                        "fecha_hora_programada": fecha_hora_programada,
                        "hora": hora_limpia,
                        "empresa": mi_empresa,
                        "estado": "Pendiente",
                        "zona": _zona_corta(dire_paciente),
                        "creado_por": user.get("nombre", ""),
                        "creado_en": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                    })
                    from core.database import _trim_db_list
                    _trim_db_list("agenda_db", 500)
                    try:
                        from core.db_sql import insert_turno
                        from core.nextgen_sync import _obtener_uuid_empresa, _obtener_uuid_paciente
                        partes = paciente_sel.split(" - ")
                        if len(partes) > 1:
                            dni = partes[1].strip()
                            empresa_id = _obtener_uuid_empresa(mi_empresa)
                            if empresa_id:
                                pac_uuid = _obtener_uuid_paciente(dni, empresa_id)
                                if pac_uuid:
                                    from core.database import supabase
                                    prof_id = None
                                    if supabase:
                                        res_prof = supabase.table("usuarios").select("id").eq("nombre", prof_ag).eq("empresa_id", empresa_id).limit(1).execute()
                                        if res_prof.data:
                                            prof_id = res_prof.data[0]["id"]
                                    datos_sql = {
                                        "paciente_id": pac_uuid,
                                        "empresa_id": empresa_id,
                                        "profesional_id": prof_id,
                                        "fecha_hora_programada": fecha_hora_programada,
                                        "estado": "Pendiente"
                                    }
                                    insert_turno(datos_sql)
                    except Exception as e:
                        from core.app_logging import log_event
                        log_event("visitas_sql", f"error_dual_write_turno:{type(e).__name__}")
                    guardar_datos(spinner=True)
                    tel_n = _normalizar_telefono_whatsapp(tel_paciente)
                    if ofrecer_wpp_tras_agendar and tel_n:
                        pls = _plantillas_whatsapp_para_empresa(mi_empresa)
                        nueva = {"fecha": fecha_ag_str, "hora": hora_limpia, "profesional": prof_ag}
                        txt = _armar_mensaje_whatsapp_visita(
                            paciente_sel, mi_empresa, user, nueva, nombre_corto_pac, dire_paciente, plantillas_empresa=pls
                        )
                        st.session_state["_wpp_recordatorio_visita"] = {
                            "paciente": paciente_sel,
                            "tel": tel_n,
                            "texto": txt,
                        }
                    queue_toast(f"Visita agendada para el {fecha_ag_str} a las {hora_limpia} hs.")
                    st.rerun()


def _render_whatsapp_agenda(paciente_sel, mi_empresa, user, rol, agenda_paciente, nombre_corto_pac, dire_paciente, tel_paciente):
    """Sección: Aviso WhatsApp + Agenda inteligente."""
    st.divider()
    st.subheader("Aviso de visita por WhatsApp")
    st.caption("Elegi la visita a informar, revisa o edita el texto y abri WhatsApp con el mensaje listo para enviar.")
    if es_control_total(rol):
        gestionar_tpl = st.checkbox(
            "Gestionar plantillas de mensaje para esta clinica (opcional)",
            value=False,
            key=f"wpp_gestion_tpl_{mi_empresa}",
        )
        if gestionar_tpl:
            emp_tpl = _plantillas_whatsapp_para_empresa(mi_empresa)
            st.caption(
                "Placeholders: {paciente} {empresa} {fecha} {hora} {profesional} {mat_profesional} "
                "{domicilio} {contacto} {rol_contacto} {mat_contacto}. Si dejas vacio, se usa el texto automatico."
            )
            tv = st.text_area("Plantilla con visita concreta (fecha y hora)", value=emp_tpl.get("visita", ""), height=140, key=f"wpp_tpl_visita_edit_{mi_empresa}")
            tg = st.text_area("Plantilla sin fecha puntual (coordinacion general)", value=emp_tpl.get("general", ""), height=120, key=f"wpp_tpl_general_edit_{mi_empresa}")
            if st.button("Guardar plantillas en la clinica", key=f"wpp_tpl_save_{mi_empresa}", type="primary"):
                _plantillas_whatsapp_store()[str(mi_empresa or "").strip() or "_default"] = {
                    "visita": str(tv).strip(),
                    "general": str(tg).strip(),
                }
                guardar_datos(spinner=True)
                queue_toast("Plantillas guardadas.")
                st.rerun()
    ahora_naive_wa = ahora().replace(tzinfo=None)
    visitas_wa = _visitas_para_aviso_whatsapp(agenda_paciente, ahora_naive_wa)
    etiquetas_wa = [_etiqueta_visita_whatsapp(v) for v in visitas_wa] + ["Coordinacion general (sin visita puntual)"]
    sel_key = f"wpp_visita_pick_{paciente_sel}"
    prev_key = f"_wpp_visita_prev_{paciente_sel}"
    msg_key = f"wpp_visita_text_{paciente_sel}"
    if prev_key not in st.session_state:
        st.session_state[prev_key] = None
    if msg_key not in st.session_state:
        st.session_state[msg_key] = ""
    pick_wa = st.selectbox("Visita a comunicar al paciente", range(len(etiquetas_wa)), format_func=lambda i: etiquetas_wa[i], key=sel_key)
    visita_elegida = visitas_wa[pick_wa] if pick_wa < len(visitas_wa) else None
    pls_msg = _plantillas_whatsapp_para_empresa(mi_empresa)
    if st.session_state[prev_key] != pick_wa:
        st.session_state.pop(msg_key, None)
        st.session_state[msg_key] = _armar_mensaje_whatsapp_visita(
            paciente_sel, mi_empresa, user, visita_elegida, nombre_corto_pac, dire_paciente, plantillas_empresa=pls_msg
        )
        st.session_state[prev_key] = pick_wa
    st.text_area("Texto del mensaje", key=msg_key, height=200)
    texto_final_wa = st.session_state.get(msg_key, "").strip()
    tel_wa = _normalizar_telefono_whatsapp(tel_paciente)
    if tel_wa and texto_final_wa:
        link_wpp = f"https://wa.me/{tel_wa}?text={urllib.parse.quote(texto_final_wa)}"
        st.link_button("Abrir WhatsApp con este mensaje", link_wpp, use_container_width=True, type="primary")
    elif not tel_paciente:
        st.warning("Este paciente no tiene telefono registrado. Cargalo en Admision para poder avisar por WhatsApp.")
    else:
        st.warning("Completa el mensaje antes de abrir WhatsApp.")

    if agenda_paciente:
        st.divider()
        from core.view_helpers import lista_plegable
        with lista_plegable("Agenda inteligente — gráficos, filtros y tablas", count=len(agenda_paciente), expanded=False, height=None):
            st.caption("Expandí para ver barras de estado, acciones rápidas, semana y tablas sin alargar toda la página.")
            st.markdown("#### Agenda inteligente")
            df_agenda = pd.DataFrame(agenda_paciente)
            df_agenda["Fecha y Hora"] = df_agenda["_fecha_dt"].apply(lambda x: x.strftime("%d/%m/%Y %H:%M") if x.year > 1900 else "Sin fecha")
            df_agenda["Profesional"] = df_agenda["profesional"].fillna("Sin profesional")
            df_agenda["Estado"] = df_agenda["estado_calc"]
            busqueda_ag = st.text_input("🔍 Buscar turno", placeholder="Profesional, estado o fecha...", key=f"agenda_busq_{paciente_sel}").strip().lower()
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
            if busqueda_ag:
                mask = (
                    df_filtrado["Profesional"].str.lower().str.contains(busqueda_ag, na=False)
                    | df_filtrado["Estado"].str.lower().str.contains(busqueda_ag, na=False)
                    | df_filtrado["Fecha y Hora"].str.lower().str.contains(busqueda_ag, na=False)
                )
                df_filtrado = df_filtrado[mask]
                st.caption(f"{len(df_filtrado)} resultado(s) para '{busqueda_ag}'")
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
                        (x for x in agenda_paciente if f"{x['_fecha_dt'].strftime('%d/%m/%Y %H:%M') if x['_fecha_dt'].year > 1900 else 'Sin fecha'} | {x.get('profesional', 'Sin profesional')} | {x['estado_calc']}" == seleccion),
                        None,
                    )
                    if objetivo:
                        if objetivo.get("id_sql"):
                            try:
                                from core.db_sql import update_estado_turno
                                nuevo_estado = "Realizada" if accion == "Marcar realizada" else "Cancelada"
                                update_estado_turno(objetivo["id_sql"], nuevo_estado)
                            except Exception as e:
                                from core.app_logging import log_event
                                log_event("visitas_sql", f"error_dual_write_update_turno:{type(e).__name__}")
                        for item in st.session_state["agenda_db"]:
                            if (
                                item.get("paciente") == objetivo.get("paciente")
                                and item.get("profesional") == objetivo.get("profesional")
                                and item.get("fecha") == objetivo.get("fecha")
                                and normalizar_hora_texto(item.get("hora", ""), default="") == normalizar_hora_texto(objetivo.get("hora", ""), default="")
                            ):
                                item["estado"] = "Realizada" if accion == "Marcar realizada" else "Cancelada"
                                break
                        guardar_datos(spinner=True)
                        queue_toast("Agenda actualizada correctamente.")
                        st.rerun()
            st.markdown("##### Agenda semanal del paciente")
            semana_ref = st.date_input("Semana de referencia", value=ahora().date(), key=f"agenda_semana_ref_{paciente_sel}")
            inicio_semana = semana_ref - timedelta(days=semana_ref.weekday())
            fin_semana = inicio_semana + timedelta(days=6)
            agenda_semana = [item for item in agenda_paciente if item["_fecha_dt"] != datetime.min and inicio_semana <= item["_fecha_dt"].date() <= fin_semana]
            cols_semana = st.columns(7)
            for idx_dia in range(7):
                dia = inicio_semana + timedelta(days=idx_dia)
                items_dia = [x for x in agenda_semana if x["_fecha_dt"].date() == dia]
                pendientes_dia = sum(1 for x in items_dia if x["estado_calc"] in {"Pendiente", "En curso", "Vencida"})
                realizadas_dia = sum(1 for x in items_dia if x["estado_calc"] == "Realizada")
                cols_semana[idx_dia].markdown(
                    f"""
                    <div class="mc-card" style="padding:14px 12px; min-height:118px;">
                        <div style="font-size:0.78rem; color:#93c5fd; text-transform:uppercase; letter-spacing:1px;">{dia.strftime('%a')}</div>
                        <div style="font-size:1rem; font-weight:800; color:#f8fafc; margin-top:4px;">{dia.strftime('%d/%m')}</div>
                        <div style="font-size:1.4rem; font-weight:900; color:#ffffff; margin-top:10px;">{len(items_dia)}</div>
                        <div style="font-size:0.86rem; color:#cbd5e1; margin-top:4px;">{pendientes_dia} pendientes<br>{realizadas_dia} realizadas</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            if agenda_semana:
                df_semana = pd.DataFrame(agenda_semana)
                df_semana["Dia"] = df_semana["_fecha_dt"].apply(lambda x: x.strftime("%A") if x != datetime.min else "Sin fecha")
                df_semana["Fecha"] = df_semana["_fecha_dt"].apply(lambda x: x.strftime("%d/%m/%Y") if x != datetime.min else "Sin fecha")
                df_semana["Hora"] = df_semana["_fecha_dt"].apply(lambda x: x.strftime("%H:%M") if x != datetime.min else "--:--")
                df_semana["Profesional"] = df_semana["profesional"].fillna("Sin profesional")
                df_semana["Zona"] = df_semana.get("zona", pd.Series(["Zona sin definir"] * len(df_semana))).fillna("Zona sin definir")
                df_semana["Estado"] = df_semana["estado_calc"]
                df_semana = df_semana[["Dia", "Fecha", "Hora", "Profesional", "Zona", "Estado"]].sort_values(["Fecha", "Hora"])
                limite_semana = seleccionar_limite_registros("Filas de la semana", len(df_semana), key=f"agenda_semana_limit_{paciente_sel}", default=14, opciones=(7, 14, 21, 35, 50))
                mostrar_dataframe_con_scroll(df_semana.head(limite_semana), height=300)
            else:
                bloque_estado_vacio("Semana sin visitas en agenda", "No hay turnos en la semana elegida para este paciente.", sugerencia="Cambiá la fecha de referencia de la semana o agendá una visita nueva.")
            limite = seleccionar_limite_registros("Visitas a mostrar", len(df_filtrado), key=f"agenda_limit_{paciente_sel}", default=20, opciones=(10, 20, 30, 50, 80, 120))
            cols_visibles = ["Fecha y Hora", "Profesional", "Estado", "fecha", "hora"]
            df_render = df_filtrado.sort_values("_fecha_dt", ascending=False)[cols_visibles].rename(columns={"fecha": "Fecha", "hora": "Hora"})
            mostrar_dataframe_con_scroll(df_render.head(limite), height=360)
