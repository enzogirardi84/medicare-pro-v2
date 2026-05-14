"""Chatbot IA - Asistente virtual con datos del paciente, exportacion y navegacion inteligente."""
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
# IA
# ============================================================
def preguntar_a_ia(consulta: str, contexto: str = "") -> Optional[str]:
    try:
        from core.ai_assistant import LLM_ENABLED, LLM_PROVIDER, LLM_API_KEY, LLM_MODEL
        if not LLM_ENABLED:
            return None
        prompt = f"Contexto del paciente: {contexto}\n\nPregunta: {consulta}\n\nResponde de forma clara, concisa y profesional. Si no sabes algo, sugiere consultar con un medico."
        if LLM_PROVIDER == "openai":
            from openai import OpenAI
            resp = OpenAI(api_key=LLM_API_KEY, timeout=15).chat.completions.create(
                model=LLM_MODEL, messages=[{"role": "system", "content": "Eres un asistente medico profesional."}, {"role": "user", "content": prompt}],
                max_tokens=600, temperature=0.3
            )
            return resp.choices[0].message.content.strip()
        elif LLM_PROVIDER == "anthropic":
            import anthropic
            resp = anthropic.Anthropic(api_key=LLM_API_KEY).completions.create(
                model=LLM_MODEL, prompt=f"Human: {prompt}\n\nAssistant:", max_tokens_to_sample=600, temperature=0.3
            )
            return resp.completion.strip()
    except Exception as e:
        log_event("chatbot", f"error_ia:{e}")
    return None


# ============================================================
# CONOCIMIENTO LOCAL (multi-idioma)
# ============================================================
CONOCIMIENTO = {
    "horario": "Lunes a viernes de 8:00 a 18:00 hs. Sabados de 9:00 a 13:00 hs.",
    "turno": "Solicita turno en Turnos Online. Elegi profesional, fecha y confirma.",
    "consulta": "Consulta medica domiciliaria: $15,000. Incluye evaluacion y signos vitales.",
    "medicamento": "Revisa indicaciones activas en Recetas. No modifiques dosis sin consultar al medico.",
    "medicacion": "Revisa tus indicaciones activas en el modulo Recetas.",
    "emergencia": "Si es una emergencia llama al 107 (SAME) o al hospital mas cercano INMEDIATAMENTE.",
    "obra social": "Trabajamos con OSDE, Swiss Medical, Galeno, Medicus y la mayoria de las prepagas.",
    "domicilio": "Visitas domiciliarias en un radio de 15 km. Costo adicional segun distancia.",
    "estudio": "Resultados en 48-72 hs habiles. Consulta en Estudios.",
    "laboratorio": "Subi resultados completos en Laboratorio.",
    "factura": "Emitimos factura electronica AFIP/ARCA. Solicitala en Factura Electronica.",
    "vacuna": "Aplicamos calendario nacional. Consulta en Vacunacion.",
    "covid": "Protocolo: barbijo obligatorio en instalaciones. Sintomas respiratorios: avisar al ingresar.",
    "receta": "Recetas electronicas validas por 30 dias desde su emision.",
    "derivacion": "Gestiona derivaciones desde Coordinacion. Demora 48-72 hs.",
    "firma": "Documentos digitales con firma electronica en PDF.",
    # English
    "schedule": "Monday to Friday 8:00 to 18:00 hs. Saturdays 9:00 to 13:00 hs.",
    "appointment": "Request an appointment in Turnos Online module.",
    "emergency": "If it's an emergency call 107 (SAME) or go to the nearest hospital IMMEDIATELY.",
    "insurance": "We work with OSDE, Swiss Medical, Galeno, Medicus and most insurance companies.",
}


def _detectar_idioma(texto: str) -> str:
    es = sum(1 for w in ["horario", "turno", "consulta", "medicamento", "emergencia", "hola", "gracias"] if w in texto.lower())
    en = sum(1 for w in ["schedule", "appointment", "consultation", "medication", "emergency", "hello", "thanks", "please", "help"] if w in texto.lower())
    return "en" if en > es else "es"


def _respuesta_local(consulta: str) -> str:
    cl = consulta.lower()
    for clave, resp in CONOCIMIENTO.items():
        if clave != "default" and clave in cl:
            return resp
    return CONOCIMIENTO["default"] if "default" in CONOCIMIENTO else "No tengo informacion sobre eso."


# ============================================================
# DATOS DEL PACIENTE
# ============================================================
def _datos_paciente(paciente_sel) -> str:
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
    if detalles.get("telefono"):
        texto += f"\nTelefono: {detalles['telefono']}"
    return texto


