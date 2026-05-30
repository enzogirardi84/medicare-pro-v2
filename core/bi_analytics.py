"""Motor de analitica epidemiologica y geolocalizacion de alto rendimiento.
Procesa datos agregados de evoluciones, check-ins GPS comprimidos
y geofencing para dashboards BI en Streamlit.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

import pandas as pd

from core.app_logging import log_event
from core.gps_processor import GPSProcessor


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE DATOS
# ═══════════════════════════════════════════════════════════════════

@dataclass
class MetricasBI:
    """Metricas preparadas para dashboard BI."""
    total_pacientes: int = 0
    total_visitas: int = 0
    tiempo_total_atencion_hs: float = 0.0
    costo_total_estimado: float = 0.0
    diagnosticos_frecuentes: dict[str, int] = field(default_factory=dict)
    visitas_por_dia: dict[str, int] = field(default_factory=dict)
    densidad_sintomas: list[dict[str, Any]] = field(default_factory=list)
    tiempo_promedio_visita_min: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# 2. MOTOR DE ANALITICA BI
# ═══════════════════════════════════════════════════════════════════

class BiAnalyticsEngine:
    """Motor de analitica para dashboards epidemiologicos y operativos.

    Procesa datos agregados de sesion_state (evoluciones, check-ins)
    y datos de geofencing para generar metricas de alto nivel.

    Tolerante a fallos: si no hay datos suficientes, retorna metricas
    vacias sin lanzar excepciones.
    """

    COSTO_HORA_ESTIMADO = 8500  # ARS/hora (configurable por tenant)

    def __init__(self, tenant_id: str = "default"):
        self._tenant_id = tenant_id
        self._cache: dict[str, Any] = {}
        self._cache_ts: float = 0.0
        self._cache_ttl = 30.0  # segundos

    # ── Procesamiento de evoluciones ──────────────────────────

    def _diagnosticos_frecuentes(
        self, evoluciones: list[dict[str, Any]]
    ) -> dict[str, int]:
        """Cuenta frecuencias de diagnosticos de forma eficiente."""
        freq: dict[str, int] = defaultdict(int)
        for evo in evoluciones:
            diag = str(evo.get("diagnostico", "") or "").strip().lower()
            if diag:
                # Normalizar: tomar solo la primera parte del diagnostico
                diag_main = diag.split(",")[0].split("(")[0].strip()
                freq[diag_main] += 1
        return dict(sorted(freq.items(), key=lambda x: -x[1])[:20])

    def _visitas_por_dia(
        self, evoluciones: list[dict[str, Any]]
    ) -> dict[str, int]:
        """Agrupa evoluciones por dia."""
        dias: dict[str, int] = defaultdict(int)
        for evo in evoluciones:
            fecha = str(evo.get("fecha", ""))[:10]
            if fecha:
                dias[fecha] += 1
        return dict(sorted(dias.items()))

    # ── Procesamiento GPS comprimido ──────────────────────────

    def _densidad_sintomas_por_coordenada(
        self,
        checkins: list[dict[str, Any]],
        evoluciones: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Genera mapa de densidad de atenciones por zona geografica.

        Usa las coordenadas de check-ins comprimidos (Douglas-Peucker)
        y las cruza con diagnosticos de evoluciones para generar
        un mapa de calor de incidencias.
        """
        # Indexar evoluciones por paciente para cruce rapido
        evos_por_paciente: dict[str, list[str]] = defaultdict(list)
        for evo in evoluciones:
            pac = str(evo.get("paciente", ""))
            diag = str(evo.get("diagnostico", "") or "").strip().lower()
            if pac and diag:
                evos_por_paciente[pac].append(diag)

        densidad: list[dict[str, Any]] = []
        for ci in checkins:
            gps = str(ci.get("gps", "") or "").strip()
            if not gps or "," not in gps:
                continue
            try:
                lat, lon = (float(x) for x in gps.split(",", 1))
            except (ValueError, TypeError):
                continue

            paciente = str(ci.get("paciente", ""))
            diagnosticos = evos_por_paciente.get(paciente, [])

            punto = {
                "lat": lat,
                "lon": lon,
                "peso": max(len(diagnosticos), 1),
                "diagnosticos": diagnosticos[:3] if diagnosticos else ["Sin diagnostico"],
                "profesional": str(ci.get("profesional", ci.get("tipo", ""))),
                "fecha": str(ci.get("fecha_hora", ""))[:10],
            }
            densidad.append(punto)

        return densidad

    def _costo_operativo(
        self, visitas_geofencing: list[dict[str, Any]]
    ) -> float:
        """Calcula costo operativo basado en tiempo neto de atencion.

        Usa los eventos de entrada/salida del GeofencingEngine
        para calcular tiempo efectivo en domicilio.
        """
        total_segundos = sum(
            v.get("duracion_seg", 0) for v in visitas_geofencing
        )
        horas = total_segundos / 3600.0
        return round(horas * self.COSTO_HORA_ESTIMADO, 2)

    # ── Metrica principal ─────────────────────────────────────

    def calcular_metricas(
        self,
        evoluciones: list[dict[str, Any]],
        checkins: list[dict[str, Any]],
        visitas_geofencing: list[dict[str, Any]] | None = None,
        force: bool = False,
    ) -> MetricasBI:
        """Calcula metricas BI con cache de 30 segundos.

        Args:
            evoluciones: Lista de evoluciones medicas.
            checkins: Lista de check-ins GPS comprimidos.
            visitas_geofencing: Lista de visitas detectadas por geofencing.
            force: Si True, ignora el cache.

        Returns:
            MetricasBI con indicadores calculados.
        """
        ahora = time.time()
        if not force and (ahora - self._cache_ts) < self._cache_ttl:
            cached = self._cache.get("metricas")
            if cached:
                return cached

        metrics = MetricasBI()

        if not evoluciones and not checkins:
            self._cache = {"metricas": metrics}
            self._cache_ts = ahora
            return metrics

        # Diagnosticos frecuentes
        try:
            metrics.diagnosticos_frecuentes = self._diagnosticos_frecuentes(evoluciones)
        except Exception as exc:
            log_event("bi", f"diagnosticos_error:{type(exc).__name__}")

        # Visitas por dia
        try:
            metrics.visitas_por_dia = self._visitas_por_dia(evoluciones)
        except Exception as exc:
            log_event("bi", f"visitas_error:{type(exc).__name__}")

        # Densidad geografica
        try:
            metrics.densidad_sintomas = self._densidad_sintomas_por_coordenada(
                checkins, evoluciones
            )
        except Exception as exc:
            log_event("bi", f"densidad_error:{type(exc).__name__}")

        # Costo operativo
        if visitas_geofencing:
            try:
                metrics.costo_total_estimado = self._costo_operativo(visitas_geofencing)
                metrics.tiempo_total_atencion_hs = round(
                    sum(v.get("duracion_seg", 0) for v in visitas_geofencing) / 3600.0, 2
                )
                metrics.total_visitas = len(visitas_geofencing)
                if metrics.total_visitas > 0:
                    metrics.tiempo_promedio_visita_min = round(
                        (metrics.tiempo_total_atencion_hs * 60) / metrics.total_visitas, 1
                    )
            except Exception as exc:
                log_event("bi", f"costo_error:{type(exc).__name__}")

        metrics.total_pacientes = len(set(
            e.get("paciente", "") for e in evoluciones
        ))

        self._cache = {"metricas": metrics}
        self._cache_ts = ahora
        return metrics

    # ── DataFrames para Streamlit ─────────────────────────────

    def evoluciones_a_dataframe(self, evoluciones: list[dict[str, Any]]) -> pd.DataFrame:
        """Convierte evoluciones a DataFrame optimizado para graficos."""
        if not evoluciones:
            return pd.DataFrame()
        rows = []
        for evo in evoluciones:
            rows.append({
                "fecha": str(evo.get("fecha", ""))[:10],
                "paciente": evo.get("paciente", ""),
                "diagnostico": str(evo.get("diagnostico", "") or "").strip(),
                "profesional": evo.get("firma", evo.get("profesional", "")),
            })
        df = pd.DataFrame(rows)
        if not df.empty and "fecha" in df.columns:
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        return df

    def densidad_a_dataframe(self) -> pd.DataFrame:
        """Convierte densidad geografica a DataFrame listo para st.map()."""
        puntos = self._cache.get("metricas", MetricasBI()).densidad_sintomas
        if not puntos:
            return pd.DataFrame(columns=["lat", "lon"])
        df = pd.DataFrame(puntos)
        if "peso" in df.columns:
            df["size"] = df["peso"] * 5
        return df

    def diagnosticos_a_dataframe(self) -> pd.DataFrame:
        """Convierte frecuencias de diagnosticos a DataFrame."""
        diag = self._cache.get("metricas", MetricasBI()).diagnosticos_frecuentes
        if not diag:
            return pd.DataFrame(columns=["diagnostico", "cantidad"])
        return pd.DataFrame([
            {"diagnostico": k, "cantidad": v} for k, v in diag.items()
        ])

    def reset_cache(self) -> None:
        self._cache = {}
        self._cache_ts = 0.0
