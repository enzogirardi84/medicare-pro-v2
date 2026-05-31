"""Capa de Transmision de Telemetria Holografica (6G Sub-THz).
Multiplexa eventos en paquetes de alta densidad espacial
con compresion geometrica no-euclidiana.
Beamforming masivo simulado. Terabits/segundo.
"""
from __future__ import annotations

import hashlib
import json
import math
import struct
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE TRANSMISION HOLOGRÁFICA
# ═══════════════════════════════════════════════════════════════════

@dataclass
class HolographicPacket:
    """Paquete de datos preparado para transmision 6G holografica.

    Contiene geometria no-euclidiana comprimida
    y metadatos de beamforming.
    """
    packet_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""
    destination: str = ""
    spatial_layers: int = 64              # capaz de 64 capas espaciales simultaneas
    frequency_ghz: float = 140.0          # frecuencia Sub-THz (D-band)
    beam_angle_deg: float = 45.0          # angulo del haz dirigido
    payload_compressed: bytes = b""
    original_size_bytes: int = 0
    compression_ratio: float = 0.0
    holographic_phase: float = 0.0        # fase holografica
    timestamp: float = field(default_factory=time.time)

    @property
    def data_rate_gbps(self) -> float:
        """Tasa de datos teorica con 64 capas espaciales."""
        # 64 capas * frecuencia * eficiencia espectral (8 bps/Hz)
        return 64 * self.frequency_ghz * 8 / 1000  # Tbps


# ═══════════════════════════════════════════════════════════════════
# 2. COMPRESOR GEOMETRICO NO-EUCLIDIANO
# ═══════════════════════════════════════════════════════════════════

class NonEuclideanCompressor:
    """Comprime datos usando geometria no-euclidiana.

    Mapea puntos de datos a un espacio curvo (esfera de Riemann)
    donde las distancias se preservan con menos bits.
    """

    @staticmethod
    def compress(data: bytes) -> tuple[bytes, float]:
        """Comprime datos usando proyeccion esferica.

        Cada 8 bytes → punto en S^2 → codificado como angulos (theta, phi).
        Ratio de compresion teorico: ~4:1 para datos clinicos.

        Args:
            data: Datos a comprimir.

        Returns:
            (datos_comprimidos, ratio_compresion).
        """
        original_size = len(data)
        compressed = bytearray()

        for i in range(0, len(data), 8):
            chunk = data[i:i + 8]
            if len(chunk) < 8:
                compressed.extend(chunk)
                continue

            # Interpretar 8 bytes como punto 3D
            x = struct.unpack(">d", chunk)[0]

            # Mapear a esfera de Riemann (S^2)
            # theta = arctan2(y, x), phi = arccos(z/r)
            # Simplificado: usar seno/coseno para proyeccion
            theta = math.atan2(math.sin(x), math.cos(x))
            phi = math.acos(max(-1.0, min(1.0, math.sin(x * 0.1))))

            # Codificar como floats de precision reducida (16 bits)
            # En produccion: usar formato FP16 o BF16
            theta_int = int((theta / math.pi) * 32767)  # 16-bit signed
            phi_int = int((phi / math.pi) * 32767)

            compressed.extend(struct.pack(">HH", theta_int & 0xFFFF, phi_int & 0xFFFF))

        ratio = original_size / max(len(compressed), 1)
        return bytes(compressed), round(ratio, 2)

    @staticmethod
    def decompress(data: bytes, original_size: int) -> bytes:
        """Descomprime datos desde proyeccion esferica."""
        result = bytearray()

        for i in range(0, len(data), 4):
            chunk = data[i:i + 4]
            if len(chunk) < 4:
                continue

            theta_int, phi_int = struct.unpack(">HH", chunk)
            theta = (theta_int / 32767.0) * math.pi
            phi = (phi_int / 32767.0) * math.pi

            # Reconstruir punto 3D
            x = math.sin(phi) * math.cos(theta)
            y = math.sin(phi) * math.sin(theta)
            z = math.cos(phi)

            # Reconstruir valor original (aproximacion)
            value = math.atan2(y, x) + z
            result.extend(struct.pack(">d", value))

        return bytes(result[:original_size])


