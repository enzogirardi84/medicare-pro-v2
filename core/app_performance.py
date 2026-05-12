"""Métricas de rendimiento y guardado pendiente consolidado.

Evita que main.py cargue lógica de procesar_guardado_pendiente directamente.
"""

import time

import streamlit as st

from core.app_logging import log_event
from core.perf_metrics import record_perf, summarize_perf


def procesar_guardado_pendiente_seguro() -> bool:
    """Flush silencioso para guardados agrupados. Protegido contra loops."""
    if not st.session_state.get("_guardar_datos_pendiente"):
        return False
    try:
        from core.feature_flags import GUARDAR_DATOS_MIN_INTERVALO_SEGUNDOS
        min_intervalo = float(GUARDAR_DATOS_MIN_INTERVALO_SEGUNDOS or 0)
    except Exception:
        min_intervalo = 0.0
    if min_intervalo <= 0:
        return False

    ultimo = float(st.session_state.get("_guardar_datos_ultimo_intento_ts", 0.0) or 0.0)
    if ultimo > 0 and (time.monotonic() - ultimo) < min_intervalo:
        return False

    st.session_state["_guardar_datos_pendiente"] = False
    try:
        from core.database import guardar_datos
        guardar_datos(spinner=False, force=True)
    except Exception as e:
        log_event("db", f"procesar_guardado_pendiente_error:{type(e).__name__}")
    return True


def guardar_datos_seguro(spinner: bool = True):
    """Wrapper seguro alrededor de core.database.guardar_datos con reimport fallback."""
    try:
        from core.database import guardar_datos as _gd
        try:
            return _gd(spinner=spinner)
        except TypeError:
            return _gd()
    except Exception as exc:
        log_event("main_guardar", f"guardar_datos_no_disponible:{type(exc).__name__}:{exc}")
        st.warning("No se encontró la función de guardado. Revisá core.database.guardar_datos.")
        return False


def render_metricas_admin_sidebar(rol: str) -> None:
    """Muestra métricas de rendimiento en el sidebar (solo admin)."""
    try:
        from core.utils import es_control_total
        if not es_control_total(rol):
            return
    except Exception:
        return

    with st.sidebar.expander("Rendimiento (ult. 15 min)", expanded=False):
        resumen_perf = summarize_perf(window_seconds=900)
        if not resumen_perf:
            st.caption("Sin métricas todavía.")
        else:
            for ev in sorted(resumen_perf.keys()):
                r = resumen_perf[ev]
                st.caption(
                    f"{ev} | n={r['count']} err={r['errors']} "
                    f"p50={r['p50_ms']}ms p95={r['p95_ms']}ms max={r['max_ms']}ms"
                )
