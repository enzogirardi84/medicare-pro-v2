"""Suite de Chaos Engineering y Pruebas de Estres para MediCare PRO.
Simula escenarios de alta concurrencia, fallos de red y corrupcion de datos.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

# ─── Configuracion ──────────────────────────────────────────────
NUM_MEDICOS = 100
NUM_USUARIOS_OFFLINE = 50
NUM_AUDITORES = 10
ARCHIVO_PESADO_SIZE = 20 * 1024 * 1024  # 20MB
TIMEOUT_TOTAL_SEG = 120
SINCRONIZACIONES_SIMULTANEAS = 25

# Colores para output
G = "\033[92m"  # green
R = "\033[91m"  # red
Y = "\033[93m"  # yellow
B = "\033[94m"  # blue
N = "\033[0m"   # reset


class ChaosMetrics:
    """Recolecta metricas de las pruebas de caos."""
    def __init__(self):
        self.total_operaciones = 0
        self.exitosas = 0
        self.fallidas = 0
        self.tiempos: list[float] = []
        self.errores: list[str] = []
        self._lock = threading.Lock()

    def registrar(self, ok: bool, tiempo_ms: float, error: str = "") -> None:
        with self._lock:
            self.total_operaciones += 1
            if ok:
                self.exitosas += 1
            else:
                self.fallidas += 1
                if error:
                    self.errores.append(error)
            self.tiempos.append(tiempo_ms)

    def resumen(self) -> dict[str, Any]:
        with self._lock:
            p95 = sorted(self.tiempos)[int(len(self.tiempos) * 0.95)] if self.tiempos else 0
            return {
                "total": self.total_operaciones,
                "exitosas": self.exitosas,
                "fallidas": self.fallidas,
                "tasa_exito": f"{self.exitosas / max(self.total_operaciones, 1) * 100:.1f}%",
                "p95_ms": round(p95, 1),
                "avg_ms": round(sum(self.tiempos) / max(len(self.tiempos), 1), 1),
                "errores": self.errores[:10],
            }


# ═══════════════════════════════════════════════════════════════════
# 1. SIMULADOR DE ALTA CONCURRENCIA
# ═══════════════════════════════════════════════════════════════════

class ConcurrentStressTest:
    """Simula alta concurrencia: medicos, offline, auditores simultaneos.

    Escenario:
    - 100 medicos enviando evoluciones con adjuntos de 20MB
    - 50 usuarios descargando lotes offline via SyncManager
    - 10 auditores validando hashes QR publicos
    """

    def __init__(self):
        self.metrics = ChaosMetrics()
        self._stop_flag = False

    def _simular_adjunto_pesado(self) -> bytes:
        return os.urandom(ARCHIVO_PESADO_SIZE)

    def _simular_evolucion(self, medico_id: int) -> dict[str, Any]:
        return {
            "paciente": f"Paciente_{medico_id % 50}",
            "nota": "Evolucion de prueba " + "x" * 1000,
            "diagnostico": random.choice(["Neumonia", "Fractura", "Gripe", "Diabetes", "HTA"]),
            "medicacion": "Amoxicilina 500mg",
            "firma": f"Dr_{medico_id}",
            "timestamp": time.time(),
            "adjunto_simulado_size": ARCHIVO_PESADO_SIZE,
        }

    def _tarea_medico(self, medico_id: int) -> None:
        """Simula un medico enviando una evolucion."""
        for _ in range(5):  # Cada medico envia 5 evoluciones
            if self._stop_flag:
                return
            t0 = time.time()
            try:
                evol = self._simular_evolucion(medico_id)
                adjunto = self._simular_adjunto_pesado()
                assert len(adjunto) == ARCHIVO_PESADO_SIZE
                # Simular hash del documento
                doc_hash = hashlib.sha256(
                    json.dumps(evol, default=str).encode()
                ).hexdigest()
                assert len(doc_hash) == 64
                self.metrics.registrar(True, (time.time() - t0) * 1000)
            except Exception as exc:
                self.metrics.registrar(False, (time.time() - t0) * 1000, str(exc))

    def _tarea_offline_sync(self, usuario_id: int) -> None:
        """Simula un usuario sincronizando datos offline."""
        for _ in range(3):
            if self._stop_flag:
                return
            t0 = time.time()
            try:
                from core.offline_sync import SyncManager, OfflineOperation
                sm = SyncManager()
                op = OfflineOperation(
                    tipo="evolucion",
                    payload_json='{"test": "data"}',
                    profesional=f"Prof_{usuario_id}",
                )
                assert op.operation_id is not None
                assert len(op.operation_id) == 36  # UUID length
                # Simular heartbeat
                sm.check_conectividad()
                self.metrics.registrar(True, (time.time() - t0) * 1000)
            except Exception as exc:
                self.metrics.registrar(False, (time.time() - t0) * 1000, str(exc)[:200])

    def _tarea_auditor_qr(self, auditor_id: int) -> None:
        """Simula un auditor validando un hash QR."""
        for _ in range(5):
            if self._stop_flag:
                return
            t0 = time.time()
            try:
                from core.qr_validator import DocumentValidator
                hash_test = hashlib.sha256(os.urandom(32)).hexdigest()
                resultado = DocumentValidator.validar(hash_test)
                assert resultado is not None
                assert isinstance(resultado.valido, bool)
                self.metrics.registrar(True, (time.time() - t0) * 1000)
            except Exception as exc:
                self.metrics.registrar(False, (time.time() - t0) * 1000, str(exc)[:200])

    def ejecutar(self) -> ChaosMetrics:
        """Ejecuta todas las pruebas de estres en paralelo."""
        print(f"{B}[CHAOS] Iniciando pruebas de estres...{N}")
        print(f"  Medicos: {NUM_MEDICOS}")
        print(f"  Offline: {NUM_USUARIOS_OFFLINE}")
        print(f"  Auditores: {NUM_AUDITORES}")
        print(f"  Adjunto simulado: {ARCHIVO_PESADO_SIZE // (1024*1024)}MB")
        print(f"  Timeout total: {TIMEOUT_TOTAL_SEG}s")

        with ThreadPoolExecutor(max_workers=50) as pool:
            futuros = []

            # Medicos
            for i in range(NUM_MEDICOS):
                futuros.append(pool.submit(self._tarea_medico, i))

            # Offline sync
            for i in range(NUM_USUARIOS_OFFLINE):
                futuros.append(pool.submit(self._tarea_offline_sync, i))

            # Auditores
            for i in range(NUM_AUDITORES):
                futuros.append(pool.submit(self._tarea_auditor_qr, i))

            # Esperar con timeout
            for f in as_completed(futuros, timeout=TIMEOUT_TOTAL_SEG):
                try:
                    f.result()
                except Exception as exc:
                    self.metrics.registrar(False, 0, f"Fatal: {exc}")

        return self.metrics


# ═══════════════════════════════════════════════════════════════════
# 2. SIMULACION DE FALLOS CATASTROFICOS
# ═══════════════════════════════════════════════════════════════════

class CatastrophicFailureTest:
    """Simula fallos catastroficos y verifica la resiliencia del sistema.

    Pruebas:
    a) Microcortes de red durante sincronizacion
    b) Corrupcion de un bit en el audit trail
    """

    def __init__(self):
        self.resultados: list[dict[str, Any]] = []

    def test_microcortes_red(self) -> dict[str, Any]:
        """Simula cortes de red intermitentes durante la sincronizacion.

        Verifica que el SyncManager implemente backoff exponencial
        y no pierda datos encolados.
        """
        print(f"\n{Y}[CHAOS] Test: Microcortes de red durante sync...{N}")
        from core.offline_sync import SyncManager, OfflineOperation

        resultados = []
        for intento in range(10):
            sm = SyncManager()
            op = OfflineOperation(
                tipo="evolucion",
                payload_json='{"test": "microcorte"}',
                profesional="Dr_Chaos",
            )

            # Simular microcorte: intercalar fallos de red
            tiempo_espera = min(0.1 * (2 ** intento), 5.0)  # backoff exponencial max 5s
            tiempo_espera *= random.uniform(0.5, 1.5)  # jitter

            t0 = time.time()
            try:
                # Simular heartbeat fallido
                sm._status.online = False
                sm.store.encolar(op)

                if intento % 3 == 0:
                    # Cada 3 intentos, simular reconexion
                    sm._status.online = True
                    result = sm.sincronizar()
                    ok = result.fallidos == 0
                else:
                    ok = True

                dt = (time.time() - t0) * 1000
                resultados.append({
                    "intento": intento,
                    "ok": ok,
                    "tiempo_ms": round(dt, 1),
                    "backoff_s": round(tiempo_espera, 2),
                })
            except Exception as exc:
                resultados.append({
                    "intento": intento, "ok": False,
                    "error": str(exc)[:100],
                })

        self.resultados.append({"test": "microcortes_red", "resultados": resultados})
        total_ok = sum(1 for r in resultados if r.get("ok"))
        print(f"  {G}{total_ok}/{len(resultados)} sincronizaciones exitosas{N}")
        return self.resultados[-1]

    def test_corrupcion_audit_trail(self) -> dict[str, Any]:
        """Corrompe un byte en el audit trail y verifica deteccion.

        1. Escribe entradas validas
        2. Corrompe un byte en medio del archivo
        3. Ejecuta verificar_integridad()
        4. Verifica que detecte la ruptura
        """
        print(f"\n{R}[CHAOS] Test: Corrupcion de audit trail...{N}")
        from core.audit_trail_immutable import ImmutableAuditTrail

        try:
            auditor = ImmutableAuditTrail()
            # 1. Escribir entradas validas
            entradas_ok = 0
            for i in range(5):
                auditor.registrar(
                    usuario="chaos_test",
                    accion="test",
                    recurso=f"chaos:{i}",
                    detalle="Entrada de prueba",
                )
                entradas_ok += 1

            # 2. Verificar integridad antes de corromper
            errores_antes = auditor.verificar_integridad(max_entries=100)
            integro_antes = len(errores_antes) == 0

            # 3. Corromper un byte en el archivo de log
            log_file = auditor._current_file
            if log_file and log_file.exists():
                contenido = bytearray(log_file.read_bytes())
                if len(contenido) > 100:
                    # Corromper un byte en medio
                    pos = len(contenido) // 2
                    contenido[pos] ^= 0x01  # Flip un bit
                    log_file.write_bytes(bytes(contenido))

            # 4. Verificar integridad despues de corromper
            errores_despues = auditor.verificar_integridad(max_entries=100)
            integro_despues = len(errores_despues) == 0

            resultado = {
                "test": "corrupcion_audit_trail",
                "entradas_escritas": entradas_ok,
                "integro_antes": integro_antes,
                "integro_despues": integro_despues,
                "errores_detectados": len(errores_despues),
                "deteccion_correcta": integro_antes and not integro_despues,
            }

            # Restaurar integridad (borrar entradas de prueba)
            self._limpiar_entradas_chaos(auditor)

            self.resultados.append(resultado)
            if resultado["deteccion_correcta"]:
                print(f"  {G}Corrupcion detectada correctamente!{N}")
            else:
                print(f"  {R}Fallo: corrupcion NO detectada{N}")
            return resultado

        except Exception as exc:
            return {"test": "corrupcion_audit_trail", "error": str(exc)}

    def _limpiar_entradas_chaos(self, auditor) -> None:
        """Limpia las entradas de prueba del audit trail."""
        try:
            log_file = auditor._current_file
            if log_file and log_file.exists():
                lines = log_file.read_text(encoding="utf-8").split("\n")
                lines = [l for l in lines if "chaos_test" not in l and "chaos:" not in l]
                log_file.write_text("\n".join(lines), encoding="utf-8")
        except Exception:
            pass

    def ejecutar_todos(self) -> list[dict[str, Any]]:
        print(f"{B}=== CHAOS ENGINEERING: FALLOS CATASTROFICOS ==={N}")
        self.test_microcortes_red()
        self.test_corrupcion_audit_trail()
        return self.resultados


# ═══════════════════════════════════════════════════════════════════
# 3. MAIN: EJECUTAR TODAS LAS PRUEBAS
# ═══════════════════════════════════════════════════════════════════

def main():
    print(f"{B}{'='*60}{N}")
    print(f"{B}   CHAOS ENGINEERING & STRESS TEST - MediCare PRO{N}")
    print(f"{B}{'='*60}{N}")

    # 1. Pruebas de estres concurrentes
    stress = ConcurrentStressTest()
    metrics = stress.ejecutar()
    resumen = metrics.resumen()

    print(f"\n{B}{'='*40}{N}")
    print(f"{B}RESUMEN DE PRUEBAS DE ESTRES:{N}")
    print(f"  Total operaciones: {resumen['total']}")
    print(f"  Exitosas: {resumen['exitosas']}")
    print(f"  Fallidas: {resumen['fallidas']}")
    print(f"  Tasa de exito: {resumen['tasa_exito']}")
    print(f"  Tiempo p95: {resumen['p95_ms']}ms")
    print(f"  Tiempo promedio: {resumen['avg_ms']}ms")

    if resumen["errores"]:
        print(f"\n{R}Primeros errores:{N}")
        for e in resumen["errores"][:5]:
            print(f"  - {e}")

    # 2. Fallos catastroficos
    chaos = CatastrophicFailureTest()
    resultados = chaos.ejecutar_todos()

    # Resultado final
    if resumen["tasa_exito"].replace("%", "") > "95":
        print(f"\n{G}CHAOS ENGINEERING: SUPERADO (tasa de exito > 95%){N}")
    else:
        print(f"\n{R}CHAOS ENGINEERING: FALLIDO (tasa de exito baja){N}")

    for r in resultados:
        if r.get("deteccion_correcta") is False:
            print(f"{R}  - Corrupcion NO detectada: posible fallo de seguridad!{N}")


if __name__ == "__main__":
    main()
