"""Tests reales para core._db_retry (retry con exponential backoff)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core._db_retry import supabase_execute_with_retry


class TestSupabaseExecuteWithRetry:
    def test_exitoso_primer_intento(self):
        fn = MagicMock(return_value="ok")
        assert supabase_execute_with_retry("test", fn, attempts=3) == "ok"
        assert fn.call_count == 1

    def test_exitoso_tras_fallos(self):
        fn = MagicMock(side_effect=[Exception("err1"), Exception("err2"), "ok"])
        assert supabase_execute_with_retry("test", fn, attempts=3) == "ok"
        assert fn.call_count == 3

    def test_re_raise_si_agota_intentos(self):
        fn = MagicMock(side_effect=Exception("siempre falla"))
        with pytest.raises(Exception, match="siempre falla"):
            supabase_execute_with_retry("test", fn, attempts=2)
        assert fn.call_count == 2

    def test_intento_unico(self):
        fn = MagicMock(side_effect=Exception("unico"))
        with pytest.raises(Exception):
            supabase_execute_with_retry("test", fn, attempts=1)
        assert fn.call_count == 1

    @patch("core._db_retry.time.sleep")
    def test_exponential_backoff(self, mock_sleep):
        fn = MagicMock(side_effect=[Exception("e1"), Exception("e2"), "ok"])
        supabase_execute_with_retry("test", fn, attempts=3, base_delay=0.1)
        assert fn.call_count == 3
        # Verifica que se llamó sleep al menos 2 veces (entre intentos)
        assert mock_sleep.call_count == 2

    @patch("core._db_retry.time.sleep")
    def test_sin_delay_en_exito(self, mock_sleep):
        fn = MagicMock(return_value="ok")
        supabase_execute_with_retry("test", fn, attempts=3)
        assert mock_sleep.call_count == 0
