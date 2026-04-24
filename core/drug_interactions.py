"""
Sistema de Alertas de Interacciones Medicamentosas para Medicare Pro.

Características:
- Base de datos de interacciones medicamentosas
- Alertas en tiempo real al prescribir
- Niveles de severidad (contraindicado, precaución, información)
- Alternativas seguras sugeridas
- Historial de alertas ignoradas/dismissed
- Integración con prescripción médica
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum, auto
import json

import streamlit as st

from core.app_logging import log_event
from core.audit_trail import audit_log, AuditEventType


class InteractionSeverity(Enum):
    """Niveles de severidad de interacción."""
    CONTRAINDICATED = "contraindicated"  # No debe combinarse
    MAJOR = "major"                      # Riesgo significativo
    MODERATE = "moderate"                # Monitorizar
    MINOR = "minor"                      # Generalmente seguro
    UNKNOWN = "unknown"                  # Sin datos suficientes


@dataclass
class DrugInteraction:
    """Interacción entre dos medicamentos."""
    drug_a: str
    drug_b: str
    severity: InteractionSeverity
    description: str
    mechanism: Optional[str] = None
    clinical_effects: Optional[str] = None
    management: Optional[str] = None  # Qué hacer
    alternative_drugs: List[str] = None
    references: List[str] = None
    
    def __post_init__(self):
        if self.alternative_drugs is None:
            self.alternative_drugs = []
        if self.references is None:
            self.references = []


@dataclass
class InteractionAlert:
    """Alerta generada para un paciente específico."""
    id: str
    patient_id: str
    prescription_id: str
    interaction: DrugInteraction
    triggered_at: str
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_reason: Optional[str] = None


class DrugInteractionDatabase:
    """
    Base de datos de interacciones medicamentosas.
    
    En producción, esto debería conectar con bases de datos como:
    - First Databank (FDB)
    - Cerner Multum
    - DrugBank
    - O bases locales del ministerio de salud
    """
    
    # Base de datos local simplificada (subset de interacciones comunes)
    INTERACTIONS: Dict[Tuple[str, str], DrugInteraction] = {
        # Warfarina + AINES
        ("warfarina", "ibuprofeno"): DrugInteraction(
            drug_a="warfarina",
            drug_b="ibuprofeno",
            severity=InteractionSeverity.MAJOR,
            description="El ibuprofeno aumenta el riesgo de sangrado con warfarina",
            mechanism="Inhibición de la agregación plaquetaria + efecto anticoagulante",
            clinical_effects="Mayor riesgo de sangrado gastrointestinal y hemorragias",
            management="Evitar combinación o usar AINE alternativo con menor riesgo (celecoxib). Monitorizar INR frecuentemente.",
            alternative_drugs=["acetaminofén", "celecoxib"],
            references=["FDA Drug Interactions", "Clinical Pharmacology"]
        ),
        
        # Warfarina + Aspirina
        ("warfarina", "aspirina"): DrugInteraction(
            drug_a="warfarina",
            drug_b="aspirina",
            severity=InteractionSeverity.MAJOR,
            description="Aspirina + Warfarina: alto riesgo de sangrado",
            management="Generalmente contraindicado. Si es necesario, usar dosis bajas y monitorización intensiva.",
            alternative_drugs=["clopidogrel (bajo supervisión médica)"]
        ),
        
        # IECA + Diurético ahorrador de potasio
        ("enalapril", "espironolactona"): DrugInteraction(
            drug_a="enalapril",
            drug_b="espironolactona",
            severity=InteractionSeverity.MAJOR,
            description="Riesgo de hiperkalemia severa",
            clinical_effects="Hiperkalemia potencialmente fatal",
            management="Monitorizar potasio sérico. Reducir dosis o suspender uno de los fármacos si K+ > 5.0 mEq/L.",
            alternative_drugs=["furosemida", "tiazida"]
        ),
        
        # Metformina + Yodo contrastado
        ("metformina", "contraste yodado"): DrugInteraction(
            drug_a="metformina",
            drug_b="medio de contraste yodado",
            severity=InteractionSeverity.MAJOR,
            description="Riesgo de acidosis láctica",
            management="Suspender metformina 48h antes del estudio. Reiniciar cuando función renal esté verificada."
        ),
        
        # Fluoxetina + Tramadol
        ("fluoxetina", "tramadol"): DrugInteraction(
            drug_a="fluoxetina",
            drug_b="tramadol",
            severity=InteractionSeverity.MAJOR,
            description="Riesgo de síndrome serotoninérgico",
            clinical_effects="Agitación, temblor, diaforesis, hipertermia, rigidez muscular",
            management="Evitar combinación. Si ocurre, suspender ambos fármacos y tratar sintomáticamente.",
            alternative_drugs=["amitriptilina", "nortriptilina"]
        ),
        
        # Amiodarona + Warfarina
        ("amiodarona", "warfarina"): DrugInteraction(
            drug_a="amiodarona",
            drug_b="warfarina",
            severity=InteractionSeverity.MAJOR,
            description="Amiodarona aumenta efecto de warfarina",
            mechanism="Inhibición del metabolismo de warfarina (CYP2C9)",
            management="Reducir dosis de warfarina 30-50%. Monitorizar INR semanalmente.",
            alternative_drugs=["dronedarona (con precaución)"]
        ),
        
        # Digoxina + Amiodarona
        ("digoxina", "amiodarona"): DrugInteraction(
            drug_a="digoxina",
            drug_b="amiodarona",
            severity=InteractionSeverity.MAJOR,
            description="Aumento de niveles de digoxina",
            clinical_effects="Toxicidad por digoxina (arritmias, náuseas, confusión)",
            management="Reducir dosis de digoxina 50%. Monitorizar niveles séricos."
        ),
        
        # Clopidogrel + Omeprazol
        ("clopidogrel", "omeprazol"): DrugInteraction(
            drug_a="clopidogrel",
            drug_b="omeprazol",
            severity=InteractionSeverity.MAJOR,
            description="Omeprazol reduce efecto antiplaquetario de clopidogrel",
            mechanism="Inhibición de CYP2C19 (activación de clopidogrel)",
            management="Usar inhibidor de bomba de protones alternativo (pantoprazol, esomeprazol).",
            alternative_drugs=["pantoprazol", "esomeprazol", "ranitidina"]
        ),
        
        # Estatina + Gemfibrozilo
        ("atorvastatina", "gemfibrozilo"): DrugInteraction(
            drug_a="atorvastatina",
            drug_b="gemfibrozilo",
            severity=InteractionSeverity.MAJOR,
            description="Alto riesgo de rabdomiolisis",
            clinical_effects="Dolor muscular, debilidad, elevación de CK",
            management="Evitar combinación. Si es necesario, usar dosis bajas de estatina y monitorizar CK.",
            alternative_drugs=["fenofibrato"]
        ),
        
        # Litio + Diuréticos
        ("litio", "furosemida"): DrugInteraction(
            drug_a="litio",
            drug_b="furosemida",
            severity=InteractionSeverity.MAJOR,
            description="Diuréticos reducen eliminación de litio",
            clinical_effects="Toxicidad por litio (temblor, ataxia, confusión)",
            management="Evitar diuréticos de asa y tiazidas. Si es inevitable, monitorizar niveles de litio frecuentemente.",
            alternative_drugs=["amilorida (diurético ahorrador de litio)"]
        ),
        
        # AINES + IECA/ARA II
        ("ibuprofeno", "enalapril"): DrugInteraction(
            drug_a="ibuprofeno",
            drug_b="enalapril",
            severity=InteractionSeverity.MODERATE,
            description="AINES reducen efecto antihipertensivo de IECA",
            mechanism="Inhibición de prostaglandinas vasodilatadoras",
            clinical_effects="Control tensional deficiente, posible daño renal",
            management="Limitar uso de AINES. Monitorizar presión arterial y función renal."
        ),
        
        # Corticoides + NSAIDs
        ("prednisona", "ibuprofeno"): DrugInteraction(
            drug_a="prednisona",
            drug_b="ibuprofeno",
            severity=InteractionSeverity.MODERATE,
            description="Mayor riesgo de úlcera gástrica y sangrado",
            management="Usar profilaxis con IBP si ambos son necesarios. Monitorizar síntomas GI."
        ),
        
        # Triptanos + ISRS/SNRI
        ("sumatriptan", "sertralina"): DrugInteraction(
            drug_a="sumatriptan",
            drug_b="sertralina",
            severity=InteractionSeverity.MODERATE,
            description="Riesgo de síndrome serotoninérgico",
            management="Usar con precaución. Espaciar dosis. Monitorizar síntomas."
        ),
        
        # Beta-bloqueantes no selectivos + Broncodilatadores beta-2
        ("propranolol", "salbutamol"): DrugInteraction(
            drug_a="propranolol",
            drug_b="salbutamol",
            severity=InteractionSeverity.MODERATE,
            description="Propranolol antagoniza efecto broncodilatador",
            management="Usar beta-bloqueante cardioselectivo (metoprolol, bisoprolol) o ajustar dosis de broncodilatador."
        ),
        
        # Insulina + Beta-bloqueantes
        ("insulina", "metoprolol"): DrugInteraction(
            drug_a="insulina",
            drug_b="metoprolol",
            severity=InteractionSeverity.MODERATE,
            description="Beta-bloqueantes enmascaran síntomas de hipoglucemia",
            clinical_effects="Hipoglucemia silente (sin taquicardia, sudoración)",
            management="Monitorizar glucosa más frecuentemente. Educar al paciente sobre otros síntomas de hipoglucemia."
        ),
        
        # Alopurinol + Azatioprina
        ("alopurinol", "azatioprina"): DrugInteraction(
            drug_a="alopurinol",
            drug_b="azatioprina",
            severity=InteractionSeverity.CONTRAINDICATED,
            description="Alopurinol aumenta toxicidad de azatioprina (x4-5)",
            clinical_effects="Mielosupresión severa, posible letal",
            management="⚠️ CONTRAINDICADO. Suspender alopurinol o reducir dosis de azatioprina 75-90% con monitorización intensiva.",
            alternative_drugs=["colchicina (para gota)", "febuxostat (si es necesario)"]
        ),
    }
    
    @classmethod
    def get_interaction(cls, drug_a: str, drug_b: str) -> Optional[DrugInteraction]:
        """Busca interacción entre dos fármacos (en ambas direcciones)."""
        # Normalizar nombres
        drug_a_norm = drug_a.lower().strip()
        drug_b_norm = drug_b.lower().strip()
        
        # Buscar en ambas direcciones
        interaction = cls.INTERACTIONS.get((drug_a_norm, drug_b_norm))
        if not interaction:
            interaction = cls.INTERACTIONS.get((drug_b_norm, drug_a_norm))
        
        return interaction
    
    @classmethod
    def check_interactions(cls, drugs: List[str]) -> List[DrugInteraction]:
        """Verifica interacciones en una lista de fármacos."""
        interactions = []
        drugs_lower = [d.lower().strip() for d in drugs]
        
        for i, drug_a in enumerate(drugs_lower):
            for drug_b in drugs_lower[i+1:]:
                interaction = cls.get_interaction(drug_a, drug_b)
                if interaction:
                    interactions.append(interaction)
        
        # Ordenar por severidad
        severity_order = {
            InteractionSeverity.CONTRAINDICATED: 0,
            InteractionSeverity.MAJOR: 1,
            InteractionSeverity.MODERATE: 2,
            InteractionSeverity.MINOR: 3,
            InteractionSeverity.UNKNOWN: 4
        }
        
        interactions.sort(key=lambda x: severity_order.get(x.severity, 5))
        
        return interactions


class DrugInteractionMonitor:
    """
    Monitor de interacciones medicamentosas.
    
    Se integra con el sistema de prescripción para alertar en tiempo real.
    """
    
    def __init__(self):
        self._alerts: Dict[str, InteractionAlert] = {}
        self._dismissed_combinations: Set[Tuple[str, str, str]] = set()  # (patient_id, drug_a, drug_b)
        self._load_data()
    
    def _load_data(self):
        """Carga datos persistidos."""
        if "interaction_alerts" in st.session_state:
            try:
                data = st.session_state["interaction_alerts"]
                if isinstance(data, dict):
                    self._alerts = data
            except:
                pass
        
        if "dismissed_interactions" in st.session_state:
            try:
                dismissed = st.session_state["dismissed_interactions"]
                self._dismissed_combinations = set(tuple(x) for x in dismissed)
            except:
                pass
    
    def _save_data(self):
        """Guarda datos."""
        st.session_state["interaction_alerts"] = self._alerts
        st.session_state["dismissed_interactions"] = [list(x) for x in self._dismissed_combinations]
    
    def check_prescription(
        self,
        patient_id: str,
        patient_name: str,
        new_drugs: List[str],
        current_drugs: List[str] = None,
        prescription_id: str = ""
    ) -> Tuple[List[DrugInteraction], List[DrugInteraction]]:
        """
        Verifica interacciones al prescribir.
        
        Returns:
            (critical_interactions, warnings)
            critical_interactions: severidad CONTRAINDICATED o MAJOR
            warnings: severidad MODERATE o MINOR
        """
        if current_drugs is None:
            current_drugs = []
        
        # Combinar todos los fármacos
        all_drugs = list(set([d.lower().strip() for d in new_drugs + current_drugs]))
        
        # Verificar interacciones
        all_interactions = DrugInteractionDatabase.check_interactions(all_drugs)
        
        # Filtrar según severidad
        critical = [i for i in all_interactions 
                   if i.severity in [InteractionSeverity.CONTRAINDICATED, InteractionSeverity.MAJOR]]
        warnings = [i for i in all_interactions 
                   if i.severity in [InteractionSeverity.MODERATE, InteractionSeverity.MINOR]]
        
        # Registrar alertas
        for interaction in all_interactions:
            # Verificar si fue descartada previamente
            combo_key = (patient_id, interaction.drug_a, interaction.drug_b)
            combo_key_rev = (patient_id, interaction.drug_b, interaction.drug_a)
            
            if combo_key not in self._dismissed_combinations and combo_key_rev not in self._dismissed_combinations:
                alert_id = f"{patient_id}_{prescription_id}_{interaction.drug_a}_{interaction.drug_b}"
                
                if alert_id not in self._alerts:
                    self._alerts[alert_id] = InteractionAlert(
                        id=alert_id,
                        patient_id=patient_id,
                        prescription_id=prescription_id,
                        interaction=interaction,
                        triggered_at=datetime.now().isoformat()
                    )
        
        self._save_data()
        
        # Log
        if critical or warnings:
            log_event("drug_interaction", f"Interactions detected for {patient_name}: {len(critical)} critical, {len(warnings)} warnings")
        
        return critical, warnings
    
    def dismiss_alert(self, alert_id: str, dismissed_by: str, reason: str):
        """Marca una alerta como descartada con justificación."""
        if alert_id in self._alerts:
            alert = self._alerts[alert_id]
            alert.acknowledged = True
            alert.acknowledged_by = dismissed_by
            alert.acknowledged_reason = reason
            
            # Agregar a combinaciones descartadas
            combo = (alert.patient_id, alert.interaction.drug_a, alert.interaction.drug_b)
            self._dismissed_combinations.add(combo)
            
            self._save_data()
            
            # Audit
            audit_log(
                AuditEventType.DATA_MODIFICATION,
                resource_type="drug_interaction_alert",
                resource_id=alert_id,
                action="DISMISS",
                description=f"Alert dismissed by {dismissed_by}: {reason}"
            )
    
    def render_interaction_checker(self):
        """Renderiza herramienta de verificación de interacciones."""
        st.title("⚠️ Verificador de Interacciones Medicamentosas")
        
        st.markdown("""
        <div style="background: rgba(239, 68, 68, 0.1); border-left: 4px solid #ef4444; padding: 15px; margin-bottom: 20px;">
            <p style="margin: 0; color: #fca5a5;">
                <strong>⚠️ Importante:</strong> Esta herramienta proporciona información sobre interacciones conocidas. 
                Siempre use su criterio clínico y consulte fuentes adicionales cuando sea necesario.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Verificador manual
        st.subheader("🔍 Verificar Interacción Manual")
        
        col1, col2 = st.columns(2)
        
        with col1:
            drug_a = st.text_input("Fármaco A", placeholder="Ej: warfarina").lower().strip()
        
        with col2:
            drug_b = st.text_input("Fármaco B", placeholder="Ej: ibuprofeno").lower().strip()
        
        if drug_a and drug_b:
            interaction = DrugInteractionDatabase.get_interaction(drug_a, drug_b)
            
            if interaction:
                self._render_interaction_detail(interaction)
            else:
                st.success(f"✅ No se encontraron interacciones conocidas entre **{drug_a}** y **{drug_b}**")
                st.info("💡 Nota: La ausencia de interacción en la base de datos no garantiza que sea segura.")
        
        st.divider()
        
        # Verificador de lista
        st.subheader("📋 Verificar Lista de Medicamentos")
        
        drugs_input = st.text_area(
            "Ingrese los medicamentos (uno por línea)",
            placeholder="warfarina\nenalapril\nibuprofeno"
        )
        
        if st.button("🔍 Verificar Interacciones", use_container_width=True):
            drugs = [d.strip().lower() for d in drugs_input.split("\n") if d.strip()]
            
            if len(drugs) < 2:
                st.warning("Ingrese al menos 2 medicamentos para verificar interacciones")
            else:
                interactions = DrugInteractionDatabase.check_interactions(drugs)
                
                if interactions:
                    st.error(f"⚠️ Se encontraron **{len(interactions)}** interacciones")
                    
                    for interaction in interactions:
                        self._render_interaction_detail(interaction)
                else:
                    st.success("✅ No se encontraron interacciones conocidas entre estos medicamentos")
    
    def _render_interaction_detail(self, interaction: DrugInteraction):
        """Renderiza detalle de una interacción."""
        severity_colors = {
            InteractionSeverity.CONTRAINDICATED: ("🔴", "#ef4444", "CONTRAINDICADO"),
            InteractionSeverity.MAJOR: ("🟠", "#f97316", "MAYOR"),
            InteractionSeverity.MODERATE: ("🟡", "#eab308", "MODERADA"),
            InteractionSeverity.MINOR: ("🟢", "#22c55e", "MENOR"),
            InteractionSeverity.UNKNOWN: ("⚪", "#94a3b8", "DESCONOCIDA")
        }
        
        icon, color, label = severity_colors.get(
            interaction.severity, 
            ("⚪", "#94a3b8", "DESCONOCIDA")
        )
        
        with st.container():
            st.markdown(f"""
            <div style="
                border-left: 4px solid {color};
                background: rgba(0,0,0,0.2);
                padding: 15px;
                margin: 10px 0;
                border-radius: 0 8px 8px 0;
            ">
                <h4 style="margin: 0 0 10px 0; color: {color};">{icon} {interaction.drug_a.title()} + {interaction.drug_b.title()}</h4>
                <p style="margin: 5px 0; color: #fca5a5;"><strong>⚠️ Severidad: {label}</strong></p>
                <p style="margin: 5px 0;">{interaction.description}</p>
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander("📖 Ver detalles completos"):
                if interaction.mechanism:
                    st.markdown(f"**Mecanismo:** {interaction.mechanism}")
                
                if interaction.clinical_effects:
                    st.markdown(f"**Efectos clínicos:** {interaction.clinical_effects}")
                
                if interaction.management:
                    st.markdown(f"**Manejo recomendado:** {interaction.management}")
                
                if interaction.alternative_drugs:
                    st.markdown("**Alternativas seguras:**")
                    for alt in interaction.alternative_drugs:
                        st.markdown(f"- {alt}")
                
                if interaction.references:
                    st.markdown("**Referencias:**")
                    for ref in interaction.references:
                        st.caption(f"📚 {ref}")
    
    def render_prescription_alerts(
        self,
        patient_id: str,
        new_drugs: List[str],
        current_drugs: List[str] = None,
        prescription_id: str = ""
    ) -> bool:
        """
        Renderiza alertas durante la prescripción y retorna si es seguro continuar.
        
        Returns:
            True si el médico puede continuar (aceptó o no hay alertas críticas)
            False si hay contraindicaciones que deben resolverse
        """
        critical, warnings = self.check_prescription(
            patient_id=patient_id,
            patient_name="",
            new_drugs=new_drugs,
            current_drugs=current_drugs,
            prescription_id=prescription_id
        )
        
        # Mostrar alertas críticas (bloqueantes)
        if critical:
            st.error("## ⚠️ INTERACCIONES CRÍTICAS DETECTADAS")
            st.markdown("<p style='color: #ef4444;'>Estas combinaciones pueden ser peligrosas. Revise cuidadosamente.</p>", unsafe_allow_html=True)
            
            for interaction in critical:
                self._render_interaction_detail(interaction)
            
            # Requerir confirmación para contraindicaciones
            contraindications = [i for i in critical if i.severity == InteractionSeverity.CONTRAINDICATED]
            
            if contraindications:
                st.error("🚫 **CONTRAINDICACIONES ABSOLUTAS:** Estas combinaciones NO deben usarse juntas.")
                
                with st.form(key="override_contraindication"):
                    st.markdown("Para continuar a pesar de la contraindicación, debe justificar:")
                    justification = st.text_area("Justificación clínica", 
                                                placeholder="Explique por qué es necesario usar estas drogas juntas a pesar de la contraindicación...")
                    confirm = st.checkbox("Asumo la responsabilidad de esta prescripción")
                    
                    submitted = st.form_submit_button("Continuar con justificación", type="primary")
                    
                    if submitted:
                        if not justification or not confirm:
                            st.error("Debe proporcionar justificación y confirmar")
                            return False
                        
                        user = st.session_state.get("u_actual", {})
                        self.dismiss_alert(
                            f"{patient_id}_{prescription_id}_{contraindications[0].drug_a}_{contraindications[0].drug_b}",
                            user.get("nombre", "Sistema"),
                            f"Override con justificación: {justification}"
                        )
                        return True
                
                return False
            
            # Para interacciones MAYORES (no contraindicaciones)
            st.warning("Para continuar, confirme que ha revisado estas interacciones:")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ He revisado y acepto los riesgos", use_container_width=True):
                    return True
            with col2:
                if st.button("❌ Modificar prescripción", use_container_width=True):
                    return False
            
            return None  # Esperando decisión
        
        # Mostrar advertencias (no bloqueantes)
        if warnings:
            with st.expander(f"⚠️ {len(warnings)} advertencias de interacciones moderadas/menores"):
                for interaction in warnings:
                    self._render_interaction_detail(interaction)
        
        return True


# Singleton
_interaction_monitor: Optional[DrugInteractionMonitor] = None


def get_interaction_monitor() -> DrugInteractionMonitor:
    """Obtiene instancia del monitor."""
    global _interaction_monitor
    if _interaction_monitor is None:
        _interaction_monitor = DrugInteractionMonitor()
    return _interaction_monitor
