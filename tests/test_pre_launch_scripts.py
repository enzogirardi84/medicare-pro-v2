"""Tests para scripts de validación pre-launch (E2E, Profiling, Stress, Sanitize)."""
from __future__ import annotations

import asyncio
import os
import sys

# Los scripts asumen estar en la raíz del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestE2EConflictSimulation:
    """Valida que el script de simulación de conflicto carga y su lógica interna funciona."""

    def test_import(self):
        from scripts.e2e_conflict_simulation import CrossDeviceScenario
        assert CrossDeviceScenario is not None

    def test_scenario_instantiation(self):
        from scripts.e2e_conflict_simulation import CrossDeviceScenario
        scenario = CrossDeviceScenario()
        assert scenario.outbox is not None
        assert scenario.crdt_engine is not None
        assert scenario.replicator is not None

    def test_outbox_flow(self):
        from scripts.e2e_conflict_simulation import CrossDeviceScenario
        from core.mobile_outbox import SyncStatus

        scenario = CrossDeviceScenario()
        entry = scenario.outbox.add_entry(
            action_type="alerta_news2",
            summary="Alerta para test",
            patient_name="Paciente Test",
            professional_id="prof-test",
            tenant_id="t1",
        )
        assert entry.status == SyncStatus.PENDING

        scenario.outbox.mark_synced(entry.entry_id)
        assert entry.status == SyncStatus.SYNCED

    def test_crdt_merge(self):
        from scripts.e2e_conflict_simulation import CrossDeviceScenario
        import time

        scenario = CrossDeviceScenario()
        resultado = asyncio.run(scenario.crdt_engine.merge_batch(
            registros_cliente=[{"id": "r1", "diagnostico": "gripe", "version": 1, "updated_at": 100.0}],
            registros_servidor=[{"id": "r1", "diagnostico": "neumonia", "version": 2, "updated_at": 200.0}],
            tabla="evoluciones",
            tenant_id="t1",
        ))
        assert "merged" in resultado
        assert "conflictos" in resultado


class TestMemoryProfiler:
    def test_import(self):
        from scripts.memory_profiler_report import PoolBenchmark, GCLatencyProbe, MemoryProfilerReport
        assert PoolBenchmark is not None
        assert GCLatencyProbe is not None

    def test_pool_benchmark_runs(self):
        from scripts.memory_profiler_report import PoolBenchmark
        bench = PoolBenchmark()
        result = bench.benchmark_pool()
        assert "speedup_x" in result
        assert result["iterations"] == 10000

    def test_buffer_benchmark_runs(self):
        from scripts.memory_profiler_report import PoolBenchmark
        bench = PoolBenchmark()
        result = bench.benchmark_buffer()
        assert result["iterations"] == 5000

    def test_gc_probe_instantiation(self):
        from scripts.memory_profiler_report import GCLatencyProbe
        import hashlib
        from core.runtime_telemetry import RuntimeMetricsCollector

        probe = GCLatencyProbe()
        collector = RuntimeMetricsCollector()
        result = probe.measure(collector)
        assert "avg_duration_ms" in result


class TestStressTestRunner:
    def test_import(self):
        from scripts.stress_test_runner import StressTestRunner
        assert StressTestRunner is not None

    def test_instantiation(self):
        from scripts.stress_test_runner import StressTestRunner
        runner = StressTestRunner()
        assert len(runner.PHASES) == 3
        assert runner.PHASES[0]["name"] == "ingesta_delta"

    def test_phase_structure(self):
        from scripts.stress_test_runner import StressTestRunner
        runner = StressTestRunner()
        for phase in runner.PHASES:
            assert "name" in phase
            assert "users" in phase
            assert "desc" in phase


class TestPreLaunchSanitizer:
    def test_import(self):
        from scripts.pre_launch_sanitizer import PreLaunchSanitizer
        assert PreLaunchSanitizer is not None

    def test_vacuum_sql_exists(self):
        from scripts.pre_launch_sanitizer import VACUUM_TUNE_SQL
        assert "event_ingest_queue" in VACUUM_TUNE_SQL
        assert "checkins_gps" in VACUUM_TUNE_SQL

    def test_reindex_sql_exists(self):
        from scripts.pre_launch_sanitizer import REINDEX_CONCURRENTLY_SQL
        assert "REINDEX INDEX CONCURRENTLY" in REINDEX_CONCURRENTLY_SQL
        assert "checkins_gps" in REINDEX_CONCURRENTLY_SQL
        assert "clinical_event_store" in REINDEX_CONCURRENTLY_SQL
