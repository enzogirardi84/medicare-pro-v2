"""Alertas de medicación - cruza indicaciones activas con alergias del paciente."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Any

import streamlit as st

from core.app_logging import log_event

# Base de conocimiento: medicamentos y sus principios activos
_ALERGENOS_COMUNES = {
    "penicilina": ["amoxicilina", "ampicilina", "bencilpenicilina", "penicilina v", "penicilina g",
                   "amoxicilina/clavulánico", "amoxicilina/clavulanico"],
    "cefalosporinas": ["cefalexina", "cefazolina", "ceftriaxona", "cefuroxima"],
    "sulfa": ["sulfametoxazol/trimetoprima", "sulfametoxazol", "trimetoprima/sulfa", "cotrimoxazol"],
    "aas": ["aspirina", "ácido acetilsalicílico", "acido acetilsalicilico", "aas"],
    "antiinflamatorios no esteroideos": ["ibuprofeno", "naproxeno", "diclofenac", "ketoprofeno",
                                          "meloxicam", "piroxicam", "celecoxib"],
    "paracetamol": ["paracetamol", "acetaminofén", "acetaminofen"],
}

_OPIOIDES = ["morfina", "codeína", "codeina", "tramadol", "fentanilo", "oxicodona", "hidrocodona"]


def _normalizar(texto: str) -> str:
    """Normaliza texto: minúsculas, sin tildes, sin espacios extra."""
    t = str(texto or "").lower().strip()
    replacements = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
                    "ñ": "n", "ü": "u"}
    for a, b in replacements.items():
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t)


def _medicamentos_en_texto(texto: str) -> List[str]:
    """Extrae nombres de medicamentos de un texto libre."""
    texto_norm = _normalizar(texto)
    encontrados = set()
    for categoria, medicamentos in _ALERGENOS_COMUNES.items():
        for med in medicamentos:
            if med in texto_norm:
                encontrados.add(med)
                encontrados.add(categoria)
    for opioide in _OPIOIDES:
        if opioide in texto_norm:
            encontrados.add(opioide)
    return list(encontrados)


def verificar_alergias_medicacion(paciente_sel: str) -> List[Dict[str, str]]:
    """Cruza las alergias del paciente con sus indicaciones activas. Retorna alertas."""
    alertas = []
    try:
        detalles = st.session_state.get("detalles_pacientes_db", {}).get(paciente_sel, {})
        alergias_raw = str(detalles.get("alergias", "") or "").strip()
        if not alergias_raw:
            return alertas

        alergias_norm = _normalizar(alergias_raw)
        alergenos = _medicamentos_en_texto(alergias_raw)

        indicaciones = st.session_state.get("indicaciones_db", [])
        for ind in indicaciones:
            if ind.get("paciente") != paciente_sel:
                continue
            texto_med = str(ind.get("med", "") or ind.get("medicacion", "") or ind.get("descripcion", "") or "")
            if not texto_med:
                continue
            meds_en_ind = _medicamentos_en_texto(texto_med)
            for med in meds_en_ind:
                if med in alergias_norm or any(a in texto_med.lower() for a in alergenos):
                    alertas.append({
                        "medicamento": texto_med[:80],
                        "alergia": alergias_raw[:80],
                        "nivel": "alta",
                        "mensaje": f"Paciente alergico a **{alergias_raw[:60]}**. "
                                   f"Indicacion activa: **{texto_med[:60]}**"
                    })
    except Exception as exc:
        log_event("alertas_med", f"error:{type(exc).__name__}:{exc}")
    return alertas


def render_alertas_medicacion(paciente_sel: str):
    """Renderiza alertas de medicación en la UI."""
    alertas = verificar_alergias_medicacion(paciente_sel)
    if not alertas:
        return
    for alerta in alertas:
        st.error(alerta["mensaje"], icon="🚨")
    st.caption(f"{len(alertas)} alerta(s) de medicacion detectada(s)")
