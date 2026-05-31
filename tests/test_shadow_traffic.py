"""Tests para core.shadow_traffic — Shadow / Dark Launching."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestShadowAnonymizer:
    def test_hash_name_truncated(self):
        from core.shadow_traffic import ShadowAnonymizer
        h = ShadowAnonymizer.hash_name("Juan Perez")
        assert len(h) == 8

    def test_mask_dni(self):
        from core.shadow_traffic import ShadowAnonymizer
        assert ShadowAnonymizer.mask_dni("12345678") == "***678"

    def test_mask_dni_corto(self):
        from core.shadow_traffic import ShadowAnonymizer
        assert ShadowAnonymizer.mask_dni("12") == "***"
        assert ShadowAnonymizer.mask_dni("") == ""

    def test_age_range_menor(self):
        from core.shadow_traffic import ShadowAnonymizer
        assert ShadowAnonymizer.age_range("2020-01-01") == "0-17"

    def test_age_range_adulto(self):
        from core.shadow_traffic import ShadowAnonymizer
        assert ShadowAnonymizer.age_range("1990-06-15") == "30-49"

    def test_age_range_null(self):
        from core.shadow_traffic import ShadowAnonymizer
        assert ShadowAnonymizer.age_range(None) == "S/D"

    def test_round_coord(self):
        from core.shadow_traffic import ShadowAnonymizer
        lat, lon = ShadowAnonymizer.round_coord(-34.603, -58.381)
        assert lat == -34.6
        assert lon == -58.4

    def test_anonymize_payload_flat(self):
        from core.shadow_traffic import ShadowAnonymizer
        anon = ShadowAnonymizer()
        payload = {"nombre": "Maria Lopez", "dni": "87654321", "edad": 35}
        result = anon.anonymize_payload(payload)
        assert result["nombre"] == anon.hash_name("Maria Lopez")
        assert result["dni"] == "***321"
        assert result["edad"] == 35

    def test_anonymize_payload_nested(self):
        from core.shadow_traffic import ShadowAnonymizer
        anon = ShadowAnonymizer()
        payload = {
            "patient": {"nombre": "Carlos", "fecha_nacimiento": "1980-03-10"},
            "vital_signs": [{"lat": -34.603, "lon": -58.381}],
        }
        result = anon.anonymize_payload(payload)
        assert result["patient"]["nombre"] == anon.hash_name("Carlos")
        assert result["patient"]["fecha_nacimiento"] == "30-49"
        assert result["vital_signs"][0]["lat"] == -34.6


class TestShadowDispatcher:
    def test_should_sample_always_for_rate_1(self):
        from core.shadow_traffic import ShadowDispatcher, ShadowConfig
        disp = ShadowDispatcher(ShadowConfig(sample_rate=1.0))
        assert disp._should_sample() is True

    def test_should_sample_never_for_rate_0(self):
        from core.shadow_traffic import ShadowDispatcher, ShadowConfig
        disp = ShadowDispatcher(ShadowConfig(sample_rate=0.0))
        assert disp._should_sample() is False

    def test_mirror_request_payload_too_large(self):
        from core.shadow_traffic import ShadowDispatcher, ShadowConfig
        disp = ShadowDispatcher(ShadowConfig(sample_rate=1.0, max_payload_size=10))
        asyncio.run(disp.mirror_request("POST", "/sync/batch", {}, {"large": "x" * 100}))
        assert disp._stats["dropped"] == 1

    def test_mirror_request_increments_mirrored(self):
        from core.shadow_traffic import ShadowDispatcher, ShadowConfig
        disp = ShadowDispatcher(ShadowConfig(sample_rate=1.0))
        # Desactivar worker para verificar el contador
        disp._ensure_worker = MagicMock()
        asyncio.run(disp.mirror_request("POST", "/sync/batch",
                                         {"Authorization": "Bearer x"},
                                         {"nombre": "Juan", "dni": "123"}))
        assert disp._stats["mirrored"] == 1

    def test_get_stats(self):
        from core.shadow_traffic import ShadowDispatcher
        disp = ShadowDispatcher()
        stats = disp.get_stats()
        assert stats["mirrored"] == 0
        assert stats["sent"] == 0
        assert stats["failed"] == 0

    def test_close(self):
        from core.shadow_traffic import ShadowDispatcher
        disp = ShadowDispatcher()
        asyncio.run(disp.close())

    def test_worker_sends_to_sandbox(self):
        from core.shadow_traffic import ShadowDispatcher, ShadowConfig

        async def run():
            disp = ShadowDispatcher(ShadowConfig(sandbox_url="https://sandbox.test",
                                                  api_key="test-key"))
            disp._client = MagicMock()
            disp._client.post = AsyncMock(return_value=MagicMock(status_code=200))
            await disp.mirror_request("POST", "/sync/batch", {}, {"test": 1})
            await disp._worker_loop()
            disp._client.post.assert_called_once()
            return True

        assert asyncio.run(run()) is True


class TestFastAPIMiddlewareCode:
    def test_middleware_code_importable(self):
        from core.shadow_traffic import FASTAPI_MIDDLEWARE_SHADOW
        assert "ShadowTrafficMiddleware" in FASTAPI_MIDDLEWARE_SHADOW
