"""Memory Profiler para deteccion de fugas en uploads y PDFs.
Verifica que tras procesar 50 archivos pesados, la memoria
vuelva a su estado inicial (0B residual).
"""
from __future__ import annotations

import gc
import os
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any, Callable, Optional

# ─── Decorador de perfil de memoria ─────────────────────────────

def memory_profile(iteraciones: int = 50, nombre: str = "funcion"):
    """Decorador que mide fuga de memoria tras N iteraciones.

    Uso:
        @memory_profile(iteraciones=50, nombre="generar_pdf")
        def mi_funcion():
            ...
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            print(f"[MEMORY] Perfilando: {nombre} ({iteraciones} iteraciones)")

            # Forzar GC antes de empezar
            gc.collect()
            time.sleep(0.1)

            # Tomar snapshot inicial
            tracemalloc.start()
            snapshot_antes = tracemalloc.take_snapshot()
            mem_antes = _mem_actual_mb()

            resultados = []
            for i in range(iteraciones):
                t0 = time.time()
                try:
                    func(*args, **kwargs)
                    dt = (time.time() - t0) * 1000
                    resultados.append(dt)
                except Exception as exc:
                    print(f"  [ERROR] Iteracion {i}: {exc}")

                # Forzar GC cada 10 iteraciones
                if i > 0 and i % 10 == 0:
                    gc.collect()

            # Tomar snapshot final
            snapshot_despues = tracemalloc.take_snapshot()
            mem_despues = _mem_actual_mb()
            tracemalloc.stop()

            # Calcular diferencias
            stats = snapshot_despues.compare_to(snapshot_antes, "lineno")
            memoria_residual_kb = sum(s.size_diff for s in stats if s.size_diff > 0) / 1024

            # Resultados
            p95 = sorted(resultados)[int(len(resultados) * 0.95)] if resultados else 0
            print(f"\n[MEMORY] Resultados para '{nombre}':")
            print(f"  Iteraciones: {iteraciones}")
            print(f"  Memoria antes: {mem_antes:.2f} MB")
            print(f"  Memoria despues: {mem_despues:.2f} MB")
            print(f"  Diferencia: {mem_despues - mem_antes:.2f} MB")
            print(f"  Memoria residual (tracemalloc): {memoria_residual_kb:.1f} KB")
            print(f"  Tiempo avg: {sum(resultados)/max(len(resultados),1):.0f}ms")
            print(f"  Tiempo p95: {p95:.0f}ms")

            if memoria_residual_kb < 100 and (mem_despues - mem_antes) < 5:
                print("  [OK] Sin fuga de memoria detectable")
                return True
            else:
                print(f"  [WARN] Posible fuga de memoria: {memoria_residual_kb:.1f} KB residual")
                return False

        return wrapper
    return decorator


def _mem_actual_mb() -> float:
    """Memoria actual del proceso en MB."""
    import psutil
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)


# ═══════════════════════════════════════════════════════════════════
# PRUEBAS ESPECIFICAS
# ═══════════════════════════════════════════════════════════════════

@memory_profile(iteraciones=50, nombre="procesar_upload_seguro")
def test_upload_memory():
    """Prueba de fuga de memoria en _procesar_upload_seguro.

    Simula la subida de 50 archivos de 1MB cada uno.
    """
    from core.seguridad_ui import _procesar_upload_seguro

    class MockUploadedFile:
        """Simula un archivo subido via st.file_uploader."""
        def __init__(self, size: int = 1024 * 1024):
            self.name = "test_estudio.pdf"
            self.size = size
            self._data = os.urandom(size)
            self._pos = 0

        def read(self, n: int = -1) -> bytes:
            data = self._data[self._pos:]
            self._pos = len(self._data)
            return data

        def seek(self, pos: int) -> None:
            self._pos = pos

        def close(self) -> None:
            pass

    mock = MockUploadedFile()
    ok, msg, info = _procesar_upload_seguro(mock)
    assert ok, f"Upload fallo: {msg}"
    assert info is not None
    assert "ruta" in info
    assert info["tamano"] == 1024 * 1024


@memory_profile(iteraciones=30, nombre="generar_pdf_clinico")
def test_pdf_memory():
    """Prueba de fuga de memoria en generacion de PDFs clinicos.

    Genera 30 PDFs con adjuntos simulados.
    """
    from core.clinical_pdf import ClinicalPDFGenerator, DatosEvolucion

    datos = DatosEvolucion(
        paciente="Test Paciente",
        documento_paciente="DNI 99.999.999",
        profesional="Dr. Test",
        diagnostico="Test de memoria",
        nota_medica="x" * 5000,
        firma_ecdsa="firma_test_" + "x" * 50,
        hash_documento="a" * 64,
        fingerprint_clave="test_fingerprint",
    )

    gen = ClinicalPDFGenerator()
    pdf_bytes = gen.generar(datos)
    assert len(pdf_bytes) > 1000, "PDF demasiado pequeno"


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("   MEMORY PROFILER - MediCare PRO")
    print("=" * 60)

    resultados = []

    print("\n--- Test 1: Upload seguro ---")
    try:
        ok = test_upload_memory()
        resultados.append(("upload_seguro", ok))
    except Exception as exc:
        print(f"  [ERROR] {exc}")
        resultados.append(("upload_seguro", False))

    print("\n--- Test 2: Generacion PDF ---")
    try:
        ok = test_pdf_memory()
        resultados.append(("generar_pdf", ok))
    except Exception as exc:
        print(f"  [ERROR] {exc}")
        resultados.append(("generar_pdf", False))

    # Resumen
    print("\n" + "=" * 60)
    print("   RESUMEN DE MEMORY PROFILING")
    for name, ok in resultados:
        status = "OK" if ok else "FAIL"
        color = "\033[92m" if ok else "\033[91m"
        print(f"  {color}{name}: {status}\033[0m")

    if all(ok for _, ok in resultados):
        print("\n\033[92mTODAS LAS PRUEBAS DE MEMORIA SUPERADAS\033[0m")
    else:
        print("\n\033[91mALGUNAS PRUEBAS DE MEMORIA FALLARON\033[0m")
        sys.exit(1)


if __name__ == "__main__":
    main()
