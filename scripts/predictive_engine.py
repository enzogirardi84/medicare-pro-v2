#!/usr/bin/env python3
"""Motor predictivo de ausentismo y demanda de turnos.
Usa regresion logistica con scikit-learn. Entrena con datos historicos
de check-ins y evoluciones. Alerta cuando probabilidad > 70%.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

import numpy as np

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELO DE DATOS
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TurnoPredict:
    """Datos de un turno para prediccion de ausentismo."""
    turno_id: str = ""
    paciente_id: str = ""
    tenant_id: str = ""
    fecha_turno: float = 0.0
    hora_turno: int = 0  # Hora del dia 0-23
    dia_semana: int = 0  # 0=lunes, 6=domingo
    # Features
    ausencias_previas: int = 0
    asistencias_previas: int = 0
    edad_paciente: int = 0
    distancia_km: float = 0.0  # Distancia del domicilio al centro
    tiene_obra_social: bool = True
    lluvia_prob: float = 0.0  # Probabilidad de lluvia (API externa)

    @property
    def tasa_asistencia(self) -> float:
        total = self.ausencias_previas + self.asistencias_previas
        return self.asistencias_previas / max(total, 1)


# ═══════════════════════════════════════════════════════════════════
# 2. MODELO PREDICTIVO (Regresion Logistica)
# ═══════════════════════════════════════════════════════════════════

class AusentismoPredictor:
    """Predictor de ausentismo usando regresion logistica.

    Entrena con datos historicos de la base de datos del tenant.
    Genera alertas con probabilidad > 70%.
    """

    def __init__(self):
        self._modelo = None
        self._features_mean: list[float] = []
        self._features_std: list[float] = []

    def _entrenar(self, turnos_historicos: list[TurnoPredict]) -> None:
        """Entrena el modelo con datos historicos.

        Usa regresion logistica con regularizacion L2.
        Si no hay suficientes datos, usa heuristica basada en
        tasa de asistencia historica del paciente.
        """
        if len(turnos_historicos) < 50:
            # Poca data: usar heuristica simple
            log_event("predict", "Pocos datos: usando heuristica")
            self._modelo = "heuristic"
            return

        try:
            from sklearn.linear_model import LogisticRegression
            from sklearn.preprocessing import StandardScaler

            X = np.array([
                [t.ausencias_previas, t.asistencias_previas,
                 t.edad_paciente, t.distancia_km,
                 float(t.tiene_obra_social), t.lluvia_prob,
                 t.hora_turno, t.dia_semana]
                for t in turnos_historicos
            ])
            y = np.array([1 if t.tasa_asistencia < 0.3 else 0 for t in turnos_historicos])

            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            self._features_mean = scaler.mean_.tolist()
            self._features_std = scaler.scale_.tolist()

            model = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
            model.fit(X_scaled, y)
            self._modelo = model
            log_event("predict", f"Modelo entrenado: accuracy={model.score(X_scaled, y):.2f}")

        except ImportError:
            log_event("predict", "scikit-learn no instalado: usando heuristica")
            self._modelo = "heuristic"

    def predecir(self, turno: TurnoPredict) -> tuple[float, bool]:
        """Predice probabilidad de ausentismo.

        Returns:
            (probabilidad_0_1, es_alta)
        """
        if self._modelo is None:
            return 0.0, False

        if self._modelo == "heuristic":
            prob = 1.0 - turno.tasa_asistencia
            return prob, prob > 0.7

        try:
            features = np.array([[
                turno.ausencias_previas, turno.asistencias_previas,
                turno.edad_paciente, turno.distancia_km,
                float(turno.tiene_obra_social), turno.lluvia_prob,
                turno.hora_turno, turno.dia_semana
            ]])
            features_scaled = (features - self._features_mean) / self._features_std
            prob = self._modelo.predict_proba(features_scaled)[0][1]
            return prob, prob > 0.7

        except Exception as exc:
            log_event("predict", f"error:{type(exc).__name__}")
            return 0.0, False


# ═══════════════════════════════════════════════════════════════════
# 3. WORKER DE PREDICCION (procesa turnos del dia siguiente)
# ═══════════════════════════════════════════════════════════════════

class PredictiveWorker:
    """Worker que analiza turnos del dia siguiente y genera alertas."""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.predictor = AusentismoPredictor()

    async def entrenar_con_historicos(self) -> None:
        """Entrena el modelo con datos de los ultimos 90 dias."""
        import asyncpg
        conn = await asyncpg.connect(self.db_url)
        try:
            rows = await conn.fetch("""
                SELECT
                    a.id, a.paciente_id, a.tenant_id,
                    EXTRACT(HOUR FROM a.fecha_programada) as hora,
                    EXTRACT(DOW FROM a.fecha_programada) as dia_semana,
                    COALESCE(a.estado = 'omitida', false) as fue_ausencia
                FROM administracion_med a
                WHERE a.fecha_programada >= NOW() - INTERVAL '90 days'
                LIMIT 10000
            """)
            turnos = []
            for r in rows:
                t = TurnoPredict(
                    turno_id=str(r["id"]),
                    paciente_id=str(r["paciente_id"]),
                    tenant_id=str(r["tenant_id"]),
                    hora_turno=int(r["hora"]),
                    dia_semana=int(r["dia_semana"]),
                    ausencias_previas=1 if r["fue_ausencia"] else 0,
                    asistencias_previas=0 if r["fue_ausencia"] else 1,
                )
                turnos.append(t)
            self.predictor._entrenar(turnos)
        finally:
            await conn.close()

    async def predecir_turnos_manana(self) -> list[dict[str, Any]]:
        """Predice ausentismo para los turnos de manana."""
        import asyncpg
        conn = await asyncpg.connect(self.db_url)
        alertas = []
        try:
            rows = await conn.fetch("""
                SELECT id, paciente_id, tenant_id,
                       fecha_programada
                FROM administracion_med
                WHERE fecha_programada::DATE = (CURRENT_DATE + INTERVAL '1 day')
                  AND estado = 'programada'
                LIMIT 1000
            """)
            for r in rows:
                turno = TurnoPredict(
                    turno_id=str(r["id"]),
                    paciente_id=str(r["paciente_id"]),
                    tenant_id=str(r["tenant_id"]),
                    fecha_turno=r["fecha_programada"].timestamp(),
                    hora_turno=r["fecha_programada"].hour,
                    dia_semana=r["fecha_programada"].weekday(),
                )
                prob, es_alta = self.predictor.predecir(turno)
                if es_alta:
                    alertas.append({
                        "turno_id": turno.turno_id,
                        "paciente_id": turno.paciente_id,
                        "tenant_id": turno.tenant_id,
                        "probabilidad": round(prob, 2),
                        "alerta": f"Probabilidad de ausentismo: {prob:.0%}",
                    })
                    log_event("predict", f"alerta:{turno.turno_id}:prob={prob:.0%}")
        finally:
            await conn.close()
        return alertas


if __name__ == "__main__":
    import asyncio
    db_url = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/medicare")
    worker = PredictiveWorker(db_url)
    asyncio.run(worker.entrenar_con_historicos())
    alertas = asyncio.run(worker.predecir_turnos_manana())
    print(f"Alertas generadas: {len(alertas)}")
    for a in alertas[:5]:
        print(f"  {a['alerta']}")
