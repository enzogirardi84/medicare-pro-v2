"""AI-powered clinical features for Medicare Pro."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

from core.ai_assistant import (
    AIEvolutionAssistant,
    ClinicalRiskPredictor,
    VitalSignAnomalyDetector,
    PriorityClassifier,
    get_evolution_assistant,
    get_risk_predictor,
    get_anomaly_detector,
    get_priority_classifier,
    is_llm_enabled,
)

_LLM_SYSTEM_PROMPTS = {
    "evolution": (
        "Eres un médico clínico redactando una evolución en formato SOAP. "
        "Genera un texto profesional, conciso y estructurado en español."
    ),
    "summary": (
        "Eres un médico preparando un resumen clínico para entrega de turno o derivación. "
        "Incluye: diagnóstico principal, medicación activa, alertas, estudios pendientes y plan."
    ),
    "prescription": (
        "Eres un médico redactando una receta. Incluye: medicamento, dosis, frecuencia, duración y advertencias. "
        "Formato profesional en español."
    ),
    "interaction": (
        "Eres un farmacólogo clínico. Analiza interacciones medicamentosas. "
        "Responde en español con: nivel de severidad, mecanismo, recomendación."
    ),
    "study": (
        "Eres un médico interpretando estudios clínicos. "
        "Explica en lenguaje claro: qué mide cada valor, si está normal o alterado, y sugerencia clínica."
    ),
    "icd": (
        "Eres un codificador médico experto en CIE-10. "
        "Sugiere códigos de diagnóstico apropiados basados en la descripción clínica. "
        "Devuelve SOLO un JSON con formato: [{\"code\": \"...\", \"description\": \"...\", \"confidence\": \"alta/media/baja\"}]"
    ),
    "differential": (
        "Eres un médico internista. Basado en síntomas, signos vitales, edad y comorbilidades, "
        "sugiere diagnósticos diferenciales ordenados por probabilidad. "
        "Devuelve SOLO un JSON con formato: [{\"diagnosis\": \"...\", \"probability\": \"alta/media/baja\", \"reasoning\": \"...\"}]"
    ),
    "population": (
        "Eres un epidemiólogo clínico. Analiza datos de población de pacientes "
        "y sugiere acciones de seguimiento, screenings y alertas de salud pública."
    ),
    "search": (
        "Eres un asistente de búsqueda clínica. Ayuda a encontrar pacientes, estudios o notas "
        "usando lenguaje natural. Responde en español."
    ),
    "report": (
        "Eres un médico generando un informe clínico narrativo. "
        "Resume la evolución del paciente en un período, destacando cambios relevantes."
    ),
}


def _call_llm(prompt: str, system_key: str = "evolution", temperature: float = 0.3) -> Optional[str]:
    if not is_llm_enabled():
        return None
    system_prompt = _LLM_SYSTEM_PROMPTS.get(system_key, _LLM_SYSTEM_PROMPTS["evolution"])
    try:
        assistant = get_evolution_assistant()
        full_prompt = f"{system_prompt}\n\n{prompt}"
        return assistant._call_llm(prompt=full_prompt, temperature=temperature)
    except Exception:
        return None


def ai_not_available_warning():
    """Muestra aviso con botón directo a Configuración de IA."""
    st.warning("⚠️ IA no disponible. Activá un proveedor en Ajustes > Integraciones.", icon="🤖")
    if st.button("⚙️ Ir a Configuración de IA", use_container_width=True, key="_ai_goto_settings"):
        st.session_state["_show_settings"] = True
        st.rerun()


def _paciente_data(paciente_sel: str) -> Dict[str, Any]:
    detalles = st.session_state.get("detalles_pacientes_db", {}).get(paciente_sel, {})
    vitales = [v for v in (st.session_state.get("vitales_db") or []) if v.get("paciente") == paciente_sel]
    evoluciones = [e for e in (st.session_state.get("evoluciones_db") or []) if e.get("paciente") == paciente_sel]
    estudios = [e for e in (st.session_state.get("estudios_db") or []) if e.get("paciente") == paciente_sel]
    recetas = [r for r in (st.session_state.get("recetas_db") or []) if r.get("paciente") == paciente_sel]
    diagnosticos = str(detalles.get("patologias", "") or "")
    alergias = str(detalles.get("alergias", "") or "")
    return {
        "paciente_sel": paciente_sel,
        "nombre": str(detalles.get("nombre", "") or ""),
        "edad": str(detalles.get("edad", "") or ""),
        "diagnosticos": diagnosticos,
        "alergias": alergias,
        "vitales": vitales[-5:] if vitales else [],
        "evoluciones": evoluciones[-5:] if evoluciones else [],
        "estudios": estudios[-5:] if estudios else [],
        "recetas": recetas[-5:] if recetas else [],
    }


def suggest_evolution_ai(paciente_sel: str) -> Optional[str]:
    """Genera un borrador de evolución SOAP usando IA."""
    data = _paciente_data(paciente_sel)
    prompt = (
        f"Paciente: {data['nombre']}, {data['edad']} años.\n"
        f"Diagnósticos: {data['diagnosticos']}\n"
        f"Alergias: {data['alergias']}\n"
    )
    if data["vitales"]:
        v = data["vitales"][-1]
        prompt += f"\nSignos vitales (último):\n"
        for k in ("TA", "FC", "FR", "Temp", "Sat", "HGT"):
            if k in v:
                prompt += f"  {k}: {v[k]}\n"
    if data["evoluciones"]:
        e = data["evoluciones"][-1]
        prompt += f"\nÚltima evolución: {e.get('texto', '')[:300]}\n"
    prompt += (
        "\nGenera una evolución en formato SOAP (Subjetivo, Objetivo, Evaluación, Plan) "
        "en español, profesional y concisa."
    )
    return _call_llm(prompt, "evolution")


def generate_patient_summary(paciente_sel: str) -> Optional[str]:
    """Resumen clínico para entrega de turno o derivación."""
    data = _paciente_data(paciente_sel)
    prompt = (
        f"Genera un resumen clínico para entrega de turno del paciente {data['nombre']} ({data['edad']} años).\n\n"
        f"Diagnósticos: {data['diagnosticos']}\n"
        f"Alergias: {data['alergias']}\n"
    )
    if data["recetas"]:
        prompt += f"\nMedicación activa:\n"
        for r in data["recetas"]:
            prompt += f"  - {r.get('medicamento', '?')}: {r.get('dosis', '?')} {r.get('frecuencia', '')}\n"
    if data["estudios"]:
        prompt += f"\nEstudios recientes:\n"
        for e in data["estudios"]:
            prompt += f"  - {e.get('tipo', '?')}: {e.get('resultado', '')[:100]}\n"
    if data["evoluciones"]:
        prompt += f"\nÚltima evolución: {data['evoluciones'][-1].get('texto', '')[:300]}\n"
    prompt += (
        "\nIncluye: motivo de consulta, diagnóstico principal, medicación activa, "
        "alertas, estudios pendientes y plan de tratamiento."
    )
    return _call_llm(prompt, "summary")


def interpret_study_ai(paciente_sel: str, study_text: str) -> Optional[str]:
    """Interpreta resultados de estudios/laboratorio."""
    data = _paciente_data(paciente_sel)
    prompt = (
        f"Paciente: {data['nombre']}, {data['edad']} años.\n"
        f"Diagnósticos: {data['diagnosticos']}\n"
        f"Resultado de estudio:\n{study_text}\n\n"
        f"Interpreta en lenguaje claro: qué mide cada parámetro, si está en rango normal, "
        f"y sugerencia clínica si aplica."
    )
    return _call_llm(prompt, "study")


def generate_prescription_ai(paciente_sel: str, medicamento: str, indicacion: str = "") -> Optional[str]:
    """Genera texto de receta profesional."""
    data = _paciente_data(paciente_sel)
    prompt = (
        f"Paciente: {data['nombre']}, {data['edad']} años.\n"
        f"Diagnósticos: {data['diagnosticos']}\n"
        f"Alergias: {data['alergias']}\n"
        f"Medicamento: {medicamento}\n"
    )
    if indicacion:
        prompt += f"Indicación: {indicacion}\n"
    prompt += (
        "\nGenera el texto de una receta médica profesional en español. "
        "Incluye: nombre del medicamento, dosis, frecuencia, duración del tratamiento, "
        "vía de administración y advertencias relevantes."
    )
    return _call_llm(prompt, "prescription")


def check_drug_interactions(paciente_sel: str, nuevo_medicamento: str = "") -> Optional[str]:
    """Analiza interacciones entre medicamentos del paciente."""
    data = _paciente_data(paciente_sel)
    if not data["recetas"]:
        return None
    medicamentos = [r.get("medicamento", "?") for r in data["recetas"] if r.get("medicamento")]
    prompt = (
        f"Paciente: {data['nombre']}, {data['edad']} años.\n"
        f"Diagnósticos: {data['diagnosticos']}\n"
        f"Medicamentos actuales: {', '.join(medicamentos)}\n"
    )
    if nuevo_medicamento:
        prompt += f"Nuevo medicamento a agregar: {nuevo_medicamento}\n"
    prompt += (
        "\nAnaliza posibles interacciones medicamentosas. Para cada interacción encontrada, "
        "indica: nivel de severidad (leve/moderado/grave), mecanismo de interacción, "
        "y recomendación clínica. Si no hay interacciones relevantes, indícalo."
    )
    return _call_llm(prompt, "interaction")


def suggest_icd_codes(descripcion: str) -> Optional[str]:
    """Sugiere códigos CIE-10 a partir de texto libre."""
    prompt = (
        f"Basado en la siguiente descripción clínica, sugiere los códigos CIE-10 más apropiados:\n\n"
        f"{descripcion}\n\n"
        f"Devuelve SOLO un array JSON válido con objetos que tengan: code, description, confidence."
    )
    return _call_llm(prompt, "icd", temperature=0.1)


def suggest_differential_ai(paciente_sel: str) -> Optional[str]:
    """Sugiere diagnósticos diferenciales usando LLM."""
    data = _paciente_data(paciente_sel)
    prompt = (
        f"Paciente: {data['nombre']}, {data['edad']} años.\n"
        f"Diagnósticos previos: {data['diagnosticos']}\n"
        f"Alergias: {data['alergias']}\n"
    )
    if data["vitales"]:
        v = data["vitales"][-1]
        prompt += f"Signos vitales: TA={v.get('TA','?')}, FC={v.get('FC','?')}, Temp={v.get('Temp','?')}\n"
    if data["evoluciones"]:
        e = data["evoluciones"][-1]
        prompt += f"Última evolución: {e.get('texto', '')[:300]}\n"
    prompt += (
        "\nBasado en la información disponible, sugiere diagnósticos diferenciales "
        "ordenados por probabilidad. Devuelve SOLO un array JSON."
    )
    return _call_llm(prompt, "differential")


def population_analysis_ai(query: str, pacientes_list: List[Dict]) -> Optional[str]:
    """Análisis de población de pacientes."""
    total = len(pacientes_list)
    sample = pacientes_list[:20]
    prompt = (
        f"Analiza una población de {total} pacientes. "
        f"El usuario pregunta: {query}\n\n"
        f"Muestra de {len(sample)} pacientes:\n"
    )
    for p in sample:
        prompt += f"  - {p.get('nombre','?')}, {p.get('edad','?')} años, {p.get('patologias','?')[:100]}\n"
    prompt += (
        "\nBasado en los datos disponibles, proporciona un análisis útil "
        "y sugerencias de acción clínica o seguimiento."
    )
    return _call_llm(prompt, "population")


def smart_search_ai(query: str, paciente_sel: str = "") -> Optional[str]:
    """Búsqueda inteligente en lenguaje natural."""
    data = _paciente_data(paciente_sel) if paciente_sel else {}
    prompt = (
        f"Búsqueda del usuario: {query}\n"
    )
    if data:
        prompt += (
            f"Contexto del paciente actual: {data.get('nombre','')} - {data.get('diagnosticos','')}\n"
        )
    prompt += (
        "\nAyuda al usuario a encontrar información clínica. "
        "Sugiere dónde buscar en el sistema o responde directamente si es información general."
    )
    return _call_llm(prompt, "search")


def generate_report_ai(paciente_sel: str, dias: int = 30) -> Optional[str]:
    """Genera informe narrativo de evolución en un período."""
    data = _paciente_data(paciente_sel)
    evoluciones = data.get("evoluciones", [])
    estudios = data.get("estudios", [])
    prompt = (
        f"Genera un informe de evolución de los últimos {dias} días para:\n"
        f"Paciente: {data['nombre']}, {data['edad']} años.\n"
        f"Diagnósticos: {data['diagnosticos']}\n\n"
    )
    if evoluciones:
        prompt += "Evoluciones del período:\n"
        for e in evoluciones:
            prompt += f"  [{e.get('fecha','?')}] {e.get('texto','')[:200]}\n"
    if estudios:
        prompt += "\nEstudios del período:\n"
        for e in estudios:
            prompt += f"  [{e.get('fecha','?')}] {e.get('tipo','?')}: {e.get('resultado','')[:100]}\n"
    prompt += (
        "\nGenera un informe narrativo profesional en español, destacando: "
        "cambios en el estado clínico, resultados de estudios relevantes, "
        "ajustes de medicación, y plan a seguir."
    )
    return _call_llm(prompt, "report")


def classify_urgency(symptoms: str, age: str, vitals: Dict) -> Dict:
    """Clasificación de urgencia usando reglas + LLM."""
    classifier = get_priority_classifier()
    rule_based = classifier.classify(
        symptoms=symptoms,
        vital_signs=vitals,
        age=age,
    )
    return {
        "priority": rule_based.priority,
        "timeframe": rule_based.suggested_timeframe,
        "reasons": rule_based.reasons,
    }


def check_vital_trends(paciente_sel: str) -> Optional[str]:
    """Analiza tendencias de signos vitales."""
    data = _paciente_data(paciente_sel)
    if len(data["vitales"]) < 2:
        return None
    prompt = "Analiza las tendencias de signos vitales:\n\n"
    for v in data["vitales"]:
        prompt += f"  [{v.get('fecha','?')[:16]}] TA={v.get('TA','?')} FC={v.get('FC','?')} "
        prompt += f"FR={v.get('FR','?')} Temp={v.get('Temp','?')} Sat={v.get('Sat','?')} HGT={v.get('HGT','?')}\n"
    prompt += (
        "\nIdentifica tendencias anormales, cambios significativos entre mediciones, "
        "y sugerencias de acción clínica."
    )
    return _call_llm(prompt, "study")
