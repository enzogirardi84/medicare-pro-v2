"""
Asistente de IA para Medicare Pro.

Características:
- Asistente de redacción de evoluciones
- Predicción de riesgo clínico
- Detección de anomalías en signos vitales
- Clasificación automática de prioridades
- Sugerencias de diagnóstico diferencial

NOTA: Este módulo requiere configuración de API keys para LLM providers.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
from enum import Enum, auto

from core.app_logging import log_event


# Configuración de providers de LLM
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "none")  # openai, anthropic, local, none
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")
LLM_ENABLED = LLM_PROVIDER != "none" and LLM_API_KEY != ""


class AIModelType(Enum):
    """Tipos de modelos disponibles."""
    TEXT_GENERATION = auto()
    RISK_PREDICTION = auto()
    ANOMALY_DETECTION = auto()
    CLASSIFICATION = auto()


@dataclass
class ClinicalRiskAssessment:
    """Resultado de evaluación de riesgo clínico."""
    score: float  # 0-100
    level: str  # low, medium, high, critical
    factors: List[str]
    recommendations: List[str]
    confidence: float


@dataclass
class VitalSignAnomaly:
    """Anomalía detectada en signos vitales."""
    parameter: str  # presion_arterial, frecuencia_cardiaca, etc.
    value: Union[int, float]
    expected_range: Tuple[float, float]
    severity: str  # low, medium, high, critical
    description: str
    suggestion: str


@dataclass
class PriorityClassification:
    """Clasificación de prioridad clínica."""
    priority: str  # low, medium, high, urgent
    reasons: List[str]
    suggested_timeframe: str
    confidence: float


class AIEvolutionAssistant:
    """
    Asistente de redacción de evoluciones médicas.
    
    Genera sugerencias y ayuda a estructurar notas clínicas.
    """
    
    # Templates de prompts
    EVOLUTION_PROMPT = """Eres un médico clínico experimentado. Ayuda a redactar una evolución médica profesional.

DATOS DEL PACIENTE:
- Nombre: {nombre}
- Edad: {edad} años
- Sexo: {sexo}
- Motivo de consulta anterior: {motivo_consulta}

DATOS ACTUALES:
- Signos vitales: {signos_vitales}
- Síntomas actuales: {sintomas}
- Evolución desde última consulta: {evolucion_previa}

INSTRUCCIONES:
1. Redacta una nota de evolución clínica estructurada
2. Usa lenguaje médico profesional pero claro
3. Incluye: Subjetivo, Objetivo, Análisis, Plan (SOAP)
4. No inventes datos que no se proporcionaron
5. Mantén un tono objetivo y profesional

