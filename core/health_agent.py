"""Agente operativo de salud para priorizar acciones clinicas y administrativas.

El agente combina reglas deterministicas del Asistente Clinico 360 con una capa
de planificacion de acciones. No emite diagnosticos ni ordenes medicas: organiza
datos existentes, evidencia y proximos pasos para revision profesional.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from core.clinical_assistant_service import compilar_dashboard_ejecutivo


PRIORIDAD_PESO = {
    "critica": 4,
    "alta": 3,
    "media": 2,
    "baja": 1,
}

MODULO_POR_CATEGORIA = {
    "vitales": "Clinica",
    "farmacologia": "Recetas",
    "cuidados": "Evolucion",
    "insumos": "Materiales",
    "emergencias": "Emergencias y Ambulancia",
    "infeccion": "Evolucion",
    "nutricion": "Evolucion",
    "consistencia": "Historial",
    "documentacion": "Evolucion",
    "estudios": "Estudios",
    "balance": "Balance",
}

RESPONSABLE_POR_CATEGORIA = {
    "vitales": "Equipo clinico",
    "farmacologia": "Medico / Enfermeria",
    "cuidados": "Enfermeria",
    "insumos": "Coordinacion / Enfermeria",
    "emergencias": "Guardia / Coordinacion",
    "infeccion": "Medico",
    "nutricion": "Equipo clinico",
    "consistencia": "Coordinacion",
    "documentacion": "Profesional tratante",
    "estudios": "Coordinacion",
    "balance": "Enfermeria",
}


@dataclass(frozen=True)
class HealthAgentAction:
    """Accion sugerida por el agente."""

    id: str
    titulo: str
    detalle: str
    prioridad: str
    categoria: str
    modulo_sugerido: str
    responsable: str
    evidencia: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class HealthAgentResult:
    """Resultado completo de una ejecucion del agente."""

    paciente_id: str
    estado: str
    resumen: str
    acciones: List[HealthAgentAction]
    dashboard: Dict[str, Any]
    generado_en: str
    guardrails: List[str]

    @property
    def acciones_criticas(self) -> int:
        return sum(1 for a in self.acciones if a.prioridad == "critica")

    @property
    def acciones_altas(self) -> int:
        return sum(1 for a in self.acciones if a.prioridad == "alta")


def _prioridad_desde_alerta(alerta: Dict[str, Any]) -> str:
    nivel = str(alerta.get("nivel", "")).strip().lower()
    if nivel == "danger":
        return "critica"
    if nivel == "warning":
        return "alta"
    if nivel == "info":
        return "media"
    return "baja"


def _estado_desde_dashboard(dashboard: Dict[str, Any]) -> str:
    semaforo = str(dashboard.get("semaforo", "")).strip().lower()
    if semaforo == "rojo":
        return "critico"
    if semaforo == "amarillo":
        return "atencion"
    return "estable"


def _accion_desde_alerta(index: int, alerta: Dict[str, Any]) -> HealthAgentAction:
    categoria = str(alerta.get("categoria") or "consistencia").strip().lower()
    prioridad = _prioridad_desde_alerta(alerta)
    titulo = str(alerta.get("titulo") or "Revision pendiente").strip()
    detalle = str(alerta.get("detalle") or "Revisar el registro asociado.").strip()
    return HealthAgentAction(
        id=f"alerta-{index + 1}",
        titulo=titulo,
        detalle=detalle,
        prioridad=prioridad,
        categoria=categoria,
        modulo_sugerido=MODULO_POR_CATEGORIA.get(categoria, "Historial"),
        responsable=RESPONSABLE_POR_CATEGORIA.get(categoria, "Equipo clinico"),
        evidencia=[detalle],
    )


def _acciones_de_cobertura(datos: Dict[str, Any], dashboard: Dict[str, Any]) -> List[HealthAgentAction]:
    acciones: List[HealthAgentAction] = []
    if dashboard.get("total_vitales", 0) == 0:
        acciones.append(
            HealthAgentAction(
                id="cobertura-vitales",
                titulo="Registrar signos vitales iniciales",
                detalle="No hay controles de signos vitales cargados para el paciente.",
                prioridad="alta",
                categoria="vitales",
                modulo_sugerido="Clinica",
                responsable="Enfermeria",
                evidencia=["total_vitales=0"],
            )
        )
    elif dashboard.get("ultima_actualizacion_hs") is not None and dashboard["ultima_actualizacion_hs"] > 12:
        acciones.append(
            HealthAgentAction(
                id="cobertura-vitales-recientes",
                titulo="Actualizar signos vitales",
                detalle="El ultimo control de signos vitales tiene mas de 12 horas.",
                prioridad="media",
                categoria="vitales",
                modulo_sugerido="Clinica",
                responsable="Enfermeria",
                evidencia=[f"ultima_actualizacion_hs={dashboard['ultima_actualizacion_hs']:.1f}"],
            )
        )

    if dashboard.get("total_evoluciones", 0) == 0:
        acciones.append(
            HealthAgentAction(
                id="cobertura-evolucion",
                titulo="Completar primera evolucion clinica",
                detalle="No hay evoluciones registradas para respaldar el seguimiento.",
                prioridad="media",
                categoria="documentacion",
                modulo_sugerido="Evolucion",
                responsable="Profesional tratante",
                evidencia=["total_evoluciones=0"],
            )
        )

    if dashboard.get("estudios_pendientes", 0) > 0:
        acciones.append(
            HealthAgentAction(
                id="seguimiento-estudios",
                titulo="Revisar estudios pendientes",
                detalle=f"Hay {dashboard['estudios_pendientes']} estudio(s) pendiente(s) de resultado.",
                prioridad="media",
                categoria="estudios",
                modulo_sugerido="Estudios",
                responsable="Coordinacion",
                evidencia=[f"estudios_pendientes={dashboard['estudios_pendientes']}"],
            )
        )

    if dashboard.get("total_balance", 0) > 0 and not dashboard.get("balance_tendencia"):
        acciones.append(
            HealthAgentAction(
                id="balance-incompleto",
                titulo="Validar balance hidrico",
                detalle="Hay registros de balance sin tendencia calculable; revisar fechas y campos de ingreso/egreso.",
                prioridad="baja",
                categoria="balance",
                modulo_sugerido="Balance",
                responsable="Enfermeria",
                evidencia=["balance_tendencia vacia con total_balance > 0"],
            )
        )

    if not acciones and not dashboard.get("alertas"):
        acciones.append(
            HealthAgentAction(
                id="seguimiento-rutina",
                titulo="Continuar seguimiento habitual",
                detalle="No se detectaron alertas automaticas ni brechas de cobertura relevantes.",
                prioridad="baja",
                categoria="consistencia",
                modulo_sugerido="Historial",
                responsable="Equipo clinico",
                evidencia=["sin_alertas_automaticas"],
            )
        )
    return acciones


def _ordenar_acciones(acciones: Iterable[HealthAgentAction]) -> List[HealthAgentAction]:
    return sorted(
        acciones,
        key=lambda accion: (
            -PRIORIDAD_PESO.get(accion.prioridad, 0),
            accion.categoria,
            accion.titulo,
        ),
    )


def _resumen(resultado_estado: str, acciones: List[HealthAgentAction], dashboard: Dict[str, Any]) -> str:
    criticas = sum(1 for a in acciones if a.prioridad == "critica")
    altas = sum(1 for a in acciones if a.prioridad == "alta")
    pendientes = len(acciones)
    if resultado_estado == "critico":
        return f"Prioridad critica: {criticas} accion(es) critica(s), {altas} alta(s), {pendientes} total."
    if resultado_estado == "atencion":
        return f"Requiere atencion: {altas} accion(es) alta(s), {pendientes} total."
    if dashboard.get("total_vitales", 0) == 0 and dashboard.get("total_evoluciones", 0) == 0:
        return "Paciente sin base clinica suficiente; iniciar registros minimos."
    return f"Seguimiento estable con {pendientes} accion(es) sugerida(s)."


def generar_plan_agente_salud(
    paciente_id: str,
    datos: Dict[str, Any],
    *,
    mi_empresa: str = "",
    objetivo: Optional[str] = None,
) -> HealthAgentResult:
    """Genera un plan de acciones para un paciente a partir de datos ya recopilados."""
    dashboard = compilar_dashboard_ejecutivo(datos)
    acciones = [
        _accion_desde_alerta(i, alerta)
        for i, alerta in enumerate(dashboard.get("alertas", []))
        if isinstance(alerta, dict)
    ]
    acciones.extend(_acciones_de_cobertura(datos, dashboard))
    acciones = _ordenar_acciones(acciones)
    estado = _estado_desde_dashboard(dashboard)

    if objetivo:
        acciones.insert(
            0,
            HealthAgentAction(
                id="objetivo-operativo",
                titulo="Objetivo solicitado",
                detalle=str(objetivo).strip(),
                prioridad="media",
                categoria="consistencia",
                modulo_sugerido="Historial",
                responsable="Equipo clinico",
                evidencia=["objetivo ingresado por usuario"],
            ),
        )

    guardrails = [
        "Las acciones sugeridas no reemplazan criterio medico ni protocolos institucionales.",
        "Ante signos de emergencia, activar el circuito local de urgencias.",
        "No se agregan datos clinicos que no existan en el registro.",
    ]
    if mi_empresa:
        guardrails.append(f"Contexto institucional: {mi_empresa}.")

    return HealthAgentResult(
        paciente_id=paciente_id,
        estado=estado,
        resumen=_resumen(estado, acciones, dashboard),
        acciones=acciones,
        dashboard=dashboard,
        generado_en=datetime.now().strftime("%d/%m/%Y %H:%M"),
        guardrails=guardrails,
    )


def ejecutar_agente_salud_paciente(
    paciente_id: str,
    *,
    mi_empresa: str = "",
    objetivo: Optional[str] = None,
) -> HealthAgentResult:
    """Recopila datos desde session_state y ejecuta el agente para un paciente."""
    from core.clinical_assistant_service import recopilar_datos_paciente

    datos = recopilar_datos_paciente(paciente_id)
    return generar_plan_agente_salud(
        paciente_id,
        datos,
        mi_empresa=mi_empresa,
        objetivo=objetivo,
    )


def exportar_plan_texto(resultado: HealthAgentResult) -> str:
    """Convierte el plan del agente a texto plano descargable."""
    lineas = [
        f"Agente de Salud - {resultado.paciente_id}",
        f"Generado: {resultado.generado_en}",
        f"Estado: {resultado.estado}",
        f"Resumen: {resultado.resumen}",
        "",
        "Acciones:",
    ]
    for idx, accion in enumerate(resultado.acciones, start=1):
        lineas.extend(
            [
                f"{idx}. [{accion.prioridad.upper()}] {accion.titulo}",
                f"   Responsable: {accion.responsable}",
                f"   Modulo sugerido: {accion.modulo_sugerido}",
                f"   Detalle: {accion.detalle}",
                f"   Evidencia: {' | '.join(accion.evidencia) if accion.evidencia else 'S/D'}",
            ]
        )
    lineas.extend(["", "Limites:"])
    lineas.extend(f"- {item}" for item in resultado.guardrails)
    return "\n".join(lineas)
