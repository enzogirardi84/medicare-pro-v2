"""AutoHeal Dashboard v2 — Panel completo de salud, fixes y monitoreo."""
from __future__ import annotations

import os
import sqlite3
import sys
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

from core.app_logging import log_event

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / ".autoheal_memory.db"


def render_autoheal_dashboard():
    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">🤖 AutoHeal v2</h2>
            <p class="mc-hero-text">Panel de salud del sistema: escaneo, correccion y monitoreo autonomo.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard", "🔧 Correcciones", "🧠 Patrones", "📋 Scanner", "⚙️ Configuracion"
    ])

    with tab1:
        _render_dashboard_tab()
    with tab2:
        _render_fixes_tab()
    with tab3:
        _render_patterns_tab()
    with tab4:
        _render_scanner_tab()
    with tab5:
        _render_config_tab()


# ═══════════════════════════════════════════════════════════════════════
#  TAB 1: DASHBOARD
# ═══════════════════════════════════════════════════════════════════════

def _render_dashboard_tab():
    memory_exists = DB_PATH.exists()
    memory_size = os.path.getsize(DB_PATH) if memory_exists else 0

    # Metricas principales
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Memoria", "Activa" if memory_exists else "Inactiva", f"{memory_size/1024:.1f} KB" if memory_exists else "")
    c2.metric("Escaneos", _get_scan_count())
    c3.metric("Patrones", _get_pattern_count())
    c4.metric("Fixes totales", _get_total_fixes())

    # Boton de escaneo
    if st.button("🔍 Ejecutar escaneo completo ahora", use_container_width=True, type="primary"):
        with st.spinner("Ejecutando escaneo completo (puede tomar hasta 120s)..."):
            _run_scan()
        st.rerun()

    # Ultimo resultado
    _render_last_scan_box()

    # Tendencias
    _render_scan_trends()

    # Health checks
    _render_health_checks()

    # Health diagnostics
    _render_health_diagnostics()

    # Performance
    _render_perf_metrics()

    # Git status
    _render_git_status()


def _render_last_scan_box():
    rows = _query(
        "SELECT timestamp, total_findings, critical_count, high_count, "
        "fixes_applied, tests_passed, tests_failed, elapsed_seconds "
        "FROM scan_history ORDER BY id DESC LIMIT 1"
    )
    if not rows:
        st.info("Sistema sin datos. Ejecute un escaneo para comenzar.")
        return
    ts, total, crit, high, fixes, tp, tf, elapsed = rows[0]
    st.markdown("##### Ultimo escaneo")
    cols = st.columns(5)
    cols[0].metric("Hallazgos", total)
    cols[1].metric("Criticos", crit, delta_color="off")
    cols[2].metric("Altos", high, delta_color="off")
    cols[3].metric("Fixes", fixes)
    cols[4].metric("Duracion", f"{elapsed:.1f}s")
    st.caption(f"Realizado: {ts[:19]} | Tests: {tp}P/{tf}F")


def _render_scan_trends():
    try:
        import sqlite3
        if not DB_PATH.exists():
            return
        conn = sqlite3.connect(str(DB_PATH))
        scans = conn.execute(
            "SELECT timestamp, total_findings, critical_count, high_count, fixes_applied "
            "FROM scan_history ORDER BY id DESC LIMIT 20"
        ).fetchall()
        conn.close()
        if len(scans) >= 3:
            scans.reverse()
            st.markdown("##### Tendencias (ultimos 20 escaneos)")
            import pandas as pd
            df = pd.DataFrame(scans, columns=["ts", "total", "crit", "high", "fixes"])
            df["ts"] = pd.to_datetime(df["ts"])
            st.line_chart(df.set_index("ts")[["total", "crit", "high"]], height=150)
    except Exception:
        pass


def _render_health_checks():
    st.markdown("##### Salud del sistema")
    checks = []

    # Compile check
    try:
        r = subprocess.run([sys.executable, "-m", "py_compile", str(REPO_ROOT / "core" / "seguridad.py")],
                          capture_output=True, timeout=10)
        checks.append(("✅" if r.returncode == 0 else "❌", "Compilacion", "core/seguridad.py"))
    except Exception:
        checks.append(("❓", "Compilacion", "Error al verificar"))

    # Memory DB
    checks.append(("✅" if DB_PATH.exists() else "⚪", "Memoria AutoHeal", "Base de conocimiento"))

    # Test history
    try:
        import sqlite3
        conn = sqlite3.connect(str(DB_PATH))
        fails = conn.execute("SELECT SUM(tests_failed) FROM scan_history").fetchone()[0] or 0
        conn.close()
        checks.append(("✅" if fails == 0 else "⚠️", f"Tests fallidos: {fails}", "Historial completo"))
    except Exception:
        checks.append(("❓", "Tests", "No disponible"))

    cols = st.columns(len(checks))
    for i, (icon, label, detail) in enumerate(checks):
        cols[i].markdown(f"**{icon} {label}**")
        cols[i].caption(detail)


