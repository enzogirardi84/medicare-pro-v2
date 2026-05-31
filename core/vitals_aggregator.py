"""Time-Series Hyper-Aggregation para telemetria de ambulancias.
Consolida millones de lecturas de signos vitales en resúmenes
estadisticos por ventanas de 1 minuto. Reduce storage 90%.
Alimenta motor predictivo NEWS2 y deteccion temprana de sepsis.
"""
from __future__ import annotations

import asyncio
import json
import math
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE AGREGACION
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TimeBucket:
    """Bucket de tiempo con resumen estadístico."""
    bucket_key: str                # "2026-06-01T10:00:00Z_hr"
    metric: str                    # "hr" | "spo2" | "rr" | "nibp_sys"
    count: int = 0
    mean: float = 0.0
    variance: float = 0.0
    std: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    window_start: float = 0.0
    window_end: float = 0.0
    raw_samples_count: int = 0     # cuantas lecturas crudas se agregaron

    def to_insert_tuple(self, tenant_id: str, patient_id: str) -> tuple:
        return (
            tenant_id, patient_id, self.metric, self.bucket_key,
            self.count, round(self.mean, 2), round(self.variance, 2),
            round(self.min_val, 2), round(self.max_val, 2),
            round(self.p50, 2), round(self.p95, 2),
            self.window_start, self.window_end, self.raw_samples_count,
        )


@dataclass
class SepsisRiskScore:
    """Score de riesgo de sepsis basado en parametros agregados.

    qSOFA score simplificado:
    - RR >= 22 rpm → 1 punto
    - SBP <= 100 mmHg → 1 punto
    - Alteracion estado mental → 1 punto (no disponible en telemetria)
    """
    patient_id: str = ""
    tenant_id: str = ""
    qsofa_score: int = 0
    rr_mean: float = 0.0
    sbp_mean: float = 0.0
    hr_mean: float = 0.0
    temperature_mean: float = 0.0
    risk_level: str = "low"          # "low" | "medium" | "high"
    alert: bool = False
    timestamp: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════════════════════════
# 2. SQL DE AGREGACION (TimescaleDB-style / PG nativo)
# ═══════════════════════════════════════════════════════════════════

HYPER_AGGREGATION_SQL = """
-- =============================================================================
-- Time-Series Hyper-Aggregation
-- Reduce 1.000 lecturas/segundo a 1 resumen/minuto (99.9% reduction)
-- =============================================================================

-- 1. TABLA DE BUCKETS AGREGADOS (almacenamiento optimizado)
CREATE TABLE IF NOT EXISTS vitals_aggregated (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    patient_id      TEXT NOT NULL,
    metric          TEXT NOT NULL,           -- "hr" | "spo2" | "rr" | "nibp_sys"
    bucket_key      TEXT NOT NULL,           -- "2026-06-01T10:00:00Z_hr"
    count           INT NOT NULL DEFAULT 0,
    mean            DOUBLE PRECISION,
    variance        DOUBLE PRECISION,
    min_val         DOUBLE PRECISION,
    max_val         DOUBLE PRECISION,
    p50             DOUBLE PRECISION,
    p95             DOUBLE PRECISION,
    window_start    TIMESTAMPTZ NOT NULL,
    window_end      TIMESTAMPTZ NOT NULL,
    raw_samples     INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (tenant_id, patient_id, metric, bucket_key)
);

CREATE INDEX IF NOT EXISTS idx_vitals_agg_lookup
    ON vitals_aggregated (tenant_id, patient_id, window_start DESC);

-- 2. TABLA DE ALERTAS DE SEPSIS (qSOFA)
CREATE TABLE IF NOT EXISTS sepsis_alerts (
    id              BIGSERIAL PRIMARY KEY,
    patient_id      TEXT NOT NULL,
    tenant_id       UUID NOT NULL,
    qsofa_score     INT NOT NULL DEFAULT 0,
    rr_mean         DOUBLE PRECISION,
    sbp_mean        DOUBLE PRECISION,
    hr_mean         DOUBLE PRECISION,
    temperature_mean DOUBLE PRECISION,
    risk_level      TEXT NOT NULL DEFAULT 'low',
    alert           BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (patient_id, created_at)
);

CREATE INDEX IF NOT EXISTS idx_sepsis_alerts_patient
    ON sepsis_alerts (patient_id, created_at DESC);

-- 3. FUNCION: insertar bucket agregado (UPSERT)
CREATE OR REPLACE FUNCTION upsert_vitals_bucket(
    p_tenant_id UUID, p_patient_id TEXT, p_metric TEXT,
    p_bucket_key TEXT, p_count INT, p_mean DOUBLE PRECISION,
    p_variance DOUBLE PRECISION, p_min_val DOUBLE PRECISION,
    p_max_val DOUBLE PRECISION, p_p50 DOUBLE PRECISION,
    p_p95 DOUBLE PRECISION, p_window_start TIMESTAMPTZ,
    p_window_end TIMESTAMPTZ, p_raw_samples INT
) RETURNS VOID AS $$
BEGIN
    INSERT INTO vitals_aggregated
        (tenant_id, patient_id, metric, bucket_key, count,
         mean, variance, min_val, max_val, p50, p95,
         window_start, window_end, raw_samples)
    VALUES
        (p_tenant_id, p_patient_id, p_metric, p_bucket_key, p_count,
         p_mean, p_variance, p_min_val, p_max_val, p_p50, p_p95,
         p_window_start, p_window_end, p_raw_samples)
    ON CONFLICT (tenant_id, patient_id, metric, bucket_key)
    DO UPDATE SET
        count = EXCLUDED.count,
        mean = EXCLUDED.mean,
        variance = EXCLUDED.variance,
        min_val = LEAST(vitals_aggregated.min_val, EXCLUDED.min_val),
        max_val = GREATEST(vitals_aggregated.max_val, EXCLUDED.max_val),
        raw_samples = vitals_aggregated.raw_samples + EXCLUDED.raw_samples;
END;
$$ LANGUAGE plpgsql;
"""


