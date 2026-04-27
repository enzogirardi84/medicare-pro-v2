"""
Consulta rapida a Supabase `alertas_pacientes` para sidebar y banner (alertas ROJAS pendientes).

Rendimiento: una sola peticion a Supabase cada N segundos (cache en session_state). Sidebar y banner
reusan el mismo resultado en el mismo rerun. Sin Supabase no hace nada.

Secrets opcionales (`.streamlit/secrets.toml`):
- **APP_PACIENTE_ALERTAS_POLL**: `false` desactiva consultas (sidebar/banner de app paciente).
- **APP_PACIENTE_ALERTAS_TTL_SECONDS**: segundos entre refrescos (default **30**, rango 8–180).
"""

from __future__ import annotations

import time
from html import escape
from typing import Any, Dict, List, Optional

import streamlit as st

from core.alert_toasts import firma_alertas_por_ids, toast_alerta_si_firma_cambia
from core.feature_flags import ALERTAS_APP_PACIENTE_VISIBLE
from core.database import supabase
from core.norm_empresa import norm_empresa_key
from core.utils import es_control_total


def _empresa_key(mi_empresa: str) -> str:
    return norm_empresa_key(mi_empresa) or ""


def _poll_app_alertas_enabled() -> bool:
    try:
        raw = st.secrets.get("APP_PACIENTE_ALERTAS_POLL", True)
    except Exception:
        return True
    if isinstance(raw, str):
        return raw.strip().lower() not in ("0", "false", "no", "off", "")
    return bool(raw)


def _ttl_seconds() -> float:
    try:
        raw = st.secrets.get("APP_PACIENTE_ALERTAS_TTL_SECONDS", 30)
        n = float(raw)
    except Exception:
        return 30.0
    return max(8.0, min(n, 180.0))


def _throttle_fetch(empresa_key: str, fetch_fn):
    """Evita golpear Supabase en cada clic de Streamlit (cada clic = un rerun)."""
    cache_key = "_mc_app_alerta_fetch"
    ts_key = "_mc_app_alerta_ts"
    emp_key = "_mc_app_alerta_emp"
    now = time.time()
    ttl = _ttl_seconds()
    if (
        st.session_state.get(emp_key) == empresa_key
        and now - float(st.session_state.get(ts_key) or 0) < ttl
        and cache_key in st.session_state
    ):
        return st.session_state[cache_key]
    data = fetch_fn()
    st.session_state[cache_key] = data
    st.session_state[ts_key] = now
    st.session_state[emp_key] = empresa_key
    return data


def obtener_alertas_rojas_pendientes(mi_empresa: str) -> List[Dict[str, Any]]:
    if not ALERTAS_APP_PACIENTE_VISIBLE:
        return []
    if supabase is None or not _poll_app_alertas_enabled():
        return []
    ek = _empresa_key(mi_empresa)
    if not ek:
        return []

    def fetch():
        try:
            r = (
                supabase.table("alertas_pacientes")
                .select("id,sintoma,paciente_id,fecha_hora,latitud,longitud")
                .eq("empresa", ek)
                .eq("nivel_urgencia", "Rojo")
                .eq("estado", "Pendiente")
                .order("fecha_hora", desc=True)
                .limit(12)
                .execute()
            )
            return list(r.data or [])
        except Exception:
            return []

    return _throttle_fetch(ek, fetch)


def render_sidebar_bloque_app_paciente(mi_empresa: str, rol: Optional[str]) -> None:
    """Bloque rojo en sidebar si hay triage ROJO pendiente (coordinacion / clinica)."""
    if not ALERTAS_APP_PACIENTE_VISIBLE:
        return
    if supabase is None:
        return
    rows = obtener_alertas_rojas_pendientes(mi_empresa)
    if not rows:
        return

    n = len(rows)
    st.markdown(
        f"""
        <div class="mc-app-paciente-critico" style="
            margin: 10px 0 14px 0;
            padding: 14px 12px;
            border-radius: 12px;
            border: 2px solid #f87171;
            background: linear-gradient(135deg, rgba(127,29,29,0.95), rgba(69,10,10,0.98));
            box-shadow: 0 0 0 1px rgba(248,113,113,0.35), 0 8px 24px rgba(0,0,0,0.35);
            animation: mc-pulse-red 1.8s ease-in-out infinite;
        ">
            <div style="font-size:0.72rem; letter-spacing:0.12em; text-transform:uppercase; color:#fecaca; font-weight:800;">App paciente — riesgo de vida</div>
            <div style="font-size:1.15rem; font-weight:900; color:#fff; margin-top:6px;">{n} alerta(s) ROJA(s) pendiente(s)</div>
            <div style="font-size:0.82rem; color:#fecaca; margin-top:6px;">Abri el modulo <b>Alertas app paciente</b> y asigná respuesta.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if es_control_total(rol):
        for r in rows[:4]:
            sint = escape(str(r.get("sintoma", ""))[:48])
            pid = escape(str(r.get("paciente_id", ""))[:20])
            st.caption(f"· {sint} — id {pid}…")


def render_banner_alertas_criticas_si_aplica(mi_empresa: str) -> None:
    """Franja superior en area principal (solo ROJO pendiente)."""
    if not ALERTAS_APP_PACIENTE_VISIBLE:
        return
    if supabase is None:
        return
    rows = obtener_alertas_rojas_pendientes(mi_empresa)
    if not rows:
        toast_alerta_si_firma_cambia("app_paciente_rojo", "", None)
        return
    n = len(rows)
    firma = firma_alertas_por_ids(rows)
    toast_alerta_si_firma_cambia(
        "app_paciente_rojo",
        firma,
        f"{n} alerta(s) ROJA(s) pendiente(s). Revisá «Alertas app paciente».",
        icon="🚨",
    )
    st.markdown(
        f"""
        <div style="
            padding: 12px 16px;
            margin-bottom: 12px;
            border-radius: 10px;
            background: #7f1d1d;
            color: #fecaca;
            border: 1px solid #f87171;
            font-weight: 700;
            text-align: center;
        ">
            ATENCION: {n} alerta(s) desde app paciente con triage <span style="color:#fff">ROJO</span> (Pendiente).
            Revisá el modulo <b>Alertas app paciente</b>.
        </div>
        """,
        unsafe_allow_html=True,
    )
