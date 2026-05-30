"""Motor proactivo de deteccion de amenazas y compliance (SOC2/HIPAA).
Analiza logs del Audit Trail en tiempo real para detectar:
a) Geographic Velocity Violation - Accesos imposibles por distancia
b) Mass Export Anomaly - Exfiltracion masiva de datos
"""
from __future__ import annotations

import hashlib
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE DATOS
# ═══════════════════════════════════════════════════════════════════

@dataclass
class EventoAudit:
    """Evento del audit trail para analisis."""
    timestamp: float
    usuario: str
    accion: str
    recurso: str
    detalle: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertaCompliance:
    """Alerta generada por el motor de compliance."""
    tipo: str  # "velocity_violation" | "mass_export" | "anomaly"
    severidad: str  # "CRITICAL" | "WARNING" | "INFO"
    mensaje: str
    usuario: str
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)
    detectado_en: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════════════════════════
# 2. MOTOR DE THREAT DETECTION
# ═══════════════════════════════════════════════════════════════════

class ComplianceGuard:
    """Motor de deteccion de anomalias en tiempo real.

    Analiza eventos del Audit Trail usando ventanas de tiempo
    deslizantes y reglas heuristicas.

    Uso:
        guard = ComplianceGuard()
        alertas = guard.analizar_evento(evento)
        if alertas:
            AlertManager.disparar_alerta(...)
    """

    # Configuracion de umbrales
    VELOCIDAD_MAXIMA_KMH = 180.0  # Velocidad maxima plausible
    EXPORT_PDF_MAX_EN_60S = 50    # Maximo PDFs descargados en 60s
    VENTANA_GEO_MINUTOS = 15      # Ventana para verificar ubicacion

    def __init__(self):
        # Buffer de eventos para analisis (ventana deslizante)
        self._eventos_por_usuario: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=100)
        )
        self._export_count: dict[str, list[float]] = defaultdict(list)

    # ── 2a. Geographic Velocity Violation ─────────────────────

    def _geographic_velocity_check(
        self, usuario: str, evento: EventoAudit
    ) -> Optional[AlertaCompliance]:
        """Detecta si un mismo usuario aparece en dos ubicaciones
        imposiblemente distantes en poco tiempo (indica suplantacion).
        """
        eventos_previos = self._eventos_por_usuario.get(usuario, [])
        if not eventos_previos:
            return None

        # Extraer coordenadas del evento actual
        coords_actual = self._extraer_coordenadas(evento)
        if not coords_actual:
            return None

        for prev in eventos_previos:
            coords_prev = self._extraer_coordenadas(prev)
            if not coords_prev:
                continue

            dt = abs(evento.timestamp - prev.timestamp)
            if dt <= 0:
                continue

            # Calcular distancia usando Haversine
            from core.gps_processor import GPSProcessor
            dist_km = GPSProcessor.haversine_km(
                coords_prev[0], coords_prev[1],
                coords_actual[0], coords_actual[1],
            )

            if dist_km < 1.0:  # Misma ubicacion, sin alerta
                continue

            velocidad = (dist_km / dt) * 3600.0  # km/h

            if velocidad > self.VELOCIDAD_MAXIMA_KMH:
                return AlertaCompliance(
                    tipo="velocity_violation",
                    severidad="CRITICAL",
                    mensaje=(
                        f"Acceso geograficamente imposible: {usuario} se movio "
                        f"{dist_km:.0f}km en {dt/60:.0f}min ({velocidad:.0f}km/h). "
                        f"Posible robo de credenciales o sesion clonada."
                    ),
                    usuario=usuario,
                    timestamp=evento.timestamp,
                    metadata={
                        "lat_prev": coords_prev[0],
                        "lon_prev": coords_prev[1],
                        "lat_actual": coords_actual[0],
                        "lon_actual": coords_actual[1],
                        "distancia_km": round(dist_km, 1),
                        "velocidad_kmh": round(velocidad, 0),
                        "tiempo_minutos": round(dt / 60, 1),
                    },
                )
        return None

    @staticmethod
    def _extraer_coordenadas(evento: EventoAudit) -> Optional[tuple[float, float]]:
        """Extrae coordenadas GPS del detalle o metadata del evento."""
        # Buscar en metadata
        lat = evento.metadata.get("lat") or evento.metadata.get("latitude")
        lon = evento.metadata.get("lon") or evento.metadata.get("longitude")
        if lat and lon:
            try:
                return float(lat), float(lon)
            except (ValueError, TypeError):
                pass

        # Buscar en detalle con regex
        import re
        gps_match = re.search(r'(-?\d+\.\d+),\s*(-?\d+\.\d+)', evento.detalle or "")
        if gps_match:
            try:
                return float(gps_match.group(1)), float(gps_match.group(2))
            except (ValueError, TypeError):
                pass

        return None

    # ── 2b. Mass Export Anomaly ───────────────────────────────

    def _mass_export_check(self, usuario: str, evento: EventoAudit) -> Optional[AlertaCompliance]:
        """Detecta si un usuario exporta PDFs masivamente (exfiltracion).

        Si un Coordinador descarga >50 PDFs en <60s, se bloquea
        temporalmente la accion y se alerta.
        """
        if evento.accion != "EXPORT_PDF":
            return None

        ahora = evento.timestamp
        exports = self._export_count[usuario]
        exports.append(ahora)

        # Limpiar exports fuera de la ventana de 60s
        ventana = ahora - 60.0
        self._export_count[usuario] = [t for t in exports if t > ventana]

        count_60s = len(self._export_count[usuario])

        if count_60s > self.EXPORT_PDF_MAX_EN_60S:
            # Bloquear temporalmente
            self._export_count[usuario] = []  # Resetear contador

            return AlertaCompliance(
                tipo="mass_export",
                severidad="CRITICAL",
                mensaje=(
                    f"EXFILTRACION DETECTADA: {usuario} descargo "
                    f"{count_60s} PDFs clinicos en menos de 60 segundos. "
                    f"Accion bloqueada temporalmente."
                ),
                usuario=usuario,
                timestamp=evento.timestamp,
                metadata={
                    "pdfs_descargados": count_60s,
                    "ventana_segundos": 60,
                    "umbral": self.EXPORT_PDF_MAX_EN_60S,
                },
            )
        return None

    # ── Analisis principal ────────────────────────────────────

    def analizar_evento(self, evento: EventoAudit) -> list[AlertaCompliance]:
        """Analiza un evento del audit trail contra todas las reglas.

        Args:
            evento: Evento a analizar.

        Returns:
            Lista de alertas generadas (vacia si todo OK).
        """
        alertas: list[AlertaCompliance] = []

        # Registrar evento en buffer de usuario
        self._eventos_por_usuario[evento.usuario].append(evento)

        # Regla 1: Velocidad geografica imposible
        try:
            alerta_geo = self._geographic_velocity_check(evento.usuario, evento)
            if alerta_geo:
                alertas.append(alerta_geo)
        except Exception as exc:
            log_event("compliance", f"geo_check_error:{type(exc).__name__}")

        # Regla 2: Exportacion masiva
        try:
            alerta_export = self._mass_export_check(evento.usuario, evento)
            if alerta_export:
                alertas.append(alerta_export)
        except Exception as exc:
            log_event("compliance", f"export_check_error:{type(exc).__name__}")

        return alertas

    def procesar_alerta(self, alerta: AlertaCompliance) -> None:
        """Procesa una alerta: log, audit trail y AlertManager."""
        # Log local
        log_event("compliance", f"{alerta.severidad}:{alerta.tipo}:{alerta.usuario}:{alerta.mensaje[:100]}")

        # Disparar alerta via AlertManager
        try:
            from core.metrics import AlertManager
            AlertManager.disparar_alerta(
                nivel=alerta.severidad,
                mensaje=alerta.mensaje,
                modulo="compliance_guard",
                metrica=alerta.tipo,
            )
        except Exception as exc:
            log_event("compliance", f"alertmanager_error:{type(exc).__name__}")

        # Registrar en audit trail inmutable
        try:
            from core.audit_trail_immutable import ImmutableAuditTrail
            auditor = ImmutableAuditTrail()
            auditor.registrar(
                usuario="__compliance_guard__",
                accion=f"ALERTA_{alerta.severidad}",
                recurso=f"compliance:{alerta.tipo}",
                detalle=alerta.mensaje[:500],
            )
        except Exception as exc:
            log_event("compliance", f"audit_trail_error:{type(exc).__name__}")


