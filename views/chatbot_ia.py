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
from core.farmacopea import buscar_medicamento, formatear_info_medicamento


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
        st.warning("No se pudo realizar la búsqueda web.")
    return resultados


# ============================================================
# IA
# ============================================================
def preguntar_a_ia(consulta: str, contexto: str = "") -> Optional[str]:
    try:
        from core.ai_assistant import LLM_ENABLED, LLM_PROVIDER, LLM_API_KEY, LLM_MODEL
        if not LLM_ENABLED:
            return None
        system_msg = (
            "Eres un asistente medico profesional que analiza datos clinicos en tiempo real. "
            "Recibes un contexto completo del paciente (datos personales, medicacion, signos vitales, "
            "estudios, evoluciones, vacunas, alergias, balance hidrico, etc.). "
            "Responde SOLO basandote en los datos proporcionados en el contexto. "
            "Si te preguntan algo que no esta en el contexto, indica que no hay datos registrados. "
            "Responde de forma clara, concisa y profesional en el mismo idioma de la pregunta."
        )
        prompt = f"Contexto completo del sistema:\n{contexto}\n\nPregunta del usuario:\n{consulta}"
        if LLM_PROVIDER == "openai":
            from openai import OpenAI
            resp = OpenAI(api_key=LLM_API_KEY, timeout=20).chat.completions.create(
                model=LLM_MODEL, messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
                max_tokens=800, temperature=0.2
            )
            return resp.choices[0].message.content.strip()
        elif LLM_PROVIDER == "anthropic":
            import anthropic
            resp = anthropic.Anthropic(api_key=LLM_API_KEY, timeout=20).completions.create(
                model=LLM_MODEL, prompt=f"Human: {system_msg}\n\n{prompt}\n\nAssistant:", max_tokens_to_sample=800, temperature=0.2
            )
            return resp.completion.strip()
    except Exception as e:
        log_event("chatbot", f"error_ia:{e}")
        st.warning("No se pudo obtener respuesta de la IA.")
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
    "factura": "Emitimos factura electronica AFIP/ARCA. Consulte con su coordinador.",
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
def _nombre_paciente(paciente_sel: str) -> str:
    """Extrae solo el nombre del paciente (sin DNI)."""
    return paciente_sel.split(" - ", 1)[0].strip() if paciente_sel else ""


def _coincide_paciente(paciente_sel: str, valor_bd: str) -> bool:
    """Compara paciente_sel con valor de BD tolerando formatos distintos."""
    if not valor_bd:
        return False
    if paciente_sel == valor_bd:
        return True
    nom = _nombre_paciente(paciente_sel).lower()
    val = valor_bd.strip().lower()
    return nom in val or val in nom


def _edad(fnac_str: str) -> str:
    try:
        nac = datetime.strptime(fnac_str, "%d/%m/%Y")
        edad_dias = (datetime.now() - nac).days
        if edad_dias < 30:
            return f"{edad_dias} dias"
        elif edad_dias < 365:
            return f"{edad_dias // 30} meses"
        else:
            anios = edad_dias // 365
            meses = (edad_dias % 365) // 30
            return f"{anios} anios {meses} meses" if meses else f"{anios} anios"
    except Exception:
        return fnac_str


def _datos_paciente(paciente_sel) -> str:
    if not isinstance(paciente_sel, str) or not paciente_sel:
        return "Paciente no seleccionado."
    detalles = st.session_state.get("detalles_pacientes_db", {})
    if not isinstance(detalles, dict):
        return "Error: detalles_pacientes_db no es un diccionario."
    detalles = detalles.get(paciente_sel, {})
    if not isinstance(detalles, dict):
        detalles = {}
    partes = paciente_sel.split(" - ", 1)
    nombre = partes[0] if partes else paciente_sel
    dni = partes[1] if len(partes) > 1 else "S/D"
    fnac = detalles.get("fnac") or detalles.get("fecha_nacimiento") or ""
    texto = f"Paciente: {nombre} (DNI: {dni})"
    if fnac:
        texto += f"\nFecha nac: {fnac} ({_edad(fnac)})"
    for campo, etiqueta in [("alergias", "Alergias"), ("patologias", "Patologias"),
                             ("obra_social", "Obra social"), ("telefono", "Telefono"),
                             ("direccion", "Direccion"), ("contacto_emergencia", "Contacto emergencia")]:
        val = detalles.get(campo)
        if val and str(val).strip():
            texto += f"\n{etiqueta}: {val}"
    if detalles.get("email"):
        texto += f"\nEmail: {detalles['email']}"
    return texto


