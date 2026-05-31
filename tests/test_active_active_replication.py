"""Tests para core.active_active_replication — Vector Clocks + CRDT."""
from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch


class TestVectorClock:
    def test_tick_increments_region(self):
        from core.active_active_replication import VectorClock
        vc = VectorClock()
        vc2 = vc.tick("region-a")
        assert vc2.clocks["region-a"] == 1
        vc3 = vc2.tick("region-a")
        assert vc3.clocks["region-a"] == 2

    def test_merge_takes_max(self):
        from core.active_active_replication import VectorClock
        a = VectorClock(clocks={"r1": 3, "r2": 1})
        b = VectorClock(clocks={"r1": 2, "r2": 5, "r3": 1})
        merged = a.merge(b)
        assert merged.clocks["r1"] == 3
        assert merged.clocks["r2"] == 5
        assert merged.clocks["r3"] == 1

    def test_happens_before_true(self):
        from core.active_active_replication import VectorClock
        a = VectorClock(clocks={"r1": 2, "r2": 1})
        b = VectorClock(clocks={"r1": 3, "r2": 2})
        assert a.happens_before(b) is True
        assert b.happens_before(a) is False

    def test_happens_before_false_concurrent(self):
        from core.active_active_replication import VectorClock
        a = VectorClock(clocks={"r1": 3, "r2": 1})
        b = VectorClock(clocks={"r1": 2, "r2": 2})
        assert a.happens_before(b) is False
        assert b.happens_before(a) is False

    def test_is_concurrent(self):
        from core.active_active_replication import VectorClock
        a = VectorClock(clocks={"r1": 2, "r2": 3})
        b = VectorClock(clocks={"r1": 3, "r2": 2})
        assert a.is_concurrent(b) is True

    def test_to_from_dict_roundtrip(self):
        from core.active_active_replication import VectorClock
        original = VectorClock(clocks={"r1": 5, "r2": 3})
        d = original.to_dict()
        restored = VectorClock.from_dict(d)
        assert restored.clocks["r1"] == 5
        assert restored.clocks["r2"] == 3

    def test_compact_roundtrip(self):
        from core.active_active_replication import VectorClock
        original = VectorClock(clocks={"r1": 5, "r2": 3})
        compact = original.to_compact()
        restored = VectorClock.from_compact(compact)
        assert restored.clocks["r1"] == 5
        assert restored.clocks["r2"] == 3

    def test_from_compact_empty(self):
        from core.active_active_replication import VectorClock
        vc = VectorClock.from_compact("")
        assert vc.clocks == {}

    def test_eq(self):
        from core.active_active_replication import VectorClock
        a = VectorClock(clocks={"r1": 1})
        b = VectorClock(clocks={"r1": 1})
        assert a == b


