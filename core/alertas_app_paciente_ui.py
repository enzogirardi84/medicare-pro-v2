"""
Consulta rapida a Supabase `alertas_pacientes` para sidebar y banner (alertas rojas pendientes).

Rendimiento: una sola peticion a Supabase cada N segundos (cache en session_state). Sidebar y banner
reusan el mismo resultado en el mismo rerun. Sin Supabase no hace nada.

Secrets opcionales (`.streamlit/secrets.toml`):
- **APP_PACIENTE_ALERTAS_POLL**: `false` desactiva consultas (sidebar/banner de app paciente).
- **APP_PACIENTE_ALERTAS_TTL_SECONDS**: segundos entre refrescos (default **30**, rango 8-180).
"""

from __future__ import annotations

import time
from datetime import datetime
from html import escape
from typing import Any, Dict, List, Optional

import streamlit as st

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


def _formatear_fecha_alerta(valor: Any) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return "Sin horario informado"
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).strftime("%d/%m %H:%M")
    except Exception:
        return texto[:16]


def render_sidebar_bloque_app_paciente(mi_empresa: str, rol: Optional[str]) -> None:
    """Bloque rojo en sidebar si hay triage rojo pendiente (coordinacion / clinica)."""
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
            <div style="font-size:0.72rem; letter-spacing:0.12em; text-transform:uppercase; color:#fecaca; font-weight:800;">App paciente - riesgo de vida</div>
            <div style="font-size:1.15rem; font-weight:900; color:#fff; margin-top:6px;">{n} alerta(s) ROJA(s) pendiente(s)</div>
            <div style="font-size:0.82rem; color:#fecaca; margin-top:6px;">Abri el modulo <b>Alertas app paciente</b> y asigna respuesta.</div>
        </div>
        <style>
        @keyframes mc-pulse-red {{
            0%, 100% {{ box-shadow: 0 0 0 1px rgba(248,113,113,0.35), 0 8px 24px rgba(0,0,0,0.35); }}
            50% {{ box-shadow: 0 0 0 3px rgba(248,113,113,0.55), 0 10px 28px rgba(220,38,38,0.25); }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    if es_control_total(rol):
        for row in rows[:4]:
            sint = escape(str(row.get("sintoma", ""))[:48])
            pid = escape(str(row.get("paciente_id", ""))[:20])
            st.caption(f"- {sint} | id {pid}")


def render_banner_alertas_criticas_si_aplica(mi_empresa: str) -> None:
    """Franja superior en area principal (solo rojo pendiente)."""
    if supabase is None:
        return
    rows = obtener_alertas_rojas_pendientes(mi_empresa)
    if not rows:
        return

    n = len(rows)
    preview_cards = []
    for row in rows[:3]:
        sintoma = escape(str(row.get("sintoma", "Sin sintoma informado"))[:72])
        paciente_id = escape(str(row.get("paciente_id", "S/D"))[:28])
        horario = escape(_formatear_fecha_alerta(row.get("fecha_hora")))
        preview_cards.append(
            f"""
            <div class="mc-critical-banner-preview">
                <div class="mc-critical-banner-preview-top">
                    <span class="mc-critical-banner-preview-badge">Paciente {paciente_id}</span>
                    <span class="mc-critical-banner-preview-time">{horario}</span>
                </div>
                <div class="mc-critical-banner-preview-title">{sintoma}</div>
                <div class="mc-critical-banner-preview-copy">Abrir Alertas app paciente y coordinar respuesta clinica inmediata.</div>
            </div>
            """
        )

    extra = ""
    if n > 3:
        extra = f'<div class="mc-critical-banner-more">+{n - 3} alerta(s) adicional(es) esperando revision</div>'

    st.markdown(
        f"""
        <div class="mc-critical-banner" role="alert" aria-live="polite">
            <div class="mc-critical-banner-main">
                <span class="mc-critical-banner-kicker">Atencion prioritaria</span>
                <h3 class="mc-critical-banner-title">{n} alerta(s) roja(s) pendiente(s)</h3>
                <p class="mc-critical-banner-copy">
                    Hay eventos reportados desde la app del paciente con triage rojo. Revisa el modulo
                    <strong>Alertas app paciente</strong> y organiza una respuesta inmediata.
                </p>
                <div class="mc-critical-banner-chip-row">
                    <span class="mc-chip mc-chip-danger">Respuesta urgente</span>
                    <span class="mc-chip">Empresa actual</span>
                    <span class="mc-chip">Actualizacion automatica</span>
                </div>
            </div>
            <div class="mc-critical-banner-side">
                {''.join(preview_cards)}
                {extra}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
