"""Evaluación y renderizado de Signos Vitales con alertas de color.

Extraído de views/historial.py.
"""
from typing import Any, Dict, List

import streamlit as st

_RANGOS_VITALES = {
    "FC":   {"min": 60,   "max": 100,  "critico_min": 40,   "critico_max": 130,  "unidad": "lpm"},
    "FR":   {"min": 12,   "max": 20,   "critico_min": 8,    "critico_max": 30,   "unidad": "rpm"},
    "Sat":  {"min": 94,   "max": 100,  "critico_min": 88,   "critico_max": 100,  "unidad": "%"},
    "Temp": {"min": 36.0, "max": 37.5, "critico_min": 35.0, "critico_max": 39.0, "unidad": "°C"},
    "HGT":  {"min": 70,   "max": 180,  "critico_min": 50,   "critico_max": 300,  "unidad": "mg/dL"},
}

_TA_SISTOLICA_MIN = 90
_TA_SISTOLICA_MAX = 140
_TA_DIASTOLICA_MIN = 60
_TA_DIASTOLICA_MAX = 90

_ESTADO_EMOJI = {"normal": "🟢", "alerta": "🟡", "critico": "🔴", "sin_dato": "⚪"}
_ESTADO_LABEL = {"normal": "Normal", "alerta": "Fuera de rango", "critico": "¡Crítico!", "sin_dato": "S/D"}


def _evaluar_ta(ta_str: str) -> str:
    if not ta_str or ta_str in ("-", "S/D", ""):
        return "sin_dato"
    try:
        partes = str(ta_str).replace("/", " ").split()
        if len(partes) < 2:
            return "sin_dato"
        sis = float(partes[0])
        dia = float(partes[1])
        if sis < 80 or sis > 180 or dia < 50 or dia > 120:
            return "critico"
        if sis < _TA_SISTOLICA_MIN or sis > _TA_SISTOLICA_MAX or dia < _TA_DIASTOLICA_MIN or dia > _TA_DIASTOLICA_MAX:
            return "alerta"
        return "normal"
    except Exception:
        return "sin_dato"


def _evaluar_vital(clave: str, valor_raw) -> str:
    if clave == "TA":
        return _evaluar_ta(str(valor_raw or ""))
    rango = _RANGOS_VITALES.get(clave)
    if not rango:
        return "sin_dato"
    try:
        val = float(str(valor_raw).replace(",", "."))
    except Exception:
        return "sin_dato"
    if val < rango["critico_min"] or val > rango["critico_max"]:
        return "critico"
    if val < rango["min"] or val > rango["max"]:
        return "alerta"
    return "normal"


def _render_signos_vitales_con_alertas(registros: List[Dict[str, Any]], paciente_sel: str) -> None:
    claves_vitales = ["TA", "FC", "FR", "Sat", "Temp", "HGT"]
    for idx, reg in enumerate(registros):
        fecha = reg.get("fecha", reg.get("fecha_hora", "S/D"))
        firma = reg.get("firma", reg.get("firmado_por", reg.get("profesional", "S/D")))
        estados = {k: _evaluar_vital(k, reg.get(k)) for k in claves_vitales}
        hay_critico = any(e == "critico" for e in estados.values())
        hay_alerta = any(e == "alerta" for e in estados.values())
        titulo_badge = " 🔴 CRÍTICO" if hay_critico else (" 🟡 Alerta" if hay_alerta else "")
        with st.container(border=True):
            col_h1, col_h2 = st.columns([3, 1])
            col_h1.markdown(f"**{fecha}**{titulo_badge}")
            col_h2.caption(f"Por: {firma}")
            cols = st.columns(len(claves_vitales))
            for i, clave in enumerate(claves_vitales):
                valor = reg.get(clave, "")
                estado = estados[clave]
                emoji = _ESTADO_EMOJI[estado]
                unidad = _RANGOS_VITALES.get(clave, {}).get("unidad", "")
                label_estado = _ESTADO_LABEL[estado]
                display = f"{valor} {unidad}".strip() if valor and str(valor) not in ("-", "") else "—"
                cols[i].metric(
                    label=f"{emoji} {clave}",
                    value=display,
                    help=f"{label_estado}" + (
                        f" | Rango: {_RANGOS_VITALES[clave]['min']}–{_RANGOS_VITALES[clave]['max']} {unidad}"
                        if clave in _RANGOS_VITALES else ""
                    ),
                )
            if hay_critico:
                criticos = [k for k, e in estados.items() if e == "critico"]
                st.error(f"⚠️ Valores críticos: **{', '.join(criticos)}**. Requiere atención inmediata.")
            elif hay_alerta:
                alertas = [k for k, e in estados.items() if e == "alerta"]
                st.warning(f"⚠️ Fuera de rango: **{', '.join(alertas)}**. Revisar evolución.")
