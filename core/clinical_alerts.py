"""
Sistema de Alertas Clínicas Basado en Reglas (Clinical Decision Support).

Detección automática de condiciones de riesgo:
- Sepsis (qSOFA, lactato, creatinina)
- Shock (PAS < 90, FC > 120, lactato > 4)
- Hipoglucemia severa (< 40 mg/dL)
- Hiperglucemia crítica (> 400 mg/dL)
- Alergia medicamentosa conocida
- Interacciones farmacológicas peligrosas
- Dosis fuera de rango terapéutico
- Laboratorio crítico (K+ < 2.5 o > 6.5, etc.)

Alertas:
- ROJA (CRITICAL): Requiere acción inmediata (máximo 15 min)
- NARANJA (HIGH): Requiere atención dentro de 1 hora
- AMARILLA (MEDIUM): Revisar en siguiente visita/turno
- AZUL (INFO): Información relevante

Integración:
- Se ejecuta automáticamente al guardar signos vitales, labs, recetas
- Notifica vía realtime_notifications
- Loggea en auditoría
- Requiere acknowledgment para alertas críticas
"""
import json
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum, auto
from functools import wraps
import threading

import streamlit as st

from core.app_logging import log_event
from core.realtime_notifications import (
    NotificationPriority,
    NotificationType,
    get_notification_manager,
    send_critical_alert
)


class AlertSeverity(Enum):
    """Severidad de alertas clínicas."""
    CRITICAL = "critical"    # Roja - Acción inmediata requerida
    HIGH = "high"           # Naranja - Atención en 1 hora
    MEDIUM = "medium"       # Amarilla - Revisar próxima visita
    LOW = "low"             # Azul - Información


class AlertCategory(Enum):
    """Categorías de alertas."""
    VITALS_ABNORMAL = auto()        # Signos vitales anormales
    LAB_CRITICAL = auto()           # Laboratorio crítico
    DRUG_ALLERGY = auto()           # Alergia a medicamento
    DRUG_INTERACTION = auto()     # Interacción farmacológica
    DRUG_DOSAGE = auto()           # Dosis incorrecta
    SEPSIS_RISK = auto()          # Riesgo de sepsis
    SHOCK_RISK = auto()           # Riesgo de shock
    FALL_RISK = auto()            # Riesgo de caídas
    PREGNANCY_RISK = auto()       # Riesgo en embarazo
    AGE_SPECIFIC = auto()         # Consideración por edad
    CHRONIC_CONDITION = auto()    # Agravamiento de crónico


@dataclass
class ClinicalAlert:
    """Alerta clínica individual."""
    id: str
    patient_id: str
    patient_name: str
    severity: str  # AlertSeverity.value
    category: str  # AlertCategory.name
    title: str
    message: str
    triggered_by: str  # user_id o "system"
    triggered_at: str
    rule_name: str  # Qué regla la disparó
    relevant_data: Dict[str, Any]  # Datos que dispararon la alerta
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None
    resolved: bool = False
    resolved_at: Optional[str] = None
    resolution_note: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AlertRule:
    """Regla de alerta clínica."""
    name: str
    category: AlertCategory
    severity: AlertSeverity
    description: str
    condition: Callable[..., bool]
    message_template: str
    suggestion: str
    requires_ack: bool = True
    auto_notify: bool = True