def _medicaciones(paciente_sel) -> str:
    inds = [r for r in st.session_state.get("indicaciones_db", [])
            if r.get("paciente") == paciente_sel
            and str(r.get("estado_receta", "Activa")).lower() not in ("suspendida", "cancelada")]
    if not inds:
        return "Sin indicaciones activas."
    texto = "Indicaciones activas:\n"
    for i in inds[:8]:
        med = i.get("med", i.get("medicacion", "?"))
        dosis = i.get("dosis", "")
        freq = i.get("frecuencia", "")
        via = i.get("via", "")
        texto += f"- {med} {dosis} {freq} {via}\n".strip() + "\n"
    return texto


def _vitales(paciente_sel) -> str:
    vitales = [r for r in st.session_state.get("vitales_db", []) if r.get("paciente") == paciente_sel]
    if not vitales:
        return "Sin signos vitales registrados."
    ult = vitales[-1]
    texto = f"Ultimos signos vitales ({ult.get('fecha', '?')}):"
    for campo, etiqueta in [("ta", "TA"), ("fc", "FC"), ("fr", "FR"), ("temp", "Temp"), ("sat", "Sat O2"), ("hgt", "HGT")]:
        if ult.get(campo):
            texto += f"\n- {etiqueta}: {ult[campo]}"
    return texto


def _estudios(paciente_sel) -> str:
    ests = [r for r in st.session_state.get("estudios_db", []) if r.get("paciente") == paciente_sel]
    if not ests:
        return "Sin estudios registrados."
    texto = "Ultimos estudios:\n"
    for e in ests[-5:]:
        texto += f"- {e.get('tipo', e.get('estudio', '?'))} ({e.get('fecha', '?')})\n"
    return texto


def _evoluciones(paciente_sel) -> str:
    evols = [r for r in st.session_state.get("evoluciones_db", []) if r.get("paciente") == paciente_sel]
    if not evols:
        return "Sin evoluciones registradas."
    ult = evols[-1]
    fecha = ult.get("fecha", ult.get("fecha_evolucion", "?"))
    nota = str(ult.get("nota", ult.get("evolucion", "")) or "")[:300]
    return f"Ultima evolucion ({fecha}):\n{nota}"


def _turnos(paciente_sel) -> str:
    turnos = [t for t in st.session_state.get("turnos_online_db", []) if t.get("paciente") == paciente_sel and t.get("estado") == "Reservado"]
    if not turnos:
        return "Sin turnos reservados."
    texto = "Turnos reservados:\n"
    for t in turnos[:5]:
        texto += f"- {t.get('fecha','?')} {t.get('horario','?')} - {t.get('profesional','?')}\n"
    return texto


def _exportar_conversacion(conv: list) -> bytes:
    """Exporta la conversacion a TXT."""
    lines = [f"Chat Medicare Pro - {datetime.now().strftime('%d/%m/%Y %H:%M')}", "=" * 40]
    for msg in conv:
        rol = "Tu" if msg["rol"] == "user" else "Asistente"
        lines.append(f"\n[{msg.get('hora','?')}] {rol}:")
        lines.append(msg["texto"])
    return "\n".join(lines).encode("utf-8")


# ============================================================
# NAVEGACION INTELIGENTE
# ============================================================
MODULOS_MAP = {
    "receta": "Recetas", "indicacion": "Recetas", "medicamento": "Recetas", "medicacion": "Recetas",
    "turno": "Turnos Online", "agenda": "Turnos Online",
    "estudio": "Estudios", "laboratorio": "Laboratorio",
    "evolucion": "Evolucion", "clinica": "Clinica",
    "vacuna": "Vacunacion",
    "factura": "Factura Electronica", "cobro": "Caja",
    "inventario": "Inventario", "stock": "Inventario",
    "historial": "Historial",
    "balance": "Balance",
    "chat": "Chatbot IA",
}


