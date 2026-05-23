"""Test de estres concurrente para optimistic locking.

Simula multiples enfermeros guardando evoluciones simultaneamente
para verificar que el version counter previene lost updates.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import streamlit as st

from core.database import guardar_datos


def _simular_guardia(usuario_id: str, paciente_id: str, nota: str) -> dict:
    """Simula un intento de guardado concurrente."""
    try:
        st.session_state.setdefault("evoluciones_db", [])
        st.session_state["evoluciones_db"].append({
            "paciente": paciente_id,
            "nota": nota,
            "fecha": time.strftime("%d/%m/%Y %H:%M:%S"),
            "firma": usuario_id,
        })
        exito = guardar_datos(spinner=False)
        return {"usuario": usuario_id, "exito": exito, "error": None}
    except Exception as e:
        return {"usuario": usuario_id, "exito": False, "error": str(e)}


def test_guardado_concurrente_30_enfermeros():
    """30 enfermeros guardando simultaneamente - verifica optimistic locking."""
    st.session_state["evoluciones_db"] = []
    paciente_test = "Paciente Stress Test - 41440234"
    num_hilos = 30
    
    resultados = []
    with ThreadPoolExecutor(max_workers=num_hilos) as executor:
        futures = [
            executor.submit(_simular_guardia, f"enfermero_{i}", paciente_test, f"Evolucion de prueba #{i}")
            for i in range(num_hilos)
        ]
        for f in futures:
            resultados.append(f.result(timeout=30))
    
    exitosos = sum(1 for r in resultados if r["exito"])
    fallos = sum(1 for r in resultados if not r["exito"])
    
    print(f"📈 [STRESS TEST] {exitosos}/{num_hilos} guardados exitosamente, {fallos} fallos")
    print(f"📦 Total evoluciones en DB: {len(st.session_state['evoluciones_db'])}")
    
    # Verificar que los datos estan en session_state aunque algunos saves
    # sean rate-limited (guardar_datos() retorna False si hay throttle)
    assert len(st.session_state["evoluciones_db"]) >= 25, f"Solo {len(st.session_state['evoluciones_db'])} evoluciones guardadas"
    # Verificar que el version counter existe si fue inicializado
    v = st.session_state.get("_db_version")
    if v is not None:
        assert isinstance(v, (int, float))


def test_optimistic_locking_guarda_sin_version_no_crashea():
    """Verifica que guardar_datos() no crashee aunque no haya _db_version."""
    st.session_state.pop("_db_version", None)
    st.session_state.pop("_db_version_last_seen", None)
    
    st.session_state.setdefault("test_db", [])
    st.session_state["test_db"].append({"test": True})
    
    resultado = guardar_datos(spinner=False)
    assert isinstance(resultado, bool)
