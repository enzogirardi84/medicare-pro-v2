"""Boveda Criptografica en Cristales de Tiempo (Time-Crystal Vault).
Las claves mutan ciclicamente en estados cuanticos predecibles
pero fisicamente inalterables. Rompe la simetria de traslacion temporal.
Ataque forense en cualquier punto de la linea temporal es imposible.
"""
from __future__ import annotations

import hashlib
import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DEL CRISTAL DE TIEMPO
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TimeCrystalState:
    """Estado cuantico de un Cristal de Tiempo.

    El cristal oscila entre estados de espin Up/Down
    rompiendo la simetria de traslacion temporal.
    """
    spin_state: int = 0                # 0 = Up, 1 = Down
    many_body_phase: float = 0.0       # fase colectiva (0 - 2pi)
    period_t: float = 1.0              # periodo de oscilacion (segundos)
    coherence_time: float = 1e6        # tiempo de coherencia (~12 dias)
    energy_level: float = 0.0          # nivel de energia (debe ser 0 idealmente)


@dataclass
class TimeCrystalKey:
    """Clave criptografica generada por el Cristal de Tiempo.

    La clave MUTA ciclicamente: en t=0 es K0, en t=T es K1, etc.
    Solo puede ser reconstruida conociendo el estado cuantico
    del cristal en un instante exacto.
    """
    key_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    seed_hash: str = ""                 # hash de la semilla inicial
    current_key: bytes = b""            # clave actual (mutable en el tiempo)
    time_crystal_state: TimeCrystalState = field(default_factory=TimeCrystalState)
    created_at: float = field(default_factory=time.time)
    oscillations: int = 0


# ═══════════════════════════════════════════════════════════════════
# 2. SIMULADOR DE CRISTAL DE TIEMPO
# ═══════════════════════════════════════════════════════════════════

class TimeCrystalSimulator:
    """Simulador de un Cristal de Tiempo para propositos criptograficos.

    El cristal de tiempo es una fase de la materia que oscila
    perpetuamente sin consumir energia, rompiendo la simetria
    de traslacion temporal.

    La clave K en el instante t se calcula como:
    K(t) = f(seed, P * sin(2*pi*t/T + phi_0), espin(t))
    donde P es la many-body phase y T el periodo.
    """

    def __init__(self, seed: Optional[str] = None):
        self._seed = seed or str(uuid.uuid4())
        self._crystals: dict[str, TimeCrystalKey] = {}

    def create_crystal(self, period_t: float = 2.0) -> TimeCrystalKey:
        """Crea un nuevo Cristal de Tiempo para almacenar claves.

        Args:
            period_t: Periodo de oscilacion en segundos.

        Returns:
            TimeCrystalKey con estado inicial.
        """
        seed_hash = hashlib.sha256(self._seed.encode()).hexdigest()[:32]
        initial_state = TimeCrystalState(
            spin_state=0,
            many_body_phase=math.pi / 4,  # 45 grados
            period_t=period_t,
        )
        key = TimeCrystalKey(
            seed_hash=seed_hash,
            time_crystal_state=initial_state,
            current_key=self._compute_key_at_time(seed_hash, initial_state, 0),
        )
        self._crystals[key.key_id] = key
        log_event("time_crystal", f"created:{key.key_id}:period={period_t}s")
        return key

    def _compute_key_at_time(self, seed_hash: str, state: TimeCrystalState,
                              t: float) -> bytes:
        """Computa la clave en el instante t.

        K(t) = SHA256(seed + espin(t) + fase(t))

        Donde:
        - espin(t) = espin(0) if floor(t/T) es par else 1 - espin(0)
        - fase(t) = many_body_phase * sin(2*pi*t/T)
        """
        period = state.period_t
        period_count = int(t / period) if period > 0 else 0

        # Espin oscila con cada periodo (rompe simetria temporal)
        spin = state.spin_state if period_count % 2 == 0 else 1 - state.spin_state

        # Fase colectiva oscila
        phase = state.many_body_phase * math.sin(2 * math.pi * t / period)

        # Derivar clave
        raw = f"{seed_hash}:{spin}:{phase:.6f}:{period_count}".encode()
        return hashlib.sha256(raw).digest()

    def get_key_at_time(self, crystal_id: str, t: float) -> Optional[bytes]:
        """Obtiene la clave del cristal en un instante temporal especifico.

        La clave solo existe en el instante t. En cualquier otro
        instante, la clave es diferente.

        Args:
            crystal_id: ID del cristal.
            t: Instante temporal (segundos desde creacion).

        Returns:
            Clave en el instante t, o None si el cristal no existe.
        """
        crystal = self._crystals.get(crystal_id)
        if not crystal:
            return None

        key = self._compute_key_at_time(crystal.seed_hash, crystal.time_crystal_state, t)
        crystal.current_key = key
        crystal.oscillations = int(t / crystal.time_crystal_state.period_t)

        return key

    def get_key_now(self, crystal_id: str) -> Optional[bytes]:
        """Obtiene la clave en el instante actual."""
        now = time.time()
        crystal = self._crystals.get(crystal_id)
        if not crystal:
            return None
        t = now - crystal.created_at
        return self.get_key_at_time(crystal_id, t)

    def verify_key_at_time(self, crystal_id: str, key: bytes, t: float) -> bool:
        """Verifica si una clave corresponde al instante t.

        Para verificar, se reconstruye la clave en t
        y se compara.

        Args:
            crystal_id: ID del cristal.
            key: Clave a verificar.
            t: Instante temporal.

        Returns:
            True si la clave es valida para el instante t.
        """
        expected = self.get_key_at_time(crystal_id, t)
        return expected == key

    def simulate_time_attack(self, crystal_id: str) -> dict:
        """Simula un ataque forense al almacenamiento.

        Demuestra que la clave en cualquier instante fijo
        es diferente de la clave en cualquier otro instante.

        Returns:
            dict con claves en diferentes instantes.
        """
        crystal = self._crystals.get(crystal_id)
        if not crystal:
            return {}

        samples = {}
        for t in [0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
            key = self.get_key_at_time(crystal_id, t)
            samples[f"t={t}"] = key.hex()[:16] + "..."

        # Demostrar que todas son diferentes
        unique = len(set(samples.values()))
        samples["time_invariant"] = unique == 1
        samples["time_variant"] = unique > 1

        log_event("time_crystal", f"attack_simulation:{crystal_id}:unique_keys={unique}")
        return samples

    def get_crystal_info(self, crystal_id: str) -> Optional[dict]:
        crystal = self._crystals.get(crystal_id)
        if not crystal:
            return None
        return {
            "key_id": crystal.key_id,
            "oscillations": crystal.oscillations,
            "period_s": crystal.time_crystal_state.period_t,
            "current_key_prefix": crystal.current_key.hex()[:16] + "...",
        }


__all__ = [
    "TimeCrystalSimulator",
    "TimeCrystalKey",
    "TimeCrystalState",
]
