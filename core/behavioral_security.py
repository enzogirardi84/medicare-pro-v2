"""Autenticación Continua por Biometria de Conducta.
Analiza cadencia de tipeo, giroscopio, scrolling.
Calcula Trust Score (0-100%). Si cae < 70%, revoca token y bloquea.
Corre 100% offline en el dispositivo.
"""
from __future__ import annotations

import math
import statistics
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODALIDADES BIOMETRICAS
# ═══════════════════════════════════════════════════════════════════

class BiometricModality(Enum):
    KEYSTROKE = "keystroke"         # cadencia de tipeo
    GYROSCOPE = "gyroscope"         # aceleración al sostener
    SCROLL = "scroll"               # patron de desplazamiento
    TOUCH_PRESSURE = "touch_pressure" # fuerza del toque


@dataclass
class BiometricSample:
    """Una muestra de biometria de conducta."""
    modality: BiometricModality
    features: dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_vector(self) -> list[float]:
        """Vector de características para el clasificador."""
        return list(self.features.values())


# ═══════════════════════════════════════════════════════════════════
# 2. EXTRACTORES DE CARACTERISTICAS POR MODALIDAD
# ═══════════════════════════════════════════════════════════════════

class KeystrokeAnalyzer:
    """Analiza cadencia de tipeo: intervalo entre teclas y hold time.

    Características:
    - key_down_time: tiempo presionando cada tecla
    - key_interval: tiempo entre tecla y tecla
    - digraph_latency: latencia de pares de letras comunes
    """

    def __init__(self):
        self._last_key_time: float = 0.0
        self._intervals: deque[float] = deque(maxlen=50)
        self._hold_times: deque[float] = deque(maxlen=50)

    def record_key(self, key: str, action: str, timestamp: float) -> Optional[BiometricSample]:
        """Registra un evento de tecla.

        Args:
            key: Caracter presionado.
            action: "down" | "up".
            timestamp: Tiempo del evento.

        Returns:
            BiometricSample si hay suficientes datos, None si no.
        """
        if action == "down":
            if self._last_key_time > 0:
                interval = (timestamp - self._last_key_time) * 1000  # ms
                self._intervals.append(interval)
            self._last_key_time = timestamp
            self._key_down_start = timestamp

        elif action == "up":
            if hasattr(self, '_key_down_start') and self._key_down_start > 0:
                hold = (timestamp - self._key_down_start) * 1000
                self._hold_times.append(hold)

        if len(self._intervals) >= 5:
            return BiometricSample(
                modality=BiometricModality.KEYSTROKE,
                features={
                    "mean_interval_ms": statistics.mean(self._intervals),
                    "std_interval_ms": statistics.stdev(self._intervals) if len(self._intervals) > 1 else 0,
                    "mean_hold_ms": statistics.mean(self._hold_times) if self._hold_times else 0,
                },
            )
        return None


class GyroscopeAnalyzer:
    """Analiza aceleración del giroscopio al sostener el dispositivo.

    El perfil de cómo un usuario sostiene el teléfono es único
    (ángulo, micro-movimientos, temblor natural).
    """

    def __init__(self):
        self._samples: deque[dict] = deque(maxlen=100)

    def record_gyro(self, x: float, y: float, z: float) -> Optional[BiometricSample]:
        """Registra una lectura del giroscopio.

        Args:
            x, y, z: Aceleración en m/s² en cada eje.

        Returns:
            BiometricSample si hay suficientes datos.
        """
        magnitude = math.sqrt(x ** 2 + y ** 2 + z ** 2)
        self._samples.append({"x": x, "y": y, "z": z, "mag": magnitude})

        if len(self._samples) >= 10:
            magnitudes = [s["mag"] for s in self._samples]
            return BiometricSample(
                modality=BiometricModality.GYROSCOPE,
                features={
                    "mean_magnitude": statistics.mean(magnitudes),
                    "std_magnitude": statistics.stdev(magnitudes) if len(magnitudes) > 1 else 0,
                    "max_magnitude": max(magnitudes),
                    "min_magnitude": min(magnitudes),
                },
            )
        return None


class ScrollAnalyzer:
    """Analiza patrón de desplazamiento en pantalla táctil.

    Velocidad de scroll, aceleración, pausas entre scrolls.
    """

    def __init__(self):
        self._scroll_events: deque[float] = deque(maxlen=50)
        self._last_scroll_y: float = 0.0
        self._last_scroll_time: float = 0.0

    def record_scroll(self, delta_y: float, timestamp: float) -> Optional[BiometricSample]:
        """Registra un evento de scroll.

        Args:
            delta_y: Distancia desplazada (píxeles).
            timestamp: Tiempo del evento.

        Returns:
            BiometricSample si hay suficientes datos.
        """
        if self._last_scroll_time > 0:
            time_delta = (timestamp - self._last_scroll_time) * 1000  # ms
            if time_delta > 0:
                speed = abs(delta_y) / time_delta  # px/ms
                self._scroll_events.append(speed)

        self._last_scroll_y = delta_y
        self._last_scroll_time = timestamp

        if len(self._scroll_events) >= 5:
            return BiometricSample(
                modality=BiometricModality.SCROLL,
                features={
                    "mean_speed": statistics.mean(self._scroll_events),
                    "std_speed": statistics.stdev(self._scroll_events) if len(self._scroll_events) > 1 else 0,
                    "max_speed": max(self._scroll_events),
                },
            )
        return None


# ═══════════════════════════════════════════════════════════════════
# 3. CLASIFICADOR DE CONFIANZA (TRUST SCORE)
# ═══════════════════════════════════════════════════════════════════

