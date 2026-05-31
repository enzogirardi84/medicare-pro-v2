"""Simulador de Procesamiento Fotonico No-Lineal (Optical Co-Processor).
Procesa senales analiticas a traves de compuertas logicas fotonicas
simuladas. Consumo energetico teorico cero. Velocidad de la luz.
"""
from __future__ import annotations

import cmath
import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from enum import Enum

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE COMPUTACION FOTONICA
# ═══════════════════════════════════════════════════════════════════

class PhotonicGate(Enum):
    BEAM_SPLITTER = "beam_splitter"    # divisor de haz 50/50
    PHASE_SHIFTER = "phase_shifter"    # desfasador
    MACH_ZEHNDER = "mach_zehnder"      # interferometro MZ
    DIRECTIONAL_COUPLER = "directional_coupler"
    OPTICAL_AMPLIFIER = "optical_amplifier"


@dataclass
class OpticalMode:
    """Modo optico con amplitud compleja."""
    amplitude: complex = 1.0 + 0j       # amplitud del campo electrico
    phase: float = 0.0                   # fase en radianes
    frequency_thz: float = 193.5         # frecuencia en THz (C-band: 1550nm)
    power_mw: float = 1.0                # potencia en mW

    @property
    def intensity(self) -> float:
        return abs(self.amplitude) ** 2


@dataclass
class PhotonicCircuit:
    """Circuito fotonico con compuertas y modos."""
    circuit_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    modes: list[OpticalMode] = field(default_factory=list)
    gates: list[dict] = field(default_factory=list)  # {type, input, output, params}
    latency_ps: float = 0.0             # latencia en picosegundos
    energy_pj: float = 0.0              # energia en picojoules


# ═══════════════════════════════════════════════════════════════════
# 2. COMPUERTAS LOGICAS FOTONICAS
# ═══════════════════════════════════════════════════════════════════

class PhotonicGateProcessor:
    """Procesador de compuertas logicas fotonicas.

    Opera sobre modos opticos (amplitudes complejas).
    Simula el comportamiento de componentes fotonicos reales.
    """

    @staticmethod
    def beam_splitter(mode_a: OpticalMode, mode_b: OpticalMode,
                       ratio: float = 0.5) -> tuple[OpticalMode, OpticalMode]:
        """Divisor de haz 50/50 con matriz de scattering.

        [Ea_out]   [sqrt(r)   i*sqrt(1-r)] [Ea_in]
        [Eb_out] = [i*sqrt(1-r) sqrt(r)  ] [Eb_in]
        """
        r = ratio
        a_out = OpticalMode(
            amplitude=math.sqrt(r) * mode_a.amplitude + 1j * math.sqrt(1 - r) * mode_b.amplitude,
            phase=mode_a.phase,
        )
        b_out = OpticalMode(
            amplitude=1j * math.sqrt(1 - r) * mode_a.amplitude + math.sqrt(r) * mode_b.amplitude,
            phase=mode_b.phase,
        )
        return a_out, b_out

    @staticmethod
    def phase_shifter(mode: OpticalMode, phase_shift: float) -> OpticalMode:
        """Desfasador optico: e^(i*phi)."""
        return OpticalMode(
            amplitude=mode.amplitude * cmath.exp(1j * phase_shift),
            phase=(mode.phase + phase_shift) % (2 * math.pi),
        )

    @staticmethod
    def mach_zehnder_interferometer(mode_a: OpticalMode, mode_b: OpticalMode,
                                     phase_diff: float) -> tuple[OpticalMode, OpticalMode]:
        """Interferometro Mach-Zehnder: BS + PS + BS."""
        a1, b1 = PhotonicGateProcessor.beam_splitter(mode_a, mode_b, 0.5)
        a1 = PhotonicGateProcessor.phase_shifter(a1, phase_diff)
        return PhotonicGateProcessor.beam_splitter(a1, b1, 0.5)

    @staticmethod
    def directional_coupler(modes: list[OpticalMode],
                            coupling_matrix: list[list[complex]]) -> list[OpticalMode]:
        """Acoplador direccional MxN: M salidas, N entradas."""
        num_outputs = len(coupling_matrix)
        n_modes = len(modes)
        outputs = []
        for i in range(num_outputs):
            amplitude = sum(coupling_matrix[i][j] * modes[j].amplitude for j in range(min(n_modes, len(coupling_matrix[i]))))
            outputs.append(OpticalMode(amplitude=amplitude))
        return outputs


