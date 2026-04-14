"""Tests para claves de archivo local por tenant (seguridad de ruta)."""

from core.database import _tenant_local_fs_key


def test_tenant_local_fs_key_normal_unchanged():
    assert _tenant_local_fs_key("Clinica General") == "clinica general"


def test_tenant_local_fs_key_strips_path_components():
    assert ".." not in _tenant_local_fs_key("../evil")
    assert "/" not in _tenant_local_fs_key("a/b")
    assert "\\" not in _tenant_local_fs_key("a\\b")


def test_tenant_local_fs_key_empty():
    assert _tenant_local_fs_key("") == ""
    assert _tenant_local_fs_key("   ") == ""


def test_tenant_local_fs_key_fallback_when_only_bad_chars():
    # Solo caracteres no permitidos → "tenant"
    assert _tenant_local_fs_key("@@@") == "tenant"
