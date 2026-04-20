"""Utilidades y helpers de UI para el módulo de Recetas/Indicaciones.

Extraído de views/recetas.py para mantenerlo bajo las 300 líneas.
"""
import base64
import re
from html import escape

import streamlit as st

from core.utils import (
    ahora,
    format_horarios_receta,
    mostrar_dataframe_con_scroll,
)

FPDF_DISPONIBLE = False
try:
    from fpdf import FPDF  # noqa: F401
    FPDF_DISPONIBLE = True
except ImportError:
    pass

CANVAS_DISPONIBLE = False
try:
    from streamlit_drawable_canvas import st_canvas  # noqa: F401
    CANVAS_DISPONIBLE = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Helpers de tabla / UI
# ---------------------------------------------------------------------------

def render_tabla_clinica(df, key=None, max_height=420, sticky_first_col=False):
    _ = key, sticky_first_col
    mostrar_dataframe_con_scroll(df, height=max_height, border=True, hide_index=True)


def render_dataframe_filas_tarjetas(df):
    if df is None or getattr(df, "empty", True):
        st.caption("Sin filas para mostrar.")
        return
    for idx, row in df.iterrows():
        cols_prev = list(df.columns)[:4]
        partes = []
        for c in cols_prev:
            try:
                v = str(row[c])[:52].strip()
            except Exception:
                v = ""
            if v:
                partes.append(v)
        titulo = " · ".join(partes) if partes else f"Ítem {idx}"
        with st.expander(titulo[:110], expanded=False):
            for c in df.columns:
                try:
                    val = row[c]
                except Exception:
                    val = ""
                st.markdown(f"**{escape(str(c))}:** {escape(str(val))}")


def render_plan_hidratacion_preview(plan_hidratacion):
    if not plan_hidratacion:
        return
    bloques = ["<div class='mc-rx-mini-board'>"]
    for item in plan_hidratacion[:12]:
        hora = escape(str(item.get("Hora sugerida", "--:--")))
        velocidad = escape(str(item.get("Velocidad (ml/h)", "S/D")))
        bloques.append(
            "<div class='mc-rx-mini-item'>"
            f"<span class='mc-rx-mini-hour'>{hora}</span>"
            f"<span class='mc-rx-mini-speed'>{velocidad} ml/h</span>"
            "</div>"
        )
    if len(plan_hidratacion) > 12:
        bloques.append(
            "<div class='mc-rx-mini-item mc-rx-mini-more'>"
            f"+{len(plan_hidratacion) - 12} horario(s) mas"
            "</div>"
        )
    bloques.append("</div>")
    st.markdown("".join(bloques), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers de datos
# ---------------------------------------------------------------------------

def archivo_a_base64(uploaded_file):
    if uploaded_file is None:
        return "", "", ""
    try:
        contenido = uploaded_file.getvalue()
        if not contenido:
            return "", "", ""
        return (
            base64.b64encode(contenido).decode("utf-8"),
            uploaded_file.name,
            uploaded_file.type or "application/octet-stream",
        )
    except Exception:
        return "", "", ""


def estado_icono(estado):
    estado_norm = str(estado or "").strip().lower()
    if estado_norm == "realizada":
        return "OK"
    if "no realizada" in estado_norm or "suspendida" in estado_norm:
        return "NO"
    return "PEND"


def estado_legible(estado):
    estado_norm = str(estado or "").strip().lower()
    if estado_norm == "realizada":
        return "Realizada"
    if "no realizada" in estado_norm or "suspendida" in estado_norm:
        return "No realizada"
    return "Pendiente"


def extraer_nombre_medicacion(texto):
    return str(texto or "").split(" | ")[0].strip()


def resumen_plan_hidratacion(plan_hidratacion):
    if not plan_hidratacion:
        return ""
    partes = []
    for item in plan_hidratacion:
        hora = item.get("Hora sugerida", "")
        velocidad = item.get("Velocidad (ml/h)", "")
        if hora and velocidad != "":
            partes.append(f"{hora}: {velocidad} ml/h")
    return " | ".join(partes)


def detalle_horario_infusion(registro, horario):
    plan = registro.get("plan_hidratacion", []) or []
    for item in plan:
        if item.get("Hora sugerida") == horario:
            velocidad = item.get("Velocidad (ml/h)")
            if velocidad not in ("", None):
                return f"{velocidad} ml/h"
    velocidad = registro.get("velocidad_ml_h")
    if velocidad not in ("", None):
        return f"{velocidad} ml/h"
    return registro.get("detalle_infusion", "")


def nombre_usuario(user):
    return str(user.get("nombre", "") or "Sistema")


def firma_trazabilidad_admin(admin_reg):
    if not admin_reg:
        return ""
    nom = str(admin_reg.get("firma", "") or "").strip()
    mp = str(admin_reg.get("matricula_profesional", "") or admin_reg.get("matricula", "") or "").strip()
    if nom and mp:
        return f"{nom} (Mat. {mp})"
    return nom or (f"Mat. {mp}" if mp else "")


def parse_hora_hhmm(valor):
    t = str(valor or "").strip()
    if not t:
        return ""
    m = re.match(r"^(\d{1,2}):(\d{1,2})$", t)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return None
    return f"{h:02d}:{mi:02d}"


def hora_real_para_registro(hora_real_admin):
    if hora_real_admin is None:
        return ahora().strftime("%H:%M"), ""
    s = str(hora_real_admin).strip()
    if not s:
        return ahora().strftime("%H:%M"), ""
    p = parse_hora_hhmm(s)
    if p is None:
        return "", "Hora real inválida. Usá formato HH:MM (ej. 08:30 o 14:05)."
    return p, ""


def orden_horario_programado(valor):
    texto = str(valor or "").strip()
    if texto.lower() == "a demanda":
        return 9999
    partes = texto.split(":")
    if len(partes) != 2 or not all(parte.isdigit() for parte in partes):
        return 9999
    return int(partes[0]) * 60 + int(partes[1])


def texto_corto(valor, fallback="S/D", max_len=70):
    texto = str(valor or "").strip()
    if not texto:
        return fallback
    if len(texto) > max_len:
        return f"{texto[: max_len - 3].rstrip()}..."
    return texto


def etiqueta_receta(registro):
    nombre = texto_corto(extraer_nombre_medicacion(registro.get("med", "")), fallback="Indicacion sin titulo", max_len=48)
    horarios = texto_corto(format_horarios_receta(registro), fallback="Sin horarios", max_len=34)
    estado = texto_corto(registro.get("estado_receta", "Activa"), fallback="Activa", max_len=20)
    return f"{nombre} | {horarios} | {estado}"
