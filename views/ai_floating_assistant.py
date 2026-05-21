"""Floating AI assistant widget — accessible from every view."""

from __future__ import annotations

import streamlit as st

from core.ai_assistant import is_llm_enabled
from core.ai_context import get_view_help, get_view_tips, get_quick_actions
from core.feature_flags import SELF_HEALING_MODE


def render_ai_floating_assistant(vista_actual: str, paciente_sel: str):
    """Renderiza el asistente flotante accesible desde cualquier vista."""

    _key = "_ai_fab_open"

    st.markdown("""
        <style>
        .ai-fab-container {
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 8px;
        }
        .ai-fab-btn {
            width: 56px;
            height: 56px;
            border-radius: 50%;
            background: linear-gradient(135deg, #6366f1, #8b5cf6);
            border: none;
            color: white;
            font-size: 24px;
            cursor: pointer;
            box-shadow: 0 4px 16px rgba(99,102,241,0.4);
            transition: transform 0.2s, box-shadow 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .ai-fab-btn:hover {
            transform: scale(1.1);
            box-shadow: 0 6px 24px rgba(99,102,241,0.6);
        }
        .ai-fab-panel {
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(99,102,241,0.3);
            border-radius: 16px;
            padding: 16px;
            width: 360px;
            max-height: 500px;
            overflow-y: auto;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            margin-bottom: 8px;
        }
        .ai-fab-panel h4 {
            color: #a5b4fc;
            margin: 0 0 8px 0;
            font-size: 14px;
        }
        .ai-fab-panel p, .ai-fab-panel li {
            color: #cbd5e1;
            font-size: 13px;
            line-height: 1.5;
        }
        .ai-fab-panel small {
            color: #64748b;
            font-size: 11px;
        }
        .ai-fab-panel .tip {
            background: rgba(99,102,241,0.1);
            border-left: 3px solid #6366f1;
            padding: 8px 12px;
            margin: 6px 0;
            border-radius: 0 8px 8px 0;
            font-size: 12px;
            color: #e2e8f0;
        }
        @media (max-width: 768px) {
            .ai-fab-panel { width: 300px; right: 8px; }
            .ai-fab-btn { width: 48px; height: 48px; font-size: 20px; }
        }
        </style>
    """, unsafe_allow_html=True)

    fab_state = st.session_state.get(_key, False)

    col_spacer, col_btn = st.columns([0.9, 0.1])
    with col_btn:
        if st.button("💡", key="_ai_fab_toggle", help="Asistente IA contextual"):
            st.session_state[_key] = not fab_state
            st.rerun()

    if not st.session_state.get(_key, False):
        return

    llm_ok = is_llm_enabled()

    with st.container():
        st.markdown(f"""<div class="ai-fab-panel">""", unsafe_allow_html=True)

        st.markdown(f"<h4>🤖 Asistente IA — {vista_actual}</h4>", unsafe_allow_html=True)

        st.markdown(f"<p>{get_view_help(vista_actual)}</p>", unsafe_allow_html=True)

        tips = get_view_tips(vista_actual)
        if tips:
            st.markdown("<h4>💡 Sugerencias</h4>", unsafe_allow_html=True)
            for tip in tips:
                st.markdown(f"""<div class="tip">{tip}</div>""", unsafe_allow_html=True)

        actions = get_quick_actions(vista_actual)
        if actions:
            st.markdown("<h4>⚡ Acciones rápidas</h4>", unsafe_allow_html=True)
            for act in actions:
                if st.button(act["label"], key=f"_ai_qa_{act['action']}", use_container_width=True):
                    _handle_quick_action(act["action"], vista_actual, paciente_sel)

        if llm_ok:
            st.markdown("<h4>💬 Consultá a la IA</h4>", unsafe_allow_html=True)
            query = st.text_input("Hacé una pregunta sobre este módulo",
                                  placeholder="Ej: ¿cómo registro un estudio?",
                                  key="_ai_fab_query",
                                  label_visibility="collapsed")
            if query:
                with st.spinner("..."):
                    from core.ai_features import smart_search_ai
                    respuesta = smart_search_ai(f"En el módulo {vista_actual}: {query}", paciente_sel)
                if respuesta:
                    st.session_state["_ai_fab_answer"] = respuesta
                else:
                    from core.ai_features import ai_not_available_warning
                    ai_not_available_warning()
                    st.session_state["_ai_fab_answer"] = ""

        if st.session_state.get("_ai_fab_answer"):
            st.markdown(f"""<div class="tip">{st.session_state['_ai_fab_answer']}</div>""", unsafe_allow_html=True)
            if st.button("Cerrar respuesta", key="_ai_fab_clear", use_container_width=True):
                st.session_state.pop("_ai_fab_answer", None)
                st.rerun()

        st.markdown(f"""<small>Modo: {SELF_HEALING_MODE} · {'IA conectada' if llm_ok else 'IA sin configurar'}</small>""", unsafe_allow_html=True)
        st.markdown(f"""</div>""", unsafe_allow_html=True)


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