class TestActiveActiveReplicator:
    def test_tick_increments(self):
        from core.active_active_replication import ActiveActiveReplicator
        rep = ActiveActiveReplicator("r1")
        clock = rep.tick()
        assert clock.clocks["r1"] == 1
        assert rep.get_local_clock().clocks["r1"] == 1

    def test_resolve_conflict_causal(self):
        from core.active_active_replication import (ActiveActiveReplicator,
                                                     VectorEvent, VectorClock)
        rep = ActiveActiveReplicator("local")
        local = VectorEvent(
            event_id="e1", region_id="local",
            aggregate_type="evo", aggregate_id="a1",
            event_type="Modificada",
            payload={"d": "v1"},
            vector_clock=VectorClock(clocks={"local": 2, "remote": 1}),
            timestamp=100.0,
        )
        remote = VectorEvent(
            event_id="e2", region_id="remote",
            aggregate_type="evo", aggregate_id="a1",
            event_type="Modificada",
            payload={"d": "v2"},
            vector_clock=VectorClock(clocks={"local": 3, "remote": 1}),
            timestamp=200.0,
        )
        winner = rep.resolve_conflict(local, remote)
        assert winner.region_id == "remote"  # remote causally succeeds local

    def test_resolve_conflict_concurrent_lww_timestamp(self):
        from core.active_active_replication import (ActiveActiveReplicator,
                                                     VectorEvent, VectorClock)
        rep = ActiveActiveReplicator("local")
        local = VectorEvent(
            event_id="e1", region_id="local",
            aggregate_type="evo", aggregate_id="a1",
            event_type="Modificada", payload={"d": "old"},
            vector_clock=VectorClock(clocks={"local": 1, "remote": 0}),
            timestamp=100.0, checksum="aaa",
        )
        remote = VectorEvent(
            event_id="e2", region_id="remote",
            aggregate_type="evo", aggregate_id="a1",
            event_type="Modificada", payload={"d": "new"},
            vector_clock=VectorClock(clocks={"local": 0, "remote": 1}),
            timestamp=200.0, checksum="bbb",
        )
        winner = rep.resolve_conflict(local, remote)
        assert winner.event_id == "e2"  # timestamp mas reciente gana

    def test_resolve_conflict_concurrent_lww_checksum(self):
        from core.active_active_replication import (ActiveActiveReplicator,
                                                     VectorEvent, VectorClock)
        rep = ActiveActiveReplicator("local")
        ts = 100.0
        local = VectorEvent(
            event_id="e1", region_id="local",
            aggregate_type="evo", aggregate_id="a1",
            event_type="Modificada", payload={"d": "a"},
            vector_clock=VectorClock(clocks={"local": 1, "remote": 0}),
            timestamp=ts, checksum="aaa",
        )
        remote = VectorEvent(
            event_id="e2", region_id="remote",
            aggregate_type="evo", aggregate_id="a1",
            event_type="Modificada", payload={"d": "b"},
            vector_clock=VectorClock(clocks={"local": 0, "remote": 1}),
            timestamp=ts, checksum="bbb",
        )
        winner = rep.resolve_conflict(local, remote)
        assert winner.checksum == "bbb"  # checksum mayor gana

    def test_ingest_remote_event_merges_clock(self):
        from core.active_active_replication import (ActiveActiveReplicator,
                                                     VectorEvent, VectorClock)
        rep = ActiveActiveReplicator("local")
        rep.tick()
        remote = VectorEvent(
            event_id="r1", region_id="remote",
            aggregate_type="evo", aggregate_id="a1",
            event_type="Creada", payload={},
            vector_clock=VectorClock(clocks={"remote": 3}),
        )
        rep.ingest_remote_event(remote)
        clock = rep.get_local_clock()
        assert clock.clocks.get("remote", 0) == 3

    def test_conflict_log(self):
        from core.active_active_replication import (ActiveActiveReplicator,
                                                     VectorEvent, VectorClock)
        rep = ActiveActiveReplicator("local")
        local = VectorEvent("e1", "local", "evo", "a1", "Modificada", {},
                            VectorClock(clocks={"local": 1}), 100.0, "a")
        remote = VectorEvent("e2", "remote", "evo", "a1", "Modificada", {},
                             VectorClock(clocks={"remote": 1}), 200.0, "b")
        rep.resolve_conflict(local, remote)
        assert len(rep.get_conflict_log()) == 1


class TestVectorCRDTMergeEngine:
    def test_merge_batch_replicated_no_conflicts(self):
        from core.active_active_replication import VectorCRDTMergeEngine
        import asyncio
        engine = VectorCRDTMergeEngine(region_id="local")
        local = [{"id": "e1", "aggregate_type": "evo", "aggregate_id": "a1",
                  "event_type": "Creada", "payload": {"d": "v1"},
                  "vector_clock": "local:1", "timestamp": 100.0, "checksum": "a"}]
        remote = [{"id": "e2", "aggregate_type": "evo", "aggregate_id": "a2",
                   "event_type": "Creada", "payload": {"d": "v2"},
                   "vector_clock": "remote:1", "timestamp": 200.0, "checksum": "b"}]
        result = asyncio.run(engine.merge_batch_replicated(local, remote, "remote"))
        assert result["total"] == 2
        assert len(result["conflictos"]) == 0

    def test_merge_batch_replicated_with_conflicts(self):
        from core.active_active_replication import VectorCRDTMergeEngine
        import asyncio
        engine = VectorCRDTMergeEngine(region_id="local")
        local = [{"id": "e1", "aggregate_type": "evo", "aggregate_id": "a1",
                  "event_type": "Modificada", "payload": {"d": "v1"},
                  "vector_clock": "local:1", "timestamp": 100.0, "checksum": "a"}]
        remote = [{"id": "e2", "aggregate_type": "evo", "aggregate_id": "a1",
                   "event_type": "Modificada", "payload": {"d": "v2"},
                   "vector_clock": "remote:1", "timestamp": 200.0, "checksum": "b"}]
        result = asyncio.run(engine.merge_batch_replicated(local, remote, "remote"))
        assert len(result["conflictos"]) == 1


class TestReplicationSQL:
    def test_sql_contains_tables(self):
        from core.active_active_replication import REPLICATION_SQL
        assert "replication_log" in REPLICATION_SQL

    def test_conflict_trigger_sql(self):
        from core.active_active_replication import CONFLICT_TRIGGER_SQL
        assert "resolve_region_conflict" in CONFLICT_TRIGGER_SQL