# ═══════════════════════════════════════════════════════════════════
# 3. CO-PROCESADOR OPTICO DE SEÑALES CLINICAS
# ═══════════════════════════════════════════════════════════════════

class OpticalCoProcessor:
    """Co-Procesador Optico para analisis de señales clinicas.

    Mapea señales de ECG/EEG a modos opticos,
    las procesa a traves de compuertas fotonicas,
    extrae diagnostico a velocidad de la luz.
    """

    def __init__(self):
        self._circuits: list[PhotonicCircuit] = []
        self._total_energy_pj = 0.0

    def encode_signal_to_optical(self, samples: list[float]) -> list[OpticalMode]:
        """Codifica una señal analogica a modos opticos.

        Cada muestra → modo optico con amplitud proporcional.
        Frecuencia portadora: 193.5 THz (1550 nm).
        """
        modes = []
        for i, s in enumerate(samples):
            # Normalizar amplitud y codificar como fase + amplitud
            amp = max(-1.0, min(1.0, s / max(abs(s) for s in samples))) if samples else 0
            phase = 2 * math.pi * i / len(samples) if samples else 0
            mode = OpticalMode(
                amplitude=amp * (0.8 + 0.2j),
                phase=phase,
            )
            modes.append(mode)
        return modes

    def process_ecg_beat_detection(self, modes: list[OpticalMode]) -> list[float]:
        """Deteccion de latidos ECG usando interferometria optica.

        Los picos R se detectan por interferencia constructiva
        en un interferometro Mach-Zehnder.
        """
        peaks = []
        if len(modes) < 4:
            return peaks

        for i in range(1, len(modes) - 1):
            # Interferometro MZ: detectar cambios bruscos de fase
            a, b = PhotonicGateProcessor.mach_zehnder_interferometer(
                modes[i - 1], modes[i], phase_diff=math.pi * modes[i].intensity,
            )
            # Pico R: interferencia destructiva (intensidad minima)
            if a.intensity < 0.1 and b.intensity < 0.1:
                peaks.append(float(i))

        circuit = PhotonicCircuit(
            modes=modes,
            gates=[{"type": "mach_zehnder", "count": len(modes)}],
            latency_ps=len(modes) * 0.1,   # 0.1 ps por modo
            energy_pj=len(modes) * 0.001,  # 1 fJ por operacion
        )
        self._circuits.append(circuit)
        self._total_energy_pj += circuit.energy_pj

        log_event("photonic", f"ecg_peaks:{len(peaks)}:{circuit.latency_ps:.1f}ps:{circuit.energy_pj:.3f}pJ")
        return peaks

    def process_eeg_band_separation(self, modes: list[OpticalMode]) -> dict:
        """Separacion de bandas EEG usando acopladores direccionales.

        Cada banda (Delta, Theta, Alpha, Beta, Gamma) se separa
        en un modo optico diferente por filtrado interferometrico.
        """
        bands = {"delta": 0, "theta": 0, "alpha": 0, "beta": 0, "gamma": 0}
        if not modes:
            return bands

        # Matriz de acoplamiento: separa frecuencias por fase
        n = len(modes)
        coupling = [[complex(0) for _ in range(n)] for _ in range(5)]
        for i in range(n):
            phase = modes[i].phase
            # Banda Delta: fase 0-0.5
            coupling[0][i] = complex(math.cos(phase * 0.5), 0)
            # Theta: fase 0.5-1.0
            coupling[1][i] = complex(math.sin(phase * 0.5), 0)
            # Alpha: fase 1.0-1.5
            coupling[2][i] = complex(math.cos(phase), math.sin(phase))
            # Beta: fase 1.5-2.0
            coupling[3][i] = complex(math.cos(phase * 2), 0)
            # Gamma: fase 2.0+
            coupling[4][i] = complex(math.sin(phase * 2), math.cos(phase))

        outputs = PhotonicGateProcessor.directional_coupler(modes, coupling)
        for i, name in enumerate(["delta", "theta", "alpha", "beta", "gamma"]):
            bands[name] = round(outputs[i].intensity, 4)

        return bands

    def get_stats(self) -> dict:
        return {
            "circuits_processed": len(self._circuits),
            "total_energy_pj": round(self._total_energy_pj, 6),
            "total_latency_ps": round(
                sum(c.latency_ps for c in self._circuits), 2
            ),
        }


__all__ = [
    "OpticalCoProcessor",
    "PhotonicGateProcessor",
    "OpticalMode",
    "PhotonicCircuit",
]
