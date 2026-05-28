"""Tests para core/seguridad.py — Cifrado, XSS, tenant, archivos, auditoría.
Ley 25.326, Resolución AAIP 47/2018.
"""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_streamlit():
    """Mockea st.session_state y st.markdown para evitar UI en tests."""
    with patch("core.seguridad.st") as mock_st:
        mock_st.session_state = {}
        mock_st.markdown = MagicMock()
        mock_st.error = MagicMock()
        mock_st.stop = MagicMock()
        yield mock_st


@pytest.fixture
def seg():
    """Carga el módulo con FERNET_KEY válida."""
    from cryptography.fernet import Fernet
    _key = Fernet.generate_key().decode()
    with patch.dict("os.environ", {"FERNET_KEY": _key}, clear=False):
        import importlib
        import core.seguridad as s
        importlib.reload(s)
        return s


@pytest.fixture
def seg_no_fernet():
    """Carga el módulo SIN FERNET_KEY (modo degradado)."""
    with patch.dict("os.environ", {}, clear=True):
        import importlib
        import core.seguridad as s
        importlib.reload(s)
        return s


@pytest.fixture
def mock_user_admin():
    return {"login": "admin", "rol": "SuperAdmin", "empresa": "Clinica A"}


@pytest.fixture
def mock_user_medico():
    return {"login": "dr.garcia", "rol": "medico", "empresa": "Clinica A"}


# ═══════════════════════════════════════════════════════════════════════
# CIFRADO
# ═══════════════════════════════════════════════════════════════════════

class TestCifrado:
    def test_encrypt_decrypt_roundtrip(self, seg):
        orig = "Paciente alergico a penicilina"
        enc = seg.encrypt_field(orig)
        assert enc != orig
        assert seg.decrypt_field(enc) == orig

    def test_encrypt_empty_string(self, seg):
        assert seg.encrypt_field("") == ""
        assert seg.decrypt_field("") == ""

    def test_decrypt_unencrypted_data(self, seg):
        assert seg.decrypt_field("texto plano") == "texto plano"

    def test_encrypt_without_key(self, seg_no_fernet):
        assert seg_no_fernet.encrypt_field("test") == "test"
        assert seg_no_fernet.decrypt_field("test") == "test"

    def test_patient_dict_defensive_copy(self, seg):
        orig = {"nombre": "Juan", "alergias": "Penicilina"}
        orig_copy = dict(orig)
        result = seg.encrypt_patient_dict(orig)
        assert result is not orig
        assert result["alergias"] != orig["alergias"]
        assert orig["alergias"] == orig_copy["alergias"]

    def test_decrypt_patient_dict_defensive_copy(self, seg):
        enc = seg.encrypt_patient_dict({"alergias": "Test"})
        enc_copy = dict(enc)
        result = seg.decrypt_patient_dict(enc)
        assert result is not enc
        assert result["alergias"] != enc["alergias"]
        assert enc["alergias"] == enc_copy["alergias"]

    def test_encrypt_decrypt_all_sensitive_fields(self, seg):
        data = {f: f"valor_{f}" for f in seg.SENSITIVE_FIELDS}
        enc = seg.encrypt_patient_dict(data)
        for f in seg.SENSITIVE_FIELDS:
            assert enc[f] != data[f], f"{f} no fue cifrado"
        dec = seg.decrypt_patient_dict(enc)
        for f in seg.SENSITIVE_FIELDS:
            assert dec[f] == data[f], f"{f} no coincide tras roundtrip"


# ═══════════════════════════════════════════════════════════════════════
# SANITIZE PII
# ═══════════════════════════════════════════════════════════════════════

class TestSanitizePII:
    def test_dni_replaced(self, seg):
        r = seg.sanitize_for_log("DNI: 1234567")
        assert "***DNI***" in r
        assert "1234567" not in r

    def test_email_replaced(self, seg):
        r = seg.sanitize_for_log("email: test@mail.com")
        assert "***EMAIL***" in r

    def test_phone_replaced(self, seg):
        r = seg.sanitize_for_log("tel: +5491123456789")
        assert "***TEL***" in r

    def test_extra_sensitive(self, seg):
        r = seg.sanitize_for_log("Nombre: Juan Perez", extra_sensitive="Juan Perez")
        assert "***SENSIBLE***" in r

    def test_empty_returns_empty(self, seg):
        assert seg.sanitize_for_log("") == ""
        assert seg.sanitize_for_log(None) == ""

    def test_long_truncated(self, seg):
        assert len(seg.sanitize_for_log("a" * 1000)) == 500