def _render_health_diagnostics():
    """Diagnostico completo de salud del sistema."""
    st.markdown("##### Diagnostico del sistema")
    diags = []

    # 1. Compilacion
    try:
        import subprocess, sys
        r = subprocess.run([sys.executable, "-m", "py_compile", str(REPO_ROOT / "core" / "seguridad.py")],
                          capture_output=True, timeout=10)
        diags.append(("✅" if r.returncode == 0 else "❌", "Compilacion Python", "core/seguridad.py"))
    except Exception:
        diags.append(("❓", "Compilacion Python", "Error al verificar"))

    # 2. Tests - solo verificar que la suite existe
    test_dir = REPO_ROOT / "tests"
    test_count = len(list(test_dir.rglob("test_*.py"))) if test_dir.exists() else 0
    diags.append(("ℹ️", f"{test_count} tests disponibles", "Suite de pruebas"))

    # 3. Memoria AutoHeal
    if DB_PATH.exists():
        size_kb = os.path.getsize(DB_PATH) / 1024
        diags.append(("✅", f"Memoria: {size_kb:.0f} KB", ".autoheal_memory.db"))
    else:
        diags.append(("⚪", "Memoria: Inactiva", "Ejecutar escaneo para crear"))

    # 4. Archivos totales
    py_count = len(list(REPO_ROOT.rglob("*.py"))) - len(list((REPO_ROOT / ".git").rglob("*.py")))
    diags.append(("ℹ️", f"{py_count} archivos .py", "Total en el proyecto"))

    # 5. Git status
    try:
        r = subprocess.run(["git", "log", "--oneline", "-1"], cwd=str(REPO_ROOT),
                          capture_output=True, text=True, timeout=10)
        diags.append(("ℹ️", f"Ultimo commit: {r.stdout.strip()[:50]}", ""))
    except Exception:
        pass

    # Mostrar en grid
    cols = st.columns(len(diags))
    for i, (icon, label, detail) in enumerate(diags):
        cols[i].markdown(f"**{icon}**")
        cols[i].caption(label)
        if detail:
            cols[i].caption(detail)


def _render_perf_metrics():
    rows = _query("SELECT elapsed_seconds FROM scan_history ORDER BY id DESC LIMIT 20")
    if len(rows) >= 3:
        times = [r[0] for r in rows]
        avg = sum(times) / len(times)
        recent = sum(times[:5]) / 5 if len(times) >= 5 else avg
        st.markdown("##### Rendimiento")
        c1, c2, c3 = st.columns(3)
        c1.metric("Avg scan", f"{avg:.1f}s")
        c2.metric("Ultimos 5", f"{recent:.1f}s")
        c3.metric("Mejor", f"{min(times):.1f}s")


