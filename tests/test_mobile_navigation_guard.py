from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mobile_nav_usa_selector_estable_para_evitar_vista_en_blanco():
    source = (ROOT / "core" / "app_navigation.py").read_text(encoding="utf-8")
    start = source.index("def render_module_nav")
    end = source.index("def _get_render_fn", start)
    body = source[start:end]

    assert "mc-module-linkbar" in body
    assert 'href="?login=1&modulo=' in body
    assert "st.selectbox(" not in body
    assert "_render_modulos_sub(" not in body
    query_nav = source[source.index("def procesar_query_params_navegacion"):source.index("def resolve_menu_for_role")]
    assert "\n        st.rerun()" not in query_nav


def test_modulos_clinicos_sin_paciente_muestran_estado_vacio():
    source = (ROOT / "main_medicare.py").read_text(encoding="utf-8")

    assert "MODULOS_REQUIEREN_PACIENTE" in source
    assert "_render_estado_vacio_sin_paciente(menu_set)" in source
    assert "render_current_view(" in source
    assert "Admision" not in source[
        source.index("MODULOS_REQUIEREN_PACIENTE"):
        source.index("def _ir_a_modulo_desde_estado_vacio")
    ]