def _contexto_completo(paciente_sel: str, mi_empresa: str) -> str:
    """Arma un contexto completo con TODOS los datos del sistema para la IA."""
    partes = []
    partes.append("=== DATOS DEL PACIENTE ===")
    partes.append(_datos_paciente(paciente_sel))
    partes.append("\n=== INDICACIONES / MEDICACION ===")
    partes.append(_medicaciones(paciente_sel))
    partes.append("\n=== SIGNOS VITALES ===")
    partes.append(_vitales(paciente_sel))
    partes.append("\n=== ESTUDIOS ===")
    partes.append(_estudios(paciente_sel))
    partes.append("\n=== EVOLUCIONES ===")
    partes.append(_evoluciones(paciente_sel))
    partes.append("\n=== VACUNAS ===")
    partes.append(_listar_vacunas(paciente_sel))
    partes.append("\n=== ALERGIAS Y PATOLOGIAS ===")
    partes.append(_alergias(paciente_sel))
    partes.append("\n=== TURNOS ===")
    partes.append(_turnos(paciente_sel))
    partes.append("\n=== BALANCE HIDRICO ===")
    partes.append(_balance(paciente_sel))
    partes.append("\n=== CONSENTIMIENTOS ===")
    partes.append(_consentimientos(paciente_sel))
    partes.append("\n=== INVENTARIO (STOCK CRITICO) ===")
    partes.append(_stock_critico(mi_empresa))
    partes.append("\n=== FACTURACION ===")
    partes.append(_facturacion(mi_empresa))
    partes.append("\n=== PACIENTES DEL SISTEMA ===")
    partes.append(_conteo_pacientes())
    partes.append("\n=== PROXIMOS CUMPLEANIOS ===")
    partes.append(_proximos_cumple())
    return "\n".join(partes)


def _medicaciones(paciente_sel) -> str:
    inds = [r for r in st.session_state.get("indicaciones_db", [])
            if _coincide_paciente(paciente_sel, r.get("paciente", ""))
            and str(r.get("estado_receta", "Activa")).lower() not in ("suspendida", "cancelada")]
    if not inds:
        return "Sin indicaciones activas."
    texto = "Indicaciones activas:\n"
    for i in inds[:8]:
        med = i.get("med", i.get("medicacion", "?"))
        dosis = i.get("dosis", "")
        freq = i.get("frecuencia", "")
        via = i.get("via", "")
        texto += f"- {med} {dosis} {freq} {via}".strip() + "\n"
    return texto


def _vitales(paciente_sel) -> str:
    vitales = [r for r in st.session_state.get("vitales_db", []) if _coincide_paciente(paciente_sel, r.get("paciente", ""))]
    if not vitales:
        return "Sin signos vitales registrados."
    ult = vitales[-1]
    texto = f"Ultimos signos vitales ({ult.get('fecha', '?')}):"
    alias = {"TA": ["TA", "tension_arterial", "presion"], "FC": ["FC", "frecuencia_cardiaca", "pulso"],
             "FR": ["FR", "frecuencia_respiratoria"], "Sat": ["Sat", "saturacion", "sat_o2", "SpO2"],
             "Temp": ["Temp", "temperatura"], "HGT": ["HGT", "glucemia", "glucosa"]}
    for etiqueta, variantes in alias.items():
        valor = None
        for v in variantes:
            valor = ult.get(v) or ult.get(v.upper()) or ult.get(v.lower()) or ult.get(v.capitalize())
            if valor:
                break
        if valor and str(valor).strip():
            texto += f"\n- {etiqueta}: {valor}"
    if texto.count("\n") == 1:
        texto += "\n- (Sin valores numericos registrados)"
    return texto


def _estudios(paciente_sel) -> str:
    ests = [r for r in st.session_state.get("estudios_db", []) if _coincide_paciente(paciente_sel, r.get("paciente", ""))]
    if not ests:
        return "Sin estudios registrados."
    texto = "Ultimos estudios:\n"
    for e in ests[-5:]:
        texto += f"- {e.get('tipo', e.get('estudio', '?'))} ({e.get('fecha', '?')})\n"
    return texto


def _evoluciones(paciente_sel) -> str:
    evols = [r for r in st.session_state.get("evoluciones_db", []) if _coincide_paciente(paciente_sel, r.get("paciente", ""))]
    if not evols:
        return "Sin evoluciones registradas."
    ult = evols[-1]
    fecha = ult.get("fecha", ult.get("fecha_evolucion", "?"))
    nota = str(ult.get("nota", ult.get("evolucion", "")) or "")[:300]
    return f"Ultima evolucion ({fecha}):\n{nota}"