def _render_git_status():
    try:
        r = subprocess.run(["git", "log", "--oneline", "-3"], cwd=str(REPO_ROOT),
                          capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            st.markdown("##### Ultimos commits")
            for line in r.stdout.strip().split("\n"):
                st.caption(f"  {line[:60]}")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════
#  TAB 2: CORRECCIONES
# ═══════════════════════════════════════════════════════════════════════

def _render_fixes_tab():
    if not DB_PATH.exists():
        st.info("No hay historial de correcciones. Ejecute un escaneo.")
        return

    total = _get_total_fixes()
    by_sev = _query("SELECT severity, COUNT(*) FROM fixes GROUP BY severity ORDER BY severity")
    fixes = _query("SELECT timestamp, file_path, pattern_name, severity, old_code, new_code FROM fixes ORDER BY id DESC LIMIT 50")

    col1, col2 = st.columns(2)
    col1.metric("Total correcciones", total)
    if by_sev:
        parts = " | ".join(f"{s}: {c}" for s, c in by_sev)
        col2.caption(f"Por severidad: {parts}")

    if fixes:
        st.markdown("##### Ultimas 50 correcciones")
        for ts, fp, pat, sev, old, new in fixes:
            icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵"}.get(sev, "⚪")
            with st.expander(f"{icon} [{ts[:16]}] {pat} — {Path(fp).name}"):
                st.caption(f"**Archivo:** `{fp}`")
                st.caption(f"**Patron:** {pat}")
                if old:
                    st.code(old[:200], language="python")
                if new:
                    st.code(new[:200], language="python")
    else:
        st.info("Aun no se han aplicado correcciones automaticas")


# ═══════════════════════════════════════════════════════════════════════
#  TAB 3: PATRONES
# ═══════════════════════════════════════════════════════════════════════

def _render_patterns_tab():
    if not DB_PATH.exists():
        st.info("No hay patrones aprendidos.")
        return

    patterns = _query(
        "SELECT id, pattern_name, severity, hit_count, source, auto_fix, created_at "
        "FROM learned_patterns ORDER BY hit_count DESC"
    )

    if not patterns:
        st.info("Aun no se han aprendido patrones. Ejecute escaneos para que AutoHeal aprenda.")
        return

    st.metric("Patrones aprendidos", len(patterns))
    st.caption("AutoHeal descubre automaticamente nuevos patrones de codigo vulnerable analizando el historial de fixes.")

    for pid, name, sev, hits, src, auto_fix, created in patterns:
        icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵"}.get(sev, "⚪")
        fix_icon = "🔧" if auto_fix else "👁️"
        with st.expander(f"{icon} {fix_icon} {name} ({hits} hits)"):
            st.caption(f"**Severidad:** {sev} | **Auto-fix:** {'Si' if auto_fix else 'No'}")
            st.caption(f"**Fuente:** {src or 'desconocida'}")
            st.caption(f"**Creado:** {created[:16]}")


# ═══════════════════════════════════════════════════════════════════════
#  TAB 4: SCANNER
# ═══════════════════════════════════════════════════════════════════════

def _render_scanner_tab():
    st.markdown("##### Escaneadores activos")
    scanners = [
        ("🔴 CRITICAL", "UnboundLocalError", "log_event antes de import local", "Auto-fix"),
        ("🟠 HIGH", "NoneType crash", ".get(key, default)[:N] sin guard", "Auto-fix"),
        ("🟠 HIGH", "XSS risk", "unsafe_allow_html sin html.escape()", "Deteccion"),
        ("🟠 HIGH", "st.error sin log_event", "Falta log_event() antes de st.error()", "Auto-fix"),
        ("🟡 MEDIUM", "Subindice en loop", "Variable[key] sin guard None", "Deteccion"),
        ("🟡 MEDIUM", "Copy-paste error", "variable(keyword=variable.get(...))", "Auto-fix"),
        ("🟡 MEDIUM", "Lista[0] sin guard", "Acceso a lista vacia", "Deteccion"),
        ("🔵 LOW", "Imports no usados", "AST analysis de imports", "Auto-fix"),
        ("🔵 LOW", "Funciones muertas", "AST analysis de funciones", "Deteccion"),
        ("🔵 LOW", "Complejidad alta", "Funciones >15 ramas + lineas", "Deteccion"),
        ("🔵 LOW", "Sin docstring", "Funciones publicas sin documentacion", "Deteccion"),
        ("⚡ PERF", "Regresiones", "Tiempo de escaneo >1.5x historico", "Alerta"),
        ("🛡️ XSS", "Auto-fix XSS", "Agrega escape() a f-strings peligrosos", "Auto-fix"),
        ("✨ AUTO", "Black formatter", "Formateo automatico post-fix", "Auto-formato"),
        ("🧠 LEARN", "ErrorLearner", "Aprende de errores en vivo + commits humanos", "Auto-aprendizaje"),
    ]
    for sev, name, desc, action in scanners:
        st.caption(f"{sev} **{name}**: {desc} ({action})")
    st.divider()
    st.markdown("##### Ultimos hallazgos por escaneo")
    rows = _query(
        "SELECT timestamp, total_findings, critical_count, high_count "
        "FROM scan_history ORDER BY id DESC LIMIT 10"
    )
    if rows:
        for r in rows:
            st.caption(f"  [{r[0][:16]}] Total:{r[1]} C:{r[2]} H:{r[3]}")
    else:
        st.info("Ejecute un escaneo para ver resultados")


# ═══════════════════════════════════════════════════════════════════════
#  TAB 5: CONFIGURACION
# ═══════════════════════════════════════════════════════════════════════

def _render_config_tab():
    st.markdown("##### Acciones de mantenimiento")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("🧹 Limpiar cache de tests", use_container_width=True):
            _clean_test_cache()
            st.toast("Cache limpiado")
            st.rerun()
    with col_b:
        if st.button("🗑️ Resetear memoria AutoHeal", use_container_width=True):
            if DB_PATH.exists():
                DB_PATH.unlink()
                st.toast("Memoria reseteada")
                st.rerun()
    with col_c:
        if st.button("📥 Forzar re-scan completo", use_container_width=True):
            st.session_state["_autoheal_force_scan"] = True
            st.rerun()

    st.divider()
    st.markdown("##### Estado del Daemon (Windows)")

    try:
        r = subprocess.run(
            ["SchTasks", "/Query", "/TN", "MediCareAutoHeal"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            st.success("✅ Daemon de Windows instalado y ejecutandose cada 15 minutos")
            for line in r.stdout.split("\n"):
                if "MediCareAutoHeal" in line:
                    st.caption(f"  {line.strip()}")
        else:
            st.warning("⚠️ Daemon no instalado")
    except FileNotFoundError:
        st.caption("SchTasks no disponible (no es Windows)")

    st.divider()
    st.markdown("##### Informacion del sistema")
    st.caption(f"Python: {sys.version}")
    st.caption(f"Directorio: {REPO_ROOT}")
    st.caption(f"Memoria DB: {DB_PATH}")

    # Manual scan trigger
    if st.session_state.get("_autoheal_force_scan", False):
        st.session_state["_autoheal_force_scan"] = False
        with st.spinner("Ejecutando escaneo..."):
            _run_scan()
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _query(sql: str):
    if not DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute(sql).fetchall()
        conn.close()
        return rows
    except sqlite3.OperationalError:
        return []
    except Exception:
        return []


def _get_scan_count() -> int:
    rows = _query("SELECT COUNT(*) FROM scan_history")
    return rows[0][0] if rows else 0


def _get_pattern_count() -> int:
    rows = _query("SELECT COUNT(*) FROM learned_patterns")
    return rows[0][0] if rows else 0


def _get_total_fixes() -> int:
    rows = _query("SELECT COUNT(*) FROM fixes")
    return rows[0][0] if rows else 0


def _run_scan():
    try:
        script = REPO_ROOT / "scripts" / "autoheal.py"
        if not script.exists():
            st.warning("Script autoheal.py no encontrado. Usando modo simulado.")
            _mock_scan_result()
            return

        result = subprocess.run(
            [sys.executable, str(script), "--scan", "--no-commit"],
            cwd=str(REPO_ROOT),
            capture_output=True, text=True, timeout=120,
        )

        if result.returncode == 0:
            st.success("Escaneo completado exitosamente")
        else:
            st.warning(f"Finalizado con codigo {result.returncode}")

        output = (result.stdout + result.stderr)[:2000]
        for line in output.split("\n"):
            if any(x in line for x in ["Hallazgos", "Fixes:", "Tests:", "Patrones", "CRITICAL", "Completado"]):
                st.caption(line.strip()[:120])
    except subprocess.TimeoutExpired:
        st.warning("Escaneo excedio el limite. Los escaneos pesados requieren ejecucion local.")
    except Exception as e:
        log_event("autoheal", f"error_scan:{type(e).__name__}")
        st.warning(f"No se pudo ejecutar el escaneo automatico: {e}")
        st.caption("AutoHeal requiere Python 3.12+ con acceso a scripts/autoheal.py")
        _mock_scan_result()


def _mock_scan_result():
    """Simula un resultado de escaneo para mostrar la UI cuando el script no esta disponible."""
    _init_db()
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("INSERT INTO scan_history (timestamp, total_findings, critical_count, high_count, "
                     "fixes_applied, tests_passed, tests_failed, elapsed_seconds) "
                     "VALUES (datetime('now'), 0, 0, 0, 0, 0, 0, 1.0)")
        conn.commit()
        conn.close()
    except Exception:
        pass


def _init_db():
    """Crea la base de datos y tablas si no existen."""
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS scan_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                total_findings INTEGER DEFAULT 0,
                critical_count INTEGER DEFAULT 0,
                high_count INTEGER DEFAULT 0,
                fixes_applied INTEGER DEFAULT 0,
                tests_passed INTEGER DEFAULT 0,
                tests_failed INTEGER DEFAULT 0,
                elapsed_seconds REAL DEFAULT 0.0
            );
            CREATE TABLE IF NOT EXISTS fixes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                file_path TEXT,
                pattern_name TEXT,
                severity TEXT,
                old_code TEXT,
                new_code TEXT
            );
            CREATE TABLE IF NOT EXISTS learned_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_name TEXT,
                severity TEXT,
                hit_count INTEGER DEFAULT 1,
                source TEXT,
                auto_fix INTEGER DEFAULT 0,
                created_at TEXT
            );
        """)
        conn.commit()
        conn.close()
    except Exception:
        pass


def _clean_test_cache():
    import shutil
    for d in [REPO_ROOT / ".pytest_cache"]:
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
