"""Configuracion de integraciones (IA, APIs externas)."""

from __future__ import annotations

import streamlit as st

from core.app_logging import log_event
from core.database import guardar_datos


def _probar_conexion_ia(provider_display: str, api_key: str, model: str) -> bool:
    """Prueba conexion contra el proveedor de IA."""
    if not api_key.strip():
        st.warning("Primero ingresa una API Key.")
        return False
    provider_map = {
        "OpenAI": ("openai", None, "gpt-4o"),
        "DeepSeek": ("deepseek", "https://api.deepseek.com/v1", "deepseek-chat"),
        "OpenRouter": ("openrouter", "https://openrouter.ai/api/v1", "deepseek/deepseek-v3.2"),
    }
    entry = provider_map.get(provider_display)
    if not entry:
        st.warning(f"Test automatico no soportado para {provider_display}.")
        return False
    internal, base_url, default_model = entry
    clean_key = api_key.strip().split(maxsplit=1)[0]
    if any(ord(c) > 127 for c in clean_key):
        st.warning("La API Key contiene caracteres no validos.")
        return False
    try:
        from openai import OpenAI
        client = OpenAI(api_key=clean_key, base_url=base_url, timeout=30)
        test_model = (model or default_model).strip()
        if any(ord(c) > 127 for c in test_model):
            test_model = default_model
        resp = client.chat.completions.create(
            model=test_model,
            messages=[{"role": "user", "content": "Responde solo: OK"}],
            max_tokens=5, temperature=0,
        )
        content = resp.choices[0].message.content
        if content is not None:
            return "OK" in content.strip()
        return True
    except Exception as e:
        import traceback
        st.error(f"Error de conexion: {e}")
        st.caption(f"Detalle: {traceback.format_exc(limit=1)}")
        return False


def render_integration_settings(is_admin: bool):
    st.header("🔗 Integraciones")
    _s = st.session_state.setdefault("settings_db", {})
    st.caption("Conecta Medicare Pro con servicios externos de IA, facturacion y mas.")

    with st.expander("🤖 Asistente de IA", expanded=True):
        ai_enabled = st.toggle("Habilitar asistente de IA en todo el programa",
                               value=_s.get("integ_ai_enabled", False),
                               help="Activa IA contextual, sugerencias de evolucion, etc.")
        if ai_enabled:
            prov_opts = ["Ninguno", "OpenAI", "Anthropic", "DeepSeek", "OpenRouter"]
            ai_provider = st.selectbox("Proveedor de IA", prov_opts,
                                       index=prov_opts.index(_s.get("integ_ai_provider", "Ninguno")) if _s.get("integ_ai_provider", "Ninguno") in prov_opts else 0)
            ai_key = st.text_input("API Key", type="password", value=_s.get("integ_ai_key", ""), help="Token de API del proveedor seleccionado")
            model_presets = {
                "OpenAI": ["gpt-4o", "gpt-4o-mini", "o3-mini"],
                "Anthropic": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
                "DeepSeek": ["deepseek-chat", "deepseek-reasoner"],
                "OpenRouter": ["deepseek/deepseek-v3.2", "deepseek/deepseek-v4-flash", "deepseek/deepseek-v4-flash:free", "google/gemini-2.0-flash-exp:free", "anthropic/claude-3.5-haiku"],
            }
            preset = model_presets.get(ai_provider, [])
            otros = "Otro"
            if preset:
                sel = st.selectbox("Modelo", preset + [otros], index=0 if _s.get("integ_ai_model") not in preset else preset.index(_s["integ_ai_model"]))
                ai_model = sel if sel != otros else st.text_input("Nombre del modelo personalizado", value=_s.get("integ_ai_model", ""))
            else:
                ai_model = st.text_input("Nombre del modelo (ej: gpt-4o)", value=_s.get("integ_ai_model", ""))

            col_test, col_save = st.columns([1, 1])
            with col_test:
                if st.button("🔄 Probar conexion", use_container_width=True):
                    if ai_provider != "Ninguno" and ai_key:
                        ok = _probar_conexion_ia(ai_provider, ai_key, ai_model)
                        if ok:
                            _s["integ_ai_enabled"] = True
                            _s["integ_ai_provider"] = ai_provider
                            _s["integ_ai_key"] = ai_key
                            _s["integ_ai_model"] = ai_model
                            guardar_datos(spinner=True, force=True)
                            st.success("Configuracion de IA guardada automaticamente.")
                            log_event("settings", "IA configurada y probada exitosamente")
            with col_save:
                if st.button("💾 Guardar configuracion IA", use_container_width=True):
                    _s["integ_ai_enabled"] = ai_enabled
                    _s["integ_ai_provider"] = ai_provider
                    _s["integ_ai_key"] = ai_key
                    _s["integ_ai_model"] = ai_model
                    guardar_datos(spinner=True, force=True)
                    st.success("Configuracion de IA guardada (requiere reinicio)")
                    log_event("settings", "Configuracion de IA guardada manualmente")
