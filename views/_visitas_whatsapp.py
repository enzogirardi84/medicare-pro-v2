"""Helpers de WhatsApp para el módulo Visitas y Agenda.

Extraído de views/visitas.py.
"""
import streamlit as st

from core.utils import normalizar_hora_texto


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
    from datetime import datetime
    activas = [
        x for x in agenda_paciente
        if x.get("estado_calc") in {"Pendiente", "En curso", "Vencida"} and x["_fecha_dt"] != datetime.min
    ]
    futuro = [x for x in activas if x["_fecha_dt"] >= now_naive]
    resto = [x for x in activas if x["_fecha_dt"] < now_naive]
    futuro.sort(key=lambda x: x["_fecha_dt"])
    resto.sort(key=lambda x: x["_fecha_dt"], reverse=True)
    return futuro + resto


def _etiqueta_visita_whatsapp(item):
    _dt = item.get("_fecha_dt")
    try:
        fh = _dt.strftime("%d/%m/%Y %H:%M") if hasattr(_dt, "year") and _dt.year > 1900 else "Sin fecha"
    except Exception:
        fh = "Sin fecha"
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
        prof = fecha = hora = mat_asign = ""
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


def _armar_mensaje_whatsapp_visita(
    paciente_sel, mi_empresa, user, visita_dict, nombre_corto, dire_paciente, plantillas_empresa=None
):
    plantillas_empresa = plantillas_empresa or _plantillas_whatsapp_para_empresa(mi_empresa)
    vals = _valores_placeholders_whatsapp(mi_empresa, user, visita_dict, nombre_corto, dire_paciente)
    tpl = str(plantillas_empresa.get("visita" if visita_dict else "general", "")).strip()
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
