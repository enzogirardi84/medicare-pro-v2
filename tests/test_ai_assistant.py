"""
Tests para el asistente de IA.

EJECUTAR:
    python -m pytest tests/test_ai_assistant.py -v
"""

import pytest
from unittest.mock import Mock, patch


class TestAIEvolutionAssistant:
    """Tests para AIEvolutionAssistant"""
    
    def test_assistant_disabled_without_config(self):
        """Test que asistente está deshabilitado sin configuración"""
        from core.ai_assistant import AIEvolutionAssistant
        
        with patch("core.ai_assistant.LLM_ENABLED", False):
            assistant = AIEvolutionAssistant()
            assert assistant.enabled is False
    
    def test_generate_evolution_disabled(self):
        """Test evolución con AI deshabilitada"""
        from core.ai_assistant import AIEvolutionAssistant
        
        with patch("core.ai_assistant.LLM_ENABLED", False):
            assistant = AIEvolutionAssistant()
            result = assistant.generate_evolution_suggestion({"nombre": "Test"})
            
            assert result["enabled"] is False
            assert "error" in result
    
    def test_format_vitals(self):
        """Test formateo de signos vitales"""
        from core.ai_assistant import AIEvolutionAssistant
        
        assistant = AIEvolutionAssistant()
        
        vitals = {
            "presion_arterial": "120/80",
            "frecuencia_cardiaca": 72,
            "temperatura": 36.5,
            "saturacion_o2": 98
        }
        
        formatted = assistant._format_vitals(vitals)
        
        assert "PA:" in formatted
        assert "120/80" in formatted
        assert "FC:" in formatted
    
    def test_improve_note_disabled(self):
        """Test mejora de nota deshabilitada"""
        from core.ai_assistant import AIEvolutionAssistant
        
        with patch("core.ai_assistant.LLM_ENABLED", False):
            assistant = AIEvolutionAssistant()
            draft = "Paciente con dolor."
            result = assistant.improve_note(draft)
            
            assert result == draft  # Retorna sin cambios


class TestClinicalRiskPredictor:
    """Tests para ClinicalRiskPredictor"""
    
    def test_low_risk_assessment(self):
        """Test evaluación de bajo riesgo"""
        from core.ai_assistant import ClinicalRiskPredictor
        
        predictor = ClinicalRiskPredictor()
        
        result = predictor.assess_risk(
            age=30,
            vital_signs={
                "presion_arterial": "120/80",
                "frecuencia_cardiaca": 70,
                "temperatura": 36.5,
                "saturacion_o2": 98
            },
            symptoms=["dolor leve"],
            comorbidities=[]
        )
        
        assert result.level == "low"
        assert result.score < 30
    
    def test_high_risk_elderly(self):
        """Test riesgo alto por edad avanzada"""
        from core.ai_assistant import ClinicalRiskPredictor
        
        predictor = ClinicalRiskPredictor()
        
        result = predictor.assess_risk(
            age=80,
            vital_signs={},
            symptoms=["dolor de pecho"],
            comorbidities=["diabetes descompensada"]
        )
        
        assert result.level in ["high", "critical"]
        assert result.score > 50
    
    def test_critical_hypoxemia(self):
        """Test riesgo crítico por hipoxemia"""
        from core.ai_assistant import ClinicalRiskPredictor
        
        predictor = ClinicalRiskPredictor()
        
        result = predictor.assess_risk(
            age=50,
            vital_signs={"saturacion_o2": 85},
            symptoms=["disnea"],
            comorbidities=[]
        )
        
        assert result.level == "critical"
        assert any("urgente" in r.lower() for r in result.recommendations)
    
    def test_severe_hypertension(self):
        """Test riesgo por hipertensión severa"""
        from core.ai_assistant import ClinicalRiskPredictor
        
        predictor = ClinicalRiskPredictor()
        
        result = predictor.assess_risk(
            age=60,
            vital_signs={"presion_arterial": "190/110"},
            symptoms=["cefalea"],
            comorbidities=[]
        )
        
        assert result.score >= 25
        assert any("PA >180" in f for f in result.factors)


