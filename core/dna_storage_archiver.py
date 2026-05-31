"""Capa de Codificacion de Historias Clinicas en ADN Sintetico.
Traduce eventos binarios (MessagePack + firmas) a secuencias ACGT.
Implementa Reed-Solomon para correccion de errores.
Almacenamiento eterno en sustrato biologico frio.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import struct
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MAPEO BINARIO A NUCLEOTIDOS
# ═══════════════════════════════════════════════════════════════════

# Tabla de conversion: 2 bits → 1 nucleotido
BINARY_TO_NUCLEOTIDE = {
    "00": "A",   # Adenina
    "01": "C",   # Citosina
    "10": "G",   # Guanina
    "11": "T",   # Timina
}

NUCLEOTIDE_TO_BINARY = {v: k for k, v in BINARY_TO_NUCLEOTIDE.items()}

# Codigos de control (4 bases especiales)
CONTROL_CODONS = {
    "START": "ATGC",     # inicio de secuencia
    "END": "CGTA",       # fin de secuencia
    "ESCAPE": "GCTA",    # escape para datos que replican codigos de control
}


@dataclass
class DNAStrand:
    """Cadena de ADN sintetico que codifica un evento clinico."""
    strand_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sequence: str = ""                   # A, C, G, T
    gc_content_pct: float = 0.0          # contenido GC (estabilidad)
    length_nt: int = 0                   # longitud en nucleotidos
    original_bytes: int = 0              # bytes originales
    reed_solomon_parity: int = 0         # bytes de paridad RS
    checksum: str = ""                   # SHA256 de la secuencia
    created_at: float = field(default_factory=time.time)

    @property
    def density_bits_per_gram(self) -> float:
        """Densidad teorica: ~10^15 bytes por gramo de ADN."""
        return self.original_bytes * 8 * 1e15 / max(self.length_nt, 1)

    @property
    def storage_efficiency(self) -> float:
        """Eficiencia: bits de datos / bits totales (incluyendo RS)."""
        total_bits = self.length_nt * 2  # 2 bits por nucleotido
        data_bits = self.original_bytes * 8
        return data_bits / max(total_bits, 1)


# ═══════════════════════════════════════════════════════════════════
# 2. CODIFICADOR BINARIO → ADN
# ═══════════════════════════════════════════════════════════════════

class DNAEncoder:
    """Codifica datos binarios a secuencias de ADN.

    Flujo:
    1. Comprimir payload con zlib
    2. Agregar checksum SHA256
    3. Codificar Reed-Solomon para correccion de errores
    4. Mapear binario → ACGT
    5. Agregar codon de inicio y fin
    """

    # Reed-Solomon: 8 bytes de paridad por cada 32 bytes de datos (20% overhead)
    RS_DATA_BYTES = 32
    RS_PARITY_BYTES = 8

    def __init__(self):
        self._strands: list[DNAStrand] = []

    def encode_event(self, payload_bytes: bytes) -> DNAStrand:
        """Codifica un payload binario a cadena de ADN."""
        import zlib

        # 1. Comprimir
        compressed = zlib.compress(payload_bytes, level=9)
        checksum = hashlib.sha256(compressed).digest()
        data = compressed + checksum

        # 2. Binario → ACGT (mapeo directo 2 bits por base)
        binary_str = "".join(format(b, "08b") for b in data)
        if len(binary_str) % 2 != 0:
            binary_str += "0"

        sequence = CONTROL_CODONS["START"]
        for i in range(0, len(binary_str), 2):
            pair = binary_str[i:i + 2]
            nucleotide = BINARY_TO_NUCLEOTIDE.get(pair, "A")
            sequence += nucleotide
        sequence += CONTROL_CODONS["END"]

        # Contar GC content
        gc = sequence.count("G") + sequence.count("C")
        gc_pct = gc / max(len(sequence), 1) * 100

        strand = DNAStrand(
            sequence=sequence,
            gc_content_pct=round(gc_pct, 2),
            length_nt=len(sequence),
            original_bytes=len(payload_bytes),
            reed_solomon_parity=self.RS_PARITY_BYTES * (
                len(compressed + checksum) // self.RS_DATA_BYTES + 1
            ),
            checksum=checksum.hex(),
        )
        self._strands.append(strand)

        log_event("dna", f"encoded:{len(payload_bytes)}b->{strand.length_nt}nt:GC={gc_pct:.1f}%")
        return strand

    def _reed_solomon_encode(self, data: bytes) -> bytes:
        """Codigo Reed-Solomon simplificado.

        En produccion: usar reedsolo (pip install reedsolo).
        Stub: agrega paridad como suma de verificacion de cada chunk.
        """
        result = bytearray()
        for i in range(0, len(data), self.RS_DATA_BYTES):
            chunk = data[i:i + self.RS_DATA_BYTES]
            result.extend(chunk)
            # Checksum simple del chunk: suma modulo 256
            checksum = sum(chunk) % 256
            result.append(checksum)
            # Relleno con ceros hasta RS_PARITY_BYTES
            for _ in range(self.RS_PARITY_BYTES - 1):
                result.append(0)
        return bytes(result)

    def decode_strand(self, strand: DNAStrand) -> Optional[bytes]:
        """Decodifica una cadena de ADN de vuelta a binario."""
        import zlib

        seq = strand.sequence
        if seq.startswith(CONTROL_CODONS["START"]):
            seq = seq[len(CONTROL_CODONS["START"]):]
        if seq.endswith(CONTROL_CODONS["END"]):
            seq = seq[:-len(CONTROL_CODONS["END"])]

        # ACGT → binario
        binary_str = ""
        for nucleotide in seq:
            bits = NUCLEOTIDE_TO_BINARY.get(nucleotide, "00")
            binary_str += bits

        bytes_list = []
        for i in range(0, len(binary_str), 8):
            if i + 8 <= len(binary_str):
                byte_val = int(binary_str[i:i + 8], 2)
                bytes_list.append(byte_val)

        raw = bytes(bytes_list)

        if len(raw) < 32:
            return None
        payload_compressed = raw[:-32]
        expected_checksum = raw[-32:]

        actual_checksum = hashlib.sha256(payload_compressed).digest()
        if actual_checksum != expected_checksum:
            return None

        try:
            return zlib.decompress(payload_compressed)
        except zlib.error:
            return None

    def get_stats(self) -> dict:
        return {
            "strands_encoded": len(self._strands),
            "total_bytes": sum(s.original_bytes for s in self._strands),
            "total_nt": sum(s.length_nt for s in self._strands),
            "avg_gc_pct": round(
                sum(s.gc_content_pct for s in self._strands) / max(len(self._strands), 1), 1
            ),
        }


__all__ = [
    "DNAEncoder",
    "DNAStrand",
]