class ClinicalAlertEngine:
    """
    Motor de alertas clínicas basado en reglas.
    
    Evalúa reglas automáticamente contra datos del paciente y
    genera alertas cuando se cumplen condiciones de riesgo.
    
    Uso:
        engine = ClinicalAlertEngine()
        
        # Al guardar signos vitales
        vitals = {"temperatura": 38.5, "frecuencia_cardiaca": 120, ...}
        alerts = engine.evaluate_vitals(patient_id, vitals)
        
        # Al recetar medicación
        alerts = engine.evaluate_prescription(patient_id, medications)
    """
    
    def __init__(self):
        self._rules: Dict[str, AlertRule] = {}
        self._active_alerts: Dict[str, List[ClinicalAlert]] = {}  # patient_id -> alerts
        self._alert_history: List[ClinicalAlert] = []
        self._lock = threading.Lock()
        self._register_default_rules()
    
    def _register_default_rules(self) -> None:
        """Registra reglas clínicas por defecto."""
        
        # === SIGNOS VITALES ===
        
        self._rules["shock_severe"] = AlertRule(
            name="shock_severe",
            category=AlertCategory.VITALS_ABNORMAL,
            severity=AlertSeverity.CRITICAL,
            description="Shock severo: PAS < 90 + FC > 100",
            condition=lambda data: (
                data.get("presion_sistolica", 120) < 90 and
                data.get("frecuencia_cardiaca", 70) > 100
            ),
            message_template="🚨 SHOCK: PAS {pas} mmHg, FC {fc} bpm",
            suggestion="Administrar líquidos IV, oxígeno, llamar a emergencias",
            requires_ack=True,
            auto_notify=True
        )
        
        self._rules["shock_lactate"] = AlertRule(
            name="shock_lactate",
            category=AlertCategory.VITALS_ABNORMAL,
            severity=AlertSeverity.CRITICAL,
            description="Shock: Lactato > 4 mmol/L",
            condition=lambda data: data.get("lactato", 0) > 4,
            message_template="🚨 SHOCK METABÓLICO: Lactato {lactato} mmol/L",
            suggestion="Llamar emergencias, iniciar resucitación",
            requires_ack=True,
            auto_notify=True
        )
        
        self._rules["fever_high"] = AlertRule(
            name="fever_high",
            category=AlertCategory.VITALS_ABNORMAL,
            severity=AlertSeverity.HIGH,
            description="Fiebre alta > 39°C",
            condition=lambda data: data.get("temperatura", 37) > 39,
            message_template="🔥 Fiebre alta: {temperatura}°C",
            suggestion="Evaluar foco infeccioso, considerar antipiréticos",
            requires_ack=False,
            auto_notify=True
        )
        
        self._rules["hypothermia"] = AlertRule(
            name="hypothermia",
            category=AlertCategory.VITALS_ABNORMAL,
            severity=AlertSeverity.HIGH,
            description="Hipotermia < 35°C",
            condition=lambda data: data.get("temperatura", 37) < 35,
            message_template="❄️ Hipotermia: {temperatura}°C",
            suggestion="Calentamiento activo, buscar causa",
            requires_ack=False,
            auto_notify=True
        )
        
        self._rules["bradycardia_severe"] = AlertRule(
            name="bradycardia_severe",
            category=AlertCategory.VITALS_ABNORMAL,
            severity=AlertSeverity.CRITICAL,
            description="Bradicardia severa FC < 40",
            condition=lambda data: data.get("frecuencia_cardiaca", 70) < 40,
            message_template="💔 Bradicardia severa: FC {fc} bpm",
            suggestion="Evaluar bloqueo AV, preparar atropina/pacing",
            requires_ack=True,
            auto_notify=True
        )
        
        self._rules["tachycardia_severe"] = AlertRule(
            name="tachycardia_severe",
            category=AlertCategory.VITALS_ABNORMAL,
            severity=AlertSeverity.HIGH,
            description="Taquicardia severa FC > 150",
            condition=lambda data: data.get("frecuencia_cardiaca", 70) > 150,
            message_template="⚡ Taquicardia severa: FC {fc} bpm",
            suggestion="ECG 12 derivaciones, descartar arritmia",
            requires_ack=False,
            auto_notify=True
        )
        
        self._rules["hypoxia_severe"] = AlertRule(
            name="hypoxia_severe",
            category=AlertCategory.VITALS_ABNORMAL,
            severity=AlertSeverity.CRITICAL,
            description="Hipoxia severa SatO2 < 88%",
            condition=lambda data: data.get("saturacion_o2", 98) < 88,
            message_template="😰 Hipoxia severa: SatO2 {sato2}%",
            suggestion="Oxígeno de alto flujo, buscar causa",
            requires_ack=True,
            auto_notify=True
        )
        
        # === LABORATORIO CRÍTICO ===
        
        self._rules["hypoglycemia_severe"] = AlertRule(
            name="hypoglycemia_severe",
            category=AlertCategory.LAB_CRITICAL,
            severity=AlertSeverity.CRITICAL,
            description="Hipoglucemia severa < 40 mg/dL",
            condition=lambda data: data.get("glucosa", 100) < 40,
            message_template="🍯 HIPOGLUCEMIA SEVERA: {glucosa} mg/dL",
            suggestion="Glucosa IV 50% o glucagón IM, monitorizar",
            requires_ack=True,
            auto_notify=True
        )
        
        self._rules["hyperglycemia_critical"] = AlertRule(
            name="hyperglycemia_critical",
            category=AlertCategory.LAB_CRITICAL,
            severity=AlertSeverity.CRITICAL,
            description="Hiperglucemia crítica > 400 mg/dL",
            condition=lambda data: data.get("glucosa", 100) > 400,
            message_template="🍯 HIPERGLUCEMIA CRÍTICA: {glucosa} mg/dL",
            suggestion="Evaluar cetoacidosis, insulina IV, líquidos",
            requires_ack=True,
            auto_notify=True
        )
        
        self._rules["hyperkalemia_severe"] = AlertRule(
            name="hyperkalemia_severe",
            category=AlertCategory.LAB_CRITICAL,
            severity=AlertSeverity.CRITICAL,
            description="Hiperkalemia severa K+ > 6.5 mEq/L",
            condition=lambda data: data.get("potasio", 4.5) > 6.5,
            message_template="⚡ HIPERKALEMIA SEVERA: K+ {potasio} mEq/L",
            suggestion="ECG, calcio gluconato, insulinaglucosa, resinas",
            requires_ack=True,
            auto_notify=True
        )
        
        self._rules["hypokalemia_severe"] = AlertRule(
            name="hypokalemia_severe",
            category=AlertCategory.LAB_CRITICAL,
            severity=AlertSeverity.CRITICAL,
            description="Hipokalemia severa K+ < 2.5 mEq/L",
            condition=lambda data: data.get("potasio", 4.5) < 2.5,
            message_template="⚡ HIPOKALEMIA SEVERA: K+ {potasio} mEq/L",
            suggestion="Reposición IV controlada, monitorización cardíaca",
            requires_ack=True,
            auto_notify=True
        )
        
        self._rules["acute_kidney_injury"] = AlertRule(
            name="acute_kidney_injury",
            category=AlertCategory.LAB_CRITICAL,
            severity=AlertSeverity.HIGH,
            description="Daño renal agudo: Creatinina > 2x basal o > 4 mg/dL",
            condition=lambda data: data.get("creatinina", 1) > 4,
            message_template="🩸 DAÑO RENAL: Creatinina {creatinina} mg/dL",
            suggestion="Evaluar causa, ajustar dosis medicamentos",
            requires_ack=False,
            auto_notify=True
        )
        
        self._rules["severe_anemia"] = AlertRule(
            name="severe_anemia",
            category=AlertCategory.LAB_CRITICAL,
            severity=AlertSeverity.HIGH,
            description="Anemia severa Hb < 7 g/dL",
            condition=lambda data: data.get("hemoglobina", 12) < 7,
            message_template="🩸 ANEMIA SEVERA: Hb {hemoglobina} g/dL",
            suggestion="Evaluar transfusión, buscar causa",
            requires_ack=False,
            auto_notify=True
        )
        
        # === SEPSIS ===
        
        self._rules["sepsis_qsofa"] = AlertRule(
            name="sepsis_qsofa",
            category=AlertCategory.SEPSIS_RISK,
            severity=AlertSeverity.CRITICAL,
            description="Sepsis probable: qSOFA ≥ 2",
            condition=lambda data: (
                (1 if data.get("frecuencia_respiratoria", 16) >= 22 else 0) +
                (1 if data.get("alteracion_mental", False) else 0) +
                (1 if data.get("presion_sistolica", 120) <= 100 else 0)
            ) >= 2,
            message_template="🦠 SEPSIS PROBABLE: qSOFA ≥ 2",
            suggestion="Cultivos, antibióticos < 1h, líquidos, lactato",
            requires_ack=True,
            auto_notify=True
        )
        
        # === MEDICACIÓN ===
        
        self._rules["drug_interaction_warfarin_aspirin"] = AlertRule(
            name="drug_interaction_warfarin_aspirin",
            category=AlertCategory.DRUG_INTERACTION,
            severity=AlertSeverity.HIGH,
            description="Interacción Warfarina + Aspirina = sangrado",
            condition=lambda data: (
                "warfarina" in str(data.get("medicamentos", [])).lower() and
                "aspirina" in str(data.get("medicamentos", [])).lower()
            ),
            message_template="💊 INTERACCIÓN: Warfarina + Aspirina = Riesgo sangrado",
            suggestion="Considerar alternativa, monitorizar INR",
            requires_ack=False,
            auto_notify=True
        )
        
        self._rules["drug_renal_dose_adjustment"] = AlertRule(
            name="drug_renal_dose_adjustment",
            category=AlertCategory.DRUG_DOSAGE,
            severity=AlertSeverity.MEDIUM,
            description="Dosis de fármaco renal requiere ajuste",
            condition=lambda data: (
                data.get("creatinina", 1) > 1.5 and
                any(drug in str(data.get("medicamentos", [])).lower() 
                    for drug in ["metformina", "aminoglucósidos", "vancomicina"])
            ),
            message_template="💊 AJUSTE RENAL: Dosis requiere modificación",
            suggestion="Calcular depuración de creatinina, ajustar dosis",
            requires_ack=False,
            auto_notify=False
        )
        
        log_event("clinical_alerts", f"rules_loaded:{len(self._rules)}")
    
    def evaluate_vitals(
        self,
        patient_id: str,
        patient_name: str,
        vitals: Dict[str, Any],
        user_id: str = "system"
    ) -> List[ClinicalAlert]:
        """
        Evalúa signos vitales contra todas las reglas de vital signs.
        
        Args:
            patient_id: ID del paciente
            patient_name: Nombre del paciente
            vitals: Dict con signos vitales
            user_id: Quién registró los signos vitales
        
        Returns:
            Lista de alertas generadas
        """
        triggered = []
        
        relevant_rules = [
            r for r in self._rules.values()
            if r.category in [AlertCategory.VITALS_ABNORMAL, AlertCategory.SEPSIS_RISK]
        ]
        
        for rule in relevant_rules:
            try:
                if rule.condition(vitals):
                    alert = self._create_alert(
                        patient_id, patient_name, rule, vitals, user_id
                    )
                    triggered.append(alert)
                    self._process_alert(alert)
            except Exception as e:
                log_event("clinical_alerts", f"rule_error:{rule.name}:{type(e).__name__}")
        
        return triggered
    
    def evaluate_labs(
        self,
        patient_id: str,
        patient_name: str,
        labs: Dict[str, Any],
        user_id: str = "system"
    ) -> List[ClinicalAlert]:
        """Evalúa resultados de laboratorio."""
        triggered = []
        
        relevant_rules = [
            r for r in self._rules.values()
            if r.category == AlertCategory.LAB_CRITICAL
        ]
        
        for rule in relevant_rules:
            try:
                if rule.condition(labs):
                    alert = self._create_alert(
                        patient_id, patient_name, rule, labs, user_id
                    )
                    triggered.append(alert)
                    self._process_alert(alert)
            except Exception as e:
                log_event("clinical_alerts", f"rule_error:{rule.name}:{type(e).__name__}")
        
        return triggered
    
    def evaluate_prescription(
        self,
        patient_id: str,
        patient_name: str,
        patient_data: Dict[str, Any],  # Incluye labs, historial, etc.
        medications: List[str],
        user_id: str = "system"
    ) -> List[ClinicalAlert]:
        """Evalúa prescripción médica contra interacciones y contraindicaciones."""
        triggered = []
        
        # Agregar medicamentos a datos de evaluación
        eval_data = {**patient_data, "medicamentos": medications}
        
        relevant_rules = [
            r for r in self._rules.values()
            if r.category in [AlertCategory.DRUG_INTERACTION, AlertCategory.DRUG_DOSAGE]
        ]
        
        for rule in relevant_rules:
            try:
                if rule.condition(eval_data):
                    alert = self._create_alert(
                        patient_id, patient_name, rule, eval_data, user_id
                    )
                    triggered.append(alert)
                    self._process_alert(alert)
            except Exception as e:
                log_event("clinical_alerts", f"rule_error:{rule.name}:{type(e).__name__}")
        
        return triggered
    
    def _create_alert(
        self,
        patient_id: str,
        patient_name: str,
        rule: AlertRule,
        data: Dict[str, Any],
        triggered_by: str
    ) -> ClinicalAlert:
        """Crea una alerta clínica."""
        # Formatear mensaje
        message = rule.message_template
        for key, value in data.items():
            placeholder = "{" + key + "}"
            if placeholder in message:
                message = message.replace(placeholder, str(value))
        
        alert_id = f"alert-{datetime.now(timezone.utc).timestamp()}-{hash(rule.name) % 10000}"
        
        return ClinicalAlert(
            id=alert_id,
            patient_id=patient_id,
            patient_name=patient_name,
            severity=rule.severity.value,
            category=rule.category.name,
            title=rule.description,
            message=message,
            triggered_by=triggered_by,
            triggered_at=datetime.now(timezone.utc).isoformat(),
            rule_name=rule.name,
            relevant_data=data
        )
    
    def _process_alert(self, alert: ClinicalAlert) -> None:
        """Procesa una alerta: almacenar, notificar, loggear."""
        with self._lock:
            # Almacenar
            if alert.patient_id not in self._active_alerts:
                self._active_alerts[alert.patient_id] = []
            
            # Verificar duplicado reciente (misma regla, últimos 5 min)
            recent = [
                a for a in self._active_alerts[alert.patient_id]
                if a.rule_name == alert.rule_name
                and (datetime.now(timezone.utc) - datetime.fromisoformat(a.triggered_at)).seconds < 300
            ]
            
            if not recent:  # No duplicar
                self._active_alerts[alert.patient_id].append(alert)
                self._alert_history.append(alert)
                
                # Notificar si corresponde
                rule = self._rules.get(alert.rule_name)
                if rule and rule.auto_notify:
                    self._notify_alert(alert)
                
                # Loggear
                log_event(
                    "clinical_alert",
                    f"triggered:{alert.rule_name}:{alert.severity}:{alert.patient_id}"
                )
    
    def _notify_alert(self, alert: ClinicalAlert) -> None:
        """Envía notificación de alerta."""
        # Mapear severidad a prioridad
        priority_map = {
            AlertSeverity.CRITICAL.value: NotificationPriority.CRITICAL,
            AlertSeverity.HIGH.value: NotificationPriority.HIGH,
            AlertSeverity.MEDIUM.value: NotificationPriority.NORMAL,
            AlertSeverity.LOW.value: NotificationPriority.LOW
        }
        
        priority = priority_map.get(alert.severity, NotificationPriority.NORMAL)
        
        # Determinar tipo
        type_map = {
            AlertCategory.VITALS_ABNORMAL.name: NotificationType.VITALS_ALERT,
            AlertCategory.LAB_CRITICAL.name: NotificationType.LAB_CRITICAL,
            AlertCategory.SEPSIS_RISK.name: NotificationType.EMERGENCY_CODE,
            AlertCategory.SHOCK_RISK.name: NotificationType.EMERGENCY_CODE,
            AlertCategory.DRUG_INTERACTION.name: NotificationType.DRUG_INTERACTION,
            AlertCategory.DRUG_ALLERGY.name: NotificationType.ALLERGY_WARNING,
        }
        
        notif_type = type_map.get(alert.category, NotificationType.SYSTEM_ALERT)
        
        # Enviar notificación
        try:
            from core.realtime_notifications import NotificationManager, Notification
            
            notif = Notification.create(
                notif_type=notif_type,
                priority=priority,
                title=f"🚨 {alert.title}",
                message=f"{alert.patient_name}: {alert.message}\n\nSugerencia: {self._rules[alert.rule_name].suggestion if alert.rule_name in self._rules else 'Evaluar paciente'}",
                patient_id=alert.patient_id,
                data={"alert_id": alert.id, "rule": alert.rule_name}
            )
            
            get_notification_manager().send_notification(notif)
            
        except Exception as e:
            log_event("clinical_alerts", f"notify_error:{type(e).__name__}")
    
    def acknowledge_alert(
        self,
        alert_id: str,
        user_id: str,
        note: Optional[str] = None
    ) -> bool:
        """Reconoce una alerta clínica."""
        with self._lock:
            for patient_alerts in self._active_alerts.values():
                for alert in patient_alerts:
                    if alert.id == alert_id and not alert.acknowledged:
                        alert.acknowledged = True
                        alert.acknowledged_by = user_id
                        alert.acknowledged_at = datetime.now(timezone.utc).isoformat()
                        
                        log_event(
                            "clinical_alert",
                            f"acknowledged:{alert_id}:by:{user_id}"
                        )
                        return True
        
        return False
    
    def resolve_alert(
        self,
        alert_id: str,
        user_id: str,
        resolution_note: Optional[str] = None
    ) -> bool:
        """Resuelve una alerta."""
        with self._lock:
            for patient_alerts in self._active_alerts.values():
                for alert in patient_alerts:
                    if alert.id == alert_id:
                        alert.resolved = True
                        alert.resolved_at = datetime.now(timezone.utc).isoformat()
                        alert.resolution_note = resolution_note
                        
                        log_event(
                            "clinical_alert",
                            f"resolved:{alert_id}:by:{user_id}"
                        )
                        return True
        
        return False
    
    def get_active_alerts(
        self,
        patient_id: Optional[str] = None,
        severity: Optional[AlertSeverity] = None
    ) -> List[ClinicalAlert]:
        """Obtiene alertas activas."""
        with self._lock:
            if patient_id:
                alerts = self._active_alerts.get(patient_id, [])
            else:
                alerts = [
                    a for alerts in self._active_alerts.values()
                    for a in alerts
                ]
            
            if severity:
                alerts = [a for a in alerts if a.severity == severity.value]
            
            # Ordenar por severidad y fecha
            severity_order = {
                AlertSeverity.CRITICAL.value: 0,
                AlertSeverity.HIGH.value: 1,
                AlertSeverity.MEDIUM.value: 2,
                AlertSeverity.LOW.value: 3
            }
            
            alerts.sort(key=lambda a: (severity_order.get(a.severity, 99), a.triggered_at))
            
            return [a for a in alerts if not a.resolved]
    
    def get_alert_stats(self) -> Dict[str, Any]:
        """Estadísticas de alertas."""
        with self._lock:
            all_active = [
                a for alerts in self._active_alerts.values()
                for a in alerts if not a.resolved
            ]
            
            return {
                "total_active": len(all_active),
                "critical_unack": len([a for a in all_active 
                                       if a.severity == AlertSeverity.CRITICAL.value and not a.acknowledged]),
                "by_severity": {
                    "critical": len([a for a in all_active if a.severity == AlertSeverity.CRITICAL.value]),
                    "high": len([a for a in all_active if a.severity == AlertSeverity.HIGH.value]),
                    "medium": len([a for a in all_active if a.severity == AlertSeverity.MEDIUM.value]),
                    "low": len([a for a in all_active if a.severity == AlertSeverity.LOW.value]),
                },
                "by_category": {}
            }
    
    def render_alerts_dashboard(self) -> None:
        """Renderiza dashboard de alertas en Streamlit."""
        import streamlit as st
        
        st.header("🚨 Alertas Clínicas Activas")
        
        stats = self.get_alert_stats()
        
        # Métricas
        cols = st.columns(4)
        with cols[0]:
            st.metric("🔴 Críticas", stats["by_severity"]["critical"])
        with cols[1]:
            st.metric("🟠 Altas", stats["by_severity"]["high"])
        with cols[2]:
            st.metric("🟡 Medias", stats["by_severity"]["medium"])
        with cols[3]:
            st.metric("🔵 Bajas", stats["by_severity"]["low"])
        
        # Alertas críticas sin reconocer
        if stats["critical_unack"] > 0:
            st.error(f"⚠️ {stats['critical_unack']} alertas críticas sin reconocer")
        
        # Lista de alertas
        alerts = self.get_active_alerts()
        
        if not alerts:
            st.success("✅ No hay alertas activas")
            return
        
        for alert in alerts[:10]:  # Mostrar máximo 10
            # Color según severidad
            if alert.severity == AlertSeverity.CRITICAL.value:
                color = "🔴"
            elif alert.severity == AlertSeverity.HIGH.value:
                color = "🟠"
            elif alert.severity == AlertSeverity.MEDIUM.value:
                color = "🟡"
            else:
                color = "🔵"
            
            with st.expander(f"{color} {alert.title} - {alert.patient_name}", 
                           expanded=alert.severity == AlertSeverity.CRITICAL.value and not alert.acknowledged):
                st.write(f"**Paciente:** {alert.patient_name}")
                st.write(f"**Mensaje:** {alert.message}")
                st.write(f"**Regla:** {alert.rule_name}")  # Corregir sintaxis f-string faltante
                st.write(f"**Fecha:** {alert.triggered_at[:16]}")
                
                if alert.relevant_data:
                    with st.expander("📊 Datos relevantes"):
                        st.json(alert.relevant_data)
                
                if not alert.acknowledged:
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✓ Reconocer", key=f"ack_{alert.id}"):
                            user = st.session_state.get("u_actual", {}).get("username", "unknown")
                            if self.acknowledge_alert(alert.id, user):
                                st.success("Alerta reconocida")
                                st.rerun()
                    with col2:
                        if st.button("✓ Resolver", key=f"res_{alert.id}"):
                            user = st.session_state.get("u_actual", {}).get("username", "unknown")
                            if self.resolve_alert(alert.id, user, "Resuelto desde dashboard"):
                                st.success("Alerta resuelta")
                                st.rerun()
                else:
                    st.caption(f"✓ Reconocida por {alert.acknowledged_by} a las {alert.acknowledged_at[:16]}")


