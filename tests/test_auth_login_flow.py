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
