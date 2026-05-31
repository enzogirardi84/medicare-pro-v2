"""Tests para core.clinical_event_store — Event Sourcing."""
from __future__ import annotations


class TestClinicalEvent:
    def test_create_evolucion_creada(self):
        from core.clinical_event_store import ClinicalEvent
        event = ClinicalEvent(
            aggregate_type="evolucion",
            aggregate_id="evo-123",
            event_type="EvolucionCreada",
            tenant_id="t1",
            actor_id="prof-1",
            payload={"diagnostico": "neumonia", "paciente_id": "p1"},
        )
        assert event.aggregate_type == "evolucion"
        assert event.event_type == "EvolucionCreada"
        assert len(event.checksum) == 32

    def test_checksum_deterministico(self):
        from core.clinical_event_store import ClinicalEvent
        a = ClinicalEvent("evo", "id1", "EvolucionCreada", "t1", "p1", {"d": "x"})
        b = ClinicalEvent("evo", "id1", "EvolucionCreada", "t1", "p1", {"d": "x"})
        assert a.checksum == b.checksum

    def test_checksum_cambia_con_payload(self):
        from core.clinical_event_store import ClinicalEvent
        a = ClinicalEvent("evo", "id1", "EvolucionCreada", "t1", "p1", {"d": "x"})
        b = ClinicalEvent("evo", "id1", "EvolucionCreada", "t1", "p1", {"d": "y"})
        assert a.checksum != b.checksum

    def test_to_db_tuple(self):
        from core.clinical_event_store import ClinicalEvent
        event = ClinicalEvent("evo", "id1", "EvolucionCreada", "t1", "p1", {"d": "x"}, event_version=1)
        tup = event.to_db_tuple()
        assert len(tup) == 9
        assert tup[0] == "evo"
        assert tup[3] == 1


class TestEventStoreApply:
    def test_apply_evolucion_creada(self):
        from core.clinical_event_store import ClinicalEventStore
        state = ClinicalEventStore._apply({}, "EvolucionCreada", {"d": "neumonia"})
        assert state["d"] == "neumonia"

    def test_apply_evolucion_modificada(self):
        from core.clinical_event_store import ClinicalEventStore
        state = {"d": "neumonia", "nota": "paciente estable"}
        new_state = ClinicalEventStore._apply(state, "EvolucionModificada", {"nota": "paciente en mejoria"})
        assert new_state["d"] == "neumonia"
        assert new_state["nota"] == "paciente en mejoria"

    def test_apply_evolucion_eliminada(self):
        from core.clinical_event_store import ClinicalEventStore
        state = {"d": "neumonia"}
        new_state = ClinicalEventStore._apply(state, "EvolucionEliminada", {})
        assert "deleted_at" in new_state

    def test_apply_medication_administrada(self):
        from core.clinical_event_store import ClinicalEventStore
        state = {}
        new_state = ClinicalEventStore._apply(state, "MedicationAdministrada", {"med": "paracetamol"})
        assert len(new_state["medicaciones"]) == 1
        new_state = ClinicalEventStore._apply(new_state, "MedicationAdministrada", {"med": "ibuprofeno"})
        assert len(new_state["medicaciones"]) == 2

    def test_apply_medication_omitida(self):
        from core.clinical_event_store import ClinicalEventStore
        state = {}
        new_state = ClinicalEventStore._apply(state, "MedicationOmitida", {"med": "paracetamol", "razon": "alergia"})
        assert len(new_state["medicaciones"]) == 1

    def test_replay_vacio(self):
        from core.clinical_event_store import ClinicalEventStore
        result = ClinicalEventStore._apply({}, "UnknownEvent", {})
        assert result == {}


class TestEventHelpers:
    def test_crear_evento_evolucion_crear(self):
        from core.clinical_event_store import crear_evento_evolucion
        event = crear_evento_evolucion("evo-1", "t1", "prof-1", "crear", {"d": "gripe"}, 0)
        assert event.event_type == "EvolucionCreada"
        assert event.event_version == 1

    def test_crear_evento_evolucion_modificar(self):
        from core.clinical_event_store import crear_evento_evolucion
        event = crear_evento_evolucion("evo-1", "t1", "prof-1", "modificar", {"d": "neumonia"}, 3)
        assert event.event_type == "EvolucionModificada"
        assert event.event_version == 4

    def test_crear_evento_medicacion_administrada(self):
        from core.clinical_event_store import crear_evento_medicacion
        event = crear_evento_medicacion("adm-1", "t1", "prof-1", omitida=False,
                                        medicamento="paracetamol", dosis="500mg")
        assert event.event_type == "MedicationAdministrada"

    def test_crear_evento_medicacion_omitida(self):
        from core.clinical_event_store import crear_evento_medicacion
        event = crear_evento_medicacion("adm-1", "t1", "prof-1", omitida=True,
                                        medicamento="paracetamol", razon="alergia")
        assert event.event_type == "MedicationOmitida"


class TestSchemaSQL:
    def test_schema_contiene_tablas_clave(self):
        from core.clinical_event_store import SCHEMA_SQL
        assert "clinical_event_store" in SCHEMA_SQL
        assert "clinical_snapshot" in SCHEMA_SQL
        assert "replay_aggregate" in SCHEMA_SQL
        assert "apply_event_to_state" in SCHEMA_SQL
        assert "refresh_snapshot" in SCHEMA_SQL
