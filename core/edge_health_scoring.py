"""Motor de alerta temprana en el Edge (NEWS2) con firma ECDSA offline.
Procesa constantes vitales localmente en el dispositivo del profesional,
genera un score de alerta y lo encola firmado para sync posterior.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import IntEnum
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════════
# 1. NATIONAL EARLY WARNING SCORE (NEWS2)
# ═══════════════════════════════════════════════════════════════════

class Consciousness(IntEnum):
    ALERT = 0
    CONFUSED = 3
    VOICE = 3
    PAIN = 3
    UNRESPONSIVE = 3


@dataclass
class VitalSigns:
    """Constantes vitales ingresadas por el profesional."""
    respiratory_rate: Optional[float] = None   # respiraciones/min
    oxygen_saturation: Optional[float] = None  # SpO2 %
    oxygen_therapy: bool = False               # si recibe O2 suplementario
    systolic_bp: Optional[float] = None        # mmHg
    heart_rate: Optional[float] = None         # latidos/min
    temperature: Optional[float] = None        # °C
    consciousness: Consciousness = Consciousness.ALERT


# ═══════════════════════════════════════════════════════════════════
# 2. SCORE NEWS2
# ═══════════════════════════════════════════════════════════════════

class NEWS2Scorer:
    """Calcula el National Early Warning Score 2 (NEWS2).

    Basado en: Royal College of Physicians 2017.
    Rango: 0-20 (mayor = mas critico).
    """

    @staticmethod
    def score_respiratory_rate(rr: float) -> int:
        if rr <= 8:
            return 3
        elif 9 <= rr <= 11:
            return 1
        elif 12 <= rr <= 20:
            return 0
        elif 21 <= rr <= 24:
            return 2
        else:  # >= 25
            return 3

    @staticmethod
    def score_oxygen_saturation(spo2: float, on_oxygen: bool = False) -> int:
        if on_oxygen:
            if spo2 >= 97:
                return 3  # hiperoxia en pacientes con O2
            elif 95 <= spo2 <= 96:
                return 2
            elif 93 <= spo2 <= 94:
                return 1
            elif 90 <= spo2 <= 92:
                return 0  # rango objetivo con O2
            elif 85 <= spo2 <= 89:
                return 2
            else:  # < 85
                return 3
        else:
            if spo2 >= 96:
                return 0
            elif 94 <= spo2 <= 95:
                return 1
            elif 92 <= spo2 <= 93:
                return 2
            else:  # <= 91
                return 3

    @staticmethod
    def score_oxygen_requirement(on_oxygen: bool) -> int:
        """Escala NEWS2 original: 2 pts si requiere O2."""
        return 2 if on_oxygen else 0

    @staticmethod
    def score_systolic_bp(sbp: float) -> int:
        if sbp <= 90:
            return 3
        elif 91 <= sbp <= 100:
            return 2
        elif 101 <= sbp <= 110:
            return 1
        elif 111 <= sbp <= 219:
            return 0
        else:  # >= 220
            return 3

    @staticmethod
    def score_heart_rate(hr: float) -> int:
        if hr <= 40:
            return 3
        elif 41 <= hr <= 50:
            return 1
        elif 51 <= hr <= 90:
            return 0
        elif 91 <= hr <= 110:
            return 1
        elif 111 <= hr <= 130:
            return 2
        else:  # >= 131
            return 3

    @staticmethod
    def score_temperature(temp: float) -> int:
        if temp <= 35.0:
            return 3
        elif 35.1 <= temp <= 36.0:
            return 1
        elif 36.1 <= temp <= 38.0:
            return 0
        elif 38.1 <= temp <= 39.0:
            return 1
        else:  # >= 39.1
            return 2

    @staticmethod
    def score_consciousness(consciousness: Consciousness) -> int:
        """NEWS2: 3 pts si el paciente no esta alerta."""
        return 3 if consciousness != Consciousness.ALERT else 0

    def calculate(self, vs: VitalSigns) -> dict:
        """Calcula el score NEWS2 completo.

        Returns:
            dict con scores parciales, total, nivel de alerta.
        """
        scores = {}

        if vs.respiratory_rate is not None:
            scores["respiratory_rate"] = self.score_respiratory_rate(vs.respiratory_rate)
        if vs.oxygen_saturation is not None:
            scores["oxygen_saturation"] = self.score_oxygen_saturation(
                vs.oxygen_saturation, vs.oxygen_therapy
            )
        scores["oxygen_requirement"] = self.score_oxygen_requirement(vs.oxygen_therapy)

        if vs.systolic_bp is not None:
            scores["systolic_bp"] = self.score_systolic_bp(vs.systolic_bp)
        if vs.heart_rate is not None:
            scores["heart_rate"] = self.score_heart_rate(vs.heart_rate)
        if vs.temperature is not None:
            scores["temperature"] = self.score_temperature(vs.temperature)

        scores["consciousness"] = self.score_consciousness(vs.consciousness)
        total = sum(scores.values())

        # Nivel de alerta clinica
        if total >= 7:
            nivel = "CRITICO"
            recomendacion = "Evaluacion medica inmediata. Considerar traslado a UTI."
        elif total >= 5:
            nivel = "URGENTE"
            recomendacion = "Evaluacion por medico en < 1 hora. Monitoreo frecuente."
        elif total >= 3:
            nivel = "MODERADO"
            recomendacion = "Evaluacion por medico en < 4 horas."
        else:
            nivel = "LEVE"
            recomendacion = "Monitoreo de rutina."

        return {
            "scores": scores,
            "total": total,
            "nivel": nivel,
            "recomendacion": recomendacion,
            "timestamp": time.time(),
        }


# ═══════════════════════════════════════════════════════════════════
# 3. EVALUADOR DE TEXTO LIBRE (NOTAS DE EVOLUCION)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TextHint:
    pattern: str
    keywords: list[str]
    weight: int
    category: str


CLINICAL_HINTS = [
    TextHint("disnea", ["disnea", "falta de aire", "dificultad respiratoria", "ahogo"], 2, "respiratorio"),
    TextHint("cianosis", ["cianosis", "dedos azules", "labios morados"], 3, "respiratorio"),
    TextHint("hemorragia", ["hemorragia", "sangrado activo", "hematemesis"], 3, "hemodinamico"),
    TextHint("hipotension", ["hipotenso", "presion baja", "marcado descenso"], 2, "hemodinamico"),
    TextHint("fiebre_alta", ["fiebre alta", "hipertermia", "39", "40"], 2, "infeccioso"),
    TextHint("sepsis", ["sepsis", "sepsis severa", "shock septico"], 3, "infeccioso"),
    TextHint("convulsion", ["convulsion", "crisis epileptica", "estado convulsivo"], 3, "neurologico"),
    TextHint("inconsciencia", ["inconsciente", "sin respuesta", "coma", "glasgow bajo"], 3, "neurologico"),
    TextHint("dolor_toracico", ["dolor toracico", "angina", "precordialgia"], 2, "cardiologico"),
    TextHint("arritmia", ["arritmia", "palpitaciones", "fibrilacion"], 2, "cardiologico"),
]


class ClinicalTextScorer:
    """Evalua texto de notas de evolucion para alertas tempranas."""

    @staticmethod
    def score_text(text: str) -> dict:
        """Analiza el texto y calculua un score de alerta textual.

        Returns:
            dict con alertas encontradas y score total.
        """
        if not text:
            return {"alertas": [], "score": 0, "max_score": 0}

        text_lower = text.lower()
        alertas = []
        score = 0

        for hint in CLINICAL_HINTS:
            for kw in hint.keywords:
                if kw in text_lower:
                    alertas.append({
                        "patron": hint.pattern,
                        "categoria": hint.category,
                        "peso": hint.weight,
                        "match": kw,
                    })
                    score += hint.weight
                    break

        max_possible = sum(h.weight for h in CLINICAL_HINTS)

        return {
            "alertas": alertas,
            "score": score,
            "max_score": max_possible,
            "nivel": "ALTO" if score >= 6 else "MEDIO" if score >= 3 else "BAJO",
        }


# ═══════════════════════════════════════════════════════════════════
# 4. FIRMA ECDSA PARA ALERTAS OFFLINE
# ═══════════════════════════════════════════════════════════════════

class ECDSASigner:
    """Firma alertas con clave ECDSA del dispositivo (secp256r1).

    La alerta firmada puede ser verificada por el servidor
    incluso si llega horas despues (offline-first).
    """

    @staticmethod
    def generate_keypair() -> tuple[bytes, bytes]:
        """Genera par de claves ECDSA (privada, publica) en formato PEM."""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PrivateFormat, PublicFormat, NoEncryption,
        )
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()

        private_bytes = private_key.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption(),
        )
        public_bytes = public_key.public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo,
        )
        return private_bytes, public_bytes

    @staticmethod
    def sign_alert(private_key_pem: bytes, alert_payload: dict) -> str:
        """Firma un payload de alerta con clave ECDSA.

        Returns:
            Firma en formato hex.
        """
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        private_key = load_pem_private_key(private_key_pem, password=None)
        canonical = json.dumps(alert_payload, sort_keys=True, default=str).encode("utf-8")
        signature = private_key.sign(canonical, ec.ECDSA(hashes.SHA256()))
        return signature.hex()

    @staticmethod
    def verify_alert(public_key_pem: bytes, alert_payload: dict, signature_hex: str) -> bool:
        """Verifica una alerta firmada.

        Args:
            public_key_pem: Clave publica en formato PEM.
            alert_payload: Payload original de la alerta.
            signature_hex: Firma en hex.

        Returns:
            True si la firma es valida.
        """
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        public_key = load_pem_public_key(public_key_pem)
        canonical = json.dumps(alert_payload, sort_keys=True, default=str).encode("utf-8")
        signature = bytes.fromhex(signature_hex)

        try:
            public_key.verify(signature, canonical, ec.ECDSA(hashes.SHA256()))
            return True
        except Exception:
            return False


# ═══════════════════════════════════════════════════════════════════
# 5. ALERTA CLINICA OFFLINE-FIRST (FIRMADA + ENCOLADA)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SignedClinicalAlert:
    """Alerta clinica firmada para transmision offline-first."""
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    paciente_id: str = ""
    profesional_id: str = ""
    tenant_id: str = ""
    dispositivo_id: str = ""
    news2_score: int = 0
    news2_nivel: str = ""
    text_score: int = 0
    text_alertas: list[dict] = field(default_factory=list)
    vital_signs: dict = field(default_factory=dict)
    nota_evolucion: str = ""
    timestamp: float = field(default_factory=time.time)
    device_signature: str = ""
    device_public_key: str = ""  # PEM de la publica (se envia solo en el primer alerta)

    def to_signed_payload(self) -> dict:
        """Payload canonical para firmar."""
        return asdict(self)

    def to_msgpack_ready(self) -> dict:
        """Payload listo para serializar con MessagePack."""
        return {
            "tipo": "alerta_clinica",
            "version": 2,
            "alerta": asdict(self),
        }


class EdgeAlertEngine:
    """Motor de alerta temprana ejecutable en el Edge (dispositivo movil).

    Flujo:
    1. Profesional ingresa constantes vitales + nota de evolucion
    2. Motor calcula NEWS2 + text score
    3. Genera alerta firmada con clave ECDSA del dispositivo
    4. Encola en cola local de MessagePack para sync
    """

    def __init__(self, device_private_key_pem: Optional[bytes] = None):
        self._news2 = NEWS2Scorer()
        self._text_scorer = ClinicalTextScorer()
        self._signer = ECDSASigner()
        self._private_key = device_private_key_pem
        self._public_key: Optional[bytes] = None
        self._alert_queue: list[SignedClinicalAlert] = []

        # Generar claves si no se proporcionan
        if self._private_key is None:
            self._private_key, self._public_key = self._signer.generate_keypair()

    def evaluate(self, paciente_id: str, profesional_id: str, tenant_id: str,
                 dispositivo_id: str, vital_signs: VitalSigns,
                 nota_evolucion: str = "") -> SignedClinicalAlert:
        """Evalua constantes vitales y genera alerta firmada.

        Returns:
            SignedClinicalAlert lista para encolar.
        """
        # 1. Calcular NEWS2
        news2_result = self._news2.calculate(vital_signs)

        # 2. Evaluar texto de nota
        text_result = self._text_scorer.score_text(nota_evolucion)

        # 3. Construir alerta
        alert = SignedClinicalAlert(
            paciente_id=paciente_id,
            profesional_id=profesional_id,
            tenant_id=tenant_id,
            dispositivo_id=dispositivo_id,
            news2_score=news2_result["total"],
            news2_nivel=news2_result["nivel"],
            text_score=text_result["score"],
            text_alertas=text_result["alertas"],
            vital_signs=asdict(vital_signs),
            nota_evolucion=nota_evolucion,
        )

        # 4. Firmar
        payload = alert.to_signed_payload()
        alert.device_signature = self._signer.sign_alert(self._private_key, payload)
        if self._public_key:
            alert.device_public_key = self._public_key.decode("utf-8")

        return alert

    def enqueue_alert(self, alert: SignedClinicalAlert) -> int:
        """Encola una alerta para sync posterior.

        Returns:
            Tamano actual de la cola.
        """
        self._alert_queue.append(alert)
        return len(self._alert_queue)

    def flush_queue(self) -> list[dict]:
        """Prepara todas las alertas encoladas para sync (MessagePack).

        Returns:
            Lista de dicts listos para msgpack.packb().
        """
        payloads = [a.to_msgpack_ready() for a in self._alert_queue]
        self._alert_queue.clear()
        return payloads

    def get_public_key_pem(self) -> str:
        return self._public_key.decode("utf-8") if self._public_key else ""


# ═══════════════════════════════════════════════════════════════════
# 6. INTEGRACION CON DELTA SYNC (colas de MessagePack)
# ═══════════════════════════════════════════════════════════════════

def package_alerts_for_sync(alerts: list[SignedClinicalAlert]) -> bytes:
    """Empaqueta alertas firmadas en MessagePack para sync delta."""
    import msgpack
    payloads = [a.to_msgpack_ready() for a in alerts]
    return msgpack.packb({"alerts": payloads, "type": "health_scoring"}, use_bin_type=True)


__all__ = [
    "NEWS2Scorer",
    "ClinicalTextScorer",
    "ECDSASigner",
    "EdgeAlertEngine",
    "SignedClinicalAlert",
    "VitalSigns",
    "Consciousness",
    "package_alerts_for_sync",
]