# ═══════════════════════════════════════════════════════════════════════
# XSS SAFE MARKDOWN
# ═══════════════════════════════════════════════════════════════════════

class TestSafeMarkdown:
    def test_escapes_html(self, seg):
        with patch.object(seg.st, "markdown") as md:
            seg.safe_markdown("<b>{x}</b>", x='<script>alert(1)</script>')
            called = md.call_args[0][0]
            assert "&lt;script&gt;" in called
            assert "<script>" not in called

    def test_no_kwargs_passthrough(self, seg):
        with patch.object(seg.st, "markdown") as md:
            seg.safe_markdown("texto")
            md.assert_called_with("texto", unsafe_allow_html=False)

    def test_safe_error_logs_and_shows(self, seg):
        with patch.object(seg.st, "error") as err:
            seg.safe_error("Error: {d}", d="detalle <script>")
            called = err.call_args[0][0]
            assert "&lt;script&gt;" in called


# ═══════════════════════════════════════════════════════════════════════
# TENANT ISOLATION
# ═══════════════════════════════════════════════════════════════════════

class TestTenantIsolation:
    def test_admin_bypass(self, seg, mock_user_admin):
        assert seg.verify_patient_access("cualquiera", mock_user_admin) is True

    def test_mismo_tenant(self, seg, mock_user_medico):
        with patch.object(seg, "_get_paciente_empresa", return_value="Clinica A"):
            assert seg.verify_patient_access("paciente", mock_user_medico) is True

    def test_distinto_tenant_denied(self, seg, mock_user_medico):
        with patch.object(seg, "_get_paciente_empresa", return_value="Clinica X"):
            assert seg.verify_patient_access("paciente", mock_user_medico) is False

    def test_paciente_sin_empresa(self, seg, mock_user_medico):
        with patch.object(seg, "_get_paciente_empresa", return_value=""):
            assert seg.verify_patient_access("paciente", mock_user_medico) is True

    def test_user_sin_empresa_denied(self, seg):
        assert seg.verify_patient_access("paciente", {"rol": "medico", "empresa": ""}) is False

    def test_paciente_vacio(self, seg, mock_user_medico):
        assert seg.verify_patient_access("", mock_user_medico) is False
        assert seg.verify_patient_access(None, mock_user_medico) is False


# ═══════════════════════════════════════════════════════════════════════
# FILE VALIDATION
# ═══════════════════════════════════════════════════════════════════════

class TestFileValidation:
    def _make_file(self, name, content):
        f = MagicMock()
        f.name = name
        f.read.return_value = content
        return f

    def test_valid_png(self, seg):
        ok, _ = seg.validate_uploaded_file(self._make_file("img.png", b'\x89PNG\r\n\x1a\n'))
        assert ok

    def test_valid_pdf(self, seg):
        ok, _ = seg.validate_uploaded_file(self._make_file("doc.pdf", b'%PDF-1.4'))
        assert ok

    def test_exe_disguised_as_png(self, seg):
        ok, msg = seg.validate_uploaded_file(self._make_file("virus.png", b'MZ\x90\x00'))
        assert not ok
        assert "no reconocido" in msg

    def test_bad_extension(self, seg):
        ok, _ = seg.validate_uploaded_file(self._make_file("data.csv", b'data'))
        assert not ok

    def test_none_file(self, seg):
        ok, _ = seg.validate_uploaded_file(None)
        assert not ok

    def test_empty_file(self, seg):
        ok, _ = seg.validate_uploaded_file(self._make_file("vacio.png", b''))
        assert not ok


# ═══════════════════════════════════════════════════════════════════════
# AUDITORÍA INMUTABLE
# ═══════════════════════════════════════════════════════════════════════

class TestAuditoria:
    def test_registrar_retorna_hash(self, seg):
        with patch("core.database.supabase", None):
            with patch.object(seg, "_get_last_audit_hash_from_db", return_value="0" * 64):
                h = seg.registrar_auditoria_inmutable("Test", "P1", "accion", "admin")
                assert len(h) == 64
                assert all(c in "0123456789abcdef" for c in h)

    def test_chain_detecta_modificacion(self, seg):
        entries = [
            {"hash": "aaa", "prev_hash": "0" * 64, "timestamp": "2026-01-01"},
            {"hash": "bbb", "prev_hash": "aaa", "timestamp": "2026-01-02"},
        ]
        ok, msg = seg.verify_audit_chain(entries)
        assert not ok

    def test_verify_empty_chain(self, seg):
        ok, msg = seg.verify_audit_chain([])
        assert not ok
        assert "vacía" in msg