def _navegar_a(texto: str) -> Optional[str]:
    """Si el texto pide ir a un modulo, devuelve el nombre del modulo."""
    cl = texto.lower()
    for palabra, modulo in MODULOS_MAP.items():
        if palabra in cl:
            return modulo
    return None


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
            <p class="mc-hero-text">Consulta datos del paciente, medicacion, turnos, evoluciones y mas. Exporta la conversacion.</p>
        </div>
    """, unsafe_allow_html=True)

    if "chatbot_conv" not in st.session_state:
        st.session_state["chatbot_conv"] = []
    conv = st.session_state["chatbot_conv"]

    st.markdown("""
        <style>
        .cb-us { background:linear-gradient(135deg,#2563eb,#0ea5e9); color:#fff; padding:10px 16px; border-radius:18px 18px 4px 18px; margin:8px 0; max-width:80%; margin-left:auto; }
        .cb-bot { background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.08); color:#e2e8f0; padding:10px 16px; border-radius:18px 18px 18px 4px; margin:8px 0; max-width:85%; }
        .cb-bot a { color:#60a5fa; }
        .cb-time { font-size:0.7rem; color:#64748b; }
        </style>
    """, unsafe_allow_html=True)

    # Acciones
    with st.expander("Acciones rapidas", expanded=False):
        cols = st.columns(4)
        acciones = [
            ("Datos paciente", "datos"), ("Medicacion", "med"), ("Signos vitales", "vitales"),
            ("Estudios", "ests"), ("Evoluciones", "evol"), ("Turnos", "turns"),
            ("Exportar chat", "export"), ("Limpiar chat", "clear"),
        ]
        for i, (label, acc) in enumerate(acciones):
            with cols[i % 4]:
                if st.button(label, key=f"act_{i}", width="stretch"):
                    st.session_state["chat_act"] = acc
                    st.rerun()

    act = st.session_state.pop("chat_act", None)
    if act == "clear":
        st.session_state["chatbot_conv"] = []
        st.rerun()
    elif act == "export":
        data = _exportar_conversacion(conv)
        st.download_button("Descargar conversacion (.txt)", data, f"chat_{datetime.now().strftime('%Y%m%d_%H%M')}.txt", "text/plain", key="chat_export")
    elif act:
        resp = {"datos": _datos_paciente, "med": _medicaciones, "vitales": _vitales,
                "ests": _estudios, "evol": _evoluciones, "turns": _turnos}.get(act, lambda x: "")(paciente_sel)
        if resp:
            conv.append({"rol": "bot", "texto": resp, "hora": datetime.now().strftime("%H:%M"), "fuentes": []})

    st.divider()

    # Chat
    chat = st.container(height=400, border=True)
    with chat:
        if not conv:
            st.info("Hola! Soy el asistente. Pregunta sobre el paciente o usa las acciones rapidas.")
        for msg in conv:
            css = "cb-us" if msg["rol"] == "user" else "cb-bot"
            st.markdown(f'<div class="{css}">{escape(msg["texto"])}</div>', unsafe_allow_html=True)
            if msg.get("fuentes"):
                for f in msg["fuentes"]:
                    st.markdown(f'<div class="cb-time"><a href="{escape(f["url"])}" target="_blank">{escape(f["titulo"])}</a></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="cb-time">{msg.get("hora","")}</div>', unsafe_allow_html=True)

    # Input
    with st.form("chatbot_form", clear_on_submit=True):
        mensaje = st.text_input("Tu consulta:", placeholder='Ej: "Que horarios?" o "buscar: dosis ibuprofeno" o "mostrame recetas"')
        cols = st.columns([3, 1])
        enviar = cols[0].form_submit_button("Enviar", width="stretch", type="primary")
        limpiar = cols[1].form_submit_button("Limpiar", width="stretch")

    if limpiar:
        st.session_state["chatbot_conv"] = []
        st.rerun()

    if enviar and mensaje.strip():
        texto = mensaje.strip()
        hora = datetime.now().strftime("%H:%M")
        conv.append({"rol": "user", "texto": texto, "hora": hora, "fuentes": []})

        # Detectar navegacion inteligente
        modulo_destino = _navegar_a(texto)
        if modulo_destino:
            respuesta = f"Te recomiendo ir al modulo **{modulo_destino}** para gestionar eso."
        else:
            respuesta = ""
            fuentes = []

            # 1. IA
            resp_ia = preguntar_a_ia(texto, _datos_paciente(paciente_sel))
            if resp_ia:
                respuesta = resp_ia
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
                    if respuesta and "default" not in str(type(respuesta)):
                        pass
                    else:
                        res = buscar_en_web(texto)
                        if res:
                            respuesta = "Info encontrada:\n" + "\n".join(f"- {r['titulo']}: {r['url']}" for r in res)
                            fuentes = res
                        else:
                            respuesta = "No tengo informacion sobre eso. Escribi 'buscar: tu pregunta' para buscar en internet."

        conv.append({"rol": "bot", "texto": respuesta, "hora": hora, "fuentes": fuentes})
        log_event("chatbot", f"consulta:{texto[:60]}")
        st.rerun()

    # Sidebar
    st.sidebar.markdown("### Contexto")
    st.sidebar.caption(_datos_paciente(paciente_sel))