class TestVitalSignAnomalyDetector:
    """Tests para VitalSignAnomalyDetector"""
    
    def test_no_anomalies(self):
        """Test valores normales no generan anomalías"""
        from core.ai_assistant import VitalSignAnomalyDetector
        
        detector = VitalSignAnomalyDetector()
        
        vitals = {
            "presion_arterial": "120/80",
            "frecuencia_cardiaca": 72,
            "temperatura": 36.5,
            "saturacion_o2": 98
        }
        
        anomalies = detector.detect_anomalies(vitals)
        
        assert len(anomalies) == 0
    
    def test_hypoxemia_detection(self):
        """Test detección de hipoxemia"""
        from core.ai_assistant import VitalSignAnomalyDetector
        
        detector = VitalSignAnomalyDetector()
        
        vitals = {"saturacion_o2": 88}
        
        anomalies = detector.detect_anomalies(vitals)
        
        assert len(anomalies) == 1
        assert anomalies[0].parameter == "saturacion_o2"
        assert anomalies[0].severity == "critical"
    
    def test_fever_detection(self):
        """Test detección de fiebre"""
        from core.ai_assistant import VitalSignAnomalyDetector
        
        detector = VitalSignAnomalyDetector()
        
        vitals = {"temperatura": 38.5}
        
        anomalies = detector.detect_anomalies(vitals)
        
        assert len(anomalies) == 1
        assert anomalies[0].parameter == "temperatura"
    
    def test_bradycardia_detection(self):
        """Test detección de bradicardia"""
        from core.ai_assistant import VitalSignAnomalyDetector
        
        detector = VitalSignAnomalyDetector()
        
        vitals = {"frecuencia_cardiaca": 45}
        
        anomalies = detector.detect_anomalies(vitals)
        
        assert len(anomalies) == 1
        assert anomalies[0].parameter == "frecuencia_cardiaca"
    
    def test_change_detection_with_history(self):
        """Test detección de cambios bruscos con historial"""
        from core.ai_assistant import VitalSignAnomalyDetector
        
        detector = VitalSignAnomalyDetector()
        
        history = [
            {"temperatura": 36.5},
            {"temperatura": 36.7}
        ]
        
        current = {"temperatura": 39.5}  # Cambio brusco
        
        anomalies = detector.detect_anomalies(current, history)
        
        # Debería detectar el valor alto y el cambio brusco
        assert len(anomalies) >= 1


class TestPriorityClassifier:
    """Tests para PriorityClassifier"""
    
    def test_urgent_priority_critical_symptom(self):
        """Test prioridad urgente por síntoma crítico"""
        from core.ai_assistant import PriorityClassifier
        
        classifier = PriorityClassifier()
        
        result = classifier.classify_priority(
            symptoms=["paro cardiorrespiratorio"],
            vital_signs={},
            age=50
        )
        
        assert result.priority == "urgent"
        assert "0 minutos" in result.suggested_timeframe
    
    def test_high_priority_chest_pain(self):
        """Test prioridad alta por dolor de pecho"""
        from core.ai_assistant import PriorityClassifier
        
        classifier = PriorityClassifier()
        
        result = classifier.classify_priority(
            symptoms=["dolor de pecho intenso"],
            vital_signs={"presion_arterial": "160/100"},
            age=60
        )
        
        assert result.priority in ["high", "urgent"]
    
    def test_low_priority_routine(self):
        """Test prioridad baja para consulta rutinaria"""
        from core.ai_assistant import PriorityClassifier
        
        classifier = PriorityClassifier()
        
        result = classifier.classify_priority(
            symptoms=["control rutinario"],
            vital_signs={
                "presion_arterial": "120/80",
                "temperatura": 36.5
            },
            age=35
        )
        
        assert result.priority == "low"
    
    def test_vulnerable_age_priority(self):
        """Test prioridad por edad vulnerable"""
        from core.ai_assistant import PriorityClassifier
        
        classifier = PriorityClassifier()
        
        result = classifier.classify_priority(
            symptoms=["fiebre leve"],
            vital_signs={},
            age=85
        )
        
        assert result.priority in ["medium", "high"]
        assert any("Edad vulnerable" in r for r in result.reasons)
    
    def test_ambulance_priority(self):
        """Test prioridad por arribo en ambulancia"""
        from core.ai_assistant import PriorityClassifier
        
        classifier = PriorityClassifier()
        
        result = classifier.classify_priority(
            symptoms=["dolor leve"],
            vital_signs={},
            age=40,
            arrival_mode="ambulance"
        )
        
        assert result.priority in ["medium", "high"]


class TestHelperFunctions:
    """Tests para funciones helper"""
    
    def test_suggest_evolution_disabled(self):
        """Test helper suggest_evolution deshabilitado"""
        from core.ai_assistant import suggest_evolution
        
        with patch("core.ai_assistant.LLM_ENABLED", False):
            result = suggest_evolution({"nombre": "Test"})
            assert result == ""
    
    def test_assess_clinical_risk_helper(self):
        """Test helper assess_clinical_risk"""
        from core.ai_assistant import assess_clinical_risk
        
        result = assess_clinical_risk(
            age=70,
            vitals={"presion_arterial": "140/90"},
            symptoms=["dolor"],
            comorbidities=[]
        )
        
        assert result.score > 0
        assert result.level in ["low", "medium", "high", "critical"]
    
    def test_detect_vital_anomalies_helper(self):
        """Test helper detect_vital_anomalies"""
        from core.ai_assistant import detect_vital_anomalies
        
        vitals = {"temperatura": 39.5, "saturacion_o2": 88}
        
        anomalies = detect_vital_anomalies(vitals)
        
        assert len(anomalies) == 2
    
    def test_classify_triage_helper(self):
        """Test helper classify_triage"""
        from core.ai_assistant import classify_triage
        
        result = classify_triage(
            symptoms=["dolor de pecho"],
            vitals={},
            age=60
        )
        
        assert result.priority in ["low", "medium", "high", "urgent"]
        assert len(result.reasons) > 0
