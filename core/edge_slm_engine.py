"""Motor de IA Generativa Local en el Edge Móvil (Offline SLM).
Wrapper Python/C++ para SLM cuantizado 4-bit (Phi-3-mini / Llama-3-8B).
Recibe voz/texto libre del enfermero, aplica prompt SOAP clínico,
devuelve payload estructurado listo para MessagePack delta.
Sin conexión a internet — 100% offline en el dispositivo.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS CLÍNICOS SOAP
# ═══════════════════════════════════════════════════════════════════

class SOAPSection(Enum):
    SUBJECTIVE = "subjetivo"
    OBJECTIVE = "objetivo"
    ASSESSMENT = "analisis"
    PLAN = "plan"


@dataclass
class SOAPNote:
    """Nota clínica estructurada en formato SOAP."""
    note_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subjective: str = ""       # Lo que el paciente dice
    objective: str = ""        # Lo que el médico observa / constantes
    assessment: str = ""       # Diagnóstico / análisis
    plan: str = ""             # Plan de tratamiento
    raw_text: str = ""         # Texto original dictado
    model_used: str = "phi-3-mini-4k-instruct-q4"
    processing_time_ms: float = 0.0
    generated_at: float = field(default_factory=time.time)

    def to_delta_payload(self) -> dict:
        """Payload listo para inyectar en MessagePack delta."""
        return {
            "id": self.note_id,
            "tipo": "evolucion_soap",
            "soap": {
                "s": self.subjective,
                "o": self.objective,
                "a": self.assessment,
                "p": self.plan,
            },
            "raw_text": self.raw_text,
            "modelo": self.model_used,
            "timestamp": self.generated_at,
        }

    def validate(self) -> list[str]:
        """Valida que la nota tenga contenido mínimo en cada sección."""
        warnings = []
        if len(self.subjective) < 10:
            warnings.append("Sección subjetiva muy corta — considerar más detalles del paciente")
        if len(self.objective) < 10:
            warnings.append("Sección objetiva muy corta — incluir constantes vitales")
        if len(self.assessment) < 5:
            warnings.append("Sección de análisis vacía — incluir diagnóstico")
        if len(self.plan) < 5:
            warnings.append("Sección de plan vacía — incluir tratamiento")
        return warnings


# ═══════════════════════════════════════════════════════════════════
# 2. PROMPT SYSTEM CLÍNICO (SOAP)
# ═══════════════════════════════════════════════════════════════════

CLINICAL_SOAP_SYSTEM_PROMPT = """Eres un asistente clínico de enfermería especializado en estructurar notas médicas.
Debes transformar el texto libre dictado por el enfermero en una nota SOAP estructurada.

REGLAS ESTRICTAS:
1. NO inventes información clínica. Usa SOLO lo que el enfermero dictó.
2. Si falta alguna sección, déjala vacía o con "No especificado".
3. Mantén el lenguaje técnico pero comprensible.
4. No agregues diagnósticos que no estén en el texto original.
5. Separa claramente las 4 secciones SOAP.

Formato de salida (JSON):
{
    "subjetivo": "...",
    "objetivo": "...",
    "analisis": "...",
    "plan": "..."
}

