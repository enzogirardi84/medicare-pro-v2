"""Tests para core.mobile_outbox — Outbox Pattern Movil."""
from __future__ import annotations

import time


class TestSyncStatus:
    def test_values(self):
        from core.mobile_outbox import SyncStatus
        assert SyncStatus.SYNCED.value == "synced"
        assert SyncStatus.PENDING.value == "pending"
        assert SyncStatus.CONFLICT.value == "conflict"


class TestOutboxEntry:
    def test_to_ui_dict_pending(self):
        from core.mobile_outbox import OutboxEntry, SyncStatus
        entry = OutboxEntry(
            action_type="evolucion", summary="Evolucion de Juan",
            patient_name="Juan Perez", professional_id="p1", tenant_id="t1",
        )
        ui = entry.to_ui_dict()
        assert ui["icon"] == "⏳"
        assert ui["status"] == "Pendiente"
        assert ui["patient"] == "Juan Perez"

    def test_to_ui_dict_synced(self):
        from core.mobile_outbox import OutboxEntry, SyncStatus
        entry = OutboxEntry(action_type="checkin", summary="Visita",
                             patient_name="Maria", professional_id="p1", tenant_id="t1")
        entry.status = SyncStatus.SYNCED
        ui = entry.to_ui_dict()
        assert ui["icon"] == "✓"
        assert ui["status"] == "Enviado"

    def test_to_ui_dict_conflict(self):
        from core.mobile_outbox import OutboxEntry, SyncStatus
        entry = OutboxEntry(action_type="evolucion", summary="Evo",
                             patient_name="Carlos", professional_id="p1", tenant_id="t1")
        entry.status = SyncStatus.CONFLICT
        ui = entry.to_ui_dict()
        assert ui["icon"] == "⚠"
        assert ui["can_retry"] is True


class TestMobileOutbox:
    def test_add_entry(self):
        from core.mobile_outbox import MobileOutbox
        outbox = MobileOutbox()
        entry = outbox.add_entry("checkin", "Visita a Pedro", "Pedro",
                                  "prof-1", "t1")
        assert entry.status.value == "pending"
        assert outbox.get_stats()["pending"] == 1

    def test_mark_synced(self):
        from core.mobile_outbox import MobileOutbox
        outbox = MobileOutbox()
        entry = outbox.add_entry("evolucion", "Evo de Ana", "Ana", "prof-1", "t1")
        outbox.mark_synced(entry.entry_id)
        assert outbox.get_stats()["synced"] == 1
        assert outbox.get_stats()["pending"] == 0

    def test_mark_conflict(self):
        from core.mobile_outbox import MobileOutbox
        outbox = MobileOutbox()
        entry = outbox.add_entry("medicacion", "Med a Luis", "Luis", "prof-1", "t1")
        outbox.mark_conflict(entry.entry_id, "Cambio simultaneo detectado")
        ui = entry.to_ui_dict()
        assert "cambio simultaneo" in entry.user_message.lower()

    def test_mark_failed(self):
        from core.mobile_outbox import MobileOutbox
        outbox = MobileOutbox()
        entry = outbox.add_entry("checkin", "Check a Sofia", "Sofia", "prof-1", "t1")
        outbox.mark_failed(entry.entry_id, "Firma biométrica no coincide")
        assert outbox.get_stats()["failed"] == 1

    def test_retry(self):
        from core.mobile_outbox import MobileOutbox
        outbox = MobileOutbox()
        entry = outbox.add_entry("checkin", "Check", "Paciente", "prof-1", "t1")
        outbox.mark_failed(entry.entry_id, "Error")
        assert outbox.retry(entry.entry_id) is True
        assert entry.retry_count == 1

    def test_get_pending_entries(self):
        from core.mobile_outbox import MobileOutbox
        outbox = MobileOutbox()
        outbox.add_entry("a", "A", "P1", "p1", "t1")
        outbox.add_entry("b", "B", "P2", "p1", "t1")
        assert len(outbox.get_pending_entries()) == 2

    def test_get_failed_entries(self):
        from core.mobile_outbox import MobileOutbox
        outbox = MobileOutbox()
        e = outbox.add_entry("a", "A", "P1", "p1", "t1")
        outbox.mark_failed(e.entry_id, "err")
        assert len(outbox.get_failed_entries()) == 1

    def test_get_all_for_ui(self):
        from core.mobile_outbox import MobileOutbox
        outbox = MobileOutbox()
        outbox.add_entry("checkin", "Check", "Juan", "p1", "t1")
        ui_list = outbox.get_all_for_ui()
        assert len(ui_list) == 1
        assert "icon" in ui_list[0]
        assert "status" in ui_list[0]