NOTA DE EVOLUCIÓN:"""

    def __init__(self):
        self.enabled = LLM_ENABLED
        self.provider = LLM_PROVIDER
    
    def generate_evolution_suggestion(
        self,
        patient_data: Dict[str, Any],
        vital_signs: Optional[Dict[str, Any]] = None,
        symptoms: Optional[str] = None,
        previous_evolution: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Genera sugerencia de evolución médica.
        
        Returns:
            Dict con sugerencia y metadatos
        """
        if not self.enabled:
            return {
                "suggestion": "",
                "error": "AI no configurada. Configurar LLM_PROVIDER y LLM_API_KEY.",
                "enabled": False
            }
        
        try:
            prompt = self.EVOLUTION_PROMPT.format(
                nombre=patient_data.get("nombre", "Paciente"),
                edad=patient_data.get("edad", "N/A"),
                sexo=patient_data.get("sexo", "N/A"),
                motivo_consulta=patient_data.get("motivo_consulta", "No especificado"),
                signos_vitales=self._format_vitals(vital_signs),
                sintomas=symptoms or "No reporta síntomas nuevos",
                evolucion_previa=previous_evolution or "Primera consulta"
            )
            
            # Llamar a LLM
            suggestion = self._call_llm(prompt, max_tokens=500, temperature=0.7)
            
            log_event("ai", f"Generated evolution suggestion for patient: {patient_data.get('id', 'unknown')}")
            
            return {
                "suggestion": suggestion,
                "enabled": True,
                "provider": self.provider,
                "model": LLM_MODEL
            }
            
        except Exception as e:
            log_event("ai_error", f"Failed to generate evolution: {e}")
            return {
                "suggestion": "",
                "error": str(e),
                "enabled": self.enabled
            }
    
    def improve_note(self, draft_note: str, context: Optional[Dict] = None) -> str:
        """
        Mejora una nota clínica existente.
        
        Args:
            draft_note: Nota en borrador
            context: Contexto adicional
        
        Returns:
            Nota mejorada
        """
        if not self.enabled:
            return draft_note
        
        prompt = f"""Mejora la siguiente nota clínica manteniendo toda la información médica relevante.
        
NOTA ORIGINAL:
{draft_note}

INSTRUCCIONES:
1. Corrige errores gramaticales y ortográficos
2. Mejora la claridad y estructura
3. Usa terminología médica apropiada
4. Mantén todos los datos clínicos
5. No agregues información que no exista

NOTA MEJORADA:"""
        
        try:
            return self._call_llm(prompt, max_tokens=600, temperature=0.5)
        except Exception as e:
            log_event("ai_error", f"Failed to improve note: {e}")
            return draft_note
    
    def suggest_differential_diagnosis(
        self,
        symptoms: List[str],
        vital_signs: Dict[str, Any],
        history: Optional[List[str]] = None
    ) -> List[Dict[str, str]]:
        """
        Sugiere diagnósticos diferenciales basados en síntomas.
        
        DISCLAIMER: Esto es solo para ayudar al médico, nunca para diagnóstico automático.
        
        Returns:
            Lista de diagnósticos sugeridos con probabilidad estimada
        """
        suggestions = []
        symptoms_lower = [s.lower() for s in symptoms]

        def _match_any(keywords: list[str]) -> bool:
            return any(kw in s for s in symptoms_lower for kw in keywords)

        # Reglas simples de matching (solo como ejemplo)
        if _match_any(["dolor de pecho", "opresión", "taquicardia"]):
            suggestions.append({
                "condition": "Síndrome Coronario Agudo",
                "probability": "media",
                "urgency": "alta",
                "disclaimer": "REQUIERE ECG URGENTE"
            })

        if _match_any(["cefalea", "mareos", "hipertensión"]):
            suggestions.append({
                "condition": "Crisis Hipertensiva",
                "probability": "media-alta",
                "urgency": "media",
                "disclaimer": "Verificar PA"
            })

        if _match_any(["fiebre", "tos", "disnea"]):
            suggestions.append({
                "condition": "Neumonía / Infección Respiratoria",
                "probability": "media",
                "urgency": "media",
                "disclaimer": "Considerar Rx de tórax"
            })

        return suggestions
    
    def _format_vitals(self, vitals: Optional[Dict]) -> str:
        """Formatea signos vitales para el prompt."""
        if not vitals:
            return "No disponibles"
        
        parts = []
        if vitals.get("presion_arterial"):
            parts.append(f"PA: {vitals['presion_arterial']} mmHg")
        if vitals.get("frecuencia_cardiaca"):
            parts.append(f"FC: {vitals['frecuencia_cardiaca']} lpm")
        if vitals.get("temperatura"):
            parts.append(f"T: {vitals['temperatura']}°C")
        if vitals.get("saturacion_o2"):
            parts.append(f"SatO2: {vitals['saturacion_o2']}%")
        
        return ", ".join(parts) if parts else "No disponibles"
    
    def _call_llm(self, prompt: str, max_tokens: int = 500, temperature: float = 0.7) -> str:
        """Llama al API de LLM según el provider configurado."""
        if self.provider == "openai":
            return self._call_openai(prompt, max_tokens, temperature)
        elif self.provider == "anthropic":
            return self._call_anthropic(prompt, max_tokens, temperature)
        elif self.provider == "local":
            return self._call_local(prompt, max_tokens, temperature)
        else:
            raise ValueError(f"Provider no soportado: {self.provider}")
    
    def _call_openai(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Llama API de OpenAI (v1.0+)."""
        try:
            from openai import OpenAI
            # Instanciar el cliente es obligatorio en v1.0+
            client = OpenAI(api_key=LLM_API_KEY, timeout=30.0)
            
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "Eres un asistente médico profesional."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            log_event("ai_error", f"OpenAI API error: {e}")
            raise
    
    def _call_anthropic(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Llama API de Anthropic (Claude)."""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=LLM_API_KEY)
            
            response = client.completions.create(
                model=LLM_MODEL,
                prompt=f"Human: {prompt}\n\nAssistant:",
                max_tokens_to_sample=max_tokens,
                temperature=temperature
            )
            
            return response.completion.strip()
            
        except Exception as e:
            log_event("ai_error", f"Anthropic API error: {e}")
            raise
    
    def _call_local(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Llama modelo local (ej: Ollama, LM Studio)."""
        try:
            import requests
            
            local_url = os.getenv("LOCAL_LLM_URL", "http://localhost:11434")
            local_model = os.getenv("LOCAL_LLM_MODEL", "llama3.1")
            model = local_model if LLM_MODEL in ("gpt-4", "gpt-3.5-turbo", "claude-3") else LLM_MODEL
            
            response = requests.post(
                f"{local_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                },
                timeout=60
            )
            
            result = response.json()
            return result.get("response", "").strip()
            
        except Exception as e:
            log_event("ai_error", f"Local LLM error: {e}")
            raise


class ClinicalRiskPredictor:
    """
    Predice riesgo clínico basado en datos del paciente.
    
    Usa reglas médicas establecidas + ML básico.
    """
    
    def assess_risk(
        self,
        age: int,
        vital_signs: Dict[str, Any],
        symptoms: List[str],
        comorbidities: List[str],
        history: Optional[Dict] = None
    ) -> ClinicalRiskAssessment:
        """
        Evalúa riesgo clínico del paciente.
        
        Returns:
            ClinicalRiskAssessment con score y recomendaciones
        """
        score = 0
        factors = []
        recommendations = []
        
        # Factor: Edad
        if age > 75:
            score += 15
            factors.append("Edad avanzada (>75)")
            recommendations.append("Considerar evaluación geriátrica")
        elif age > 65:
            score += 10
            factors.append("Adulto mayor (>65)")
        
        # Factor: Signos vitales
        if vital_signs.get("presion_arterial"):
            pa = vital_signs["presion_arterial"]
            if isinstance(pa, str):
                try:
                    systolic = int(pa.split("/")[0])
                    if systolic > 180:
                        score += 25
                        factors.append("Hipertensión severa (PA >180)")
                        recommendations.append("Urgente: Evaluar crisis hipertensiva")
                    elif systolic > 160:
                        score += 15
                        factors.append("Hipertensión moderada-severa")
                except (ValueError, TypeError):
                    pass
        
        if vital_signs.get("frecuencia_cardiaca"):
            fc = vital_signs["frecuencia_cardiaca"]
            if fc > 120 or fc < 50:
                score += 15
                factors.append("Frecuencia cardíaca alterada")
                recommendations.append("Evaluar causa de arritmia/bradicardia")
        
        if vital_signs.get("temperatura"):
            temp = vital_signs["temperatura"]
            if temp > 38.5 or temp < 35.5:
                score += 10
                factors.append("Temperatura alterada")
                recommendations.append("Evaluar infección/hipotermia")
        
        if vital_signs.get("saturacion_o2"):
            sat = vital_signs["saturacion_o2"]
            if sat < 90:
                score += 70
                factors.append("Hipoxemia severa (Sat <90%)")
                recommendations.append("URGENTE: Administrar O2, buscar causa")
            elif sat < 94:
                score += 15
                factors.append("Hipoxemia leve (Sat <94%)")
                recommendations.append("Evaluar función respiratoria")
        
        # Factor: Síntomas críticos
        critical_symptoms = [
            "dolor de pecho", "opresión torácica", "disnea severa",
            "pérdida de conciencia", "convulsiones", "hemorragia"
        ]
        for symptom in symptoms:
            if any(crit in symptom.lower() for crit in critical_symptoms):
                score += 30
                factors.append(f"Síntoma crítico: {symptom}")
                recommendations.append("Evaluación urgente inmediata")
                break
        
        # Factor: Comorbilidades
        high_risk_conditions = [
            "diabetes descompensada", "insuficiencia cardiaca",
            "enfermedad coronaria", "erc terminal", "cirrosis"
        ]
        for condition in comorbidities:
            if any(high in condition.lower() for high in high_risk_conditions):
                score += 10
                factors.append(f"Comorbilidad de alto riesgo: {condition}")
        
        # Determinar nivel
        if score >= 70:
            level = "critical"
        elif score >= 50:
            level = "high"
        elif score >= 30:
            level = "medium"
        else:
            level = "low"
        
        # Agregar recomendaciones generales según nivel
        if level == "critical":
            recommendations.insert(0, "CONSIDERAR TRASLADO A EMERGENCIAS")
        elif level == "high":
            recommendations.insert(0, "Evaluación médica prioritaria")
        
        if not recommendations:
            recommendations.append("Seguimiento ambulatorio según protocolo")
        
        return ClinicalRiskAssessment(
            score=score,
            level=level,
            factors=factors,
            recommendations=recommendations,
            confidence=min(0.95, 0.7 + (score / 200))  # Más score = más confianza en alerta (cap 0.95)
        )


class VitalSignAnomalyDetector:
    """
    Detecta anomalías en series temporales de signos vitales.
    """
    
    # Rangos normales por edad (adultos)
    NORMAL_RANGES = {
        "presion_arterial_systolic": (90, 140),
        "presion_arterial_diastolic": (60, 90),
        "frecuencia_cardiaca": (60, 100),
        "frecuencia_respiratoria": (12, 20),
        "temperatura": (36.1, 37.2),
        "saturacion_o2": (95, 100),
    }
    
    def detect_anomalies(
        self,
        current_vitals: Dict[str, Any],
        history: Optional[List[Dict]] = None
    ) -> List[VitalSignAnomaly]:
        """
        Detecta anomalías en signos vitales actuales.
        
        Args:
            current_vitals: Signos vitales actuales
            history: Historial de signos vitales previos (opcional)
        
        Returns:
            Lista de anomalías detectadas
        """
        anomalies = []
        
        # 1. Detección de valores fuera de rango
        for param, (min_val, max_val) in self.NORMAL_RANGES.items():
            value = current_vitals.get(param)
            
            if value is None and param in ("presion_arterial_systolic", "presion_arterial_diastolic"):
                # Extraer de formato "120/80"
                pa = current_vitals.get("presion_arterial", "")
                if isinstance(pa, str) and "/" in pa:
                    try:
                        parts = pa.split("/")
                        if param == "presion_arterial_systolic":
                            value = float(parts[0])
                        else:
                            value = float(parts[1])
                    except (ValueError, IndexError):
                        continue
            
            if value is None:
                continue
            
            if value < min_val or value > max_val:
                severity = self._calculate_severity(param, value, min_val, max_val)
                
                anomalies.append(VitalSignAnomaly(
                    parameter=param,
                    value=value,
                    expected_range=(min_val, max_val),
                    severity=severity,
                    description=f"{param}: {value} (rango normal: {min_val}-{max_val})",
                    suggestion=self._get_suggestion(param, value, severity)
                ))
        
        # 2. Detección de cambios bruscos (si hay historial)
        if history and len(history) >= 2:
            previous = history[-2]  # Último registro anterior
            
            for param in ["temperatura", "frecuencia_cardiaca", "saturacion_o2"]:
                current_val = current_vitals.get(param)
                previous_val = previous.get(param)
                
                if current_val is None or previous_val is None:
                    continue
                
                # Calcular cambio porcentual
                if isinstance(current_val, (int, float)) and isinstance(previous_val, (int, float)):
                    if previous_val == 0:
                        continue
                    change_pct = abs(current_val - previous_val) / previous_val * 100
                    
                    # Alertar si cambio > 20%
                    if change_pct > 20:
                        anomalies.append(VitalSignAnomaly(
                            parameter=f"{param}_change",
                            value=change_pct,
                            expected_range=(0, 20),
                            severity="medium",
                            description=f"Cambio brusco en {param}: {change_pct:.1f}%",
                            suggestion=f"Verificar tendencia de {param}"
                        ))
        
        return anomalies
    
    def _calculate_severity(
        self,
        parameter: str,
        value: float,
        min_val: float,
        max_val: float
    ) -> str:
        """Calcula severidad de la anomalía."""
        
        # Rangos críticos específicos
        critical_ranges = {
            "saturacion_o2": (90, None),  # < 90% es critico
            "temperatura": (None, 35),    # < 35°C hipotermia severa
            "frecuencia_cardiaca": (40, 150),
        }
        
        if parameter in critical_ranges:
            crit_min, crit_max = critical_ranges[parameter]
            if crit_min is not None and value < crit_min:
                return "critical"
            if crit_max is not None and value > crit_max:
                return "critical"
        
        # Determinar por distancia al rango normal
        if value < min_val:
            distance = (min_val - value) / min_val if min_val != 0 else abs(value)
        else:
            distance = (value - max_val) / max_val if max_val != 0 else abs(value)
        
        if distance > 0.5:
            return "high"
        elif distance > 0.2:
            return "medium"
        else:
            return "low"
    
    def _get_suggestion(self, parameter: str, value: float, severity: str) -> str:
        """Genera sugerencia basada en anomalía."""
        
        suggestions = {
            "saturacion_o2": {
                "critical": "URGENTE: Administrar oxígeno inmediatamente",
                "high": "Evaluar función respiratoria, considerar O2",
                "medium": "Monitorear saturación"
            },
            "temperatura": {
                "critical": "URGENTE: Evaluar sepsis/hipotermia severa",
                "high": "Buscar foco infeccioso, control de fiebre",
                "medium": "Continuar monitoreo"
            },
            "frecuencia_cardiaca": {
                "critical": "URGENTE: ECG inmediato, evaluar arritmia",
                "high": "ECG, buscar causa de taquicardia/bradicardia",
                "medium": "Monitorear FC"
            },
            "presion_arterial_systolic": {
                "critical": "URGENTE: Evaluar crisis hipertensiva/shock",
                "high": "Control de PA, evaluar síntomas",
                "medium": "Monitorear PA"
            }
        }
        
        param_suggestions = suggestions.get(parameter, {})
        return param_suggestions.get(severity, "Evaluar clínicamente")


class PriorityClassifier:
    """
    Clasifica prioridad de atención basada en triage.
    """
    
    def classify_priority(
        self,
        symptoms: List[str],
        vital_signs: Dict[str, Any],
        age: int,
        arrival_mode: str = "walk_in"  # walk_in, ambulance, referral
    ) -> PriorityClassification:
        """
        Clasifica prioridad de atención (triage).
        
        Returns:
            PriorityClassification con nivel y timeframe sugerido
        """
        
        # Puntuación de prioridad
        score = 0
        reasons = []
        
        # Síntomas críticos (inmediato)
        critical_symptoms = [
            "paro cardiorrespiratorio", "convulsiones en curso",
            "dolor torácico severo", "dificultad respiratoria severa",
            "pérdida de conciencia", "hemorragia activa severa"
        ]
        
        for symptom in symptoms:
            if any(crit in symptom.lower() for crit in critical_symptoms):
                return PriorityClassification(
                    priority="urgent",
                    reasons=[f"Síntoma crítico: {symptom}"],
                    suggested_timeframe="Inmediato - 0 minutos",
                    confidence=0.95
                )
        
        # Síntomas urgentes (10 minutos)
        urgent_symptoms = [
            "dolor de pecho", "disnea", "confusión",
            "fiebre alta >39°C", "dolor abdominal severo",
            "trauma cerrado", "sangrado moderado"
        ]
        
        for symptom in symptoms:
            if any(urg in symptom.lower() for urg in urgent_symptoms):
                score += 40
                reasons.append(f"Síntoma urgente: {symptom}")
        
        # Factor: Modo de llegada
        if arrival_mode == "ambulance":
            score += 20
            reasons.append("Arribo en ambulancia")
        
        # Factor: Signos vitales alterados
        anomaly_detector = VitalSignAnomalyDetector()
        anomalies = anomaly_detector.detect_anomalies(vital_signs)
        
        for anomaly in anomalies:
            if anomaly.severity == "critical":
                score += 30
                reasons.append(f"SV crítico: {anomaly.parameter}")
            elif anomaly.severity == "high":
                score += 20
                reasons.append(f"SV alterado: {anomaly.parameter}")
        
        # Factor: Edad vulnerable
        if age < 2 or age > 80:
            score += 15
            reasons.append(f"Edad vulnerable: {age} años")
        
        # Determinar prioridad
        if score >= 50:
            priority = "urgent"
            timeframe = "10-15 minutos"
        elif score >= 30:
            priority = "high"
            timeframe = "30-60 minutos"
        elif score >= 15:
            priority = "medium"
            timeframe = "1-2 horas"
        else:
            priority = "low"
            timeframe = "2-4 horas"
            reasons.append("Consulta ambulatoria estándar")
        
        return PriorityClassification(
            priority=priority,
            reasons=reasons,
            suggested_timeframe=timeframe,
            confidence=min(0.95, 0.6 + score / 100)
        )


# Singleton instances
_evolution_assistant: Optional[AIEvolutionAssistant] = None
_risk_predictor: Optional[ClinicalRiskPredictor] = None
_anomaly_detector: Optional[VitalSignAnomalyDetector] = None
_priority_classifier: Optional[PriorityClassifier] = None


def get_evolution_assistant() -> AIEvolutionAssistant:
    """Obtiene instancia del asistente de evoluciones."""
    global _evolution_assistant
    if _evolution_assistant is None:
        _evolution_assistant = AIEvolutionAssistant()
    return _evolution_assistant


def get_risk_predictor() -> ClinicalRiskPredictor:
    """Obtiene instancia del predictor de riesgo."""
    global _risk_predictor
    if _risk_predictor is None:
        _risk_predictor = ClinicalRiskPredictor()
    return _risk_predictor


def get_anomaly_detector() -> VitalSignAnomalyDetector:
    """Obtiene instancia del detector de anomalías."""
    global _anomaly_detector
    if _anomaly_detector is None:
        _anomaly_detector = VitalSignAnomalyDetector()
    return _anomaly_detector


def get_priority_classifier() -> PriorityClassifier:
    """Obtiene instancia del clasificador de prioridad."""
    global _priority_classifier
    if _priority_classifier is None:
        _priority_classifier = PriorityClassifier()
    return _priority_classifier


# Quick helper functions for direct usage
def suggest_evolution(patient_data: Dict, vitals: Optional[Dict] = None) -> str:
    """Helper rápido para sugerir evolución."""
    assistant = get_evolution_assistant()
    result = assistant.generate_evolution_suggestion(patient_data, vitals)
    return result.get("suggestion", "")


def assess_clinical_risk(
    age: int,
    vitals: Dict,
    symptoms: List[str],
    comorbidities: List[str]
) -> ClinicalRiskAssessment:
    """Helper rápido para evaluar riesgo."""
    predictor = get_risk_predictor()
    return predictor.assess_risk(age, vitals, symptoms, comorbidities)


def detect_vital_anomalies(
    vitals: Dict,
    history: Optional[List[Dict]] = None
) -> List[VitalSignAnomaly]:
    """Helper rápido para detectar anomalías."""
    detector = get_anomaly_detector()
    return detector.detect_anomalies(vitals, history)


def classify_triage(
    symptoms: List[str],
    vitals: Dict,
    age: int
) -> PriorityClassification:
    """Helper rápido para clasificación de triage."""
    classifier = get_priority_classifier()
    return classifier.classify_priority(symptoms, vitals, age)
