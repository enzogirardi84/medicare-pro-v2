"""Tests para core.hsm_kms_integration — HSM/KMS Envelope Encryption."""
from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestEnvelope:
    def test_envelope_defaults(self):
        from core.hsm_kms_integration import Envelope
        env = Envelope(encrypted_dek=b"enc", wrapped_dek="hex", key_id="k1")
        assert env.algorithm == "AES-256-GCM"
        assert env.created_at >= 0


class TestTenantDEK:
    def test_cache_invalid_by_default(self):
        from core.hsm_kms_integration import TenantDEK
        tdek = TenantDEK(tenant_id="t1")
        assert tdek.is_cache_valid() is False

    def test_cache_valid_after_set(self):
        from core.hsm_kms_integration import TenantDEK
        import time
        tdek = TenantDEK(tenant_id="t1", cached_dek=b"key123", cached_at=time.time())
        assert tdek.is_cache_valid() is True

    def test_clear_cache(self):
        from core.hsm_kms_integration import TenantDEK
        import time
        tdek = TenantDEK(tenant_id="t1", cached_dek=b"key", cached_at=time.time())
        tdek.clear_cache()
        assert tdek.is_cache_valid() is False


class TestKMSDriver:
    def test_create_key(self):
        from core.hsm_kms_integration import KMSDriver
        driver = KMSDriver(provider="aws")
        key_id = asyncio.run(driver.create_key("test-key"))
        assert key_id.startswith("kms://")

    def test_encrypt_returns_structure(self):
        from core.hsm_kms_integration import KMSDriver
        driver = KMSDriver()
        result = asyncio.run(driver.encrypt(b"data_key_32_bytes_long!!"))
        assert result["algorithm"] == "AES-256-GCM"
        assert result["wrapping_algorithm"] == "RSAES_OAEP_SHA_256"
        assert len(result["ciphertext"]) > 0

    def test_generate_data_key(self):
        from core.hsm_kms_integration import KMSDriver
        driver = KMSDriver()
        result = asyncio.run(driver.generate_data_key())
        assert len(result["plaintext"]) == 32  # AES-256 key
        assert "ciphertext" in result
        assert "key_id" in result

    def test_re_encrypt_uses_interface(self):
        from core.hsm_kms_integration import KMSDriver
        driver = KMSDriver()
        # Mock decrypt + encrypt to avoid Fernet issues
        driver.decrypt = AsyncMock(return_value=b"plain_dek")
        driver.encrypt = AsyncMock(return_value={"ciphertext": b"new_encrypted", "key_id": "new-key"})
        result = asyncio.run(driver.re_encrypt(b"old_ciphertext", "old-key", "new-key"))
        assert result == b"new_encrypted"


class TestEnvelopeEncryptionManager:
    def test_initialize_creates_master_key(self):
        from core.hsm_kms_integration import EnvelopeEncryptionManager
        mgr = EnvelopeEncryptionManager()
        key_id = asyncio.run(mgr.initialize("test-master"))
        assert key_id is not None
        assert mgr._master_key_id == key_id

    def test_generate_tenant_dek(self):
        from core.hsm_kms_integration import EnvelopeEncryptionManager
        mgr = EnvelopeEncryptionManager()
        asyncio.run(mgr.initialize())
        tdek = asyncio.run(mgr.generate_tenant_dek("t1"))
        assert tdek.tenant_id == "t1"
        assert tdek.dek_version == 1
        assert tdek.envelope is not None
        assert tdek.is_cache_valid() is True

    def test_get_dek_from_cache(self):
        from core.hsm_kms_integration import EnvelopeEncryptionManager
        mgr = EnvelopeEncryptionManager()
        asyncio.run(mgr.initialize())
        asyncio.run(mgr.generate_tenant_dek("t1"))
        dek = asyncio.run(mgr.get_dek("t1"))
        assert len(dek) == 32

    def test_get_dek_unknown_tenant(self):
        from core.hsm_kms_integration import EnvelopeEncryptionManager
        mgr = EnvelopeEncryptionManager()
        with pytest.raises(KeyError):
            asyncio.run(mgr.get_dek("unknown"))

    def test_encrypt_decrypt_tenant_data(self):
        from core.hsm_kms_integration import EnvelopeEncryptionManager
        mgr = EnvelopeEncryptionManager()
        asyncio.run(mgr.initialize())
        asyncio.run(mgr.generate_tenant_dek("t1"))
        plaintext = b"Sensitive clinical data for tenant t1"
        ciphertext = asyncio.run(mgr.encrypt_tenant_data("t1", plaintext))
        assert ciphertext != plaintext
        decrypted = asyncio.run(mgr.decrypt_tenant_data("t1", ciphertext))
        assert decrypted == plaintext

    def test_rotate_master_key(self):
        from core.hsm_kms_integration import EnvelopeEncryptionManager
        mgr = EnvelopeEncryptionManager()
        asyncio.run(mgr.initialize())

        # Mock re_encrypt to avoid Fernet issues
        mgr._kms.re_encrypt = AsyncMock(return_value=b"new_encrypted_dek")
        mgr._kms.decrypt = AsyncMock(return_value=b"cached_dek_value")

        asyncio.run(mgr.generate_tenant_dek("t1"))
        asyncio.run(mgr.generate_tenant_dek("t2"))
        count = asyncio.run(mgr.rotate_master_key("v2"))
        assert count == 2
        # Clear cache to force decrypt through mocked KMS
        mgr._tenant_deks["t1"].clear_cache()
        dek = asyncio.run(mgr.get_dek("t1"))
        assert dek == b"cached_dek_value"

    def test_get_tenant_dek_info(self):
        from core.hsm_kms_integration import EnvelopeEncryptionManager
        mgr = EnvelopeEncryptionManager()
        asyncio.run(mgr.initialize())
        asyncio.run(mgr.generate_tenant_dek("t1"))
        info = mgr.get_tenant_dek_info("t1")
        assert info["tenant_id"] == "t1"
        assert info["dek_version"] == 1
        assert info["algorithm"] == "AES-256-GCM"
        assert info["cache_valid"] is True

    def test_get_tenant_dek_info_unknown(self):
        from core.hsm_kms_integration import EnvelopeEncryptionManager
        mgr = EnvelopeEncryptionManager()
        assert mgr.get_tenant_dek_info("unknown") is None
