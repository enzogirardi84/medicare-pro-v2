from unittest.mock import MagicMock, patch

import pytest

import core.auth as auth


def test_render_login_prioriza_desafio_2fa_activo():
    sentinel = RuntimeError("stop-called")

    with patch.object(auth, "_render_bloque_verificacion_email_2fa", return_value=True) as mock_2fa:
        with patch.object(auth, "st") as mock_st:
            mock_st.session_state = {}
            mock_st.stop.side_effect = sentinel

            with pytest.raises(RuntimeError, match="stop-called"):
                auth.render_login()

            assert mock_2fa.called is True
            assert mock_st.session_state["logeado"] is False


def test_auth_strip_pwreset_url_si_hay_param_limpia_y_avisa():
    with patch.object(auth, "st") as mock_st:
        mock_st.query_params = {"pwreset": "tok123"}
        mock_st.session_state = {"mc_pwreset_token": "old", "mc_auth_mode_radio": "recover"}
        with patch.object(auth, "_auth_strip_pwreset_query_param") as strip_q:
            result = auth._auth_strip_pwreset_url_si_hay_param()
        assert result is True
        assert "mc_pwreset_token" not in mock_st.session_state
        assert "mc_auth_mode_radio" not in mock_st.session_state
        strip_q.assert_called_once()


def test_pin_coincide_tiempo_constante():
    u_ok = {"pin": "4821"}
    assert auth._pin_coincide_tiempo_constante(u_ok, "4821") is True
    assert auth._pin_coincide_tiempo_constante(u_ok, "4822") is False
    assert auth._pin_coincide_tiempo_constante(u_ok, "48") is False
    assert auth._pin_coincide_tiempo_constante({}, "4821") is False


def test_auth_strip_pwreset_url_si_hay_param_sin_parametro():
    with patch.object(auth, "st") as mock_st:
        mock_st.query_params = {}
        mock_st.session_state = {}
        with patch.object(auth, "_auth_strip_pwreset_query_param") as strip_q:
            result = auth._auth_strip_pwreset_url_si_hay_param()
        assert result is False
        strip_q.assert_not_called()
