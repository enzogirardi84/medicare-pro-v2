"""Telemetria y monitoreo de degradacion de IA en el borde (Edge AI Drift).
Procesa metricas de inferencia offline que viajan en lotes sincronizados.
Detecta fatiga de alertas (alert fatigue) cuando los medicos ignoran
advertencias de interaccion farmacologica.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE DATOS DE TELEMETRIA
# ═══════════════════════════════════════════════════════════════════

@dataclass
class EdgeInferenceResult:
    """Resultado de una inferencia del Edge AI, sincronizado desde el dispositivo."""
    paciente: str = ""
    profesional: str = ""
    timestamp_inferencia: float = 0.0
    triage_ia: str = ""           # Lo que dijo la IA
    triage_real: str = ""         # Lo que diagnostico el medico
    score_ia: int = 0
    alertas_ia: list[dict] = field(default_factory=list)
    alertas_ignoradas: int = 0    # Alertas que el medico descarto
    interacciones_detectadas: int = 0
    sincronizado_en: float = field(default_factory=time.time)


@dataclass
class ProfesionalFatigueMetric:
    """Metricas de fatiga de alertas por profesional."""
    profesional: str = ""
    total_inferencias: int = 0
    alertas_ignoradas_consecutivas: int = 0
    ultima_alerta_ignorada: float = 0.0
    en_riesgo_mala_praxis: bool = False


# ═══════════════════════════════════════════════════════════════════
# 2. MOTOR DE TELEMETRIA Y DETECCION DE FATIGA
# ═══════════════════════════════════════════════════════════════════

class EdgeAITelemetry:
    """Procesa telemetria del Edge AI para detectar degradacion y fatiga.

    Metricas expuestas (Prometheus format):
    - edge_ai_triage_false_positive_rate: Tasa de falsos positivos del triage
    - edge_ai_triage_false_negative_rate: Tasa de falsos negativos
    - edge_ai_alert_override_rate: Tasa de alertas ignoradas
    - edge_ai_profesional_en_riesgo: 1 si un profesional ignora 3+ alertas seguidas
    """

    MAX_IGNORADAS_CONSECUTIVAS = 3  # Umbral para alertar por mala praxis

    def __init__(self):
        self._inferencias: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=500)
        )
        self._profesionales: dict[str, ProfesionalFatigueMetric] = {}

    # ── Recepcion de telemetria ──────────────────────────────

    def procesar_inferencia(self, resultado: EdgeInferenceResult) -> list[str]:
        """Procesa el resultado de una inferencia sincronizada.

        Args:
            resultado: Resultado de inferencia desde el dispositivo.

        Returns:
            Lista de alertas generadas (vacia si todo OK).
        """
        alertas: list[str] = []
        prof = resultado.profesional

        # Registrar inferencia
        self._inferencias[prof].append(resultado)
        self._profesionales.setdefault(prof, ProfesionalFatigueMetric(profesional=prof))

        metric = self._profesionales[prof]
        metric.total_inferencias += 1

        # Detectar alertas ignoradas
        if resultado.alertas_ignoradas > 0:
            metric.alertas_ignoradas_consecutivas += 1
            metric.ultima_alerta_ignorada = time.time()
        else:
            metric.alertas_ignoradas_consecutivas = 0

        # Alerta por fatiga (>3 ignoradas consecutivas)
        if metric.alertas_ignoradas_consecutivas >= self.MAX_IGNORADAS_CONSECUTIVAS:
            metric.en_riesgo_mala_praxis = True
            alerta = (
                f"FATIGA DE ALERTAS: {prof} ignoro "
                f"{metric.alertas_ignoradas_consecutivas} alertas consecutivas. "
                f"Riesgo de mala praxis."
            )
            alertas.append(alerta)
            self._disparar_alerta_fatiga(prof, metric.alertas_ignoradas_consecutivas)

        return alertas

    # ── Calculo de metricas ──────────────────────────────────

    def calcular_metricas(self, ventana_seg: float = 86400) -> dict[str, Any]:
        """Calcula metricas agregadas de telemetria Edge AI.

        Args:
            ventana_seg: Ventana de tiempo en segundos (default: 24h).

        Returns:
            Dict con metricas en formato estructurado.
        """
        ahora = time.time()
        corte = ahora - ventana_seg

        total_inferencias = 0
        total_aciertos_triage = 0
        total_alertas = 0
        total_ignoradas = 0
        profesionales_en_riesgo = []

        for prof, metric in self._profesionales.items():
            if metric.en_riesgo_mala_praxis:
                profesionales_en_riesgo.append(prof)

            for inf in self._inferencias[prof]:
                if inf.timestamp_inferencia < corte:
                    continue
                total_inferencias += 1
                total_alertas += len(inf.alertas_ia)
                total_ignoradas += inf.alertas_ignoradas

                # Triage accuracy
                if inf.triage_ia and inf.triage_real:
                    if inf.triage_ia.lower() == inf.triage_real.lower():
                        total_aciertos_triage += 1

        # Metricas calculadas
        triage_accuracy = (
            (total_aciertos_triage / max(total_inferencias, 1)) * 100
        )
        alert_override_rate = (
            (total_ignoradas / max(total_alertas, 1)) * 100
        )

        return {
            "total_inferencias": total_inferencias,
            "triage_accuracy_pct": round(triage_accuracy, 1),
            "alert_override_rate_pct": round(alert_override_rate, 1),
            "profesionales_en_riesgo": profesionales_en_riesgo,
            "total_profesionales_en_riesgo": len(profesionales_en_riesgo),
            "ventana_hs": round(ventana_seg / 3600, 1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ── Formato Prometheus ───────────────────────────────────

    def to_prometheus(self) -> str:
        """Exporta metricas en formato Prometheus."""
        metrics = self.calcular_metricas()
        lines = [
            "# HELP edge_ai_inferences_total Total de inferencias Edge AI procesadas",
            "# TYPE edge_ai_inferences_total counter",
            f"edge_ai_inferences_total {metrics['total_inferencias']}",
            "",
            "# HELP edge_ai_triage_accuracy_pct Precision del triage local vs real",
            "# TYPE edge_ai_triage_accuracy_pct gauge",
            f"edge_ai_triage_accuracy_pct {metrics['triage_accuracy_pct']}",
            "",
            "# HELP edge_ai_alert_override_rate_pct Tasa de alertas ignoradas por medicos",
            "# TYPE edge_ai_alert_override_rate_pct gauge",
            f"edge_ai_alert_override_rate_pct {metrics['alert_override_rate_pct']}",
            "",
            "# HELP edge_ai_profesionales_en_riesgo Profesionales con riesgo de mala praxis",
            "# TYPE edge_ai_profesionales_en_riesgo gauge",
            f"edge_ai_profesionales_en_riesgo {metrics['total_profesionales_en_riesgo']}",
        ]
        return "\n".join(lines)

    # ── Alerta de fatiga ─────────────────────────────────────

    def _disparar_alerta_fatiga(self, profesional: str, ignoradas: int) -> None:
        """Dispara alerta via AlertManager cuando un profesional
        ignora repetidamente alertas criticas de interaccion."""
        try:
            from core.metrics import AlertManager
            AlertManager.disparar_alerta(
                nivel="WARNING",
                mensaje=(
                    f"RIESGO DE MALA PRAXIS: El profesional {profesional} "
                    f"ignoro {ignoradas} alertas de interaccion farmacologica "
                    f"consecutivas. Evaluar intervencion."
                ),
                modulo="edge_ai_telemetry",
                metrica="alert_override_rate",
            )
        except Exception as exc:
            log_event("edge_ai_telemetry", f"alert_error:{type(exc).__name__}")

        # Registrar en audit trail
        try:
            from core.audit_trail_immutable import ImmutableAuditTrail
            auditor = ImmutableAuditTrail()
            auditor.registrar(
                usuario="__edge_ai_telemetry__",
                accion="ALERTA_FATIGA",
                recurso=f"profesional:{profesional}",
                detalle=f"{ignoradas} alertas ignoradas consecutivas",
            )
        except Exception as exc:
            log_event("edge_ai_telemetry", f"audit_error:{type(exc).__name__}")


# ═══════════════════════════════════════════════════════════════════
# 3. FUNCION DE INTEGRACION (desde SyncManager / lote sincronizado)
# ═══════════════════════════════════════════════════════════════════

def procesar_telemetria_desde_lote(
    payload_lote: dict[str, Any]
) -> list[str]:
    """Procesa la telemetria Edge AI incrustada en un lote sincronizado.

    El SyncManager debe llamar a esta funcion al recibir un lote
    que contenga datos de inferencia del Edge AI.

    Args:
        payload_lote: Dict del lote sincronizado.

    Returns:
        Lista de alertas generadas.
    """
    telemetry = EdgeAITelemetry()
    alertas_totales: list[str] = []

    operaciones = payload_lote.get("operaciones", [])
    for op in operaciones:
        edge_metadata = op.get("edge_ai_telemetry")
        if not edge_metadata:
            continue

        resultado = EdgeInferenceResult(
            paciente=op.get("paciente", ""),
            profesional=op.get("profesional", ""),
            timestamp_inferencia=edge_metadata.get("timestamp", 0.0),
            triage_ia=edge_metadata.get("triage_ia", ""),
            triage_real=op.get("diagnostico", ""),
            score_ia=edge_metadata.get("score_ia", 0),
            alertas_ia=edge_metadata.get("alertas", []),
            alertas_ignoradas=edge_metadata.get("alertas_ignoradas", 0),
            interacciones_detectadas=edge_metadata.get("interacciones", 0),
        )
        alertas = telemetry.procesar_inferencia(resultado)
        alertas_totales.extend(alertas)

    return alertas_totales
