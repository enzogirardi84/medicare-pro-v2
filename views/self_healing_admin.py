"""Panel de administración del sistema Self-Healing AI."""

from __future__ import annotations

import time
from html import escape

import streamlit as st

from core.app_logging import log_event
from core.alert_toasts import queue_toast
from core.error_tracker import get_recent_errors, get_summary_stats
from core.self_healing import (
    ScanReport,
    get_scan_history,
    run_manual_scan,
    auto_fix_finding,
    rollback_fix,
)
from core.view_helpers import aviso_sin_paciente


def render_self_healing_admin(paciente_sel, mi_empresa, user, rol):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    st.markdown("""
        <div class="mc-hero">
            <h2 class="mc-hero-title">🛠 Self-Healing IA</h2>
            <p class="mc-hero-text">Diagnóstico automático y reparación inteligente del sistema.</p>
        </div>
    """, unsafe_allow_html=True)

    tab_escaneo, tab_hallazgos, tab_historial, tab_errores = st.tabs([
        "🔍 Escaneo", "📋 Hallazgos", "📜 Historial", "⚠️ Errores"
    ])

    with tab_escaneo:
        render_escaneo(paciente_sel)

    with tab_hallazgos:
        render_hallazgos()

    with tab_historial:
        render_historial()

    with tab_errores:
        render_errores()


def render_escaneo(_paciente_sel):
    st.subheader("Diagnóstico del Sistema")

    col1, col2 = st.columns(2)
    with col1:
        full_scan = st.checkbox("Escaneo completo (todos los archivos)", value=False)
    with col2:
        pass

    if st.button("▶️ Iniciar escaneo", use_container_width=True, type="primary"):
        with st.spinner("Analizando código fuente..."):
            t0 = time.time()
            report: ScanReport = run_manual_scan(full=full_scan)
            elapsed = time.time() - t0

        st.success(f"Escaneo completado en {elapsed:.1f}s")

        m1, m2, m3 = st.columns(3)
        m1.metric("Archivos escaneados", report.files_scanned)
        m2.metric("Hallazgos", report.errors_found)
        m3.metric("Duración", f"{report.duration_ms:.0f}ms")

        if report.findings:
            st.subheader("Hallazgos detectados")
            for f in report.findings:
                severity_color = {
                    "critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"
                }.get(f.severity, "⚪")
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1])
                    c1.markdown(f"{severity_color} **{escape(f.title)}**")
                    c1.caption(f"{escape(f.description[:200])}")
                    c2.caption(f"{f.file_path}:{f.line}")
                    if f.suggested_fix and st.button("🩹 Aplicar fix",
                                                      key=f"fix_{f.id}",
                                                      use_container_width=True):
                        ok = auto_fix_finding(f)
                        if ok:
                            queue_toast(f"Fix aplicado: {f.title}")
                            st.rerun()
                        else:
                            log_event("self_healing", f"fix_fallo:{f.title[:60]}")
                            st.error(f"No se pudo aplicar el fix: {f.title}")

    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.caption("Modo pasivo: solo detecta")
    with col_info2:
        st.caption("Dry-run: genera fixes sin aplicar")
    with col_info3:
        st.caption("Activo: aplica fixes que compilan")


def render_hallazgos():
    st.subheader("Hallazgos de escaneos anteriores")
    history = get_scan_history(limit=5)
    if not history:
        st.info("No hay escaneos previos. Ejecutá un escaneo en la pestaña anterior.")
        return

    findings = []
    for entry in history:
        for f in entry.get("findings", []):
            findings.append(f)

    if not findings:
        st.caption("Sin hallazgos en los últimos escaneos.")
        return

    for f in findings:
        severity_color = {
            "critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"
        }.get(f.get("severity", ""), "⚪")
        status_icon = {
            "pending": "⏳", "applied": "✅", "failed": "❌",
            "rolled_back": "↩️", "dismissed": "👁️"
        }.get(f.get("status", "pending"), "⏳")

        with st.container(border=True):
            cols = st.columns([0.5, 3, 1, 1])
            cols[0].markdown(f"{severity_color}{status_icon}")
            cols[1].markdown(f"**{escape(f.get('title', '?'))}**")
            cols[2].caption(f"{f.get('file', '?')}:{f.get('line', '?')}")
            cols[3].caption(f.status)


def render_historial():
    st.subheader("Historial de escaneos")
    history = get_scan_history(limit=50)
    if not history:
        st.info("No hay actividad de self-healing registrada.")
        return

    for entry in reversed(history):
        scan_type = entry.get("type", "scan")
        ts = entry.get("timestamp", 0)
        scanned = entry.get("files_scanned", 0)
        errors = entry.get("errors_found", 0)
        dur = entry.get("duration_ms", 0)
        icon = "🔄" if scan_type == "manual_scan" else "🤖"

        with st.container(border=True):
            cols = st.columns([1, 2, 1, 1])
            cols[0].markdown(f"{icon}")
            cols[1].caption(f"{time.strftime('%d/%m/%Y %H:%M', time.localtime(ts))}")
            cols[2].caption(f"{scanned} archivos")
            cols[3].caption(f"{errors} errores ({dur:.0f}ms)")


def render_errores():
    st.subheader("Errores recientes del sistema")
    stats = get_summary_stats()
    if stats:
        col_e1, col_e2, col_e3 = st.columns(3)
        col_e1.metric("Sin resolver", stats.get("unresolved", 0))
        col_e2.metric("Criticos", stats.get("critical", 0))
        col_e3.metric("Hoy", stats.get("today", 0))

    errors = get_recent_errors(limit=20)
    if not errors:
        st.info("No hay errores registrados recientemente.")
        return

    for e in errors:
        with st.container(border=True):
            st.caption(f"**{e.get('level', '?')}** — {(e.get('message') or '')[:200]}")
