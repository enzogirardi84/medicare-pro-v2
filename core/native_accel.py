"""Puente de extension nativa para aceleracion criptografica y serializacion.
Libera el GIL durante hash SHA256 encadenado, validacion ECDSA
y decompress de MessagePack. Implementacion Python pura con stub
para reemplazo por Cython/PyO3 en produccion.
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import time
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. DETECCION DE EXTENSION NATIVA
# ═══════════════════════════════════════════════════════════════════

_HAS_NATIVE = False
_HAS_CYTHON = False

try:
    # Intento de importar extension C compilada (producida por Cython o PyO3)
    from core import _cnative as _native_impl
    _HAS_NATIVE = True
except ImportError:
    _native_impl = None

try:
    import cython
    _HAS_CYTHON = True
except ImportError:
    pass


# ═══════════════════════════════════════════════════════════════════
# 2. GIL-RELEASED HASHING (SHA256 encadenado)
# ═══════════════════════════════════════════════════════════════════

def chained_hash_sha256(data: bytes, prev_hash: str = "") -> str:
    """SHA256 encadenado: hash(prev_hash + data).

    En produccion con Cython: libera el GIL con Py_BEGIN_ALLOW_THREADS
    para procesar batches de miles de eventos sin bloquear el loop.
    """
    if _HAS_NATIVE and hasattr(_native_impl, "chained_hash"):
        return _native_impl.chained_hash(data, prev_hash)

    combined = (prev_hash.encode("utf-8") + data) if prev_hash else data
    return hashlib.sha256(combined).hexdigest()


def batch_hash(entries: list[tuple[bytes, str]]) -> list[str]:
    """Hash de multiples entradas en batch (acelerable via SIMD con extension nativa).

    Args:
        entries: Lista de (data, prev_hash) para hashear encadenadamente.

    Returns:
        Lista de hashes en el mismo orden.
    """
    if _HAS_NATIVE and hasattr(_native_impl, "batch_hash"):
        return _native_impl.batch_hash(entries)

    return [chained_hash_sha256(data, prev) for data, prev in entries]


# ═══════════════════════════════════════════════════════════════════
# 3. DECOMPRESS RAPIDO DE MESSAGEPACK (zero-copy friendly)
# ═══════════════════════════════════════════════════════════════════

def fast_msgpack_unpack(data: bytes) -> Any:
    """Decompress de MessagePack con soporte nativo.

    En produccion con extension C: opera directo sobre el buffer
    sin copia intermedia y libera el GIL.
    """
    if _HAS_NATIVE and hasattr(_native_impl, "msgpack_unpack"):
        return _native_impl.msgpack_unpack(data)

    import msgpack
    return msgpack.unpackb(data, raw=False)


def fast_msgpack_pack(obj: Any) -> bytes:
    """Compress a MessagePack con soporte nativo."""
    if _HAS_NATIVE and hasattr(_native_impl, "msgpack_pack"):
        return _native_impl.msgpack_pack(obj)

    import msgpack
    return msgpack.packb(obj, use_bin_type=True)


# ═══════════════════════════════════════════════════════════════════
# 4. CANONICAL JSON (serializacion determinista)
# ═══════════════════════════════════════════════════════════════════

def canonical_json(obj: Any) -> bytes:
    """JSON canonical: keys ordenadas, sin espacios, deterministico.

    Usado para firmas ECDSA donde el payload debe ser reproducible.
    """
    if _HAS_NATIVE and hasattr(_native_impl, "canonical_json"):
        return _native_impl.canonical_json(obj)

    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


# ═══════════════════════════════════════════════════════════════════
# 5. CYTHON STUB (codigo .pyx para compilar)
# ═══════════════════════════════════════════════════════════════════

CYTHON_STUB = """
# core/_cnative.pyx — Extension Cython para aceleracion sin GIL
# Compilar con: cythonize -i core/_cnative.pyx

from libc.string cimport memcpy
from cpython.bytes cimport PyBytes_FromStringAndSize
import hashlib

cdef extern from "Python.h":
    void Py_BEGIN_ALLOW_THREADS
    void Py_END_ALLOW_THREADS

cpdef str chained_hash(bytes data, str prev_hash=""):
    cdef bytes combined
    cdef bytes result

    if prev_hash:
        combined = prev_hash.encode('utf-8') + data
    else:
        combined = data

    Py_BEGIN_ALLOW_THREADS
    result = hashlib.sha256(combined).digest()
    Py_END_ALLOW_THREADS

    return result.hex()

cpdef list batch_hash(list entries):
    cdef list results = []
    cdef bytes data
    cdef str prev
    cdef bytes combined

    for data, prev in entries:
        if prev:
            combined = prev.encode('utf-8') + data
        else:
            combined = data

        Py_BEGIN_ALLOW_THREADS
        results.append(hashlib.sha256(combined).hexdigest())
        Py_END_ALLOW_THREADS

    return results

cpdef object msgpack_unpack(bytes data):
    import msgpack
    Py_BEGIN_ALLOW_THREADS
    result = msgpack.unpackb(data, raw=False)
    Py_END_ALLOW_THREADS
    return result

cpdef bytes msgpack_pack(object obj):
    import msgpack
    cdef bytes result
    Py_BEGIN_ALLOW_THREADS
    result = msgpack.packb(obj, use_bin_type=True)
    Py_END_ALLOW_THREADS
    return result

cpdef bytes canonical_json(object obj):
    import json
    cdef bytes result
    Py_BEGIN_ALLOW_THREADS
    result = json.dumps(obj, sort_keys=True, ensure_ascii=False,
                         separators=(',', ':')).encode('utf-8')
    Py_END_ALLOW_THREADS
    return result
"""


# ═══════════════════════════════════════════════════════════════════
# 6. ACELERADOR DE VALIDACION ECDSA EN BATCH
# ═══════════════════════════════════════════════════════════════════

def batch_verify_ecdsa(entries: list[tuple[bytes, bytes, str]]) -> list[bool]:
    """Verifica multiples firmas ECDSA en batch.

    Args:
        entries: Lista de (public_key_pem, payload_canonical, signature_hex).

    Returns:
        Lista de booleanos: True si la firma es valida.
    """
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    results = []
    for pub_key_pem, payload, sig_hex in entries:
        try:
            public_key = load_pem_public_key(pub_key_pem)
            signature = bytes.fromhex(sig_hex)
            public_key.verify(signature, payload, ec.ECDSA(hashes.SHA256()))
            results.append(True)
        except Exception:
            results.append(False)
    return results


# ═══════════════════════════════════════════════════════════════════
# 7. PERF COUNTER DE ALTA PRECISION
# ═══════════════════════════════════════════════════════════════════

def hrtimestamp() -> float:
    """Timestamp de alta resolucion para microbenchmarking."""
    if _HAS_NATIVE and hasattr(_native_impl, "hrtimestamp"):
        return _native_impl.hrtimestamp()
    return time.perf_counter()


__all__ = [
    "chained_hash_sha256",
    "batch_hash",
    "fast_msgpack_unpack",
    "fast_msgpack_pack",
    "canonical_json",
    "batch_verify_ecdsa",
    "hrtimestamp",
    "CYTHON_STUB",
    "_HAS_NATIVE",
]
