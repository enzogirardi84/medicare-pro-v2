"""Capa de Telemetria Neuronal de Emergencia (BCI).
Procesa canales EEG crudos, aplica FFT, clasifica bandas de frecuencia,
decodifica nivel de conciencia y dolor. Almacena en Event Store.
"""
from __future__ import annotations

import math
import struct
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS NEURONALES
# ═══════════════════════════════════════════════════════════════════

class EEGBand(Enum):
    DELTA = (0.5, 4)      # sueño profundo
    THETA = (4, 8)        # somnolencia, meditacion
    ALPHA = (8, 13)       # relajacion, ojos cerrados
    BETA = (13, 30)       # actividad consciente, estres
    GAMMA = (30, 50)      # cognicion de alto nivel

    @property
    def low_hz(self) -> float:
        return self.value[0]

    @property
    def high_hz(self) -> float:
        return self.value[1]


class ConsciousnessLevel(Enum):
    ALERT = "alert"                  # consciente, orientado
    CONFUSED = "confused"            # desorientado, somnoliento
    STUPOROUS = "stuporous"          # responde solo a estimulo doloroso
    COMA = "coma"                    # sin respuesta
    BRAIN_DEATH = "brain_death"      # actividad eléctrica cerebral ausente


@dataclass
class EEGChannel:
    """Canal de EEG procesado."""
    channel_name: str               # "Fz", "Cz", "Pz", "O1", "O2", etc.
    samples: list[float] = field(default_factory=list)
    sample_rate_hz: int = 256
    timestamp: float = field(default_factory=time.time)

    # Potencia por banda (uV^2)
    delta_power: float = 0.0
    theta_power: float = 0.0
    alpha_power: float = 0.0
    beta_power: float = 0.0
    gamma_power: float = 0.0

    @property
    def total_power(self) -> float:
        return self.delta_power + self.theta_power + self.alpha_power + self.beta_power + self.gamma_power

    @property
    def alpha_ratio(self) -> float:
        """Ratio alfa/theta: indicador de relajacion vs somnolencia."""
        return self.alpha_power / max(self.theta_power, 0.001)


@dataclass
class NeuralState:
    """Estado neuronal decodificado del paciente."""
    state_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    consciousness: ConsciousnessLevel = ConsciousnessLevel.ALERT
    pain_level: float = 0.0                # 0.0 - 1.0 (estimado)
    stress_index: float = 0.0              # 0.0 - 1.0 (basado en ratio beta/alpha)
    dominant_band: str = "alpha"
    channels: list[EEGChannel] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_event_store_payload(self) -> dict:
        """Payload listo para insertar en clinical_event_store."""
        return {
            "id": self.state_id,
            "tipo": "eeg_neural_state",
            "consciousness": self.consciousness.value,
            "pain_level": round(self.pain_level, 3),
            "stress_index": round(self.stress_index, 3),
            "dominant_band": self.dominant_band,
            "channels": len(self.channels),
            "band_powers": {
                ch.channel_name: {
                    "delta": round(ch.delta_power, 2),
                    "theta": round(ch.theta_power, 2),
                    "alpha": round(ch.alpha_power, 2),
                    "beta": round(ch.beta_power, 2),
                    "gamma": round(ch.gamma_power, 2),
                }
                for ch in self.channels
            },
            "timestamp": self.timestamp,
        }


# ═══════════════════════════════════════════════════════════════════
# 2. PROCESADOR FFT Y EXTRACCION DE BANDAS
# ═══════════════════════════════════════════════════════════════════

