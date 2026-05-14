"""Chatbot IA completo con busqueda web integrada.
Usa DuckDuckGo para busquedas (sin API key) y OpenAI/Anthropic si esta configurado.
"""
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
# BUSQUEDA WEB (DuckDuckGo - sin API key)
# ============================================================
def buscar_en_web(consulta: str, max_resultados: int = 3) -> List[Dict]:
    """Busca informacion en internet via DuckDuckGo."""
    resultados = []
    try:
        import requests
        from urllib.parse import quote
        
        url = f"https://html.duckduckgo.com/html/?q={quote(consulta)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            for match in re.finditer(
                r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>',
                r.text
            ):
                link = html_mod.unescape(match.group(1))
                titulo = html_mod.unescape(match.group(2)).strip()
                resultados.append({"titulo": titulo, "url": link})
                if len(resultados) >= max_resultados:
                    break
    except Exception as e:
        log_event("chatbot", f"error_busqueda:{type(e).__name__}:{e}")
    return resultados


# ============================================================
# IA (OpenAI / Anthropic) - si esta configurada
# ============================================================
def preguntar_a_ia(consulta: str, contexto: str = "") -> Optional[str]:
    """Intenta usar IA si esta configurada."""
    try:
        from core.ai_assistant import LLM_ENABLED, LLM_PROVIDER, LLM_API_KEY, LLM_MODEL
        if not LLM_ENABLED:
            return None

        prompt = f"""Eres un asistente medico profesional de Medicare Pro.
Contexto del paciente: {contexto}
Pregunta: {consulta}
Responde de manera clara, concisa y profesional. Si no sabes algo, sugere consultar con un medico."""

        if LLM_PROVIDER == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=LLM_API_KEY, timeout=15)
            resp = client.chat.completions.create(
                model=LLM_MODEL, messages=[
                    {"role": "system", "content": "Eres un asistente medico profesional."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500, temperature=0.3
            )
            return resp.choices[0].message.content.strip()
        elif LLM_PROVIDER == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=LLM_API_KEY)
            resp = client.completions.create(
                model=LLM_MODEL,
                prompt=f"Human: {prompt}\n\nAssistant:",
                max_tokens_to_sample=500, temperature=0.3
            )
            return resp.completion.strip()
    except Exception as e:
        log_event("chatbot", f"error_ia:{type(e).__name__}:{e}")
    return None


# ============================================================
# CONOCIMIENTO LOCAL (fallback cuando no hay internet/IA)
# ============================================================
CONOCIMIENTO = {
    "horario": "Lunes a viernes de 8:00 a 18:00 hs. Sabados de 9:00 a 13:00 hs.",
    "turno": "Podes solicitar turno en el modulo Turnos Online. Selecciona profesional, fecha y confirma.",
    "consulta": "Consulta medica domiciliaria: $15,000. Incluye evaluacion clinica y signos vitales.",
    "medicamento": "Revisa tus indicaciones activas en Recetas. No modifiques dosis sin consultar a tu medico.",
    "emergencia": "Si es una emergencia: llama al 107 (SAME) o al hospital mas cercano INMEDIATAMENTE.",
    "obra social": "Trabajamos con OSDE, Swiss Medical, Galeno, Medicus y la mayoria de las prepagas.",
    "domicilio": "Visitas domiciliarias en un radio de 15 km. Costo adicional segun distancia.",
    "estudio": "Resultados de estudios: 48-72 hs habiles. Consultalos en el modulo Estudios.",
    "factura": "Emitimos factura electronica AFIP/ARCA para todas las prestaciones.",
    "vacuna": "Aplicamos todas las vacunas del calendario nacional. Consulta en Vacunacion.",
    "covid": "Protocolo COVID: uso de barbijo obligatorio en instalaciones. Sintomas respiratorios: avisar al ingresar.",
    "receta": "Las recetas electronicas tienen validez legal por 30 dias desde su emision.",
    "derivacion": "Las derivaciones a especialistas se gestionan desde Coordinacion. Tiempo estimado: 48-72 hs.",
    "default": "No tengo informacion sobre eso. Puedo buscar en internet si queres. Escribi 'buscar: [tu pregunta]'.",
}

def _respuesta_local(consulta: str) -> str:
    consulta_lower = consulta.lower()
    for clave, respuesta in CONOCIMIENTO.items():
        if clave != "default" and clave in consulta_lower:
            return respuesta
    return CONOCIMIENTO["default"]


# ============================================================
# RENDER - CHAT UI COMPLETO
# ============================================================
def render_chatbot_ia(paciente_sel, mi_empresa, user, rol):
    if not paciente_sel:
        from core.view_helpers import aviso_sin_paciente
        aviso_sin_paciente()
        return

    st.markdown("""
        <div class="mc-hero">
            <h2 class="mc-hero-title">Asistente IA</h2>
            <p class="mc-hero-text">Pregunta sobre el paciente, medicacion, horarios o cualquier tema clinico. Busca en internet si no encuentra la respuesta.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Conocimiento local</span>
                <span class="mc-chip">Busqueda web</span>
                <span class="mc-chip">IA si configurada</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if "chatbot_conversacion" not in st.session_state:
        st.session_state["chatbot_conversacion"] = []

    conversacion = st.session_state["chatbot_conversacion"]

    # CSS para burbujas de chat
    st.markdown("""
        <style>
        .chat-msg-usuario {
            background: linear-gradient(135deg, #2563eb, #0ea5e9);
            color: white; padding: 10px 16px; border-radius: 18px 18px 4px 18px;
            margin: 8px 0; max-width: 80%; margin-left: auto;
        }
        .chat-msg-bot {
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.08);
            color: #e2e8f0; padding: 10px 16px;
            border-radius: 18px 18px 18px 4px;
            margin: 8px 0; max-width: 85%;
        }
        .chat-msg-bot a { color: #60a5fa; }
        .chat-hora { font-size: 0.7rem; color: #64748b; margin-top: 2px; }
        </style>
    """, unsafe_allow_html=True)

    # Obtener contexto del paciente
    detalles = st.session_state.get("detalles_pacientes_db", {}).get(paciente_sel, {})
    contexto_paciente = f"Paciente: {paciente_sel}"
    if detalles.get("alergias"):
        contexto_paciente += f" | Alergias: {detalles['alergias']}"
    if detalles.get("patologias"):
        contexto_paciente += f" | Patologias: {detalles['patologias']}"

    # Opciones rapidas
    with st.expander("Sugerencias de consulta", expanded=False):
        cols = st.columns(2)
        sugerencias = [
            "Horarios de atencion", "Como sacar turno",
            "Costo de consultas", "Emergencia medica",
            "Obras sociales aceptadas", "Visitas domiciliarias",
            "Resultados de estudios", "Facturacion electronica",
        ]
        for i, sug in enumerate(sugerencias):
            with cols[i % 2]:
                if st.button(sug, key=f"sug_{i}", width="stretch"):
                    st.session_state["chatbot_input"] = sug
                    st.rerun()

    st.divider()

    # Chat container
    chat_container = st.container(height=400, border=True)
    with chat_container:
        if not conversacion:
            st.info("Hola! Soy el asistente virtual. Escribi tu consulta abajo.")
        for msg in conversacion:
            if msg["rol"] == "usuario":
                st.markdown(
                    f'<div class="chat-msg-usuario">{escape(msg["texto"])}</div>'
                    f'<div class="chat-hora" style="text-align:right">{msg.get("hora","")}</div>',
                    unsafe_allow_html=True
                )
            else:
                bot_html = f'<div class="chat-msg-bot">{msg["texto"]}</div>'
                if msg.get("fuentes"):
                    for f in msg["fuentes"]:
                        bot_html += f'<div class="chat-hora"><a href="{escape(f["url"])}" target="_blank">{escape(f["titulo"])}</a></div>'
                bot_html += f'<div class="chat-hora">{msg.get("hora","")}</div>'
                st.markdown(bot_html, unsafe_allow_html=True)

    # Input
    input_default = st.session_state.pop("chatbot_input", "")
    with st.form("chat_ia_form", clear_on_submit=True):
        mensaje = st.text_input(
            "Tu consulta:",
            placeholder='Ej: "Que horarios tienen?" o "buscar: dosis ibuprofeno ninos"',
        )
        col1, col2 = st.columns([3, 1])
        enviar = col1.form_submit_button("Enviar", width="stretch", type="primary")
        limpiar = col2.form_submit_button("Limpiar", width="stretch")

    if limpiar:
        st.session_state["chatbot_conversacion"] = []
        st.rerun()

    if enviar and mensaje.strip():
        texto = mensaje.strip()
        ahora = datetime.now().strftime("%H:%M")

        conversacion.append({"rol": "usuario", "texto": texto, "hora": ahora})

        respuesta = ""
        fuentes = []

        # 1. Intentar con IA primero
        respuesta_ia = preguntar_a_ia(texto, contexto_paciente)
        if respuesta_ia:
            respuesta = respuesta_ia
        else:
            # 2. Busqueda web si el usuario lo pide explicitamente
            if texto.lower().startswith("buscar:"):
                query = texto[7:].strip()
                resultados = buscar_en_web(query)
                if resultados:
                    respuesta = f"Resultados de busqueda para '{query}':\n\n"
                    for r in resultados:
                        respuesta += f"- {r['titulo']}: {r['url']}\n"
                    fuentes = resultados
                else:
                    respuesta = "No se encontraron resultados en internet para esa consulta."
            else:
                # 3. Respuesta local
                respuesta = _respuesta_local(texto)
                # Si es default, intentar busqueda web automatica
                if respuesta == CONOCIMIENTO["default"]:
                    resultados = buscar_en_web(texto)
                    if resultados:
                        respuesta = f"Informacion encontrada en internet:\n\n"
                        for r in resultados:
                            respuesta += f"- {r['titulo']}: {r['url']}\n"
                        fuentes = resultados
                    else:
                        respuesta = CONOCIMIENTO["default"]

        conversacion.append({
            "rol": "asistente",
            "texto": respuesta,
            "hora": ahora,
            "fuentes": fuentes,
        })
        log_event("chatbot", f"consulta:{texto[:60]}")
        st.rerun()

    # Datos del paciente en sidebar
    st.sidebar.markdown("### Contexto del paciente")
    st.sidebar.caption(contexto_paciente)
    st.sidebar.caption(f"Empresa: {mi_empresa}")
    st.sidebar.caption(f"Profesional: {user.get('nombre', '?')}")
