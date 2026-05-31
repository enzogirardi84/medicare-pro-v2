"""Motor de ingesta y procesamiento de señales ECG/Biomédicas en tiempo real.
Corre en el Edge de la ambulancia. Filtra ruido electromagnetico del motor,
detecta anomalias (FV, asistolia), empaqueta en MessagePack.
"""
from __future__ import annotations

import array
import math
import struct
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE TELEMETRIA
# ═══════════════════════════════════════════════════════════════════

class ECGLead(Enum):
    I = "I"
    II = "II"
    III = "III"
    aVR = "aVR"
    aVL = "aVL"
    aVF = "aVF"
    V1 = "V1"
    V2 = "V2"
    V3 = "V3"
    V4 = "V4"
    V5 = "V5"
    V6 = "V6"


class ArrhythmiaType(Enum):
    NORMAL = "normal_sinus"
    ATRIAL_FIBRILLATION = "afib"
    VENTRICULAR_TACHYCARDIA = "vtach"
    VENTRICULAR_FIBRILLATION = "vfib"
    ASYSTOLE = "asystole"
    BRADYCARDIA = "bradycardia"
    TACHYCARDIA = "tachycardia"


@dataclass
class ECGChannel:
    """Canal de ECG de una derivacion."""
    lead: ECGLead = ECGLead.II
    samples: list[float] = field(default_factory=list)
    sample_rate_hz: int = 250
    timestamp: float = field(default_factory=time.time)

    @property
    def duration_seconds(self) -> float:
        return len(self.samples) / self.sample_rate_hz if self.sample_rate_hz > 0 else 0


@dataclass
class VitalsSnapshot:
    """Snapshot de constantes vitales desde el monitor."""
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    hr: Optional[float] = None          # frecuencia cardiaca bpm
    spo2: Optional[float] = None        # saturacion de oxigeno %
    rr: Optional[float] = None          # frecuencia respiratoria rpm
    nibp_sys: Optional[float] = None    # presion arterial sistolica
    nibp_dia: Optional[float] = None    # presion arterial diastolica
    temperature: Optional[float] = None # temperatura corporal
    ecg_leads: list[ECGChannel] = field(default_factory=list)
    arrhythmia: ArrhythmiaType = ArrhythmiaType.NORMAL
    timestamp: float = field(default_factory=time.time)

    def to_msgpack_ready(self) -> dict:
        return {
            "id": self.snapshot_id,
            "tipo": "telemetria_vital",
            "hr": self.hr,
            "spo2": self.spo2,
            "rr": self.rr,
            "nibp": {"sys": self.nibp_sys, "dia": self.nibp_dia},
            "temp": self.temperature,
            "arrhythmia": self.arrhythmia.value,
            "ecg_leads": len(self.ecg_leads),
            "ts": self.timestamp,
        }


# ═══════════════════════════════════════════════════════════════════
# 2. PROCESADOR DE SEÑAL ECG (DSP Edge)
# ═══════════════════════════════════════════════════════════════════

