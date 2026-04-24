"""
Exportación estructurada de datos clínicos para integración con IA/LLM.
Fase 4: Preparación para integración de IA avanzada.

Estandariza la salida de informes clínicos en formato JSON para facilitar
su procesamiento por modelos de lenguaje grandes (LLM).
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
import json

import streamlit as st


@dataclass
class PacienteResumen:
    """Datos básicos del paciente para contexto clínico."""
    id: str
    nombre_completo: str
    dni: str
    fecha_nacimiento: Optional[str] = None
    edad: Optional[int] = None
    sexo: Optional[str] = None
    obra_social: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    estado: str = "Activo"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SignoVital:
    """Registro de signo vital con metadata."""
    tipo: str  # presion_arterial, frecuencia_cardiaca, temperatura, etc.
    valor: str
    unidad: str
    fecha_hora: str
    profesional: Optional[str] = None
    notas: Optional[str] = None
    es_normal: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvolucionClinica:
    """Registro de evolución clínica estructurada."""
    fecha_hora: str
    tipo: str  # nota_evolucion, consulta, procedimiento
    resumen: str
    detalle_completo: Optional[str] = None
    profesional: Optional[str] = None
    especialidad: Optional[str] = None
    diagnosticos: List[str] = None
    procedimientos: List[str] = None
    medicamentos: List[str] = None
    
    def __post_init__(self):
        if self.diagnosticos is None:
            self.diagnosticos = []
        if self.procedimientos is None:
            self.procedimientos = []
        if self.medicamentos is None:
            self.medicamentos = []
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EstudioMedico:
    """Registro de estudio médico estructurado."""
    tipo: str  # laboratorio, imagen, endoscopia, etc.
    subtipo: Optional[str] = None  # hemograma, radiografia, etc.
    fecha: str
    profesional_solicitante: Optional[str] = None
    resultados: Dict[str, Any] = None
    conclusiones: Optional[str] = None
    adjuntos_urls: List[str] = None
    
    def __post_init__(self):
        if self.resultados is None:
            self.resultados = {}
        if self.adjuntos_urls is None:
            self.adjuntos_urls = []
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ResumenClinicoAI:
    """
    Resumen clínico completo optimizado para consumo por IA.
    Estructura jerárquica con metadatos para facilitar el procesamiento.
    """
    # Metadata del resumen
    version: str = "1.0"
    fecha_generacion: str = None
    id_paciente: str = None
    
    # Datos del paciente
    paciente: Optional[PacienteResumen] = None
    
    # Contexto clínico
    alergias: List[str] = None
    antecedentes_patologicos: List[str] = None
    antecedentes_quirurgicos: List[str] = None
    medicamentos_habituales: List[str] = None
    
    # Datos actuales
    signos_vitales_actuales: List[SignoVital] = None
    diagnostico_actual: Optional[str] = None
    
    # Historia
    evoluciones_recientes: List[EvolucionClinica] = None
    estudios_recientes: List[EstudioMedico] = None
    
    # Timestamps para rango temporal
    fecha_inicio_datos: Optional[str] = None
    fecha_fin_datos: Optional[str] = None
    
    def __post_init__(self):
        if self.fecha_generacion is None:
            self.fecha_generacion = datetime.now().isoformat()
        if self.alergias is None:
            self.alergias = []
        if self.antecedentes_patologicos is None:
            self.antecedentes_patologicos = []
        if self.antecedentes_quirurgicos is None:
            self.antecedentes_quirurgicos = []
        if self.medicamentos_habituales is None:
            self.medicamentos_habituales = []
        if self.signos_vitales_actuales is None:
            self.signos_vitales_actuales = []
        if self.evoluciones_recientes is None:
            self.evoluciones_recientes = []
        if self.estudios_recientes is None:
            self.estudios_recientes = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertir a diccionario para serialización JSON."""
        return {
            "_metadata": {
                "version": self.version,
                "fecha_generacion": self.fecha_generacion,
                "tipo_documento": "resumen_clinico_ai",
                "formato": "structured_medical_record",
            },
            "paciente": self.paciente.to_dict() if self.paciente else None,
            "contexto_clinico": {
                "alergias": self.alergias,
                "antecedentes_patologicos": self.antecedentes_patologicos,
                "antecedentes_quirurgicos": self.antecedentes_quirurgicos,
                "medicamentos_habituales": self.medicamentos_habituales,
            },
            "datos_actuales": {
                "signos_vitales": [sv.to_dict() for sv in self.signos_vitales_actuales],
                "diagnostico_actual": self.diagnostico_actual,
            },
            "historia_clinica": {
                "evoluciones_recientes": [e.to_dict() for e in self.evoluciones_recientes],
                "estudios_recientes": [e.to_dict() for e in self.estudios_recientes],
                "rango_temporal": {
                    "fecha_inicio": self.fecha_inicio_datos,
                    "fecha_fin": self.fecha_fin_datos,
                },
            },
        }
    
    def to_json(self, indent: bool = True) -> str:
        """Exportar como JSON string."""
        return json.dumps(
            self.to_dict(), 
            ensure_ascii=False, 
            indent=2 if indent else None,
            default=str
        )