NO agregues texto adicional fuera del JSON."""


# ═══════════════════════════════════════════════════════════════════
# 3. WRAPPER DEL SLM OFFLINE (STUB PARA EJECUCIÓN LOCAL)
# ═══════════════════════════════════════════════════════════════════

class OfflineSLMEngine:
    """Wrapper para Small Language Model offline en el dispositivo.

    En producción:
    - iOS: CoreML model (`.mlpackage`) compilado desde ONNX
    - Android: ExecuTorch runtime (`.pte`) 
    - Python stub: simula inferencia para desarrollo y pruebas

    El modelo corre 100% offline. Zero latencia de red.
    """

    # En producción: ruta al modelo cuantizado 4-bit
    MODEL_PATH = os.environ.get("SLM_MODEL_PATH", "/models/phi-3-mini-q4.onnx")

    def __init__(self):
        self._model = None
        self._session = None
        self._loaded = False
        self._stats = {"inferences": 0, "total_ms": 0.0}

    def load_model(self) -> bool:
        """Carga el modelo SLM en memoria.

        En producción usa ONNX Runtime Mobile o CoreML.
        En stub: simula carga exitosa.
        """
        try:
            # stub exitoso
            self._loaded = True
            log_event("slm_edge", f"model_loaded:{self.MODEL_PATH}")
            return True
        except Exception as exc:
            log_event("slm_edge", f"model_load_failed:{type(exc).__name__}")
            return False

    def _build_prompt(self, raw_text: str, vital_signs: Optional[dict] = None) -> str:
        """Construye el prompt completo con system + contexto + entrada."""
        parts = [f"<|system|>{CLINICAL_SOAP_SYSTEM_PROMPT}</s>"]
        parts.append(f"<|user|>Dictado del enfermero: {raw_text}")
        if vital_signs:
            parts.append(f"Constantes vitales: {json.dumps(vital_signs)}")
        parts.append("\nGenera la nota SOAP estructurada en JSON:</s>")
        parts.append("<|assistant|>")
        return "\n".join(parts)

    def _parse_soap_response(self, response: str) -> dict:
        """Parsea la respuesta del modelo a estructura SOAP."""
        # Intentar extraer JSON
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Fallback: parsear secciones por palabras clave
        sections = {"subjetivo": "", "objetivo": "", "analisis": "", "plan": ""}
        current_section = None
        for line in response.split("\n"):
            line_lower = line.lower().strip()
            for key in sections:
                if key in line_lower or key.capitalize() in line:
                    current_section = key
                    continue
            if current_section and line.strip():
                sections[current_section] += line.strip() + " "
        return sections

    def generate_soap(self, raw_text: str,
                      vital_signs: Optional[dict] = None) -> SOAPNote:
        """Genera nota SOAP desde texto libre del enfermero.

        Args:
            raw_text: Texto dictado por el enfermero.
            vital_signs: Constantes vitales opcionales.

        Returns:
            SOAPNote estructurada.
        """
        if not self._loaded:
            self.load_model()

        start = time.perf_counter()
        prompt = self._build_prompt(raw_text, vital_signs)

        # ── En producción: inferencia real con ONNX/CoreML ──
        # inputs = tokenizer(prompt, return_tensors="pt")
        # outputs = model.generate(**inputs, max_new_tokens=512)
        # response = tokenizer.decode(outputs[0])

        # ── Stub para desarrollo: simular respuesta ─────────
        response = self._stub_inference(raw_text)

        parsed = self._parse_soap_response(response)
        elapsed_ms = (time.perf_counter() - start) * 1000

        note = SOAPNote(
            subjective=parsed.get("subjetivo", parsed.get("s", "")),
            objective=parsed.get("objetivo", parsed.get("o", "")),
            assessment=parsed.get("analisis", parsed.get("a", "")),
            plan=parsed.get("plan", parsed.get("p", "")),
            raw_text=raw_text,
            processing_time_ms=round(elapsed_ms, 1),
        )

        # Validar
        warnings = note.validate()
        if warnings:
            log_event("slm_edge", f"soap_warnings:{','.join(warnings)}")

        self._stats["inferences"] += 1
        self._stats["total_ms"] += elapsed_ms

        log_event("slm_edge", f"soap_generated:{note.note_id}:{elapsed_ms:.0f}ms:{len(note.subjective)}chars")
        return note

    def _stub_inference(self, raw_text: str) -> str:
        """Stub de inferencia para desarrollo.

        Simula la salida del modelo sin ejecutarlo realmente.
        En producción, reemplazar por llamada ONNX/CoreML.
        """
        import random
        time.sleep(random.uniform(0.05, 0.15))  # simular latencia de inferencia

        # Detectar palabras clave para simular estructuración
        text_lower = raw_text.lower()
        sections = {"subjetivo": "", "objetivo": "", "analisis": "", "plan": ""}

        if "dolor" in text_lower or "fiebre" in text_lower:
            sections["subjetivo"] = "Paciente refiere " + raw_text[:100]
        elif "gripe" in text_lower or "tos" in text_lower:
            sections["subjetivo"] = "Paciente consulta por síntomas respiratorios: " + raw_text[:80]
        else:
            sections["subjetivo"] = raw_text[:120]

        sections["objetivo"] = "Constantes dentro de parámetros evaluados. Se realiza examen físico completo."
        sections["analisis"] = "Paciente presenta cuadro compatible con diagnóistico de entrada."
        sections["plan"] = "Se indica tratamiento sintomático. Control en 48 horas."

        return json.dumps(sections, ensure_ascii=False)

    def get_stats(self) -> dict:
        return {
            "model_loaded": self._loaded,
            "inferences": self._stats["inferences"],
            "avg_inference_ms": round(
                self._stats["total_ms"] / max(self._stats["inferences"], 1), 1
            ),
        }


# ═══════════════════════════════════════════════════════════════════
# 4. INTEGRACIÓN CON MENSAJEPACK DELTA
# ═══════════════════════════════════════════════════════════════════

class DeltaSOAPIntegrator:
    """Integra la nota SOAP generada por el SLM en el pipeline delta.

    La nota se estructura offline, se empaqueta en MessagePack
    y se inyecta en el próximo POST /sync/batch.
    """

    def __init__(self):
        self._engine = OfflineSLMEngine()
        self._pending: list[SOAPNote] = []

    def process_voice_note(self, raw_text: str,
                           vital_signs: Optional[dict] = None) -> SOAPNote:
        """Procesa una nota de voz completa: SLM → SOAP → pending queue.

        Args:
            raw_text: Texto transcrito del dictado por voz.
            vital_signs: Constantes vitales opcionales.

        Returns:
            SOAPNote generada.
        """
        note = self._engine.generate_soap(raw_text, vital_signs)
        self._pending.append(note)
        log_event("slm_edge", f"queued_for_delta:{note.note_id}")
        return note

    def flush_to_msgpack(self) -> bytes:
        """Empaqueta todas las notas pendientes en MessagePack.

        Returns:
            Bytes listos para POST /sync/batch.
        """
        import msgpack
        payloads = [n.to_delta_payload() for n in self._pending]
        self._pending.clear()
        packed = msgpack.packb({"tipo": "evoluciones_soap", "notas": payloads},
                               use_bin_type=True)
        log_event("slm_edge", f"flushed:{len(payloads)} notas:{len(packed)}b")
        return packed


__all__ = [
    "OfflineSLMEngine",
    "DeltaSOAPIntegrator",
    "SOAPNote",
    "SOAPSection",
]
