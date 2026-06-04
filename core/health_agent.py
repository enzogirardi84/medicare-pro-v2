"""Agente operativo de salud para priorizar acciones clinicas y administrativas.

El agente combina reglas deterministicas del Asistente Clinico 360 con una capa
de planificacion de acciones. No emite diagnosticos ni ordenes medicas: organiza
datos existentes, evidencia y proximos pasos para revision profesional.
"""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from core.clinical_assistant_service import compilar_dashboard_ejecutivo


PRIORIDAD_PESO = {
    "critica": 4,
    "alta": 3,
    "media": 2,
    "baja": 1,
}

ESTADO_PESO = {
    "critico": 30,
    "atencion": 10,
    "estable": 0,
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
    vencimiento: str = "Hoy"


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
    pase_guardia: str
    resumen_derivacion: str
    plan_hoy: Dict[str, List[HealthAgentAction]]
    tareas_urgentes: List[HealthAgentAction]

    @property
    def acciones_criticas(self) -> int:
        return sum(1 for a in self.acciones if a.prioridad == "critica")

    @property
    def acciones_altas(self) -> int:
        return sum(1 for a in self.acciones if a.prioridad == "alta")


@dataclass(frozen=True)
class InstitutionPatientPriority:
    """Prioridad de un paciente dentro de la institucion."""

    paciente_id: str
    estado: str
    score: int
    resumen: str
    acciones_criticas: int
    acciones_altas: int
    tareas_urgentes: int = 0


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


def _acciones_de_cobertura(dashboard: Dict[str, Any]) -> List[HealthAgentAction]:
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


def _top_acciones(acciones: Sequence[HealthAgentAction], limite: int = 5) -> List[HealthAgentAction]:
    return list(acciones[:limite])


def _lineas_acciones(acciones: Sequence[HealthAgentAction], limite: int = 5) -> List[str]:
    if not acciones:
        return ["- Sin acciones pendientes."]
    return [
        f"- [{accion.prioridad.upper()}] {accion.titulo}: {accion.detalle}"
        for accion in _top_acciones(acciones, limite)
    ]


def _generar_pase_guardia(
    paciente_id: str,
    dashboard: Dict[str, Any],
    acciones: Sequence[HealthAgentAction],
) -> str:
    """Genera texto breve para cambio de turno."""
    diagnosticos = "; ".join(dashboard.get("diagnosticos_list") or []) or "Sin diagnosticos registrados"
    lineas = [
        f"Pase de guardia - {paciente_id}",
        f"Estado: {_estado_desde_dashboard(dashboard)}",
        f"Diagnosticos: {diagnosticos}",
        (
            "Ultimos vitales: "
            f"TA {dashboard.get('ultima_ta', '-')}, "
            f"FC {dashboard.get('ultima_fc', '-')}, "
            f"Temp {dashboard.get('ultima_temp', '-')}, "
            f"SatO2 {dashboard.get('ultima_spo2', '-')}, "
            f"Glu {dashboard.get('ultima_glu', '-')}"
        ),
        "Pendientes prioritarios:",
    ]
    lineas.extend(_lineas_acciones(acciones, limite=6))
    lineas.append("Validar con el profesional responsable antes de indicar cambios terapeuticos.")
    return "\n".join(lineas)


def _generar_resumen_derivacion(
    paciente_id: str,
    dashboard: Dict[str, Any],
    acciones: Sequence[HealthAgentAction],
) -> str:
    """Genera texto para derivacion o auditoria clinica."""
    lineas = [
        f"Resumen para derivacion/auditoria - {paciente_id}",
        f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        f"Estado operativo: {_estado_desde_dashboard(dashboard)}",
        f"Total evoluciones: {dashboard.get('total_evoluciones', 0)}",
        f"Total controles de vitales: {dashboard.get('total_vitales', 0)}",
        f"Indicaciones activas: {dashboard.get('indicaciones_activas', 0)}",
        f"Administraciones pendientes: {dashboard.get('administraciones_pendientes', 0)}",
        f"Estudios pendientes: {dashboard.get('estudios_pendientes', 0)}",
        "Hallazgos y acciones sugeridas:",
    ]
    lineas.extend(_lineas_acciones(acciones, limite=8))
    lineas.append("Este resumen se basa solo en registros cargados en el sistema.")
    return "\n".join(lineas)


def _generar_plan_hoy(acciones: Sequence[HealthAgentAction]) -> Dict[str, List[HealthAgentAction]]:
    """Agrupa acciones para el plan diario por responsable operativo."""
    plan = {
        "Enfermeria": [],
        "Coordinacion": [],
        "Medico": [],
        "Equipo clinico": [],
    }
    for accion in acciones:
        responsable = accion.responsable.lower()
        if "enfermeria" in responsable:
            plan["Enfermeria"].append(accion)
        elif "coordinacion" in responsable:
            plan["Coordinacion"].append(accion)
        elif "medico" in responsable:
            plan["Medico"].append(accion)
        else:
            plan["Equipo clinico"].append(accion)
    return {k: v for k, v in plan.items() if v}


def _tareas_urgentes(acciones: Sequence[HealthAgentAction]) -> List[HealthAgentAction]:
    return [a for a in acciones if a.prioridad in {"critica", "alta"}]


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
    acciones.extend(_acciones_de_cobertura(dashboard))
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

    tareas_urgentes = _tareas_urgentes(acciones)
    return HealthAgentResult(
        paciente_id=paciente_id,
        estado=estado,
        resumen=_resumen(estado, acciones, dashboard),
        acciones=acciones,
        dashboard=dashboard,
        generado_en=datetime.now().strftime("%d/%m/%Y %H:%M"),
        guardrails=guardrails,
        pase_guardia=_generar_pase_guardia(paciente_id, dashboard, acciones),
        resumen_derivacion=_generar_resumen_derivacion(paciente_id, dashboard, acciones),
        plan_hoy=_generar_plan_hoy(acciones),
        tareas_urgentes=tareas_urgentes,
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


def exportar_pase_guardia(resultado: HealthAgentResult) -> str:
    """Texto descargable para cambio de turno."""
    return resultado.pase_guardia


def exportar_resumen_derivacion(resultado: HealthAgentResult) -> str:
    """Texto descargable para derivacion o auditoria."""
    return resultado.resumen_derivacion


def registrar_accion_agente(
    session_state: Dict[str, Any],
    *,
    paciente_id: str,
    accion_id: str,
    accion_titulo: str,
    actor: str,
    estado: str = "realizada",
    nota: str = "",
    emit_audit: bool = True,
) -> Dict[str, Any]:
    """Registra una accion tomada por el usuario para trazabilidad."""
    evento = {
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "paciente": paciente_id,
        "accion_id": accion_id,
        "accion": accion_titulo,
        "actor": actor,
        "estado": estado,
        "nota": nota,
        "origen": "Agente de Salud",
    }
    for key in ("agente_salud_acciones_db", "agente_salud_acciones_log"):
        log = session_state.setdefault(key, [])
        if isinstance(log, list):
            log.append(dict(evento))
    try:
        from core.app_logging import log_event

        log_event("agente_salud", f"accion_{estado}:{paciente_id}:{accion_id}:{actor}")
    except Exception:
        pass
    if emit_audit:
        _emitir_auditoria_accion_agente(evento)
    return evento


def _patient_audit_id(paciente_id: str) -> str:
    raw = str(paciente_id or "").strip().lower()
    if not raw:
        return "patient:unknown"
    return "patient:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _emitir_auditoria_accion_agente(evento: Dict[str, Any]) -> None:
    """Emite auditoria formal sin guardar nombre/DNI del paciente en el trail."""
    try:
        from core.audit_trail import AuditEventType, audit_log

        audit_log(
            AuditEventType.AGENT_ACTION,
            resource_type="agente_salud",
            resource_id=_patient_audit_id(str(evento.get("paciente", ""))),
            action=str(evento.get("estado") or "realizada").upper(),
            description="Accion operativa registrada por Agente de Salud",
            metadata={
                "accion_id": str(evento.get("accion_id", "")),
                "accion": str(evento.get("accion", ""))[:120],
                "origen": "Agente de Salud",
            },
        )
    except Exception as exc:
        try:
            from core.app_logging import log_event

            log_event("agente_salud", f"audit_emit_error:{type(exc).__name__}")
        except Exception:
            pass


def _score_resultado(resultado: HealthAgentResult) -> int:
    return (
        resultado.acciones_criticas * 100
        + resultado.acciones_altas * 40
        + len(resultado.tareas_urgentes) * 10
        + ESTADO_PESO.get(resultado.estado, 0)
    )


def exportar_priorizacion_institucion(
    prioridades: Sequence[InstitutionPatientPriority | Dict[str, Any]],
) -> str:
    """CSV descargable para coordinacion, auditoria o pase institucional."""
    columnas = [
        "paciente_id",
        "estado",
        "score",
        "acciones_criticas",
        "acciones_altas",
        "tareas_urgentes",
        "resumen",
    ]
    salida = io.StringIO()
    writer = csv.DictWriter(salida, fieldnames=columnas, lineterminator="\n")
    writer.writeheader()
    for prioridad in prioridades:
        if isinstance(prioridad, dict):
            fuente = prioridad
            get = fuente.get
        else:
            get = lambda key, default="": getattr(prioridad, key, default)
        writer.writerow({col: get(col, "") for col in columnas})
    return salida.getvalue()


def priorizar_pacientes_institucion(
    pacientes: Sequence[str],
    *,
    mi_empresa: str = "",
    limite: int = 20,
) -> List[InstitutionPatientPriority]:
    """Ordena pacientes por criticidad usando el agente paciente por paciente."""
    prioridades: List[InstitutionPatientPriority] = []
    for paciente_id in pacientes:
        if not paciente_id:
            continue
        resultado = ejecutar_agente_salud_paciente(str(paciente_id), mi_empresa=mi_empresa)
        score = _score_resultado(resultado)
        prioridades.append(
            InstitutionPatientPriority(
                paciente_id=str(paciente_id),
                estado=resultado.estado,
                score=score,
                resumen=resultado.resumen,
                acciones_criticas=resultado.acciones_criticas,
                acciones_altas=resultado.acciones_altas,
                tareas_urgentes=len(resultado.tareas_urgentes),
            )
        )
    prioridades.sort(key=lambda p: (-p.score, p.paciente_id))
    return prioridades[:limite]
