"""Tests para core.data_sanity_worker — Bit-Rot Detection."""
from __future__ import annotations

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCorruptionReport:
    def test_report_defaults(self):
        from core.data_sanity_worker import CorruptionReport
        r = CorruptionReport(table="t", row_id="1", expected_checksum="abc", actual_checksum="def")
        assert r.severity == "critical"
        assert r.reconstructed is False

    def test_to_dict(self):
        from core.data_sanity_worker import CorruptionReport
        r = CorruptionReport("t", "1", "abc", "def")
        d = r.to_dict()
        assert d["table"] == "t"
        assert d["severity"] == "critical"


class TestDataSanityWorker:
    def test_compute_expected_checksum_without_prev(self):
        from core.data_sanity_worker import DataSanityWorker
        chk = DataSanityWorker._compute_expected_checksum({"d": "test"}, None)
        assert len(chk) == 32

    def test_compute_expected_checksum_with_prev(self):
        from core.data_sanity_worker import DataSanityWorker
        chk = DataSanityWorker._compute_expected_checksum({"d": "test"}, "prev_hash_abc")
        assert len(chk) == 32

    def test_compute_expected_checksum_deterministic(self):
        from core.data_sanity_worker import DataSanityWorker
        a = DataSanityWorker._compute_expected_checksum({"x": 1}, "p")
        b = DataSanityWorker._compute_expected_checksum({"x": 1}, "p")
        assert a == b

    def test_file_sha256(self):
        from core.data_sanity_worker import DataSanityWorker
        tmp = tempfile.mktemp()
        with open(tmp, "wb") as f:
            f.write(b"test data for hash")
        h = DataSanityWorker._file_sha256(tmp)
        assert len(h) == 32
        os.unlink(tmp)

    def test_audit_event_store_no_corruption(self):
        from core.data_sanity_worker import DataSanityWorker
        worker = DataSanityWorker()
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(side_effect=[
            [{"aggregate_type": "evo", "aggregate_id": "a1"}],
            [{"id": "e1", "event_version": 1, "checksum": DataSanityWorker._compute_expected_checksum({"d": "test"}, None),
              "payload": {"d": "test"}, "prev_checksum": None}],
        ])
        worker._conn = mock_conn
        reports = asyncio.run(worker.audit_event_store(limit=100))
        assert len(reports) == 0

    def test_attempt_repair_event_store(self):
        from core.data_sanity_worker import DataSanityWorker, CorruptionReport
        worker = DataSanityWorker()
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")
        worker._conn = mock_conn
        report = CorruptionReport("clinical_event_store", "e1", "correct_hash", "wrong_hash")
        result = asyncio.run(worker.attempt_repair(report))
        assert result is True
        assert report.reconstructed is True

    def test_get_stats(self):
        from core.data_sanity_worker import DataSanityWorker
        worker = DataSanityWorker()
        assert worker._stats["rows_checked"] == 0