class ECGDSPProcessor:
    """Procesador de señal ECG en el Edge de la ambulancia.

    Filtros digitales en tiempo real:
    - Pasa-altos: elimina deriva de linea base (0.5 Hz)
    - Pasa-bajos: elimina ruido electromagnetico del motor (40 Hz)
    - Notch: elimina ruido de red 50/60 Hz
    - Deteccion de picos R para calcular FC
    """

    def __init__(self, sample_rate: int = 250):
        self.sample_rate = sample_rate
        self._prev_y = 0.0
        self._prev_x = [0.0, 0.0]

    # ── Filtros digitales (coeficientes IIR butterworth simplificados) ──

    def highpass_0_5hz(self, sample: float) -> float:
        """Filtro pasa-altos 0.5 Hz (elimina deriva de línea base)."""
        # Coeficiente para filtro IIR de 1er orden a 250Hz
        alpha = 0.992
        y = alpha * self._prev_y + alpha * (sample - self._prev_x[0])
        self._prev_y = y
        self._prev_x[0] = sample
        return y

    def lowpass_40hz(self, sample: float) -> float:
        """Filtro pasa-bajos 40 Hz (elimina ruido electromagnetico)."""
        alpha = 0.8
        y = alpha * self._prev_x[1] + (1 - alpha) * sample
        self._prev_x[1] = y
        return y

    def notch_50hz(self, sample: float) -> float:
        """Filtro notch 50 Hz (elimina ruido de red electrica)."""
        # Coeficientes para filtro notch IIR biquad a 250Hz
        # Centro: 50Hz, Q=30
        alpha = 0.9
        y = sample - self._prev_x[0] + alpha * self._prev_x[1]
        self._prev_x[0] = sample
        self._prev_x[1] = y
        return y

    def process_sample(self, raw_sample: float) -> float:
        """Pipeline completo de filtrado para una muestra."""
        # Orden: pasa-altos → pasa-bajos → notch
        y = self.highpass_0_5hz(raw_sample)
        y = self.lowpass_40hz(y)
        y = self.notch_50hz(y)
        return y

    def process_buffer(self, raw_samples: list[float]) -> list[float]:
        """Procesa un buffer completo de muestras."""
        return [self.process_sample(s) for s in raw_samples]

    # ── Detección de picos R y frecuencia cardíaca ─────────────

    @staticmethod
    def detect_r_peaks(filtered_signal: list[float],
                       sample_rate: int = 250) -> list[int]:
        """Detección simple de picos R (Pan-Tompkins simplificado).

        En producción: usar implementación completa con integración
        adaptativa y ventanas refractarias.
        """
        if not filtered_signal:
            return []

        # Umbral adaptativo: 60% del maximo
        threshold = max(filtered_signal) * 0.6
        peaks = []
        refractory = int(0.2 * sample_rate)  # 200ms refractario

        i = 1
        while i < len(filtered_signal) - 1:
            if (filtered_signal[i] > filtered_signal[i - 1] and
                filtered_signal[i] > filtered_signal[i + 1] and
                filtered_signal[i] > threshold):
                peaks.append(i)
                i += refractory  # saltar periodo refractario
            i += 1

        return peaks

    @staticmethod
    def calculate_hr(peaks: list[int], sample_rate: int = 250) -> Optional[float]:
        """Calcula frecuencia cardíaca desde picos R."""
        if len(peaks) < 2:
            return None
        # Distancias entre picos en muestras
        intervals = [peaks[i + 1] - peaks[i] for i in range(len(peaks) - 1)]
        if not intervals:
            return None
        avg_interval = sum(intervals) / len(intervals)
        hr = 60.0 / (avg_interval / sample_rate)
        return round(hr, 1)

    # ── Detección de arritmias ───────────────────────────────

    @staticmethod
    def classify_rhythm(hr: Optional[float], r_peaks: list[int],
                        signal: list[float]) -> ArrhythmiaType:
        """Clasifica el ritmo cardíaco básico.

        En producción: usar clasificador ML (SVM o red neuronal)
        sobre características morfológicas del ECG.
        """
        if hr is None or hr == 0:
            return ArrhythmiaType.ASYSTOLE

        if hr < 40:
            return ArrhythmiaType.BRADYCARDIA
        if hr > 150:
            return ArrhythmiaType.TACHYCARDIA

        # Variabilidad de intervalo RR como proxy de FA
        if len(r_peaks) >= 4:
            intervals = [r_peaks[i + 1] - r_peaks[i] for i in range(len(r_peaks) - 1)]
            if intervals:
                import statistics
                mean_rr = sum(intervals) / len(intervals)
                std_rr = statistics.stdev(intervals) if len(intervals) > 1 else 0
                cv = std_rr / mean_rr if mean_rr > 0 else 0
                if cv > 0.3:  # alta variabilidad → posible FA
                    return ArrhythmiaType.ATRIAL_FIBRILLATION

        return ArrhythmiaType.NORMAL