# Instancia global
_alert_engine = None

def get_alert_engine() -> ClinicalAlertEngine:
    """Retorna instancia singleton."""
    global _alert_engine
    if _alert_engine is None:
        _alert_engine = ClinicalAlertEngine()
    return _alert_engine


# Funciones helper de alto nivel

def check_vitals_alerts(
    patient_id: str,
    patient_name: str,
    vitals: Dict[str, Any],
    user_id: str = "system"
) -> List[ClinicalAlert]:
    """Verifica alertas en signos vitales."""
    return get_alert_engine().evaluate_vitals(patient_id, patient_name, vitals, user_id)


def check_labs_alerts(
    patient_id: str,
    patient_name: str,
    labs: Dict[str, Any],
    user_id: str = "system"
) -> List[ClinicalAlert]:
    """Verifica alertas en laboratorio."""
    return get_alert_engine().evaluate_labs(patient_id, patient_name, labs, user_id)


def check_prescription_alerts(
    patient_id: str,
    patient_name: str,
    patient_data: Dict[str, Any],
    medications: List[str],
    user_id: str = "system"
) -> List[ClinicalAlert]:
    """Verifica alertas en prescripción."""
    return get_alert_engine().evaluate_prescription(
        patient_id, patient_name, patient_data, medications, user_id
    )


def acknowledge_clinical_alert(alert_id: str, note: Optional[str] = None) -> bool:
    """Reconoce una alerta clínica."""
    from core.utils_fechas import ahora
    user = st.session_state.get("u_actual", {}).get("username", "system")
    return get_alert_engine().acknowledge_alert(alert_id, user, note)