class EEGProcessor:
    """Procesador de senal EEG en el Edge (ambulancia).

    Aplica FFT a ventanas deslizantes, extrae potencia por banda.
    Clasifica nivel de conciencia y dolor.
    """

    def __init__(self, sample_rate: int = 256, window_seconds: int = 2):
        self.sample_rate = sample_rate
        self.window_size = sample_rate * window_seconds
        self._buffer: deque[float] = deque(maxlen=self.window_size)

    def ingest_sample(self, value: float):
        """Ingiere una muestra EEG cruda."""
        self._buffer.append(value)

    def process_window(self, channel_name: str = "Cz") -> Optional[EEGChannel]:
        """Procesa la ventana actual y extrae potencia por banda.

        Aplica FFT al buffer y calcula potencia espectral
        en cada banda de frecuencia (Delta, Theta, Alpha, Beta, Gamma).
        """
        if len(self._buffer) < self.window_size:
            return None

        samples = list(self._buffer)

        # Aplicar ventana Hann
        n = len(samples)
        hann = [0.5 * (1 - math.cos(2 * math.pi * i / (n - 1))) for i in range(n)]
        windowed = [samples[i] * hann[i] for i in range(n)]

        # FFT manual simplificada: descomponer en componentes frecuenciales
        # En producción: usar numpy.fft.rfft()
        spectrum = self._simple_fft_magnitudes(windowed)

        # Extraer potencia por banda
        ch = EEGChannel(channel_name=channel_name, sample_rate_hz=self.sample_rate)
        ch.delta_power = self._band_power(spectrum, EEGBand.DELTA)
        ch.theta_power = self._band_power(spectrum, EEGBand.THETA)
        ch.alpha_power = self._band_power(spectrum, EEGBand.ALPHA)
        ch.beta_power = self._band_power(spectrum, EEGBand.BETA)
        ch.gamma_power = self._band_power(spectrum, EEGBand.GAMMA)

        return ch

    def _simple_fft_magnitudes(self, signal: list[float]) -> list[float]:
        """FFT simplificada: calcula magnitudes frecuenciales.

        En producción: reemplazar por numpy.fft.rfft().
        Stub: usa Goertzel simplificado.
        """
        n = len(signal)
        magnitudes = []
        for k in range(1, n // 2 + 1):
            real = 0.0
            imag = 0.0
            for i in range(n):
                angle = 2 * math.pi * k * i / n
                real += signal[i] * math.cos(angle)
                imag -= signal[i] * math.sin(angle)
            magnitudes.append(math.sqrt(real ** 2 + imag ** 2) / n)
        return magnitudes

    def _band_power(self, spectrum: list[float], band: EEGBand) -> float:
        """Potencia total en una banda de frecuencia."""
        n = len(self._buffer)
        low_idx = int(band.low_hz * n / self.sample_rate)
        high_idx = int(band.high_hz * n / self.sample_rate)
        low_idx = max(1, min(low_idx, len(spectrum) - 1))
        high_idx = max(low_idx, min(high_idx, len(spectrum)))
        return sum(spectrum[low_idx:high_idx]) / max(high_idx - low_idx, 1)

    def decode_neural_state(self, channels: list[EEGChannel]) -> NeuralState:
        """Decodifica estado neuronal desde canales procesados.

        Algoritmo:
        - Conciencia: basado en relacion Theta/Alpha y potencia Delta
        - Dolor: ratio Beta/Alpha (mayor = mas dolor)
        - Estres: nivel de Beta + Gamma
        """
        if not channels:
            return NeuralState(consciousness=ConsciousnessLevel.ALERT)

        # Promediar potencias entre canales
        avg = {
            "delta": sum(ch.delta_power for ch in channels) / len(channels),
            "theta": sum(ch.theta_power for ch in channels) / len(channels),
            "alpha": sum(ch.alpha_power for ch in channels) / len(channels),
            "beta": sum(ch.beta_power for ch in channels) / len(channels),
            "gamma": sum(ch.gamma_power for ch in channels) / len(channels),
        }

        # Banda dominante
        dominant = max(avg, key=avg.get)

        # Nivel de conciencia
        if avg["delta"] > avg["alpha"] * 3 and avg["theta"] > avg["beta"]:
            consciousness = ConsciousnessLevel.COMA
        elif avg["theta"] > avg["alpha"] and avg["delta"] > avg["beta"]:
            consciousness = ConsciousnessLevel.STUPOROUS
        elif avg["theta"] > avg["alpha"] * 0.7:
            consciousness = ConsciousnessLevel.CONFUSED
        else:
            consciousness = ConsciousnessLevel.ALERT

        # Dolor: ratio beta/(alpha+theta)
        pain_ratio = avg["beta"] / max(avg["alpha"] + avg["theta"], 0.001)
        pain_level = min(1.0, pain_ratio / 5.0)

        # Estrés: beta/alpha
        stress_ratio = avg["beta"] / max(avg["alpha"], 0.001)
        stress_index = min(1.0, stress_ratio / 10.0)

        return NeuralState(
            consciousness=consciousness,
            pain_level=round(pain_level, 3),
            stress_index=round(stress_index, 3),
            dominant_band=dominant,
            channels=channels,
        )


# ═══════════════════════════════════════════════════════════════════
# 3. ORQUESTADOR BCI
# ═══════════════════════════════════════════════════════════════════

class BCITelemetryCore:
    """Orquestador de telemetria neuronal en la ambulancia.

    Flujo:
    1. Recibe stream LSL de cascos EEG (256 Hz, 8 canales)
    2. Procesa ventanas FFT cada 2 segundos
    3. Decodifica estado neuronal (conciencia, dolor, estres)
    4. Almacena como evento inmutable en clinical_event_store
    """

    def __init__(self, sample_rate: int = 256):
        self._processors: dict[str, EEGProcessor] = {}
        self.sample_rate = sample_rate
        self._last_state: Optional[NeuralState] = None

    def register_channel(self, channel_name: str):
        """Registra un canal EEG para procesamiento."""
        self._processors[channel_name] = EEGProcessor(
            sample_rate=self.sample_rate,
            window_seconds=2,
        )

    def ingest_sample(self, channel_name: str, value: float):
        """Ingiere una muestra EEG cruda de un canal."""
        proc = self._processors.get(channel_name)
        if proc:
            proc.ingest_sample(value)

    def process_and_decode(self) -> Optional[NeuralState]:
        """Procesa todos los canales y decodifica estado neuronal.

        Returns:
            NeuralState si hay suficientes datos, None si no.
        """
        channels = []
        for name, proc in self._processors.items():
            ch = proc.process_window(name)
            if ch:
                channels.append(ch)

        if len(channels) < 1:
            return None

        # Usar primer canal como referencia si solo hay uno
        primary = next((c for c in channels if c.channel_name == "Cz"), channels[0])
        state = EEGProcessor.decode_neural_state(NeuralState, channels if len(channels) > 1 else [primary])
        self._last_state = state

        log_event("bci", f"decoded:{state.consciousness.value}:pain={state.pain_level}:stress={state.stress_index}")
        return state

    def get_current_state(self) -> Optional[NeuralState]:
        return self._last_state


__all__ = [
    "BCITelemetryCore",
    "EEGProcessor",
    "NeuralState",
    "EEGChannel",
    "EEGBand",
    "ConsciousnessLevel",
]