class BehavioralTrustClassifier:
    """Clasificador ligero que calcula Trust Score en tiempo real.

    Estrategia:
    - Perfil de referencia: promedio de las primeras 20 muestras
    - Trust Score: similitud coseno entre muestra actual y perfil
    - Si score < 70%: anomalía detectada
    """

    REFERENCE_SAMPLES = 20
    TRUST_THRESHOLD = 70.0  # %

    def __init__(self):
        self._reference_profile: Optional[list[float]] = None
        self._samples_collected: int = 0
        self._current_score: float = 100.0
        self._alerts: list[dict] = []

    def compute_trust_score(self, sample: BiometricSample) -> float:
        """Calcula Trust Score para una muestra biométrica.

        Args:
            sample: Muestra de biometría de conducta.

        Returns:
            Trust Score (0-100%).
        """
        vector = sample.to_vector()
        if not vector:
            return 100.0

        # Fase de calibración: construir perfil de referencia
        if self._samples_collected < self.REFERENCE_SAMPLES:
            if self._reference_profile is None:
                self._reference_profile = vector[:]
            else:
                # Promedio móvil
                for i in range(min(len(vector), len(self._reference_profile))):
                    self._reference_profile[i] = (
                        (self._reference_profile[i] * self._samples_collected + vector[i])
                        / (self._samples_collected + 1)
                    )
            self._samples_collected += 1
            self._current_score = 100.0
            return 100.0

        # Calcular similitud coseno contra perfil
        score = self._cosine_similarity(self._reference_profile, vector)
        trust_pct = max(0, min(100, score * 100))

        self._current_score = trust_pct

        # Alerta si cae del umbral
        if trust_pct < self.TRUST_THRESHOLD:
            alert = {
                "timestamp": time.time(),
                "score": round(trust_pct, 1),
                "modality": sample.modality.value,
                "threshold": self.TRUST_THRESHOLD,
            }
            self._alerts.append(alert)
            log_event("behavioral", f"TRUST_DROP:{trust_pct:.0f}%:{sample.modality.value}")

        return trust_pct

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Similitud coseno entre dos vectores."""
        if not a or not b:
            return 1.0
        min_len = min(len(a), len(b))
        dot = sum(a[i] * b[i] for i in range(min_len))
        norm_a = math.sqrt(sum(v ** 2 for v in a[:min_len]))
        norm_b = math.sqrt(sum(v ** 2 for v in b[:min_len]))
        if norm_a == 0 or norm_b == 0:
            return 1.0
        return dot / (norm_a * norm_b)

    def get_trust_score(self) -> float:
        return self._current_score

    def is_anomaly(self) -> bool:
        return self._current_score < self.TRUST_THRESHOLD

    def reset_calibration(self):
        """Reinicia la calibración (nuevo usuario)."""
        self._reference_profile = None
        self._samples_collected = 0
        self._current_score = 100.0


# ═══════════════════════════════════════════════════════════════════
# 4. ORQUESTADOR DE SEGURIDAD BIOMETRICA
# ═══════════════════════════════════════════════════════════════════

class BehavioralSecurityGuard:
    """Guardián de seguridad biométrica continua.

    Monitorea todas las modalidades en background.
    Si Trust Score < 70%: dispara evento de revocación.
    """

    def __init__(self):
        self._keystroke = KeystrokeAnalyzer()
        self._gyro = GyroscopeAnalyzer()
        self._scroll = ScrollAnalyzer()
        self._classifier = BehavioralTrustClassifier()
        self._revocation_callbacks: list[Callable] = []
        self._locked = False

    def register_revocation_callback(self, callback: Callable):
        """Registra callback ejecutado cuando se revoca el acceso.

        El callback debe bloquear la pantalla y exigir re-atestación.
        """
        self._revocation_callbacks.append(callback)

    def record_keystroke(self, key: str, action: str) -> Optional[float]:
        """Registra evento de tecleo."""
        sample = self._keystroke.record_key(key, action, time.time())
        if sample:
            return self._evaluate(sample)
        return None

    def record_gyroscope(self, x: float, y: float, z: float) -> Optional[float]:
        """Registra lectura de giroscopio."""
        sample = self._gyro.record_gyro(x, y, z)
        if sample:
            return self._evaluate(sample)
        return None

    def record_scroll(self, delta_y: float) -> Optional[float]:
        """Registra evento de scroll."""
        sample = self._scroll.record_scroll(delta_y, time.time())
        if sample:
            return self._evaluate(sample)
        return None

    def _evaluate(self, sample: BiometricSample) -> float:
        """Evalúa una muestra y decide si revocar."""
        score = self._classifier.compute_trust_score(sample)

        if self._classifier.is_anomaly() and not self._locked:
            self._locked = True
            log_event("behavioral", f"REVOKING:trust_score={score:.0f}%")
            for cb in self._revocation_callbacks:
                try:
                    cb(score, sample.modality)
                except Exception as exc:
                    log_event("behavioral", f"callback_error:{type(exc).__name__}")

        return score

    def is_locked(self) -> bool:
        return self._locked

    def unlock(self):
        """Desbloquea tras re-atestación exitosa (FaceID)."""
        self._locked = False
        self._classifier.reset_calibration()
        log_event("behavioral", "unlocked:re-calibrating")

    def get_status(self) -> dict:
        return {
            "trust_score": round(self._classifier.get_trust_score(), 1),
            "locked": self._locked,
            "anomaly": self._classifier.is_anomaly(),
            "calibration_progress": min(100, int(
                self._classifier._samples_collected / self._classifier.REFERENCE_SAMPLES * 100
            )),
        }


from typing import Callable


__all__ = [
    "BehavioralSecurityGuard",
    "BehavioralTrustClassifier",
    "KeystrokeAnalyzer",
    "GyroscopeAnalyzer",
    "ScrollAnalyzer",
    "BiometricSample",
    "BiometricModality",
]