def _turnos(paciente_sel) -> str:
    turnos = [t for t in st.session_state.get("turnos_online_db", []) if _coincide_paciente(paciente_sel, t.get("paciente", "")) and t.get("estado") == "Reservado"]
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


def _listar_vacunas(paciente_sel) -> str:
    vacs = [v for v in st.session_state.get("vacunacion_db", []) if _coincide_paciente(paciente_sel, v.get("paciente", ""))]
    if not vacs:
        return "Sin vacunas registradas."
    ultimas = {}
    for v in vacs:
        vac = v["vacuna"]
        if vac not in ultimas or (v.get("fecha_aplicacion") or "") > (ultimas[vac].get("fecha_aplicacion") or ""):
            ultimas[vac] = v
    texto = "Vacunas aplicadas:\n"
    for v, reg in sorted(ultimas.items()):
        texto += f"- {v}: {reg.get('dosis','?')} ({reg.get('fecha_aplicacion','?')})\n"
    return texto


def _alergias(paciente_sel) -> str:
    detalles = st.session_state.get("detalles_pacientes_db", {}).get(paciente_sel, {})
    al = detalles.get("alergias", "").strip()
    pat = detalles.get("patologias", "").strip()
    texto = ""
    if al:
        texto += f"Alergias: {al}\n"
    if pat:
        texto += f"Patologias: {pat}\n"
    return texto or "Sin alergias ni patologias registradas."


def _stock_critico(mi_empresa) -> str:
    inventario = st.session_state.get("inventario_db", [])
    items = [i for i in inventario if i.get("empresa") == mi_empresa and int(i.get("stock", 0) or 0) <= 10]
    if not items:
        return "Stock normal. No hay items criticos."
    texto = "Stock critico (<=10 unidades):\n"
    for i in items[:10]:
        texto += f"- {i.get('item') or i.get('nombre') or i.get('insumo', '?')}: {i.get('stock', 0)} unidades\n"
    return texto


def _facturacion(mi_empresa) -> str:
    facturas = st.session_state.get("facturacion_db", [])
    fact_emp = [f for f in facturas if f.get("empresa") == mi_empresa]
    if not fact_emp:
        return "Sin movimientos de facturacion."
    total = sum(float(f.get("monto", 0) or 0) for f in fact_emp)
    cobrado = sum(float(f.get("monto", 0) or 0) for f in fact_emp if "Cobrado" in f.get("estado", ""))
    pendiente = sum(float(f.get("monto", 0) or 0) for f in fact_emp if "Pendiente" in f.get("estado", ""))
    return f"Facturacion: Total ${total:,.2f} | Cobrado ${cobrado:,.2f} | Pendiente ${pendiente:,.2f}"


def _proximos_cumple() -> str:
    from datetime import timedelta
    hoy = datetime.now().date()
    prox = hoy + timedelta(days=30)
    detalles = st.session_state.get("detalles_pacientes_db", {})
    if not isinstance(detalles, dict):
        return "Error: datos de pacientes no disponibles."
    cumples = []
    for pid, det in detalles.items():
        fnac = det.get("fnac", det.get("fecha_nacimiento", ""))
        if not fnac:
            continue
        try:
            nac = datetime.strptime(fnac, "%d/%m/%Y").date().replace(year=hoy.year)
            if hoy <= nac <= prox:
                edad = hoy.year - datetime.strptime(fnac, "%d/%m/%Y").date().year
                cumples.append(f"- {pid} ({edad} anios) el {nac.strftime('%d/%m')}")
        except Exception:
            continue
    return "Proximos cumpleanios (30 dias):\n" + "\n".join(cumples[:10]) if cumples else "Sin cumpleanios proximos."


def _conteo_pacientes() -> str:
    pacientes = [p for p in st.session_state.get("pacientes_db", []) if isinstance(p, str)]
    detalles = st.session_state.get("detalles_pacientes_db", {})
    activos = sum(1 for p in pacientes if isinstance(detalles.get(p, {}), dict) and detalles[p].get("estado", "Activo") == "Activo")
    altas = sum(1 for p in pacientes if isinstance(detalles.get(p, {}), dict) and detalles[p].get("estado") == "De Alta")
    return f"Pacientes: {len(pacientes)} totales | {activos} activos | {altas} de alta"


def _balance(paciente_sel) -> str:
    balances = [b for b in st.session_state.get("balance_db", []) if _coincide_paciente(paciente_sel, b.get("paciente", ""))]
    if not balances:
        return "Sin registro de balance."
    ingresos = sum(float(b.get("ingresos") or b.get("ingreso", 0) or 0) for b in balances[-10:])
    egresos = sum(float(b.get("egresos") or b.get("egreso", 0) or 0) for b in balances[-10:])
    return f"Balance ultimos 10: Ingresos {ingresos:.0f}ml | Egresos {egresos:.0f}ml | Balance {ingresos-egresos:.0f}ml"


