"""Floating AI assistant widget — accessible from every view."""

from __future__ import annotations

from html import escape
import streamlit as st

from core.ai_assistant import is_llm_enabled
from core.ai_context import get_view_help, get_view_tips, get_quick_actions
from core.feature_flags import SELF_HEALING_MODE


def render_ai_floating_assistant(vista_actual: str, paciente_sel: str):
    """Renderiza el asistente contextual accesible desde cualquier vista.

    Fix mobile:
    - Evita panel angosto/cortado en teléfono.
    - Evita columnas 0.9/0.1 que en mobile pueden ocultar el botón.
    - Las acciones rápidas se muestran siempre, aunque la IA no esté configurada.
    - El panel usa ancho completo seguro en pantallas chicas.
    """

    _key = "_ai_fab_open"

    st.markdown("""
        <style>
        .mc-ai-panel {
            background: rgba(15, 23, 42, 0.96);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(99,102,241,0.32);
            border-radius: 16px;
            padding: 14px;
            width: 100%;
            max-width: 420px;
            max-height: 520px;
            overflow-y: auto;
            overflow-x: hidden;
            box-shadow: 0 8px 32px rgba(0,0,0,0.35);
            margin: 8px 0 14px auto;
            box-sizing: border-box;
        }
        .mc-ai-panel h4 {
            color: #a5b4fc;
            margin: 0 0 8px 0;
            font-size: 14px;
        }
        .mc-ai-panel p,
        .mc-ai-panel li {
            color: #cbd5e1;
            font-size: 13px;
            line-height: 1.45;
            margin: 0 0 8px 0;
        }
        .mc-ai-panel small {
            color: #94a3b8;
            font-size: 11px;
        }
        .mc-ai-tip {
            background: rgba(99,102,241,0.12);
            border-left: 3px solid #6366f1;
            padding: 8px 10px;
            margin: 6px 0;
            border-radius: 0 8px 8px 0;
            font-size: 12px;
            color: #e2e8f0;
            overflow-wrap: anywhere;
        }
        .mc-ai-status {
            margin-top: 10px;
            padding-top: 8px;
            border-top: 1px solid rgba(148,163,184,0.16);
        }
        @media (max-width: 768px) {
            .mc-ai-panel {
                width: 100% !important;
                max-width: calc(100vw - 1.3rem) !important;
                max-height: 62vh !important;
                margin: 8px 0 12px 0 !important;
                padding: 12px !important;
                border-radius: 14px !important;
            }
            .mc-ai-panel h4 { font-size: 13px !important; }
            .mc-ai-panel p,
            .mc-ai-panel li { font-size: 12px !important; }
        }
        </style>
    """, unsafe_allow_html=True)

    fab_state = bool(st.session_state.get(_key, False))

    # En mobile las columnas angostas suelen romperse. Usamos botón ancho completo,
    # simple y visible dentro del flujo normal de Streamlit.
    label = "Cerrar asistente clínico" if fab_state else "💡 Abrir asistente clínico"
    if st.button(label, key="_ai_fab_toggle", help="Asistente clínico contextual", use_container_width=True):
        st.session_state[_key] = not fab_state
        st.rerun()

    if not st.session_state.get(_key, False):
        return

    llm_ok = is_llm_enabled()

    st.markdown('<div class="mc-ai-panel">', unsafe_allow_html=True)
    st.markdown(f"<h4>🤖 Asistente clínico — {escape(str(vista_actual or 'Módulo actual'))}</h4>", unsafe_allow_html=True)
    st.markdown(f"<p>{escape(get_view_help(vista_actual))}</p>", unsafe_allow_html=True)

    tips = get_view_tips(vista_actual)
    if tips:
        st.markdown("<h4>💡 Sugerencias</h4>", unsafe_allow_html=True)
        for tip in tips:
            st.markdown(f'<div class="mc-ai-tip">{escape(str(tip))}</div>', unsafe_allow_html=True)

    actions = get_quick_actions(vista_actual)
    if actions:
        st.markdown("<h4>⚡ Acciones rápidas</h4>", unsafe_allow_html=True)
        for i, act in enumerate(actions):
            label_act = str(act.get("label", "Acción"))
            action_id = str(act.get("action", f"accion_{i}"))
            if st.button(label_act, key=f"_ai_qa_{vista_actual}_{action_id}_{i}", use_container_width=True):
                _handle_quick_action(action_id, vista_actual, paciente_sel)
    else:
        st.caption("No hay acciones rápidas para este módulo.")

    if llm_ok:
        st.markdown("<h4>💬 Consultá a la IA</h4>", unsafe_allow_html=True)
        query = st.text_area(
            "Pregunta para el asistente clínico",
            placeholder="Ej: ¿qué datos faltan para una evolución completa?",
            key="_ai_fab_query",
            height=90,
            label_visibility="collapsed",
        )
        if st.button("Consultar IA", key="_ai_fab_ask", use_container_width=True) and query.strip():
            with st.spinner("Consultando…"):
                from core.ai_features import smart_search_ai
                respuesta = smart_search_ai(f"En el módulo {vista_actual}: {query}", paciente_sel)
            if respuesta:
                st.session_state["_ai_fab_answer"] = respuesta
            else:
                from core.ai_features import ai_not_available_warning
                ai_not_available_warning()
                st.session_state["_ai_fab_answer"] = ""
    else:
        st.info("IA no configurada. Las sugerencias y acciones rápidas siguen disponibles sin consumir tokens.")

    if st.session_state.get("_ai_fab_answer"):
        st.markdown(f'<div class="mc-ai-tip">{escape(str(st.session_state["_ai_fab_answer"]))}</div>', unsafe_allow_html=True)
        if st.button("Cerrar respuesta", key="_ai_fab_clear", use_container_width=True):
            st.session_state.pop("_ai_fab_answer", None)
            st.rerun()

    st.markdown(
        f'<div class="mc-ai-status"><small>Modo: {escape(str(SELF_HEALING_MODE))} · '
        f'{"IA conectada" if llm_ok else "IA sin configurar"}</small></div>',
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)


def _handle_quick_action(action: str, vista_actual: str, paciente_sel: str):
    """Maneja acciones rápidas contextuales."""
    from core.app_navigation import set_modulo_actual

    action_map = {
        "nueva_visita": lambda: set_modulo_actual("Visitas y Agenda", rerun=True),
        "agenda_hoy": lambda: set_modulo_actual("Visitas y Agenda", rerun=True),
        "sugerir_evolucion": lambda: set_modulo_actual("Evolucion", rerun=True),
        "nueva_receta": lambda: set_modulo_actual("Recetas", rerun=True),
        "interacciones": lambda: set_modulo_actual("Recetas", rerun=True),
        "registrar_vitales": lambda: set_modulo_actual("Clinica", rerun=True),
    }
    fn = action_map.get(action)
    if fn:
        fn()
    else:
        st.info("Esta acción rápida todavía no tiene navegación asignada.")
