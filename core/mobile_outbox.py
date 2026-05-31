"""Logica de Bandeja de Entrada Local (Outbox Pattern Movil).
Gestiona visibilidad de estado de sincronizacion para el profesional:
- Sincronizado (verde)
- Pendiente de envio (en cola local, amarillo)
- Rechazado por CRDT / validacion (rojo, requiere accion)
Sin jerga tecnica de criptografia.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════════
# 1. ESTADOS VISUALES DEL OUTBOX
# ═══════════════════════════════════════════════════════════════════

class SyncStatus(Enum):
    SYNCED = "synced"               # Verde: datos enviados y confirmados
    PENDING = "pending"             # Amarillo: en cola local, no enviado
    CONFLICT = "conflict"           # Rojo: rechazado por conflicto CRDT
    FAILED = "failed"               # Rojo oscuro: error de validacion biometrica
    RETRYING = "retrying"           # Naranja: reintentando envio


# ═══════════════════════════════════════════════════════════════════
# 2. ENTRADA DEL OUTBOX
# ═══════════════════════════════════════════════════════════════════

@dataclass
class OutboxEntry:
    """Una entrada en la bandeja de salida local del movil.

    EL usuario SOLO ve:
    - Que accion realizo (texto plano): "Visita a Maria Lopez"
    - Estado: ✓ Sincronizado | ⏳ Pendiente | ⚠ Necesita atencion
    - Detalle si hay conflicto: texto legible sin criptografia
    """
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_type: str = ""            # "checkin" | "evolucion" | "medicacion" | "alerta_news2"
    summary: str = ""                # Texto visible: "Evolucion de Juan Perez"
    patient_name: str = ""           # Nombre del paciente para mostrar
    professional_id: str = ""
    tenant_id: str = ""

    # Estado de sincronizacion
    status: SyncStatus = SyncStatus.PENDING
    created_at: float = field(default_factory=time.time)
    synced_at: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 5

    # Mensaje legible para el usuario (NO jerga tecnica)
    user_message: str = ""
    user_action_required: str = ""    # Que debe hacer el usuario? "Revisar y confirmar"

    # Payload interno (no visible)
    _payload: dict = field(default_factory=dict)
    _conflict_detail: dict = field(default_factory=dict)

    def to_ui_dict(self) -> dict:
        """Representacion para la UI del movil.

        Solo contiene campos que el enfermero entiende.
        Sin hashes, sin firmas, sin relojes vectoriales.
        """
        status_icon = {
            SyncStatus.SYNCED: "✓",
            SyncStatus.PENDING: "⏳",
            SyncStatus.CONFLICT: "⚠",
            SyncStatus.FAILED: "✗",
            SyncStatus.RETRYING: "⟳",
        }.get(self.status, "?")

        status_label = {
            SyncStatus.SYNCED: "Enviado",
            SyncStatus.PENDING: "Pendiente",
            SyncStatus.CONFLICT: "Requiere atencion",
            SyncStatus.FAILED: "Error de validacion",
            SyncStatus.RETRYING: "Reintentando...",
        }.get(self.status, "Desconocido")

        return {
            "id": self.entry_id,
            "icon": status_icon,
            "status": status_label,
            "summary": self.summary,
            "patient": self.patient_name,
            "time": self._format_time(self.created_at),
            "message": self.user_message,
            "action_needed": self.user_action_required,
            "can_retry": self.status in (SyncStatus.FAILED, SyncStatus.CONFLICT)
                          and self.retry_count < self.max_retries,
        }

    @staticmethod
    def _format_time(ts: float) -> str:
        """Formato amigable: 'hace 5 min' | '10:30' | 'ayer'."""
        delta = time.time() - ts
        if delta < 60:
            return "Ahora"
        elif delta < 3600:
            return f"hace {int(delta / 60)} min"
        elif delta < 86400:
            from datetime import datetime
            return datetime.fromtimestamp(ts).strftime("%H:%M")
        else:
            return "Ayer"


# ═══════════════════════════════════════════════════════════════════
# 3. GESTOR DEL OUTBOX LOCAL
# ═══════════════════════════════════════════════════════════════════

class MobileOutbox:
    """Bandeja de entrada local del dispositivo movil.

    Almacena todas las acciones del profesional hasta que se sincronizan.
    Provee metodos para la UI con estado claro y mensajes legibles.
    """

    def __init__(self):
        self._entries: dict[str, OutboxEntry] = {}
        self._stats: dict[str, int] = {
            "synced": 0, "pending": 0, "conflict": 0, "failed": 0,
        }

    def add_entry(self, action_type: str, summary: str, patient_name: str,
                  professional_id: str, tenant_id: str,
                  payload: Optional[dict] = None) -> OutboxEntry:
        """Agrega una nueva entrada pendiente en el outbox.

        Args:
            action_type: Tipo de accion ("checkin", "evolucion", etc.).
            summary: Resumen visible ("Visita a Maria Lopez").
            patient_name: Nombre del paciente.
            professional_id: ID del profesional.
            tenant_id: ID del tenant.
            payload: Datos internos para sincronizar.

        Returns:
            OutboxEntry creada.
        """
        entry = OutboxEntry(
            action_type=action_type,
            summary=summary,
            patient_name=patient_name,
            professional_id=professional_id,
            tenant_id=tenant_id,
            _payload=payload or {},
            user_message=self._generate_user_message(action_type, patient_name),
        )
        self._entries[entry.entry_id] = entry
        self._stats["pending"] += 1
        return entry

    def mark_synced(self, entry_id: str) -> bool:
        """Marca una entrada como sincronizada exitosamente.

        La UI mostrara ✓ Enviado.
        """
        entry = self._entries.get(entry_id)
        if not entry:
            return False
        entry.status = SyncStatus.SYNCED
        entry.synced_at = time.time()
        entry.user_message = "Datos enviados correctamente"
        entry.user_action_required = ""
        self._stats["pending"] -= 1
        self._stats["synced"] += 1
        return True

    def mark_conflict(self, entry_id: str, conflict_detail: str) -> bool:
        """Marca una entrada como rechazada por conflicto CRDT.

        La UI mostrara ⚠ Requiere atencion.
        El mensaje de usuario NO menciona CRDT, LWW ni vector clocks.
        """
        entry = self._entries.get(entry_id)
        if not entry:
            return False
        entry.status = SyncStatus.CONFLICT
        entry._conflict_detail = {"detail": conflict_detail}
        entry.user_message = "Se detecto un cambio simultaneo con otro profesional"
        entry.user_action_required = "Revisar los datos y confirmar cual version es la correcta"
        self._stats["pending"] -= 1
        self._stats["conflict"] += 1
        return True

    def mark_failed(self, entry_id: str, reason: str) -> bool:
        """Marca como fallida por error de validacion biometrica/firma.

        La UI mostrara ✗ Error de validacion.
        """
        entry = self._entries.get(entry_id)
        if not entry:
            return False
        entry.status = SyncStatus.FAILED
        entry.user_message = f"No se pudo validar la identidad: {reason}"
        entry.user_action_required = "Intentar de nuevo o contactar a soporte"
        self._stats["pending"] -= 1
        self._stats["failed"] += 1
        return True

    def retry(self, entry_id: str) -> bool:
        """Reintenta el envio de una entrada fallida."""
        entry = self._entries.get(entry_id)
        if not entry or entry.retry_count >= entry.max_retries:
            return False
        entry.status = SyncStatus.RETRYING
        entry.retry_count += 1
        entry.user_message = f"Reintentando envio ({entry.retry_count}/{entry.max_retries})..."
        return True

    def get_pending_entries(self) -> list[OutboxEntry]:
        """Entradas pendientes de sincronizar."""
        return [e for e in self._entries.values() if e.status == SyncStatus.PENDING]

    def get_failed_entries(self) -> list[OutboxEntry]:
        """Entradas que requieren atencion del usuario."""
        return [e for e in self._entries.values()
                if e.status in (SyncStatus.CONFLICT, SyncStatus.FAILED)]

    def get_all_for_ui(self) -> list[dict]:
        """Todas las entradas listas para mostrar en la UI del movil.

        Ordenadas por mas reciente primero.
        Solo contiene campos legibles para el profesional.
        """
        entries = sorted(self._entries.values(), key=lambda e: e.created_at, reverse=True)
        return [e.to_ui_dict() for e in entries]

    def get_stats(self) -> dict:
        """Estadisticas para la UI."""
        return {
            "total": len(self._entries),
            "synced": self._stats["synced"],
            "pending": self._stats["pending"],
            "conflict": self._stats["conflict"],
            "failed": self._stats["failed"],
            "progress_pct": round(
                self._stats["synced"] / max(len(self._entries), 1) * 100, 1
            ),
        }

    @staticmethod
    def _generate_user_message(action_type: str, patient: str) -> str:
        """Genera mensaje legible segun el tipo de accion."""
        messages = {
            "checkin": f"Visita registrada a {patient}",
            "evolucion": f"Evolucion de {patient} guardada",
            "medicacion": f"Medicacion administrada a {patient}",
            "alerta_news2": f"Alerta clinica generada para {patient}",
        }
        return messages.get(action_type, f"Accion registrada para {patient}")


__all__ = [
    "MobileOutbox",
    "OutboxEntry",
    "SyncStatus",
]
