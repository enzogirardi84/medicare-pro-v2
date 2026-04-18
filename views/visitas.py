from core.alert_toasts import queue_toast
from datetime import datetime, timedelta
import urllib.parse

import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio, lista_plegable
from core.utils import (
    ahora,
    calcular_estado_agenda,
    es_control_total,
    filtrar_registros_empresa,
    mapa_detalles_pacientes,
    normalizar_hora_texto,
    obtener_profesionales_visibles,
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


def _normalizar_telefono_whatsapp(raw):
    tel_limpio = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if not tel_limpio:
        return ""
    if tel_limpio.startswith("0"):
        tel_limpio = tel_limpio.lstrip("0") or tel_limpio
    if not tel_limpio.startswith("54"):
        tel_limpio = "549" + tel_limpio
    return tel_limpio


def _matricula_profesional_por_nombre(nombre_prof):
    if not nombre_prof:
        return ""
    target = str(nombre_prof).strip().lower()
    for u in st.session_state.get("usuarios_db", {}).values():
        if str(u.get("nombre", "")).strip().lower() == target:
            return str(u.get("matricula", "")).strip()
    return ""


def _visitas_para_aviso_whatsapp(agenda_paciente, now_naive):
    activas = [
        x
        for x in agenda_paciente
        if x.get("estado_calc") in {"Pendiente", "En curso", "Vencida"} and x["_fecha_dt"] != datetime.min
    ]
    futuro = [x for x in activas if x["_fecha_dt"] >= now_naive]
    resto = [x for x in activas if x["_fecha_dt"] < now_naive]
    futuro.sort(key=lambda x: x["_fecha_dt"])
    resto.sort(key=lambda x: x["_fecha_dt"], reverse=True)
    return futuro + resto


def _etiqueta_visita_whatsapp(item):
    fh = item["_fecha_dt"].strftime("%d/%m/%Y %H:%M") if item["_fecha_dt"].year > 1900 else "Sin fecha"
    prof = item.get("profesional") or "Sin profesional"
    return f"{fh} — {prof} ({item.get('estado_calc', '')})"


def _plantillas_whatsapp_store():
    return st.session_state.setdefault("plantillas_whatsapp_db", {})


def _plantillas_whatsapp_para_empresa(mi_empresa):
    store = _plantillas_whatsapp_store()
    key = str(mi_empresa or "").strip() or "_default"
    if key not in store or not isinstance(store[key], dict):
        store[key] = {"visita": "", "general": ""}
    return store[key]


def _valores_placeholders_whatsapp(mi_empresa, user, visita_dict, nombre_corto, dire_paciente):
    quien = str(user.get("nombre", "")).strip()
    mat_quien = str(user.get("matricula", "")).strip()
    rol = str(user.get("rol", "")).strip()
    if visita_dict:
        prof = str(visita_dict.get("profesional", "")).strip() or "su equipo de salud"
        fecha = str(visita_dict.get("fecha", "")).strip()
        hora = normalizar_hora_texto(visita_dict.get("hora", ""), default="")
        mat_asign = _matricula_profesional_por_nombre(prof)
    else:
        prof = ""
        fecha = ""
        hora = ""
        mat_asign = ""
    dom = ""
    if dire_paciente and str(dire_paciente).strip() not in ("", "No registrada"):
        dom = str(dire_paciente).strip()
    return {
        "paciente": nombre_corto,
        "empresa": str(mi_empresa or "").strip(),
        "fecha": fecha,
        "hora": hora,
        "profesional": prof,
        "mat_profesional": mat_asign,
        "domicilio": dom,
        "contacto": quien,
        "rol_contacto": rol,
        "mat_contacto": mat_quien,
    }


def _aplicar_plantilla_whatsapp(plantilla, valores):
    if not plantilla or not str(plantilla).strip():
        return None
    out = str(plantilla)
    for k, v in valores.items():
        out = out.replace("{" + k + "}", str(v) if v is not None else "")
    return out


def _armar_mensaje_whatsapp_visita(paciente_sel, mi_empresa, user, visita_dict, nombre_corto, dire_paciente, plantillas_empresa=None):
    plantillas_empresa = plantillas_empresa or _plantillas_whatsapp_para_empresa(mi_empresa)
    vals = _valores_placeholders_whatsapp(mi_empresa, user, visita_dict, nombre_corto, dire_paciente)
    if visita_dict:
        tpl = str(plantillas_empresa.get("visita", "")).strip()
    else:
        tpl = str(plantillas_empresa.get("general", "")).strip()
    armado = _aplicar_plantilla_whatsapp(tpl, vals)
    if armado is not None and str(armado).strip():
        return str(armado).strip()

    quien = vals["contacto"]
    mat_quien = vals["mat_contacto"]
    rol = vals["rol_contacto"]

    if visita_dict:
        prof = vals["profesional"]
        fecha = vals["fecha"]
        hora = vals["hora"]
        mat_asign = vals["mat_profesional"]
        lineas = [
            f"Hola {nombre_corto},",
            f"Le escribimos desde {mi_empresa} para confirmarle la visita domiciliaria programada.",
            f"Fecha: {fecha}",
            f"Hora aproximada: {hora} hs.",
            f"Profesional asignado: {prof}",
        ]
        if mat_asign:
            lineas.append(f"Matricula del profesional asignado: {mat_asign}")
        if vals["domicilio"]:
            lineas.append(f"Domicilio registrado: {vals['domicilio']}")
        lineas.append("")
        lineas.append("Ante cualquier cambio o consulta puede responder por este mismo chat.")
        firma = f"Saludos cordiales — {quien}" if quien else "Saludos cordiales"
        if rol:
            firma += f" ({rol})"
        lineas.append(firma)
        if mat_quien:
            lineas.append(f"Mat. quien envia el aviso: {mat_quien}")
        return "\n".join(lineas)

    lineas = [
        f"Hola {nombre_corto},",
        f"Nos comunicamos desde {mi_empresa} en relacion con su internacion domiciliaria.",
        "En breve coordinamos fecha y hora de la proxima visita con el equipo asignado.",
        "",
        "Ante cualquier urgencia puede responder por este mismo chat.",
    ]
    if quien:
        lineas.append(f"Contacto operativo: {quien}" + (f" ({rol})" if rol else ""))
    if mat_quien:
        lineas.append(f"Mat.: {mat_quien}")
    return "\n".join(lineas)


def _agenda_empresa(mi_empresa, rol):
    # --- SWITCH FINAL: LECTURA DESDE POSTGRESQL ---
    from core.db_sql import get_turnos_by_empresa
    from core.nextgen_sync import _obtener_uuid_empresa
    from core.utils import ahora
    from datetime import timedelta
    
    agenda_sql = []
    uso_sql = False
    
    try:
        empresa_id = _obtener_uuid_empresa(mi_empresa)
        if empresa_id:
            # Traemos turnos desde hace 30 días hasta 60 días en el futuro
            fecha_inicio = (ahora() - timedelta(days=30)).isoformat()
            fecha_fin = (ahora() + timedelta(days=60)).isoformat()
            
            turnos_sql = get_turnos_by_empresa(empresa_id, fecha_inicio, fecha_fin)
            uso_sql = True
            
            for t in turnos_sql:
                paciente_nombre = t.get("pacientes", {}).get("nombre_completo", "") if t.get("pacientes") else ""
                paciente_dni = t.get("pacientes", {}).get("dni", "") if t.get("pacientes") else ""
                paciente_visual = f"{paciente_nombre} - {paciente_dni}" if paciente_nombre else ""
                
                profesional_nombre = t.get("usuarios", {}).get("nombre", "") if t.get("usuarios") else ""
                
                fecha_hora_raw = t.get("fecha_hora_programada", "")
                fecha_str = ""
                hora_str = ""
                if fecha_hora_raw:
                    parts = fecha_hora_raw[:16].split("T")
                    if len(parts) == 2:
                        d_parts = parts[0].split("-")
                        if len(d_parts) == 3:
                            fecha_str = f"{d_parts[2]}/{d_parts[1]}/{d_parts[0]}"
                        hora_str = parts[1]
                
                agenda_sql.append({
                    "id_sql": t.get("id"),
                    "paciente": paciente_visual,
                    "profesional": profesional_nombre,
                    "fecha": fecha_str,
                    "fecha_programada": fecha_str,
                    "fecha_hora_programada": fecha_hora_raw.replace("T", " ")[:19] if fecha_hora_raw else "",
                    "hora": hora_str,
                    "empresa": mi_empresa,
                    "estado": t.get("estado", "Pendiente"),
                    "motivo": t.get("motivo", ""),
                    "notas": t.get("notas", "")
                })
    except Exception as e:
        print(f"Error en lectura SQL de agenda: {e}")
        
    if uso_sql:
        return agenda_sql
    # ----------------------------------------------

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


def _zona_corta(direccion):
    texto = str(direccion or "").strip()
    if not texto or texto == "No registrada":
        return "Zona sin definir"
    return texto.split(",")[0].strip()[:60]


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
                    # --- NUEVO CÓDIGO SQL ---
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
                        print(f"Error dual-write checkin llegada: {e}")
                    # ------------------------
                    
                    # Safe initialization antes de append
                    if "checkin_db" not in st.session_state or not isinstance(st.session_state["checkin_db"], list):
                        st.session_state["checkin_db"] = []
                    st.session_state["checkin_db"].append(
                        {
                            "paciente": paciente_sel,
                            "profesional": nombre_usuario,
                            "fecha_hora": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                            "tipo": f"LLEGADA en: {direccion_real} (Lat: {lat_str})",
                            "empresa": mi_empresa,
                            "gps": f"{lat_str},{lon_str}"
                        }
                    )
                    guardar_datos(spinner=True)
                    queue_toast("Llegada registrada.")
                    st.rerun()
                if col_out.button("Fichar SALIDA", use_container_width=True):
                    # --- NUEVO CÓDIGO SQL ---
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
                        print(f"Error dual-write checkin salida: {e}")
                    # ------------------------
                    
                    # Safe initialization antes de append (ya inicializado arriba, verificamos igual)
                    if "checkin_db" not in st.session_state or not isinstance(st.session_state["checkin_db"], list):
                        st.session_state["checkin_db"] = []
                    st.session_state["checkin_db"].append(
                        {
                            "paciente": paciente_sel,
                            "profesional": nombre_usuario,
                            "fecha_hora": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                            "tipo": f"SALIDA de: {direccion_real} (Lat: {lat_str})",
                            "empresa": mi_empresa,
                            "gps": f"{lat_str},{lon_str}"
                        }
                    )
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
    
    # 1. Intentar leer desde PostgreSQL (Hybrid Read)
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
                        
                        # Solo agregamos si coincide paciente y profesional
                        if paciente_sel.startswith(paciente_nombre) and prof_nombre == nombre_usuario:
                            fichadas_hoy.append({
                                "paciente": paciente_sel,
                                "profesional": nombre_usuario,
                                "fecha_hora": dt.strftime("%d/%m/%Y %H:%M:%S"),
                                "tipo": c.get("tipo_registro", ""),
                                "empresa": mi_empresa,
                            })
    except Exception as e:
        print(f"Error leyendo checkins SQL: {e}")

    # 2. Fallback a JSON si SQL falla o esta vacio
    if not fichadas_hoy:
        fichadas_hoy = [
            c
            for c in st.session_state.get("checkin_db", [])
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

    st.divider()
    st.subheader("Agendar Proxima Visita")
    profesionales = sorted(
        {
            str(v.get("nombre", "")).strip()
            for v in obtener_profesionales_visibles(
                st.session_state,
                mi_empresa,
                rol,
                roles_validos=["Operativo", "Enfermeria", "Medico", "Coordinador", "SuperAdmin"],
            )
            if str(v.get("nombre", "")).strip()
        }
    )
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
                        item
                        for item in _agenda_empresa(mi_empresa, rol)
                        if item.get("profesional") == prof_ag
                        and item.get("fecha") == fecha_ag_str
                        and normalizar_hora_texto(item.get("hora", ""), default="") == hora_limpia
                        and item.get("estado", "Pendiente") not in {"Cancelada", "Realizada"}
                        and item.get("paciente") != paciente_sel
                    ),
                    None,
                )
                if conflicto:
                    st.error(
                        f"{prof_ag} ya tiene una visita activa en ese horario con {conflicto.get('paciente', 'otro paciente')}."
                    )
                else:
                    # Safe initialization antes de append
                    if "agenda_db" not in st.session_state or not isinstance(st.session_state["agenda_db"], list):
                        st.session_state["agenda_db"] = []
                    st.session_state["agenda_db"].append(
                        {
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
                        }
                    )
                    
                    # --- NUEVO CÓDIGO SQL ---
                    from core.db_sql import insert_turno
                    from core.nextgen_sync import _obtener_uuid_empresa, _obtener_uuid_paciente
                    try:
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
                        print(f"Error dual-write turno: {e}")
                    # ------------------------
                    
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
                        st.rerun()
                    queue_toast(f"Visita agendada para el {fecha_ag_str} a las {hora_limpia} hs.")
                    st.rerun()

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
            tv = st.text_area(
                "Plantilla con visita concreta (fecha y hora)",
                value=emp_tpl.get("visita", ""),
                height=140,
                key=f"wpp_tpl_visita_edit_{mi_empresa}",
            )
            tg = st.text_area(
                "Plantilla sin fecha puntual (coordinacion general)",
                value=emp_tpl.get("general", ""),
                height=120,
                key=f"wpp_tpl_general_edit_{mi_empresa}",
            )
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
        # Evita que el text_area conserve el valor anterior al cambiar la visita (sincroniza bien con Streamlit).
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
        with lista_plegable(
            "Agenda inteligente — gráficos, filtros y tablas",
            count=len(agenda_paciente),
            expanded=False,
            height=None,
        ):
            st.caption("Expandí para ver barras de estado, acciones rápidas, semana y tablas sin alargar toda la página.")
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
                        # --- ACTUALIZAR EN SQL ---
                        if objetivo.get("id_sql"):
                            try:
                                from core.db_sql import update_estado_turno
                                nuevo_estado = "Realizada" if accion == "Marcar realizada" else "Cancelada"
                                update_estado_turno(objetivo["id_sql"], nuevo_estado)
                            except Exception as e:
                                print(f"Error dual-write update turno: {e}")
                        # -------------------------
                        
                        # Actualizar en JSON legacy
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
            semana_ref = st.date_input(
                "Semana de referencia",
                value=ahora().date(),
                key=f"agenda_semana_ref_{paciente_sel}",
            )
            inicio_semana = semana_ref - timedelta(days=semana_ref.weekday())
            fin_semana = inicio_semana + timedelta(days=6)
            agenda_semana = [
                item
                for item in agenda_paciente
                if item["_fecha_dt"] != datetime.min and inicio_semana <= item["_fecha_dt"].date() <= fin_semana
            ]

            cols_semana = st.columns(7)
            for idx_dia in range(7):
                dia = inicio_semana + timedelta(days=idx_dia)
                items_dia = [x for x in agenda_semana if x["_fecha_dt"].date() == dia]
                pendientes_dia = sum(1 for x in items_dia if x["estado_calc"] in {"Pendiente", "En curso", "Vencida"})
                realizadas_dia = sum(1 for x in items_dia if x["estado_calc"] == "Realizada")
                cols_semana[idx_dia].markdown(
                    f"""
                    <div class="mc-card" style="padding:14px 12px; min-height:118px;">
                        <div style="font-size:0.78rem; color:#93c5fd; text-transform:uppercase; letter-spacing:1px;">
                            {dia.strftime('%a')}
                        </div>
                        <div style="font-size:1rem; font-weight:800; color:#f8fafc; margin-top:4px;">
                            {dia.strftime('%d/%m')}
                        </div>
                        <div style="font-size:1.4rem; font-weight:900; color:#ffffff; margin-top:10px;">{len(items_dia)}</div>
                        <div style="font-size:0.86rem; color:#cbd5e1; margin-top:4px;">
                            {pendientes_dia} pendientes<br>{realizadas_dia} realizadas
                        </div>
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
                limite_semana = seleccionar_limite_registros(
                    "Filas de la semana",
                    len(df_semana),
                    key=f"agenda_semana_limit_{paciente_sel}",
                    default=14,
                    opciones=(7, 14, 21, 35, 50),
                )
                mostrar_dataframe_con_scroll(df_semana.head(limite_semana), height=300)
            else:
                bloque_estado_vacio(
                    "Semana sin visitas en agenda",
                    "No hay turnos en la semana elegida para este paciente.",
                    sugerencia="Cambiá la fecha de referencia de la semana o agendá una visita nueva.",
                )

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
