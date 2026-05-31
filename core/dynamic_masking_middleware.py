"""Motor Dynamic Data Masking en caliente para interfaces de usuario.
Middleware RBAC que intercepta queries y aplica enmascaramiento
segun el rol del usuario antes de que los datos viajen al frontend.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


# ═══════════════════════════════════════════════════════════════════
# 1. NIVELES DE ACCESO POR ROL
# ═══════════════════════════════════════════════════════════════════

class AccessLevel(Enum):
    FULL = "full"              # Ve todo: DNI, direccion, nombre completo
    RESTRICTED = "restricted"  # Ve datos clinicos pero no PHI completa
    MASKED = "masked"          # Solo ve datos anonimizados
    AUDIT = "audit"            # Solo ve metadatos de auditoria


@dataclass
class RoleAccessPolicy:
    """Politica de acceso por rol corporativo."""
    role: str
    access_level: AccessLevel
    visible_fields: set[str] = field(default_factory=set)
    masked_fields: set[str] = field(default_factory=set)
    hidden_fields: set[str] = field(default_factory=set)


# ═══════════════════════════════════════════════════════════════════
# 2. POLITICAS PREDEFINIDAS
# ═══════════════════════════════════════════════════════════════════

DEFAULT_POLICIES: dict[str, RoleAccessPolicy] = {
    "coordinador_general": RoleAccessPolicy(
        role="coordinador_general",
        access_level=AccessLevel.FULL,
        visible_fields={"nombre", "dni", "direccion", "telefono", "fecha_nacimiento",
                        "diagnostico", "medicacion", "nota", "latitud", "longitud"},
    ),
    "enfermero_campo": RoleAccessPolicy(
        role="enfermero_campo",
        access_level=AccessLevel.RESTRICTED,
        visible_fields={"nombre", "diagnostico", "medicacion", "nota", "edad"},
        masked_fields={"dni", "telefono"},
        hidden_fields={"direccion", "latitud", "longitud"},
    ),
    "auditor_contable": RoleAccessPolicy(
        role="auditor_contable",
        access_level=AccessLevel.AUDIT,
        visible_fields={"edad", "rango_edad", "obra_social", "diagnostico"},
        masked_fields={"nombre", "dni"},
        hidden_fields={"direccion", "telefono", "latitud", "longitud", "nota"},
    ),
    "investigador": RoleAccessPolicy(
        role="investigador",
        access_level=AccessLevel.MASKED,
        visible_fields={"rango_edad", "obra_social", "diagnostico", "medicacion"},
        masked_fields={"nombre", "dni"},
        hidden_fields={"direccion", "telefono", "latitud", "longitud", "nota",
                        "fecha_nacimiento"},
    ),
}


# ═══════════════════════════════════════════════════════════════════
# 3. MASCARAS POR CAMPO
# ═══════════════════════════════════════════════════════════════════

class FieldMasker:
    """Aplica mascaras deterministicas a campos PHI."""

    @staticmethod
    def mask_dni(value: str) -> str:
        """DNI: 12.345.678 -> X.XXX.XX-8 (ultimo digito visible)."""
        if not value:
            return ""
        digits = re.sub(r"\D", "", value)
        if len(digits) <= 1:
            return "X"
        return "X.XXX.XX-" + digits[-1]

    @staticmethod
    def mask_name(value: str) -> str:
        """Nombre: 'Juan Perez' -> 'J*** P***' (inicial + apellido inicial)."""
        if not value:
            return ""
        parts = value.strip().split()
        masked = []
        for p in parts:
            if len(p) <= 1:
                masked.append(p)
            else:
                masked.append(p[0] + "*" * (len(p) - 1))
        return " ".join(masked)

    @staticmethod
    def mask_phone(value: str) -> str:
        """Telefono: '+54 11 5555-1234' -> '+54 ** ****-**34'."""
        if not value:
            return ""
        digits = re.sub(r"\D", "", value)
        if len(digits) <= 2:
            return "**"
        return "**-****-" + digits[-2:]

    @staticmethod
    def mask_address(value: str) -> str:
        """Direccion: 'Av. siempre viva 742' -> '***'."""
        return "***" if value else ""

    @staticmethod
    def mask_coords(lat: Optional[float], lon: Optional[float]) -> tuple:
        """Coordenadas redondeadas al grado (no al 0.1 como los queries BI)."""
        if lat is None or lon is None:
            return (None, None)
        return (round(lat, 0), round(lon, 0))

    @staticmethod
    def apply_mask(field_name: str, value: Any) -> Any:
        """Aplica la mascara correspondiente segun el nombre del campo."""
        mask_map = {
            "dni": FieldMasker.mask_dni,
            "documento": FieldMasker.mask_dni,
            "document_number": FieldMasker.mask_dni,
            "nombre": FieldMasker.mask_name,
            "nombre_completo": FieldMasker.mask_name,
            "patient_name": FieldMasker.mask_name,
            "telefono": FieldMasker.mask_phone,
            "phone": FieldMasker.mask_phone,
            "direccion": FieldMasker.mask_address,
            "address": FieldMasker.mask_address,
        }
        masker = mask_map.get(field_name)
        if masker:
            if field_name in ("lat", "latitud", "latitude", "lon", "longitud", "longitude"):
                if isinstance(value, (int, float)):
                    return FieldMasker.mask_coords(value, 0)[0]
            return masker(str(value)) if value is not None else value
        return value


# ═══════════════════════════════════════════════════════════════════
# 4. MIDDLEWARE DE MASKING DINAMICO
# ═══════════════════════════════════════════════════════════════════

class DynamicMaskingMiddleware:
    """Middleware que aplica enmascaramiento dinamico segun el rol.

    Uso:
        middleware = DynamicMaskingMiddleware()
        user_role = obtener_rol_de_session()
        # Al obtener datos del repositorio:
        masked_data = middleware.apply(user_role, raw_data)
    """

    def __init__(self, policies: Optional[dict[str, RoleAccessPolicy]] = None):
        self._policies = policies or DEFAULT_POLICIES

    def get_policy(self, role: str) -> RoleAccessPolicy:
        """Obtiene la politica de acceso para un rol."""
        return self._policies.get(role, self._policies.get("investigador"))

    def apply(self, role: str, data: Any) -> Any:
        """Aplica masking dinamico a un dato segun el rol.

        Args:
            role: Nombre del rol del usuario.
            data: Dato o estructura a enmascarar (dict, list, o valor simple).

        Returns:
            Dato enmascarado.
        """
        policy = self.get_policy(role)

        if policy.access_level == AccessLevel.FULL:
            return data

        if isinstance(data, dict):
            return self._mask_dict(policy, data)
        elif isinstance(data, list):
            return [self.apply(role, item) for item in data]
        return data

    def _mask_dict(self, policy: RoleAccessPolicy, data: dict) -> dict:
        """Aplica mascaras a un diccionario."""
        result = {}
        for key, value in data.items():
            # Campo oculto?
            if key in policy.hidden_fields:
                continue

            # Campo a enmascarar?
            if key in policy.masked_fields:
                result[key] = FieldMasker.apply_mask(key, value)
            elif key in policy.visible_fields:
                result[key] = value
            elif policy.access_level == AccessLevel.AUDIT:
                continue  # solo visible_fields en audit
            else:
                result[key] = value  # campos no especificados pasan
        return result

    def register_policy(self, policy: RoleAccessPolicy):
        """Registra una politica personalizada."""
        self._policies[policy.role] = policy


# ═══════════════════════════════════════════════════════════════════
# 5. DECORADOR DE REPOSITORIO
# ═══════════════════════════════════════════════════════════════════

def dynamic_masking(role_provider: Callable[[], str]):
    """Decorador para metodos de repositorio que aplica masking.

    Uso:
        @dynamic_masking(lambda: st.session_state.get("user_role", "investigador"))
        async def get_pacientes(self, tenant_id):
            rows = await self.conn.fetch(...)
            return rows

    Args:
        role_provider: Funcion que retorna el rol del usuario actual.
    """
    from functools import wraps

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            role = role_provider()
            middleware = DynamicMaskingMiddleware()
            return middleware.apply(role, result)
        return wrapper
    return decorator


__all__ = [
    "DynamicMaskingMiddleware",
    "RoleAccessPolicy",
    "AccessLevel",
    "FieldMasker",
    "dynamic_masking",
    "DEFAULT_POLICIES",
]