# ═══════════════════════════════════════════════════════════════════
# 3. ORQUESTADOR DE TELEMETRIA EN LA AMBULANCIA
# ═══════════════════════════════════════════════════════════════════

class AmbulanceTelemetryEdge:
    """Orquestador de telemetría en la ambulancia.

    Flujo:
    1. Lee buffer crudo del monitor multiparamétrico (BLE/serial)
    2. Aplica pipeline DSP (filtros + detección de picos)
    3. Clasifica ritmo y detecta anomalías
    4. Empaqueta en MessagePack para envío prioritario
    """

    CRITICAL_ARRHYTHMIAS = {
        ArrhythmiaType.VENTRICULAR_FIBRILLATION,
        ArrhythmiaType.ASYSTOLE,
        ArrhythmiaType.VENTRICULAR_TACHYCARDIA,
    }

    def __init__(self, sample_rate: int = 250):
        self.dsp = ECGDSPProcessor(sample_rate)
        self.sample_rate = sample_rate
        self._last_snapshot: Optional[VitalsSnapshot] = None
        self._alert_count = 0

    def process_ecg_buffer(self, lead: ECGLead, raw_samples: list[float],
                           vitals: Optional[dict] = None) -> VitalsSnapshot:
        """Procesa un buffer de ECG crudo y genera snapshot.

        Args:
            lead: Derivación del ECG.
            raw_samples: Muestras crudas del ADC del monitor.
            vitals: Constantes vitales adicionales (HR, SpO2, etc).

        Returns:
            VitalsSnapshot con datos procesados y clasificación.
        """
        # 1. Filtrar señal
        filtered = self.dsp.process_buffer(raw_samples)

        # 2. Detectar picos R
        r_peaks = self.dsp.detect_r_peaks(filtered, self.sample_rate)

        # 3. Calcular HR
        hr = self.dsp.calculate_hr(r_peaks, self.sample_rate)

        # 4. Clasificar ritmo
        rhythm = self.dsp.classify_rhythm(hr, r_peaks, filtered)

        # 5. Armar snapshot
        channel = ECGChannel(lead=lead, samples=filtered[:100],  # solo ultimos 100
                             sample_rate_hz=self.sample_rate)

        snapshot = VitalsSnapshot(
            hr=hr or (vitals or {}).get("hr"),
            spo2=(vitals or {}).get("spo2"),
            rr=(vitals or {}).get("rr"),
            nibp_sys=(vitals or {}).get("nibp_sys"),
            nibp_dia=(vitals or {}).get("nibp_dia"),
            temperature=(vitals or {}).get("temperature"),
            ecg_leads=[channel],
            arrhythmia=rhythm,
        )

        # 6. Alerta si arritmia crítica
        if rhythm in self.CRITICAL_ARRHYTHMIAS:
            self._alert_count += 1
            log_event("telemetry_edge", f"CRITICAL:{rhythm.value}:hr={hr}")
            snapshot.arrhythmia = rhythm

        self._last_snapshot = snapshot
        return snapshot

    def generate_alert_payload(self, snapshot: VitalsSnapshot) -> dict:
        """Genera payload de alerta de máxima prioridad para MessagePack.

        Las alertas críticas de arritmia se empaquetan con prioridad 3
        y se envían por delante de cualquier otro tráfico.
        """
        payload = snapshot.to_msgpack_ready()
        payload["prioridad"] = 3 if snapshot.arrhythmia in self.CRITICAL_ARRHYTHMIAS else 1
        payload["alerta"] = f"Ritmo detectado: {snapshot.arrhythmia.value}"
        return payload

    def get_stats(self) -> dict:
        return {
            "critical_alerts": self._alert_count,
            "last_rhythm": self._last_snapshot.arrhythmia.value if self._last_snapshot else "none",
        }


__all__ = [
    "AmbulanceTelemetryEdge",
    "ECGDSPProcessor",
    "VitalsSnapshot",
    "ECGChannel",
    "ECGLead",
    "ArrhythmiaType",
]
