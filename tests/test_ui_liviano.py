"""Heurísticas UA/Save-Data sin ejecutar Streamlit."""

from core.ui_liviano import user_agent_desde_contexto, user_agent_es_telefono_movil_probable, user_agent_sugiere_equipo_liviano


def test_user_agent_sugiere_opera_mini():
    assert user_agent_sugiere_equipo_liviano("Opera Mini/9.0") is True


def test_user_agent_sugiere_android_reciente_no_liviano_forzado():
    assert user_agent_sugiere_equipo_liviano("Mozilla/5.0 (Linux; Android 14; Pixel)") is False


def test_user_agent_telefono_android_mobile():
    ua = "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 Mobile Safari/537.36"
    assert user_agent_es_telefono_movil_probable(ua) is True


def test_user_agent_desde_contexto_sin_streamlit_retorna_vacio():
    # Sin st.run: context suele faltar; no debe lanzar.
    assert user_agent_desde_contexto() == ""