def build_resumen_clinico_from_session(
    paciente_id: str,
    dias_historia: int = 30,
    max_evoluciones: int = 10,
    max_estudios: int = 5,
) -> ResumenClinicoAI:
    """
    Construir resumen clínico estructurado desde session_state.
    
    Args:
        paciente_id: ID del paciente
        dias_historia: Días de historia a incluir
        max_evoluciones: Máximo de evoluciones recientes
        max_estudios: Máximo de estudios recientes
    
    Returns:
        ResumenClinicoAI con datos estructurados
    """
    from core.utils import mapa_detalles_pacientes, ahora
    from datetime import timedelta
    
    ss = st.session_state
    
    # Datos del paciente
    detalles = mapa_detalles_pacientes(ss).get(paciente_id, {})
    paciente = PacienteResumen(
        id=paciente_id,
        nombre_completo=detalles.get("nombre_completo", paciente_id),
        dni=str(detalles.get("dni", "S/D")),
        fecha_nacimiento=detalles.get("fecha_nacimiento"),
        obra_social=detalles.get("obra_social"),
        telefono=detalles.get("telefono"),
        direccion=detalles.get("direccion"),
        estado=detalles.get("estado", "Activo"),
    )
    
    resumen = ResumenClinicoAI(
        id_paciente=paciente_id,
        paciente=paciente,
    )
    
    # Signos vitales (últimos)
    vitales_key = f"vitales_{paciente_id}"
    if vitales_key in ss:
        vitales = ss[vitales_key]
        for v in vitales[-5:]:  # Últimos 5
            sv = SignoVital(
                tipo=v.get("tipo", "desconocido"),
                valor=str(v.get("valor", "N/A")),
                unidad=v.get("unidad", ""),
                fecha_hora=str(v.get("fecha_hora", "")),
                profesional=v.get("profesional"),
            )
            resumen.signos_vitales_actuales.append(sv)
    
    # Evoluciones recientes
    evos_key = f"evoluciones_{paciente_id}"
    if evos_key in ss:
        evos = ss[evos_key]
        corte_fecha = (ahora() - timedelta(days=dias_historia)).isoformat()
        
        for e in reversed(evos[-max_evoluciones:]):
            if e.get("fecha_hora", "") > corte_fecha:
                evo = EvolucionClinica(
                    fecha_hora=str(e.get("fecha_hora", "")),
                    tipo=e.get("tipo", "nota"),
                    resumen=e.get("resumen", "")[:500],  # Truncar
                    detalle_completo=e.get("texto", "")[:2000] if len(e.get("texto", "")) > 500 else e.get("texto"),
                    profesional=e.get("profesional"),
                    especialidad=e.get("especialidad"),
                )
                resumen.evoluciones_recientes.append(evo)
    
    return resumen


def export_resumen_for_llm(paciente_id: str) -> str:
    """
    Exportar resumen clínico formateado para LLM (como string).
    
    Returns:
        String formateado listo para prompt de LLM
    """
    resumen = build_resumen_clinico_from_session(paciente_id)
    
    # Formato optimizado para LLM
    output = []
    output.append("=" * 60)
    output.append("RESUMEN CLÍNICO ESTRUCTURADO")
    output.append("=" * 60)
    output.append("")
    
    # Paciente
    if resumen.paciente:
        p = resumen.paciente
        output.append(f"PACIENTE: {p.nombre_completo}")
        output.append(f"DNI: {p.dni} | Estado: {p.estado}")
        if p.obra_social:
            output.append(f"Obra Social: {p.obra_social}")
        output.append("")
    
    # Contexto
    if resumen.alergias:
        output.append(f"ALERGIAS: {', '.join(resumen.alergias)}")
    if resumen.medicamentos_habituales:
        output.append(f"MEDICACIÓN HABITUAL: {', '.join(resumen.medicamentos_habituales)}")
    output.append("")
    
    # Signos vitales
    if resumen.signos_vitales_actuales:
        output.append("SIGNOS VITALES RECIENTES:")
        for sv in resumen.signos_vitales_actuales:
            output.append(f"  - {sv.tipo}: {sv.valor} {sv.unidad} ({sv.fecha_hora})")
        output.append("")
    
    # Evoluciones
    if resumen.evoluciones_recientes:
        output.append("EVOLUCIONES RECIENTES:")
        for evo in resumen.evoluciones_recientes[:3]:
            output.append(f"\n[{evo.fecha_hora}] {evo.profesional or 'Profesional'} - {evo.tipo}")
            output.append(f"Resumen: {evo.resumen}")
    
    output.append("")
    output.append("=" * 60)
    
    return "\n".join(output)


# ============================================================
# FUNCIÓN PARA UI STREAMLIT
# ============================================================

def render_export_ai_button(paciente_id: str, key_suffix: str = ""):
    """Renderizar botón de exportación para IA en Streamlit."""
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("📤 Exportar JSON para IA", key=f"export_json_ai_{paciente_id}_{key_suffix}"):
            resumen = build_resumen_clinico_from_session(paciente_id)
            json_str = resumen.to_json()
            st.download_button(
                "⬇️ Descargar JSON",
                json_str,
                file_name=f"resumen_clinico_{paciente_id}_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                key=f"dl_json_{paciente_id}_{key_suffix}"
            )
    
    with col2:
        if st.button("📋 Copiar resumen para LLM", key=f"copy_llm_{paciente_id}_{key_suffix}"):
            texto = export_resumen_for_llm(paciente_id)
            st.code(texto, language="text")
            st.success("Resumen generado. Copiá el texto de arriba para tu prompt.")