# ═══════════════════════════════════════════════════════════════════
# 3. FUNCION DE INTEGRACION (desde el Audit Trail)
# ═══════════════════════════════════════════════════════════════════

def analizar_eventos_recientes(limite: int = 100) -> list[AlertaCompliance]:
    """Analiza eventos recientes del audit trail.

    Se ejecuta periodicamente o bajo demanda desde el panel SRE.
    """
    guard = ComplianceGuard()
    alertas_totales: list[AlertaCompliance] = []

    try:
        from core.audit_trail_immutable import ImmutableAuditTrail
        auditor = ImmutableAuditTrail()
        entries = auditor.obtener_entradas_recientes(limite=limite)

        for entry in entries:
            evento = EventoAudit(
                timestamp=entry.get("timestamp", 0.0),
                usuario=entry.get("usuario", ""),
                accion=entry.get("accion", ""),
                recurso=entry.get("recurso", ""),
                detalle=entry.get("detalle", ""),
                metadata={
                    "lat": entry.get("lat"),
                    "lon": entry.get("lon"),
                },
            )
            alertas = guard.analizar_evento(evento)
            for a in alertas:
                guard.procesar_alerta(a)
                alertas_totales.append(a)

    except Exception as exc:
        log_event("compliance", f"analisis_error:{type(exc).__name__}")

    return alertas_totales