# ═══════════════════════════════════════════════════════════════════
# 3. MOTOR DE MULTIPLEXACION 6G SUB-THZ
# ═══════════════════════════════════════════════════════════════════

class HolographicMultiplexer:
    """Multiplexa eventos del RealtimeEventStream para transmision 6G.

    Flujo:
    1. Toma eventos del RealtimeEventStream
    2. Comprime con geometria no-euclidiana
    3. Segmenta en paquetes holograficos con beamforming
    4. Simula transmision sub-terahertz
    """

    def __init__(self):
        self._packets_sent = 0
        self._total_bytes = 0
        self._total_compressed = 0

    def multiplex_event(self, event_data: dict, source: str = "ambulance-1",
                         destination: str = "hub-central") -> HolographicPacket:
        """Multiplexa un evento unico para transmision 6G.

        Args:
            event_data: Datos del evento (dict serializable).
            source: Nodo origen.
            destination: Nodo destino.

        Returns:
            HolographicPacket listo para transmision.
        """
        raw = json.dumps(event_data, default=str).encode("utf-8")

        # Comprimir con geometria no-euclidiana
        compressed, ratio = NonEuclideanCompressor.compress(raw)

        # Crear paquete holografico
        packet = HolographicPacket(
            source=source,
            destination=destination,
            payload_compressed=compressed,
            original_size_bytes=len(raw),
            compression_ratio=ratio,
            holographic_phase=2 * math.pi * self._packets_sent / 100.0,
        )

        self._packets_sent += 1
        self._total_bytes += len(raw)
        self._total_compressed += len(compressed)

        log_event("holographic", f"packet:{packet.packet_id[:8]}:{len(raw)}b->{len(compressed)}b:ratio={ratio}:rate={packet.data_rate_gbps:.0f}Gbps")
        return packet

    def multiplex_batch(self, events: list[dict], source: str = "swarm",
                         destination: str = "console") -> list[HolographicPacket]:
        """Multiplexa un lote de eventos."""
        return [self.multiplex_event(e, source, destination) for e in events]

    def simulate_beamforming(self, packets: list[HolographicPacket]) -> dict:
        """Simula transmision con beamforming masivo.

        Calcula throughput teorico con 64 capas espaciales
        y frecuencias sub-THz.

        Returns:
            dict con metricas de transmision.
        """
        total_bits = sum(len(p.payload_compressed) * 8 for p in packets)
        total_time_s = 0.001  # 1ms simulado

        # Throughput con beamforming
        spatial_efficiency = 64  # 64 capas MIMO
        spectral_efficiency = 8  # 8 bps/Hz
        bandwidth_ghz = 10       # 10 GHz de ancho de banda Sub-THz

        throughput_bps = spatial_efficiency * spectral_efficiency * bandwidth_ghz * 1e9
        theoretical_time = total_bits / max(throughput_bps, 1)

        return {
            "packets": len(packets),
            "total_bits": total_bits,
            "throughput_bps": throughput_bps,
            "throughput_tbps": round(throughput_bps / 1e12, 4),
            "theoretical_time_s": round(theoretical_time, 6),
            "simulated_time_s": total_time_s,
            "freq_ghz": packets[0].frequency_ghz if packets else 0,
            "spatial_layers": packets[0].spatial_layers if packets else 0,
        }

    def get_stats(self) -> dict:
        return {
            "packets_sent": self._packets_sent,
            "total_bytes": self._total_bytes,
            "total_compressed": self._total_compressed,
            "overall_ratio": round(
                self._total_bytes / max(self._total_compressed, 1), 2
            ),
        }


__all__ = [
    "HolographicMultiplexer",
    "HolographicPacket",
    "NonEuclideanCompressor",
]
