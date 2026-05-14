"""Chatbot IA - Asistente virtual con busqueda web y datos del paciente."""
from __future__ import annotations

import json
import re
from datetime import datetime
from html import escape
from typing import List, Dict, Optional
import html as html_mod

import streamlit as st

from core.app_logging import log_event


# ============================================================
# BUSQUEDA WEB
# ============================================================
def buscar_en_web(consulta: str, max_res: int = 3) -> List[Dict]:
    resultados = []
    try:
        import requests
        from urllib.parse import quote
        r = requests.get(
            f"https://html.duckduckgo.com/html/?q={quote(consulta)}",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8,
        )
        if r.status_code == 200:
            for m in re.finditer(r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', r.text):
                resultados.append({"titulo": html_mod.unescape(m.group(2)).strip(), "url": html_mod.unescape(m.group(1))})
                if len(resultados) >= max_res:
                    break
    except Exception as e:
        log_event("chatbot", f"error_busqueda:{e}")
    return resultados


# ============================================================
# IA (OpenAI/Anthropic)
# ============================================================
def preguntar_a_ia(consulta: str, contexto: str = "") -> Optional[str]:
    try:
        from core.ai_assistant import LLM_ENABLED, LLM_PROVIDER, LLM_API_KEY, LLM_MODEL
        if not LLM_ENABLED:
            return None
        prompt = f"Contexto del paciente: {contexto}\n\nPregunta: {consulta}\n\nResponde de forma clara y profesional."
        if LLM_PROVIDER == "openai":
            from openai import OpenAI
            resp = OpenAI(api_key=LLM_API_KEY, timeout=15).chat.completions.create(
                model=LLM_MODEL, messages=[{"role": "system", "content": "Eres un asistente medico."}, {"role": "user", "content": prompt}],
                max_tokens=500, temperature=0.3
            )
            return resp.choices[0].message.content.strip()
        elif LLM_PROVIDER == "anthropic":
            import anthropic
            resp = anthropic.Anthropic(api_key=LLM_API_KEY).completions.create(
                model=LLM_MODEL, prompt=f"Human: {prompt}\n\nAssistant:", max_tokens_to_sample=500, temperature=0.3
            )
            return resp.completion.strip()
    except Exception as e:
        log_event("chatbot", f"error_ia:{e}")
    return None


# ============================================================
# CONOCIMIENTO LOCAL
# ============================================================
CONOCIMIENTO = {
    "horario": "Lunes a viernes de 8:00 a 18:00 hs. Sabados de 9:00 a 13:00 hs.",
    "turno": "Solicita turno en el modulo Turnos Online. Elegi profesional, fecha y confirma.",
    "consulta": "Consulta medica domiciliaria: $15,000. Incluye evaluacion y signos vitales.",
    "medicamento": "Revisa indicaciones activas en Recetas. No modifiques dosis sin consultar al medico.",
    "medicacion": "Revisa tus indicaciones activas en el modulo Recetas.",
    "emergencia": "🚨 Si es una emergencia llama al 107 (SAME) o al hospital mas cercano INMEDIATAMENTE.",
    "obra social": "Trabajamos con OSDE, Swiss Medical, Galeno, Medicus y la mayoria de las prepagas.",
    "domicilio": "Visitas domiciliarias en un radio de 15 km. Costo adicional segun distancia.",
    "estudio": "Resultados de estudios en 48-72 hs habiles. Consulta en el modulo Estudios.",
    "laboratorio": "Subi resultados completos en el modulo Laboratorio.",
    "factura": "Emitimos factura electronica AFIP/ARCA. Solicitala en Factura Electronica.",
    "vacuna": "Aplicamos calendario nacional. Consulta y registra en Vacunacion.",
    "covid": "Protocolo: barbijo obligatorio en instalaciones. Sintomas respiratorios: avisar al ingresar.",
    "receta": "Recetas electronicas validas por 30 dias desde su emision.",
    "derivacion": "Gestiona derivaciones desde Coordinacion. Demora estimada 48-72 hs.",
    "firma": "Documentos digitales con firma electronica en el modulo PDF.",
    "default": "No tengo informacion sobre eso. Escribi 'buscar: tu consulta' para buscar en internet.",
}


def _respuesta_local(consulta: str) -> str:
    cl = consulta.lower()
    for clave, resp in CONOCIMIENTO.items():
        if clave != "default" and clave in cl:
            return resp
    return CONOCIMIENTO["default"]


# ============================================================
# DATOS DEL PACIENTE
# ============================================================
def _datos_paciente(paciente_sel) -> str:
    """Devuelve resumen de datos del paciente como texto."""
    detalles = st.session_state.get("detalles_pacientes_db", {}).get(paciente_sel, {})
    partes = paciente_sel.split(" - ", 1)
    nombre = partes[0] if partes else paciente_sel
    dni = partes[1] if len(partes) > 1 else "S/D"
    texto = f"Paciente: {nombre} (DNI: {dni})"
    if detalles.get("alergias"):
        texto += f"\nAlergias: {detalles['alergias']}"
    if detalles.get("patologias"):
        texto += f"\nPatologias: {detalles['patologias']}"
    if detalles.get("obra_social"):
        texto += f"\nObra social: {detalles['obra_social']}"
    return texto


def _medicaciones_paciente(paciente_sel) -> str:
    """Devuelve medicacion activa del paciente."""
    inds = [r for r in st.session_state.get("indicaciones_db", [])
            if r.get("paciente") == paciente_sel
            and str(r.get("estado_receta", "Activa")).lower() not in ("suspendida", "cancelada")]
    if not inds:
        return "Sin indicaciones activas."
    texto = "Indicaciones activas:\n"
    for i in inds[:5]:
        med = i.get("med", i.get("medicacion", "?"))
        dosis = i.get("dosis", "")
        freq = i.get("frecuencia", "")
        texto += f"- {med} {dosis} {freq}\n"
    return texto


# ============================================================
# CHAT UI
# ============================================================
def render_chatbot_ia(paciente_sel, mi_empresa, user, rol):
    if not paciente_sel:
        from core.view_helpers import aviso_sin_paciente
        aviso_sin_paciente()
        return

    st.markdown("""
        <div class="mc-hero">
            <h2 class="mc-hero-title">Asistente IA</h2>
            <p class="mc-hero-text">Consulta sobre el paciente, medicacion, horarios o busca en internet.</p>
        </div>
    """, unsafe_allow_html=True)

    if "chatbot_conv" not in st.session_state:
        st.session_state["chatbot_conv"] = []
    conv = st.session_state["chatbot_conv"]

    # CSS burbujas
    st.markdown("""
        <style>
        .cb-us { background:linear-gradient(135deg,#2563eb,#0ea5e9); color:#fff; padding:10px 16px; border-radius:18px 18px 4px 18px; margin:8px 0; max-width:80%; margin-left:auto; }
        .cb-bot { background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.08); color:#e2e8f0; padding:10px 16px; border-radius:18px 18px 18px 4px; margin:8px 0; max-width:85%; }
        .cb-bot a { color:#60a5fa; }
        .cb-time { font-size:0.7rem; color:#64748b; margin-top:2px; }
        </style>
    """, unsafe_allow_html=True)

    # Botones de accion rapida
    st.markdown("##### Acciones rapidas")
    cols = st.columns(5)
    acciones = [
        ("Mostrar datos", "datos"),
        ("Medicacion", "medicacion"),
        ("Ultima evolucion", "evolucion"),
        ("Proximos turnos", "turnos"),
        ("Limpiar chat", "limpiar"),
    ]
    for i, (label, accion) in enumerate(acciones):
        with cols[i]:
            if st.button(label, key=f"act_{i}", width="stretch"):
                st.session_state["chatbot_accion"] = accion
                st.rerun()

    accion = st.session_state.pop("chatbot_accion", None)
    if accion == "limpiar":
        st.session_state["chatbot_conv"] = []
        st.rerun()
    elif accion == "datos":
        resp = _datos_paciente(paciente_sel)
        hora = datetime.now().strftime("%H:%M")
        conv.append({"rol": "bot", "texto": resp, "hora": hora, "fuentes": []})
    elif accion == "medicacion":
        resp = _medicaciones_paciente(paciente_sel)
        hora = datetime.now().strftime("%H:%M")
        conv.append({"rol": "bot", "texto": resp, "hora": hora, "fuentes": []})
    elif accion == "evolucion":
        evols = [r for r in st.session_state.get("evoluciones_db", []) if r.get("paciente") == paciente_sel]
        if evols:
            ult = evols[-1]
            fecha = ult.get("fecha", ult.get("fecha_evolucion", "?"))
            nota = str(ult.get("nota", ult.get("evolucion", "")) or "")[:300]
            resp = f"Ultima evolucion ({fecha}):\n{nota}"
        else:
            resp = "Sin evoluciones registradas."
        conv.append({"rol": "bot", "texto": resp, "hora": datetime.now().strftime("%H:%M"), "fuentes": []})
    elif accion == "turnos":
        turnos = [t for t in st.session_state.get("turnos_online_db", []) if t.get("paciente") == paciente_sel and t.get("estado") == "Reservado"]
        if turnos:
            resp = "Turnos reservados:\n"
            for t in turnos[:5]:
                resp += f"- {t.get('fecha','?')} {t.get('horario','?')} con {t.get('profesional','?')}\n"
        else:
            resp = "Sin turnos reservados."
        conv.append({"rol": "bot", "texto": resp, "hora": datetime.now().strftime("%H:%M"), "fuentes": []})

    st.divider()

    # Chat
    chat = st.container(height=400, border=True)
    with chat:
        if not conv:
            st.info("Hola! Soy el asistente. Hace una pregunta o usa las acciones rapidas arriba.")
        for msg in conv:
            css = "cb-us" if msg["rol"] == "user" else "cb-bot"
            st.markdown(f'<div class="{css}">{escape(msg["texto"])}</div>', unsafe_allow_html=True)
            if msg.get("fuentes"):
                for f in msg["fuentes"]:
                    st.markdown(f'<div class="cb-time"><a href="{escape(f["url"])}" target="_blank">{escape(f["titulo"])}</a></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="cb-time">{msg.get("hora","")}</div>', unsafe_allow_html=True)

    # Input
    with st.form("chat_form", clear_on_submit=True):
        mensaje = st.text_input("Tu consulta:", placeholder='Ej: "Que horarios tienen?" o "buscar: dosis ibuprofeno"')
        cols = st.columns([3, 1])
        enviar = cols[0].form_submit_button("Enviar", width="stretch", type="primary")
        limpiar = cols[1].form_submit_button("Limpiar chat", width="stretch")

    if limpiar:
        st.session_state["chatbot_conv"] = []
        st.rerun()

    if enviar and mensaje.strip():
        texto = mensaje.strip()
        hora = datetime.now().strftime("%H:%M")
        conv.append({"rol": "user", "texto": texto, "hora": hora, "fuentes": []})

        respuesta = ""
        fuentes = []

        # 1. IA
        respuesta_ia = preguntar_a_ia(texto, _datos_paciente(paciente_sel))
        if respuesta_ia:
            respuesta = respuesta_ia
        else:
            # 2. Busqueda
            if texto.lower().startswith("buscar:"):
                query = texto[7:].strip()
                res = buscar_en_web(query)
                if res:
                    respuesta = f"Resultados para '{query}':\n" + "\n".join(f"- {r['titulo']}: {r['url']}" for r in res)
                    fuentes = res
                else:
                    respuesta = "Sin resultados de busqueda."
            else:
                # 3. Local
                respuesta = _respuesta_local(texto)
                if respuesta == CONOCIMIENTO["default"]:
                    res = buscar_en_web(texto)
                    if res:
                        respuesta = "Info encontrada:\n" + "\n".join(f"- {r['titulo']}: {r['url']}" for r in res)
                        fuentes = res

        conv.append({"rol": "bot", "texto": respuesta, "hora": hora, "fuentes": fuentes})
        log_event("chatbot", f"consulta:{texto[:60]}")
        st.rerun()

    # Sidebar contexto
    st.sidebar.markdown("### Contexto")
    st.sidebar.caption(_datos_paciente(paciente_sel))
