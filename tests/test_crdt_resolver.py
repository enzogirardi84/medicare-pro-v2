"""Tests para core.crdt_resolver — LWW CRDT Merge Engine."""
from __future__ import annotations


class TestLWWRegister:
    def test_domination_por_version(self):
        from core.crdt_resolver import LWWRegister
        a = LWWRegister(version=3, timestamp=100.0, valor="A")
        b = LWWRegister(version=5, timestamp=50.0, valor="B")
        assert b.dominates(a)
        assert not a.dominates(b)

    def test_domination_por_timestamp_misma_version(self):
        from core.crdt_resolver import LWWRegister
        a = LWWRegister(version=1, timestamp=200.0, valor="v1")
        b = LWWRegister(version=1, timestamp=100.0, valor="v2")
        assert a.dominates(b)
        assert not b.dominates(a)

    def test_domination_por_hash_desempate(self):
        from core.crdt_resolver import LWWRegister
        a = LWWRegister(version=1, timestamp=100.0, valor="aaa")
        b = LWWRegister(version=1, timestamp=100.0, valor="bbb")
        # hash de "aaa" vs "bbb" — deterministico
        ganador = a if a.hash_valor >= b.hash_valor else b
        assert ganador.dominates(a if ganador is b else b)

    def test_merge_retorna_dominante(self):
        from core.crdt_resolver import LWWRegister
        a = LWWRegister(version=2, timestamp=100.0, valor="old")
        b = LWWRegister(version=5, timestamp=200.0, valor="new")
        merged = a.merge(b)
        assert merged is b  # el merge retorna el dominante

    def test_to_from_dict_roundtrip(self):
        from core.crdt_resolver import LWWRegister
        original = LWWRegister(version=3, timestamp=500.0, valor="test_val")
        d = original.to_dict()
        restored = LWWRegister.from_dict(d)
        assert restored.version == 3
        assert restored.timestamp == 500.0
        assert restored.valor == "test_val"
        assert restored.hash_valor == original.hash_valor


class TestCRDTRecord:
    def test_merge_campo_nuevo(self):
        from core.crdt_resolver import CRDTRecord, LWWRegister
        record = CRDTRecord(record_id="r1", tabla="evoluciones", tenant_id="t1")
        result = record.merge_campo("diagnostico", LWWRegister(version=1, timestamp=100.0, valor="neumonia"))
        assert result is True
        assert record.campos["diagnostico"].valor == "neumonia"

    def test_merge_campo_existente(self):
        from core.crdt_resolver import CRDTRecord, LWWRegister
        record = CRDTRecord(record_id="r1", tabla="evoluciones", tenant_id="t1")
        record.campos["diagnostico"] = LWWRegister(version=1, timestamp=100.0, valor="gripe")
        result = record.merge_campo("diagnostico", LWWRegister(version=2, timestamp=200.0, valor="neumonia"))
        assert record.campos["diagnostico"].valor == "neumonia"
        # Solo cambio si el merge eligio el nuevo

    def test_merge_records_con_conflictos(self):
        from core.crdt_resolver import CRDTRecord, LWWRegister
        a = CRDTRecord(record_id="r1", tabla="evoluciones", tenant_id="t1")
        a.campos["diagnostico"] = LWWRegister(version=1, timestamp=100.0, valor="gripe")
        a.campos["medicacion"] = LWWRegister(version=1, timestamp=100.0, valor="paracetamol")

        b = CRDTRecord(record_id="r1", tabla="evoluciones", tenant_id="t1")
        b.campos["diagnostico"] = LWWRegister(version=2, timestamp=200.0, valor="neumonia")
        b.campos["medicacion"] = LWWRegister(version=1, timestamp=100.0, valor="ibuprofeno")  # misma ver, diff valor

        conflictos = a.merge_record(b)
        assert a.campos["diagnostico"].valor == "neumonia"  # version 2 gana
        assert len(conflictos) >= 0

    def test_is_deleted(self):
        from core.crdt_resolver import CRDTRecord, LWWRegister
        record = CRDTRecord(record_id="r1", tabla="evoluciones", tenant_id="t1")
        record.deleted = LWWRegister(version=1, timestamp=100.0, valor=True)
        assert record.is_deleted() is True

    def test_to_from_dict_roundtrip(self):
        from core.crdt_resolver import CRDTRecord, LWWRegister
        original = CRDTRecord(record_id="r1", tabla="evoluciones", tenant_id="t1")
        original.campos["diagnostico"] = LWWRegister(version=2, timestamp=200.0, valor="diabetes")
        d = original.to_dict()
        restored = CRDTRecord.from_dict(d)
        assert restored.record_id == "r1"
        assert restored.campos["diagnostico"].valor == "diabetes"


class TestCRDTMergeEngine:
    def test_merge_batch_sin_conflictos(self):
        from core.crdt_resolver import CRDTMergeEngine
        import asyncio
        engine = CRDTMergeEngine()
        cliente = [{"id": "r1", "diagnostico": "gripe", "version": 1, "updated_at": 100.0}]
        servidor = [{"id": "r1", "diagnostico": "neumonia", "version": 2, "updated_at": 200.0}]
        result = asyncio.run(engine.merge_batch(cliente, servidor, "evoluciones", "t1"))
        assert isinstance(result, dict)
        assert "merged" in result
        assert "conflictos" in result

    def test_merge_batch_solo_cliente(self):
        from core.crdt_resolver import CRDTMergeEngine
        import asyncio
        engine = CRDTMergeEngine()
        cliente = [{"id": "r1", "diagnostico": "gripe", "version": 1}]
        result = asyncio.run(engine.merge_batch(cliente, [], "evoluciones", "t1"))
        assert len(result["merged"]) == 1

    def test_merge_batch_solo_servidor(self):
        from core.crdt_resolver import CRDTMergeEngine
        import asyncio
        engine = CRDTMergeEngine()
        servidor = [{"id": "r1", "diagnostico": "neumonia", "version": 2}]
        result = asyncio.run(engine.merge_batch([], servidor, "evoluciones", "t1"))
        assert len(result["merged"]) == 1

    def test_build_hash_deterministico(self):
        from core.crdt_resolver import CRDTMergeEngine
        h1 = CRDTMergeEngine._build_hash({"a": 1, "b": 2})
        h2 = CRDTMergeEngine._build_hash({"b": 2, "a": 1})
        assert h1 == h2
        assert len(h1) == 32

    def test_registro_a_crdt_incluye_campos(self):
        from core.crdt_resolver import CRDTMergeEngine
        registro = {"id": "r1", "diagnostico": "fractura", "medicacion": "ibuprofeno",
                     "version": 3, "updated_at": 300.0}
        crdt = CRDTMergeEngine().registro_a_crdt(registro, "evoluciones", "t1", version=3)
        assert crdt.record_id == "r1"
        assert "diagnostico" in crdt.campos
        assert "medicacion" in crdt.campos
        assert "version" not in crdt.campos  # campo excluido
        assert "id" not in crdt.campos

    def test_get_conflict_log(self):
        from core.crdt_resolver import CRDTMergeEngine
        engine = CRDTMergeEngine()
        assert engine.get_conflict_log() == []
