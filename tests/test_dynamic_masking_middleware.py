"""Tests para core.dynamic_masking_middleware — RBAC Masking."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock


class TestAccessLevel:
    def test_levels_exist(self):
        from core.dynamic_masking_middleware import AccessLevel
        assert AccessLevel.FULL.value == "full"
        assert AccessLevel.MASKED.value == "masked"
        assert AccessLevel.AUDIT.value == "audit"


class TestRoleAccessPolicy:
    def test_policy_defaults(self):
        from core.dynamic_masking_middleware import RoleAccessPolicy, AccessLevel
        p = RoleAccessPolicy(role="test", access_level=AccessLevel.FULL)
        assert p.visible_fields == set()
        assert p.masked_fields == set()
        assert p.hidden_fields == set()


class TestFieldMasker:
    def test_mask_dni_argentino(self):
        from core.dynamic_masking_middleware import FieldMasker
        assert FieldMasker.mask_dni("12.345.678") == "X.XXX.XX-8"

    def test_mask_dni_corto(self):
        from core.dynamic_masking_middleware import FieldMasker
        assert FieldMasker.mask_dni("5") == "X"

    def test_mask_name(self):
        from core.dynamic_masking_middleware import FieldMasker
        assert FieldMasker.mask_name("Juan Perez") == "J*** P****"

    def test_mask_name_single(self):
        from core.dynamic_masking_middleware import FieldMasker
        assert FieldMasker.mask_name("Maria") == "M****"

    def test_mask_phone(self):
        from core.dynamic_masking_middleware import FieldMasker
        assert FieldMasker.mask_phone("+54 11 5555-1234").endswith("34")

    def test_mask_address(self):
        from core.dynamic_masking_middleware import FieldMasker
        assert FieldMasker.mask_address("Av. Siempre Viva 742") == "***"

    def test_apply_mask_by_field_name(self):
        from core.dynamic_masking_middleware import FieldMasker
        assert FieldMasker.apply_mask("dni", "12345678") == "X.XXX.XX-8"
        assert FieldMasker.apply_mask("nombre", "Carlos") == "C*****"
        assert FieldMasker.apply_mask("edad", 35) == 35


class TestDynamicMaskingMiddleware:
    def test_full_access_passthrough(self):
        from core.dynamic_masking_middleware import DynamicMaskingMiddleware
        mw = DynamicMaskingMiddleware()
        data = {"nombre": "Juan", "dni": "12345678", "diagnostico": "neumonia"}
        result = mw.apply("coordinador_general", data)
        assert result == data

    def test_enfermero_masks_dni(self):
        from core.dynamic_masking_middleware import DynamicMaskingMiddleware
        mw = DynamicMaskingMiddleware()
        data = {"nombre": "Juan Perez", "dni": "12345678", "diagnostico": "neumonia",
                "direccion": "Av. Siempre Viva 742"}
        result = mw.apply("enfermero_campo", data)
        assert result["nombre"] == "Juan Perez"  # visible
        assert result["dni"] == "X.XXX.XX-8"     # masked
        assert result["diagnostico"] == "neumonia"
        assert "direccion" not in result         # hidden

    def test_auditor_only_sees_visible(self):
        from core.dynamic_masking_middleware import DynamicMaskingMiddleware
        mw = DynamicMaskingMiddleware()
        data = {"nombre": "Juan", "dni": "12345678", "edad": 45,
                "diagnostico": "gripe", "obra_social": "OSDE"}
        result = mw.apply("auditor_contable", data)
        assert "nombre" in result and "***" in result["nombre"]
        assert "diagnostico" in result
        assert "dni" not in result or "X" in result.get("dni", "")

    def test_investigador_masked(self):
        from core.dynamic_masking_middleware import DynamicMaskingMiddleware
        mw = DynamicMaskingMiddleware()
        data = {"nombre": "Maria Lopez", "dni": "87654321",
                "rango_edad": "30-49", "diagnostico": "diabetes"}
        result = mw.apply("investigador", data)
        assert result["rango_edad"] == "30-49"
        assert result["diagnostico"] == "diabetes"
        assert result["nombre"] != "Maria Lopez"

    def test_list_of_dicts(self):
        from core.dynamic_masking_middleware import DynamicMaskingMiddleware
        mw = DynamicMaskingMiddleware()
        data = [
            {"nombre": "Juan", "dni": "12345678"},
            {"nombre": "Maria", "dni": "87654321"},
        ]
        result = mw.apply("auditor_contable", data)
        assert len(result) == 2
        for item in result:
            assert "***" in item.get("nombre", "")

    def test_unknown_role_falls_back_to_investigador(self):
        from core.dynamic_masking_middleware import DynamicMaskingMiddleware
        mw = DynamicMaskingMiddleware()
        data = {"nombre": "Test", "dni": "12345678"}
        result = mw.apply("rol_inexistente", data)
        assert result["nombre"] != "Test"

    def test_register_policy(self):
        from core.dynamic_masking_middleware import (DynamicMaskingMiddleware,
                                                     RoleAccessPolicy, AccessLevel)
        mw = DynamicMaskingMiddleware()
        custom = RoleAccessPolicy(role="custom", access_level=AccessLevel.FULL)
        mw.register_policy(custom)
        assert "custom" in mw._policies


class TestDynamicMaskingDecorator:
    def test_decorator_structure(self):
        from core.dynamic_masking_middleware import dynamic_masking
        decorator = dynamic_masking(lambda: "investigador")
        assert callable(decorator)

    def test_decorator_wraps_async(self):
        from core.dynamic_masking_middleware import dynamic_masking

        @dynamic_masking(lambda: "enfermero_campo")
        async def get_data():
            return {"nombre": "Juan", "dni": "12345678", "diagnostico": "gripe"}

        result = asyncio.run(get_data())
        assert result["diagnostico"] == "gripe"
        assert result["dni"].startswith("X")