def _consentimientos(paciente_sel) -> str:
    raw = st.session_state.get("consentimientos_db")
    if not isinstance(raw, list):
        return "Sin documentos firmados."
    cons = [c for c in raw if isinstance(c, dict) and _coincide_paciente(paciente_sel, c.get("paciente", "") or c.get("paciente_id", ""))]
    if not cons:
        return "Sin documentos firmados."
    texto = "Documentos firmados:\n"
    for c in cons[-5:]:
        fecha = c.get("fecha") or c.get("fecha_firma") or c.get("created_at", "?")
        obs = str(c.get("observaciones") or c.get("notas") or "")
        texto += f"- {fecha}: {obs[:60]}\n"
    return texto


# ============================================================
# NAVEGACION INTELIGENTE
# ============================================================
MODULOS_MAP = {
    "receta": "Recetas", "indicacion": "Recetas", "medicamento": "Recetas", "medicacion": "Recetas",
    "turno": "Turnos Online", "agenda": "Turnos Online",
    "estudio": "Estudios", "laboratorio": "Estudios",
    "evolucion": "Evolucion", "clinica": "Clinica",
    "vacuna": "Vacunacion",
    "cobro": "Caja",
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
            ("Estudios", "ests"), ("Ultima evolucion", "evol"), ("Turnos", "turns"),
            ("Vacunas", "vac"), ("Alergias", "alerg"), ("Recetas activas", "rec"),
            ("Stock critico", "stock"), ("Facturacion", "fact"), ("Prox. cumple", "cumple"),
            ("Pacientes activos", "pacs"), ("Balance hidrico", "bal"), ("Consentimientos", "cons"),
            ("Exportar chat", "export"), ("Limpiar chat", "clear"), ("Ayuda", "help"),
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
    elif act == "help":
        resp = "Acciones disponibles:\n- Datos del paciente, Medicacion, Signos vitales\n- Estudios, Evoluciones, Turnos, Vacunas\n- Alergias, Recetas activas, Stock critico\n- Facturacion, Balance hidrico, Consentimientos\n- Pacientes activos, Proximos cumpleanios\n- Exportar chat, Limpiar chat"
        conv.append({"rol": "bot", "texto": resp, "hora": datetime.now().strftime("%H:%M"), "fuentes": []})
    elif act:
        handlers = {
            "datos": _datos_paciente, "med": _medicaciones, "vitales": _vitales,
            "ests": _estudios, "evol": _evoluciones, "turns": _turnos,
            "vac": lambda p: _listar_vacunas(p), "alerg": lambda p: _alergias(p),
            "rec": lambda p: _medicaciones(p), "stock": lambda _: _stock_critico(mi_empresa),
            "fact": lambda _: _facturacion(mi_empresa), "cumple": lambda _: _proximos_cumple(),
            "pacs": lambda _: _conteo_pacientes(), "bal": lambda p: _balance(p),
            "cons": lambda p: _consentimientos(p),
        }
        fn = handlers.get(act)
        if fn:
            resp = fn(paciente_sel)
            if resp:
                conv.append({"rol": "bot", "texto": resp, "hora": datetime.now().strftime("%H:%M"), "fuentes": []})

    st.divider()

    # Auto-scroll al ultimo mensaje
    st.markdown("""
        <script>
        function chatScroll(){var c=parent.document.querySelector('[data-testid="stVerticalBlock"] [style*="overflow"]');if(c){c.scrollTop=c.scrollHeight;}}
        setTimeout(chatScroll,100);setTimeout(chatScroll,500);
        </script>
    """, unsafe_allow_html=True)

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
            st.markdown(f'<div class="cb-time">{escape(str(msg.get("hora","")))}</div>', unsafe_allow_html=True)

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

            # 1. IA con contexto completo del sistema + farmacopea si menciona medicamento
            ctx = _contexto_completo(paciente_sel, mi_empresa)
            info_med = buscar_medicamento(texto)
            if info_med:
                ctx += "\n\n=== INFORMACION DEL MEDICAMENTO CONSULTADO ===\n" + formatear_info_medicamento(info_med)
            resp_ia = preguntar_a_ia(texto, ctx)
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
                    if not respuesta or respuesta.startswith("No tengo informacion"):
                        # 4. Farmacopea (buscar medicamento en la consulta)
                        info_med = buscar_medicamento(texto)
                        if info_med:
                            respuesta = formatear_info_medicamento(info_med)
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
