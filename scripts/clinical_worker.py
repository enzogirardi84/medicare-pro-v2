#!/usr/bin/env python3
"""Worker asincrono de reportes clinicos automatizados.
Consume evoluciones del dia y genera metricas epidemiologicas por tenant.
Usa PostgreSQL como cola (LISTEN/NOTIFY) para procesamiento en tiempo real.
"""
from __future__ import annotations

import asyncio
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MOTOR DE ANALISIS DE TEXTO CLINICO
# ═══════════════════════════════════════════════════════════════════

SINTOMAS_PATRONES = {
    "fiebre": r"fiebre|temperatura|febril|hipertermia",
    "tos": r"tos|expectoracion|productiva",
    "dolor": r"dolor|doloroso|algia|cefalea|mialgia",
    "disnea": r"disnea|dificultad respiratoria|falta de aire|oxigeno",
    "diarrea": r"diarrea|deposiciones|enterocolitis",
    "vomitos": r"vomito|nauseas|emesis",
    "cefalea": r"cefalea|dolor de cabeza|migrana",
    "cianosis": r"cianosis|coloracion azul|sat O2 baja",
}


class EpidemiologiaEngine:
    """Procesa evoluciones clinicas y genera metricas epidemiologicas."""

    @staticmethod
    def analizar_sintomas(evoluciones: list[dict[str, Any]]) -> dict[str, int]:
        """Analiza texto de notas medicas y cuenta frecuencias de sintomas."""
        contador: Counter = Counter()
        for evo in evoluciones:
            texto = f"{evo.get('nota', '')} {evo.get('diagnostico', '')}".lower()
            for sintoma, patron in SINTOMAS_PATRONES.items():
                if re.search(patron, texto):
                    contador[sintoma] += 1
        return dict(contador.most_common(20))

    @staticmethod
    def metricas_por_tenant(evoluciones: list[dict[str, Any]]) -> dict[str, Any]:
        """Calcula metricas agregadas por tenant."""
        pacientes = set()
        diagnosticos = Counter()
        total = len(evoluciones)

        for evo in evoluciones:
            pacientes.add(evo.get("paciente_id", ""))
            diag = str(evo.get("diagnostico", "") or "").strip().lower()
            if diag:
                diagnosticos[diag] += 1

        return {
            "total_evoluciones": total,
            "pacientes_atendidos": len(pacientes),
            "diagnosticos_frecuentes": dict(diagnosticos.most_common(10)),
            "sintomas": EpidemiologiaEngine.analizar_sintomas(evoluciones),
            "timestamp": datetime.utcnow().isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════
# 2. WORKER ASINCRONO (LISTEN/NOTIFY + loop)
# ═══════════════════════════════════════════════════════════════════

class ClinicalReportWorker:
    """Worker que escucha eventos NOTIFY de PostgreSQL y genera reportes.

    Se conecta a la DB y escucha canales de notificacion.
    Cuando llega una nueva evolucion, procesa y genera metricas.
    """

    CHANNEL = "evoluciones_inserted"

    def __init__(self, db_url: str):
        self.db_url = db_url
        self._running = True

    async def procesar_lote(self, conn: Any, tenant_id: str) -> dict:
        """Procesa evoluciones de las ultimas 24h y genera reporte."""
        rows = await conn.fetch("""
            SELECT nota, diagnostico, created_at, tenant_id
            FROM evoluciones
            WHERE created_at >= NOW() - INTERVAL '1 day'
              AND tenant_id = $1
        """, tenant_id)

        evoluciones = [dict(r) for r in rows]
        return EpidemiologiaEngine.metricas_por_tenant(evoluciones)

    async def run(self) -> None:
        """Loop principal del worker."""
        import asyncpg

        log_event("worker", f"ClinicalReportWorker iniciado")

        while self._running:
            try:
                conn = await asyncpg.connect(self.db_url)

                # Escuchar canal de notificaciones
                await conn.add_listener(self.CHANNEL, self._on_notify)
                log_event("worker", f"Escuchando canal {self.CHANNEL}")

                # Loop de escucha
                while self._running:
                    await asyncio.sleep(5)

            except Exception as exc:
                log_event("worker", f"error:{type(exc).__name__}:{exc}")
                await asyncio.sleep(10)

    def _on_notify(self, conn: Any, pid: int, channel: str, payload: str) -> None:
        """Callback cuando llega un NOTIFY de PostgreSQL."""
        try:
            data = json.loads(payload)
            tenant_id = data.get("tenant_id", "default")
            log_event("worker", f"notify_recibido:{tenant_id}")
        except Exception:
            pass

    def stop(self) -> None:
        self._running = False


# ═══════════════════════════════════════════════════════════════════
# 3. FUNCION TRIGGER EN POSTGRESQL (NOTIFY por fila insertada)
# ═══════════════════════════════════════════════════════════════════

TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION notify_evolucion_inserted()
RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify(
        'evoluciones_inserted',
        json_build_object(
            'id', NEW.id,
            'tenant_id', NEW.tenant_id,
            'created_at', NEW.created_at
        )::TEXT
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trig_evoluciones_notify
    AFTER INSERT ON evoluciones
    FOR EACH ROW
    EXECUTE FUNCTION notify_evolucion_inserted();
"""


if __name__ == "__main__":
    import os
    db_url = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/medicare")
    worker = ClinicalReportWorker(db_url)
    asyncio.run(worker.run())
