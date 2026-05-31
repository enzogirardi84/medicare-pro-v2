"""Tests para core.zero_trust_middleware — Zero-Trust API."""
from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch


class TestDeviceAttestation:
    def test_to_canonical_deterministic(self):
        from core.zero_trust_middleware import DeviceAttestation
        a = DeviceAttestation(device_id="d1", hardware_hash="abc123",
                               os_version="Android14", app_version="2.1",
                               timestamp=1000.0, nonce="n1")
        b = DeviceAttestation(device_id="d1", hardware_hash="abc123",
                               os_version="Android14", app_version="2.1",
                               timestamp=1000.0, nonce="n1")
        assert a.to_canonical() == b.to_canonical()


class TestDeviceAttestationVerifier:
    def test_unknown_device_rejected(self):
        from core.zero_trust_middleware import DeviceAttestation, DeviceAttestationVerifier
        verifier = DeviceAttestationVerifier()
        att = DeviceAttestation(device_id="unknown", hardware_hash="x",
                                 os_version="a", app_version="b",
                                 timestamp=time.time(), nonce="n1")
        assert verifier.verify(att, "sig", lambda pk, p, s: True) is False

    def test_hardware_mismatch_rejected(self):
        from core.zero_trust_middleware import DeviceAttestation, DeviceAttestationVerifier
        verifier = DeviceAttestationVerifier()
        verifier.register_device("d1", "pubkey", "expected_hash")
        att = DeviceAttestation(device_id="d1", hardware_hash="wrong_hash",
                                 os_version="a", app_version="b",
                                 timestamp=time.time(), nonce="n1")
        assert verifier.verify(att, "sig", lambda pk, p, s: True) is False

    def test_stale_timestamp_rejected(self):
        from core.zero_trust_middleware import DeviceAttestation, DeviceAttestationVerifier
        verifier = DeviceAttestationVerifier()
        verifier.register_device("d1", "pubkey", "hw_hash")
        att = DeviceAttestation(device_id="d1", hardware_hash="hw_hash",
                                 os_version="a", app_version="b",
                                 timestamp=time.time() - 60, nonce="n1")
        assert verifier.verify(att, "sig", lambda pk, p, s: True) is False

    def test_nonce_replay_rejected(self):
        from core.zero_trust_middleware import DeviceAttestation, DeviceAttestationVerifier
        verifier = DeviceAttestationVerifier()
        verifier.register_device("d1", "pubkey", "hw_hash")
        att = DeviceAttestation(device_id="d1", hardware_hash="hw_hash",
                                 os_version="a", app_version="b",
                                 timestamp=time.time(), nonce="replay_nonce")
        assert verifier.verify(att, "sig1", lambda pk, p, s: True) is True
        assert verifier.verify(att, "sig2", lambda pk, p, s: True) is False

    def test_valid_attestation_accepted(self):
        from core.zero_trust_middleware import DeviceAttestation, DeviceAttestationVerifier
        verifier = DeviceAttestationVerifier()
        verifier.register_device("d1", "pubkey", "hw_hash")
        att = DeviceAttestation(device_id="d1", hardware_hash="hw_hash",
                                 os_version="a", app_version="b",
                                 timestamp=time.time(), nonce="fresh_nonce")
        assert verifier.verify(att, "valid_sig", lambda pk, p, s: True) is True

    def test_register_device(self):
        from core.zero_trust_middleware import DeviceAttestationVerifier
        verifier = DeviceAttestationVerifier()
        verifier.register_device("d1", "pk_pem", "hw_hash")
        assert "d1" in verifier._trusted_devices


class TestSignedURLManager:
    def test_generate_endpoint(self):
        from core.zero_trust_middleware import SignedURLManager
        mgr = SignedURLManager()
        ep = mgr.generate_endpoint("/sync/batch", "t1", ttl=60)
        assert ep.original_path == "/sync/batch"
        assert ep.signed_path.startswith("/_/")
        assert ep.tenant_id == "t1"
        assert ep.used is False

    def test_verify_and_resolve_valid(self):
        from core.zero_trust_middleware import SignedURLManager
        mgr = SignedURLManager()
        ep = mgr.generate_endpoint("/sync/batch", "t1", ttl=60)
        resolved = mgr.verify_and_resolve(ep.signed_path)
        assert resolved == "/sync/batch"

    def test_verify_and_resolve_single_use(self):
        from core.zero_trust_middleware import SignedURLManager
        mgr = SignedURLManager()
        ep = mgr.generate_endpoint("/sync/delta", "t1", ttl=60)
        assert mgr.verify_and_resolve(ep.signed_path) == "/sync/delta"
        assert mgr.verify_and_resolve(ep.signed_path) is None

    def test_verify_expired_endpoint(self):
        from core.zero_trust_middleware import SignedURLManager
        mgr = SignedURLManager()
        ep = mgr.generate_endpoint("/sync/batch", "t1", ttl=-1)
        result = mgr.verify_and_resolve(ep.signed_path)
        assert result is None

    def test_verify_unknown_path(self):
        from core.zero_trust_middleware import SignedURLManager
        mgr = SignedURLManager()
        assert mgr.verify_and_resolve("/_/fake/path") is None

    def test_revoke_tenant_endpoints(self):
        from core.zero_trust_middleware import SignedURLManager
        mgr = SignedURLManager()
        mgr.generate_endpoint("/sync/batch", "t1")
        mgr.generate_endpoint("/sync/delta", "t1")
        mgr.generate_endpoint("/sync/batch", "t2")
        count = mgr.revoke_tenant_endpoints("t1")
        assert count == 2
        assert len(mgr._active_endpoints) == 1


class TestBlockingManager:
    def test_record_invalid_signature_no_redis(self):
        from core.zero_trust_middleware import BlockingManager
        mgr = BlockingManager()
        result = asyncio.run(mgr.record_invalid_signature("1.2.3.4", "t1", "d1"))
        assert result is None

    def test_is_blocked_no_redis(self):
        from core.zero_trust_middleware import BlockingManager
        mgr = BlockingManager()
        result = asyncio.run(mgr.is_blocked("1.2.3.4", "t1"))
        assert result is False

    def test_unblock_ip_no_redis(self):
        from core.zero_trust_middleware import BlockingManager
        mgr = BlockingManager()
        result = asyncio.run(mgr.unblock_ip("1.2.3.4"))
        assert result is False

    def test_unblock_tenant_no_redis(self):
        from core.zero_trust_middleware import BlockingManager
        mgr = BlockingManager()
        result = asyncio.run(mgr.unblock_tenant("t1"))
        assert result is False


class TestFastAPIMiddlewareCode:
    def test_middleware_code_importable(self):
        from core.zero_trust_middleware import FASTAPI_MIDDLEWARE_CODE
        assert "ZeroTrustMiddleware" in FASTAPI_MIDDLEWARE_CODE
        assert "DeviceAttestationVerifier" in FASTAPI_MIDDLEWARE_CODE
