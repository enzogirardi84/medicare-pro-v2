"""Motor de inferencia clinica offline para el borde (Edge AI).
Funciona sin conexion a internet. Analiza evoluciones, detecta
interacciones medicamentosas y pre-clasifica gravedad (Triage).

Disenado para ambulancias y zonas rurales sin conectividad.
Se ejecuta localmente en el dispositivo del medico.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE DATOS
# ═══════════════════════════════════════════════════════════════════

@dataclass
class AlertaClinica:
    """Alerta de seguridad clinica generada localmente."""
    tipo: str  # "interaccion" | "triage" | "contraindicacion" | "dosis"
    severidad: str  # "CRITICAL" | "WARNING" | "INFO"
    mensaje: str
    medicamento: str = ""
    diagnostico: str = ""


@dataclass
class ResultadoInferencia:
    """Resultado del analisis de la evolucion."""
    alertas: list[AlertaClinica] = field(default_factory=list)
    triage: str = "No determinado"  # "Leve" | "Moderado" | "Grave" | "Critico"
    score_urgencia: int = 0  # 0-100
    interacciones_detectadas: int = 0


# ═══════════════════════════════════════════════════════════════════
# 2. BASE DE CONOCIMIENTO LOCAL (Embedded Formulary + Interactions)
# ═══════════════════════════════════════════════════════════════════

class FarmacopeaLocal:
    """Base de conocimiento farmacologica local (sin conexion).

    Contiene interacciones medicamentosas conocidas, contraindicaciones
    y umbrales de dosis. Cargada al iniciar el modulo.
    """

    # Interacciones medicamentosas criticas (fuente: NHS / FDA)
    INTERACCIONES_CRITICAS: dict[tuple[str, str], str] = {
        ("warfarina", "aspirina"): "Riesgo de hemorragia severa",
        ("warfarina", "ibuprofeno"): "Riesgo de hemorragia gastrointestinal",
        ("warfarina", "amoxicilina"): "Potenciacion del efecto anticoagulante",
        ("metformina", "contraste_yodado"): "Riesgo de acidosis lactica",
        ("metformina", "alcohol"): "Riesgo de acidosis lactica",
        ("captopril", "potasio"): "Hiperpotasemia severa",
        ("enalapril", "potasio"): "Hiperpotasemia severa",
        ("sildenafil", "nitratos"): "Hipotension critica",
        ("sildenafil", "doxazosina"): "Hipotension ortostatica severa",
        ("claritromicina", "simvastatina"): "Rabdomiolisis",
        ("claritromicina", "atorvastatina"): "Riesgo de miopatia",
        ("fluconazol", "warfarina"): "Potenciacion del efecto anticoagulante",
        ("litio", "ibuprofeno"): "Toxicidad por litio",
        ("litio", "diureticos"): "Toxicidad por litio",
        ("digoxina", "amiodarona"): "Toxicidad por digoxina",
        ("digoxina", "verapamilo"): "Bloqueo AV severo",
    }

    # Palabras clave para triage por severidad
    TRIAGE_CRITICO = {
        "paro", "infarto", "hemorragia", "convulsion", "inconsciente",
        "paro respiratorio", "anafilaxia", "politraumatismo", "quemadura grave",
        "accidente cerebrovascular", "avc", "coma",
    }

    TRIAGE_GRAVE = {
        "fractura expuesta", "neumonia", "insuficiencia respiratoria",
        "sepsis", "shock", "arritmia", "isquemia", "edema pulmonar",
        "pancreatitis", "meningitis", "peritonitis",
    }

    TRIAGE_MODERADO = {
        "fiebre alta", "deshidratacion", "infeccion urinaria",
        "crisis hipertensiva", "taquicardia", "bradicardia",
        "hipoglucemia", "hiperglucemia", "ictericia",
    }

    @classmethod
    def detectar_interaccion(cls, medicamento_a: str, medicamento_b: str) -> Optional[str]:
        """Busca interaccion entre dos farmacos en la base local."""
        a, b = medicamento_a.lower().strip(), medicamento_b.lower().strip()
        # Buscar en ambas direcciones
        riesgo = cls.INTERACCIONES_CRITICAS.get((a, b)) or cls.INTERACCIONES_CRITICAS.get((b, a))
        return riesgo

    @classmethod
    def clasificar_triage(cls, texto_evolucion: str) -> tuple[str, int]:
        """Clasifica la severidad del paciente basado en el texto de la evolucion.

        Returns:
            (categoria, score 0-100 donde 100 es maxima urgencia)
        """
        texto = texto_evolucion.lower()

        for keyword in cls.TRIAGE_CRITICO:
            if keyword in texto:
                return ("Critico", 95)

        for keyword in cls.TRIAGE_GRAVE:
            if keyword in texto:
                return ("Grave", 75)

        for keyword in cls.TRIAGE_MODERADO:
            if keyword in texto:
                return ("Moderado", 50)

        return ("Leve", 20)


# ═══════════════════════════════════════════════════════════════════
# 3. PROCESADOR EDGE AI
# ═══════════════════════════════════════════════════════════════════

class EdgeAIProcessor:
    """Motor de inferencia clinica offline.

    Procesa evoluciones medicas localmente sin conexion a internet.
    Detecta interacciones medicamentosas, clasifica triage y genera
    alertas clinicas.

    Uso:
        processor = EdgeAIProcessor()
        resultado = processor.analizar_evolucion(
            diagnostico="Neumonia",
            medicacion="Amoxicilina 500mg, Warfarina 5mg",
            nota="Paciente con fiebre alta y dolor toracico"
        )
        if resultado.alertas:
            st.warning(resultado.alertas[0].mensaje)
    """

    def __init__(self):
        self._farmacopea = FarmacopeaLocal()

    def analizar_evolucion(
        self,
        diagnostico: str = "",
        medicacion: str = "",
        nota: str = "",
    ) -> ResultadoInferencia:
        """Analiza una evolucion medica y retorna alertas + triage.

        Todo el procesamiento es local, sin llamadas a APIs externas.
        """
        resultado = ResultadoInferencia()

        if not medicacion and not nota:
            return resultado

        # 1. Clasificar triage
        texto_completo = f"{diagnostico} {nota} {medicacion}"
        resultado.triage, resultado.score_urgencia = self._farmacopea.clasificar_triage(texto_completo)

        # 2. Detectar interacciones medicamentosas
        medicamentos = self._extraer_medicamentos(medicacion)
        if len(medicamentos) >= 2:
            for i in range(len(medicamentos)):
                for j in range(i + 1, len(medicamentos)):
                    riesgo = self._farmacopea.detectar_interaccion(medicamentos[i], medicamentos[j])
                    if riesgo:
                        resultado.alertas.append(AlertaClinica(
                            tipo="interaccion",
                            severidad="CRITICAL",
                            mensaje=f"INTERACCION: {medicamentos[i]} + {medicamentos[j]}: {riesgo}",
                            medicamento=f"{medicamentos[i]} + {medicamentos[j]}",
                            diagnostico=diagnostico,
                        ))
                        resultado.interacciones_detectadas += 1

        # 3. Alertas basadas en triage
        if resultado.triage == "Critico":
            resultado.alertas.append(AlertaClinica(
                tipo="triage",
                severidad="CRITICAL",
                mensaje=f"PACIENTE CRITICO: Score {resultado.score_urgencia}/100. "
                        f"Requiere atencion inmediata.",
                diagnostico=diagnostico,
            ))
        elif resultado.triage == "Grave":
            resultado.alertas.append(AlertaClinica(
                tipo="triage",
                severidad="WARNING",
                mensaje=f"PACIENTE GRAVE: Score {resultado.score_urgencia}/100. "
                        f"Requiere evaluacion prioritaria.",
                diagnostico=diagnostico,
            ))

        return resultado

    @staticmethod
    def _extraer_medicamentos(texto: str) -> list[str]:
        """Extrae nombres de medicamentos del texto de la receta.

        Busca patrones comunes de prescripcion medica.
        """
        if not texto:
            return []
        texto = texto.lower()
        medicamentos = []

        # Patron: "Nombre 500mg" o "Nombre 500 mg"
        patron = r'([a-zA-Z\s]{3,30}?)\s+\d+\s*(?:mg|g|ml|mcg|ui|ug)'
        for match in re.finditer(patron, texto):
            med = match.group(1).strip()
            if med and len(med) > 2:
                medicamentos.append(med)

        # Patron simple: marcas comerciales conocidas
        marcas_conocidas = {
            "amoxicilina", "ibuprofeno", "paracetamol", "warfarina",
            "metformina", "enalapril", "captopril", "sildenafil",
            "atorvastatina", "claritromicina", "fluconazol", "digoxina",
            "litio", "furosemida", "omeprazol", "ranitidina",
            "dexametasona", "prednisona", "insulina", "heparina",
            "morfina", "tramadol", "diazepam", "haloperidol",
        }
        for marca in marcas_conocidas:
            if marca in texto and marca not in medicamentos:
                medicamentos.append(marca)

        return medicamentos


# ═══════════════════════════════════════════════════════════════════
# 4. INTEGRACION CON STREAMLIT UI
# ═══════════════════════════════════════════════════════════════════

def render_edge_ai_alertas(resultado: ResultadoInferencia) -> None:
    """Renderiza las alertas del Edge AI en la UI de Streamlit."""
    import streamlit as st

    if not resultado.alertas:
        return

    for alerta in resultado.alertas:
        if alerta.severidad == "CRITICAL":
            st.error(alerta.mensaje)
        elif alerta.severidad == "WARNING":
            st.warning(alerta.mensaje)
        else:
            st.info(alerta.mensaje)

    if resultado.score_urgencia > 0:
        st.caption(f"Triage: {resultado.triage} | Score de urgencia: {resultado.score_urgencia}/100")