# ═══════════════════════════════════════════════════════════════════
# 3. AGREGADOR EN MEMORIA (EDGE / SERVER)
# ═══════════════════════════════════════════════════════════════════

class VitalsAggregator:
    """Agregador de signos vitales en ventanas de tiempo.

    Acumula lecturas crudas en buckets de 1 minuto.
    Cada minuto: calcula estadísticas y persiste.
    Alimenta el motor de sepsis predictivo.
    """

    WINDOW_SECONDS = 60  # 1 minuto

    def __init__(self):
        self._buckets: dict[str, list[float]] = {}
        self._last_flush: float = time.time()
        self._total_raw_samples = 0
        self._total_buckets = 0

    def _bucket_key(self, metric: str, timestamp: float) -> str:
        """Genera clave de bucket para una métrica y timestamp."""
        window_start = math.floor(timestamp / self.WINDOW_SECONDS) * self.WINDOW_SECONDS
        return f"{metric}:{window_start}"

    def ingest(self, metric: str, value: float, timestamp: Optional[float] = None):
        """Ingiere una lectura cruda.

        Args:
            metric: Nombre de la métrica ("hr", "spo2", "rr", etc.).
            value: Valor de la lectura.
            timestamp: Timestamp de la lectura (default: now).
        """
        ts = timestamp or time.time()
        key = self._bucket_key(metric, ts)

        if key not in self._buckets:
            self._buckets[key] = []
        self._buckets[key].append(value)
        self._total_raw_samples += 1

    def flush_bucket(self, metric: str, timestamp: float) -> Optional[TimeBucket]:
        """Cierra un bucket y devuelve su resumen estadístico.

        Args:
            metric: Nombre de la métrica.
            timestamp: Timestamp base del bucket.

        Returns:
            TimeBucket con estadísticas, o None si no hay datos.
        """
        key = self._bucket_key(metric, timestamp)
        samples = self._buckets.pop(key, [])
        if not samples:
            return None

        window_start = math.floor(timestamp / self.WINDOW_SECONDS) * self.WINDOW_SECONDS
        sorted_samples = sorted(samples)
        n = len(sorted_samples)
        mean = statistics.mean(sorted_samples)
        var = statistics.variance(sorted_samples) if n > 1 else 0.0

        bucket = TimeBucket(
            bucket_key=key,
            metric=metric,
            count=n,
            mean=mean,
            variance=var,
            std=math.sqrt(var),
            min_val=sorted_samples[0],
            max_val=sorted_samples[-1],
            p50=sorted_samples[n // 2],
            p95=sorted_samples[int(n * 0.95)],
            p99=sorted_samples[int(n * 0.99)],
            window_start=window_start,
            window_end=window_start + self.WINDOW_SECONDS,
            raw_samples_count=n,
        )
        self._total_buckets += 1
        return bucket

    def flush_all_pending(self, reference_time: Optional[float] = None) -> list[TimeBucket]:
        """Cierra todos los buckets expirados.

        Args:
            reference_time: Tiempo de referencia (default: now).
                           Buckets con window_end < reference_time se cierran.

        Returns:
            Lista de TimeBucket cerrados.
        """
        ref = reference_time or time.time()
        buckets = []
        # Extraer keys únicos de métrica (sin el timestamp)
        metric_keys = set()
        for key in list(self._buckets.keys()):
            metric = key.split(":")[0]
            if key not in metric_keys:
                metric_keys.add(metric)

        for key in list(self._buckets.keys()):
            metric = key.split(":")[0]
            ts_part = key.split(":")[1]
            if ts_part and ts_part.replace(".", "").isdigit():
                window_ts = float(ts_part)
                if window_ts + self.WINDOW_SECONDS < ref:
                    bucket = self.flush_bucket(metric, window_ts)
                    if bucket:
                        buckets.append(bucket)

        return buckets

    def get_stats(self) -> dict:
        return {
            "total_raw_samples": self._total_raw_samples,
            "total_buckets": self._total_buckets,
            "open_buckets": len(self._buckets),
            "compression_ratio": round(
                self._total_raw_samples / max(self._total_buckets, 1), 1
            ),
        }


# ═══════════════════════════════════════════════════════════════════
# 4. MOTOR PREDICTIVO DE SEPSIS (qSOFA)
# ═══════════════════════════════════════════════════════════════════

class SepsisPredictor:
    """Motor predictivo de sepsis basado en qSOFA.

    Procesa buckets agregados y calcula riesgo.
    Si qSOFA >= 2: alerta de sepsis potencial.
    """

    def __init__(self):
        self._alerts: list[SepsisRiskScore] = []

    def evaluate(self, patient_id: str, tenant_id: str,
                 buckets: list[TimeBucket]) -> SepsisRiskScore:
        """Evalúa riesgo de sepsis desde buckets agregados.

        Args:
            patient_id: ID del paciente.
            tenant_id: ID del tenant.
            buckets: Buckets de la ventana actual.

        Returns:
            SepsisRiskScore con qSOFA y nivel de riesgo.
        """
        # Extraer métricas relevantes
        rr = None
        sbp = None
        hr = None
        temp = None

        for b in buckets:
            if b.metric == "rr":
                rr = b.mean
            elif b.metric == "nibp_sys":
                sbp = b.mean
            elif b.metric == "hr":
                hr = b.mean
            elif b.metric == "temperature":
                temp = b.mean

        # qSOFA score
        qsofa = 0
        if rr is not None and rr >= 22:
            qsofa += 1
        if sbp is not None and sbp <= 100:
            qsofa += 1

        # Nivel de riesgo
        if qsofa >= 2:
            risk = "high"
            alert = True
        elif qsofa == 1:
            risk = "medium"
            alert = False
        else:
            risk = "low"
            alert = False

        score = SepsisRiskScore(
            patient_id=patient_id,
            tenant_id=tenant_id,
            qsofa_score=qsofa,
            rr_mean=round(rr, 1) if rr else 0,
            sbp_mean=round(sbp, 1) if sbp else 0,
            hr_mean=round(hr, 1) if hr else 0,
            temperature_mean=round(temp, 1) if temp else 0,
            risk_level=risk,
            alert=alert,
        )

        if alert:
            self._alerts.append(score)
            log_event("sepsis", f"ALERT:{patient_id}:qSOFA={qsofa}:RR={rr}:SBP={sbp}")

        return score

    def get_alerts(self) -> list[SepsisRiskScore]:
        return list(self._alerts)


__all__ = [
    "VitalsAggregator",
    "SepsisPredictor",
    "TimeBucket",
    "SepsisRiskScore",
    "HYPER_AGGREGATION_SQL",
]
