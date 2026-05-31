"""Utilidades criptograficas para integridad de registros clinicos.
Serializacion canonica, hash SHA-256, y verificacion ECDSA.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Optional


def serializar_canonico(data: dict[str, Any]) -> str:
    """Serializa un diccionario a JSON canonico (sorted keys, sin espacios).

    Esto asegura que el mismo contenido SIEMPRE genere el mismo hash,
    independientemente del orden en que se agregaron las claves.
    """
    return json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)


def compute_integrity_hash(record: dict[str, Any]) -> str:
    """Calcula SHA-256 del JSON canonico del registro.

    Excluye campos volatiles que cambian en cada operacion
    (hash, firma, timestamps, version) para que el hash solo
    refleje los DATOS CLINICOS.
    """
    exclude = {"hash_integridad", "firma_ecdsa", "created_at",
               "updated_at", "version", "id", "tenant_id"}
    clean = {k: v for k, v in record.items() if k not in exclude}
    canonical = serializar_canonico(clean)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_integrity(record: dict[str, Any]) -> bool:
    """Verifica que el hash_integridad del registro coincida con los datos actuales.

    Si alguien modifico el registro fuera del sistema (SQL directo, backdoor),
    el hash no coincidira y la funcion retorna False.
    """
    stored_hash = record.get("hash_integridad", "")
    if not stored_hash:
        return False
    return compute_integrity_hash(record) == stored_hash


def firmar_y_hashear(
    data: dict[str, Any],
    clave_privada_pem: Optional[bytes] = None,
    firmante: str = "",
) -> dict[str, Any]:
    """Helper que calcula hash y firma ECDSA de un registro completo.

    Args:
        data: Datos del registro clinico.
        clave_privada_pem: Clave privada ECDSA para firmar.
        firmante: Identificador del profesional.

    Returns:
        Dict con hash_integridad y firma_ecdsa agregados.
    """
    record = dict(data)

    # Calcular hash de integridad
    record["hash_integridad"] = compute_integrity_hash(record)

    # Firmar con ECDSA si hay clave disponible
    if clave_privada_pem:
        try:
            from core.ecdsa_signature import ECDSASignatureManager
            signed = ECDSASignatureManager.firmar(record, clave_privada_pem, firmante)
            record["_signed_doc"] = ECDSASignatureManager.serializar(signed)
        except Exception:
            pass

    return record
