"""AutoHeal Dashboard — Vista de administracion dentro de la app.
Permite ejecutar escaneos, ver historial de fixes y monitorear la salud del sistema.
"""
from __future__ import annotations

import os
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

from core.app_logging import log_event

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / ".autoheal_memory.db"


def render_autoheal_dashboard():
    """Renderiza el panel de AutoHeal dentro de la app."""
    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">🤖 AutoHeal v2</h2>
            <p class="mc-hero-text">Sistema autonomo de mantenimiento: escanea, corrige y testea el codigo automaticamente.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Verificar memoria
    memory_exists = DB_PATH.exists()
    if memory_exists:
        memory_size = os.path.getsize(DB_PATH)
    else:
        memory_size = 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Memoria", "Activa" if memory_exists else "Inactiva", f"{memory_size/1024:.1f} KB" if memory_exists else "0 KB")
    col2.metric("Escaneos", _get_scan_count())
    col3.metric("Patrones aprendidos", _get_pattern_count())

    # Acciones
    st.divider()
    st.markdown("### Acciones")

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🔍 Ejecutar escaneo ahora", use_container_width=True, type="primary"):
            with st.spinner("Escaneando codigo..."):
                _run_scan()
            st.rerun()

    with c2:
        if st.button("🧹 Limpiar cache de tests", use_container_width=True):
            _clean_test_cache()
            st.toast("Cache limpiado")

    with c3:
        if st.button("📊 Ver estadisticas", use_container_width=True):
            st.session_state["_autoheal_show_stats"] = not st.session_state.get("_autoheal_show_stats", False)

    # Estadisticas
    if st.session_state.get("_autoheal_show_stats", False):
        _render_stats()

    # Historial de fixes
    st.divider()
    st.markdown("### Historial de correcciones")
    _render_fix_history()

    # Ultimo escaneo
    st.divider()
    st.markdown("### Ultimo resultado")
    _render_last_scan()


def _get_scan_count() -> int:
    try:
        import sqlite3
        if not DB_PATH.exists():
            return 0
        conn = sqlite3.connect(str(DB_PATH))
        count = conn.execute("SELECT COUNT(*) FROM scan_history").fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def _get_pattern_count() -> int:
    try:
        import sqlite3
        if not DB_PATH.exists():
            return 0
        conn = sqlite3.connect(str(DB_PATH))
        count = conn.execute("SELECT COUNT(*) FROM learned_patterns").fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def _run_scan():
    """Ejecuta un ciclo completo de autoheal."""
    try:
        script = REPO_ROOT / "scripts" / "autoheal.py"
        if not script.exists():
            st.error("Script autoheal.py no encontrado")
            return

        result = subprocess.run(
            [sys.executable, str(script), "--fix", "--tests", "--learn", "--no-commit"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:
            st.success("Escaneo completado exitosamente")
        else:
            st.warning(f"Escaneo completado con codigo {result.returncode}")

        # Mostrar output relevante
        output = result.stdout + result.stderr
        for line in output.split("\n"):
            if any(x in line for x in ["Hallazgos", "Fixes:", "Tests:", "Patrones", "CRITICAL", "ALTA"]):
                st.caption(line.strip())

    except subprocess.TimeoutExpired:
        st.error("Escaneo excedio el tiempo limite (120s)")
    except Exception as e:
        log_event("autoheal", f"error_scan:{type(e).__name__}")
        st.error(f"Error al ejecutar escaneo: {e}")


def _clean_test_cache():
    """Limpia archivos temporales de tests."""
    import shutil
    cache_dirs = [
        REPO_ROOT / ".pytest_cache",
        REPO_ROOT / ".autoheal_memory.db",
    ]
    for d in cache_dirs:
        if d.exists():
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)
            else:
                d.unlink(missing_ok=True)


def _render_stats():
    """Muestra estadisticas detalladas de la memoria."""
    try:
        import sqlite3
        if not DB_PATH.exists():
            st.info("No hay datos de memoria disponibles")
            return

        conn = sqlite3.connect(str(DB_PATH))

        # Top patrones
        st.markdown("#### Top patrones corregidos")
        patterns = conn.execute(
            "SELECT pattern_name, COUNT(*) as cnt FROM fixes GROUP BY pattern_name ORDER BY cnt DESC LIMIT 10"
        ).fetchall()
        if patterns:
            for p, c in patterns:
                st.caption(f"  • {p}: {c} veces")
        else:
            st.caption("Sin datos")

        # Ultimos escaneos
        st.markdown("#### Historial de escaneos (ultimos 10)")
        scans = conn.execute(
            "SELECT timestamp, total_findings, critical_count, high_count, fixes_applied, tests_passed, tests_failed "
            "FROM scan_history ORDER BY id DESC LIMIT 10"
        ).fetchall()
        if scans:
            for s in scans:
                st.caption(
                    f"  [{s[0][:19]}] Hallazgos:{s[1]} C:{s[2]} H:{s[3]} "
                    f"Fixes:{s[4]} Tests:{s[5]}P/{s[6]}F"
                )
        else:
            st.caption("Sin escaneos registrados")

        conn.close()
    except Exception as e:
        st.caption(f"Error al leer estadisticas: {e}")


def _render_fix_history():
    """Muestra el historial de correcciones aplicadas."""
    try:
        import sqlite3
        if not DB_PATH.exists():
            st.info("No hay historial de correcciones")
            return

        conn = sqlite3.connect(str(DB_PATH))
        fixes = conn.execute(
            "SELECT timestamp, file_path, pattern_name, severity FROM fixes ORDER BY id DESC LIMIT 20"
        ).fetchall()
        conn.close()

        if not fixes:
            st.caption("Aun no se han aplicado correcciones")
            return

        for ts, fp, pat, sev in fixes:
            icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵"}.get(sev, "⚪")
            st.caption(f"{icon} [{ts[:16]}] {pat} en {fp}")
    except Exception as e:
        st.caption(f"Error: {e}")


def _render_last_scan():
    """Muestra el resultado del ultimo escaneo."""
    try:
        import sqlite3
        if not DB_PATH.exists():
            st.info("No hay datos de escaneo")
            return

        conn = sqlite3.connect(str(DB_PATH))
        last = conn.execute(
            "SELECT timestamp, total_findings, critical_count, high_count, fixes_applied, "
            "tests_passed, tests_failed, elapsed_seconds FROM scan_history ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()

        if not last:
            st.caption("Sin escaneos previos")
            return

        ts, total, crit, high, fixes, tp, tf, elapsed = last
        st.caption(f"📅 {ts[:19]}")
        st.caption(f"  Hallazgos: {total} | Criticos: {crit} | Altos: {high}")
        st.caption(f"  Fixes: {fixes} | Tests: {tp}P/{tf}F | Duracion: {elapsed:.1f}s")
    except Exception as e:
        st.caption(f"Error: {e}")
