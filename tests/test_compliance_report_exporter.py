"""Tests para core.compliance_report_exporter — Compliance Audit."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestComplianceEvidence:
    def test_evidence_defaults(self):
        from core.compliance_report_exporter import ComplianceEvidence
        ev = ComplianceEvidence(category="event_store", title="Test", description="Desc")
        assert ev.category == "event_store"
        assert len(ev.checksum) == 32

    def test_evidence_checksum_deterministic(self):
        from core.compliance_report_exporter import ComplianceEvidence
        a = ComplianceEvidence(category="test", title="T", description="D", data={"k": "v"})
        b = ComplianceEvidence(category="test", title="T", description="D", data={"k": "v"})
        assert a.checksum == b.checksum

    def test_evidence_checksum_changes_with_data(self):
        from core.compliance_report_exporter import ComplianceEvidence
        a = ComplianceEvidence(category="test", title="T", description="D", data={"k": "v1"})
        b = ComplianceEvidence(category="test", title="T", description="D", data={"k": "v2"})
        assert a.checksum != b.checksum


class TestComplianceReport:
    def test_report_defaults(self):
        from core.compliance_report_exporter import ComplianceReport
        report = ComplianceReport(tenant_id="t1")
        assert report.report_id is not None
        assert "ISO 27001" in report.standards
        assert report.version == "2.1.0"

    def test_signature_empty_by_default(self):
        from core.compliance_report_exporter import ComplianceReport
        report = ComplianceReport(tenant_id="t1")
        assert report.signature == ""


class TestComplianceEvidenceCollector:
    def test_collect_event_store_empty(self):
        from core.compliance_report_exporter import ComplianceEvidenceCollector
        collector = ComplianceEvidenceCollector()
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[{
            "total_events": 0, "aggregate_types": 0,
            "first_event": None, "last_event": None,
            "modifications": 0, "creations": 0, "deletions": 0,
        }])
        collector._conn = mock_conn
        ev = asyncio.run(collector.collect_event_store_evidence("t1", 30))
        assert ev.category == "event_store"
        assert ev.data["total_events"] == 0

    def test_collect_access_log_empty(self):
        from core.compliance_report_exporter import ComplianceEvidenceCollector
        collector = ComplianceEvidenceCollector()
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[{
            "total_accesses": 0, "unique_actors": 0,
            "phi_reads": 0, "emergency_decrypts": 0,
        }])
        collector._conn = mock_conn
        ev = asyncio.run(collector.collect_access_log_evidence("t1", 30))
        assert ev.category == "access_log"

    def test_collect_key_rotation_empty(self):
        from core.compliance_report_exporter import ComplianceEvidenceCollector
        collector = ComplianceEvidenceCollector()
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[{
            "total_rotations": 0, "last_rotation": None,
        }])
        collector._conn = mock_conn
        ev = asyncio.run(collector.collect_key_rotation_evidence("t1"))
        assert ev.category == "key_rotation"

    def test_collect_compliance_evidence(self):
        from core.compliance_report_exporter import ComplianceEvidenceCollector
        collector = ComplianceEvidenceCollector()
        ev = asyncio.run(collector.collect_compliance_evidence("t1"))
        assert ev.category == "compliance_worker"
        assert ev.data["hipaa_checks_passed"] is True

    def test_close(self):
        from core.compliance_report_exporter import ComplianceEvidenceCollector
        collector = ComplianceEvidenceCollector()
        mock_conn = MagicMock()
        mock_conn.close = AsyncMock()
        collector._conn = mock_conn
        asyncio.run(collector.close())
        mock_conn.close.assert_awaited_once()


class TestComplianceReportExporter:
    def test_generate_report(self):
        from core.compliance_report_exporter import (ComplianceReportExporter,
                                                      ComplianceEvidenceCollector)
        exporter = ComplianceReportExporter()

        # Mock collector methods
        exporter._collector.collect_event_store_evidence = AsyncMock(return_value=MagicMock(
            category="event_store", title="ES", description="D",
            data={"total_events": 1000},
            checksum="abc",
        ))
        exporter._collector.collect_access_log_evidence = AsyncMock(return_value=MagicMock(
            category="access_log", title="AL", description="D",
            data={"total_accesses": 50},
            checksum="def",
        ))
        exporter._collector.collect_key_rotation_evidence = AsyncMock(return_value=MagicMock(
            category="key_rotation", title="KR", description="D",
            data={"total_rotations": 3},
            checksum="ghi",
        ))
        exporter._collector.collect_compliance_evidence = AsyncMock(return_value=MagicMock(
            category="compliance_worker", title="CW", description="D",
            data={"hipaa_checks_passed": True},
            checksum="jkl",
        ))

        report = asyncio.run(exporter.generate_report("t1", 30))
        assert report.tenant_id == "t1"
        assert len(report.evidence) == 4
        assert report.signature != ""
        assert report.summary["hipaa_compliant"] is True

    def test_verify_report_valid(self):
        from core.compliance_report_exporter import ComplianceReportExporter
        exporter = ComplianceReportExporter()

        # Create a report with real data
        from core.compliance_report_exporter import ComplianceEvidence
        report = asyncio.run(exporter.generate_report("t1", 30))

        assert exporter.verify_report(report) is True

    def test_verify_report_tampered(self):
        from core.compliance_report_exporter import ComplianceReportExporter
        exporter = ComplianceReportExporter()
        report = asyncio.run(exporter.generate_report("t1", 30))
        report.summary["hipaa_compliant"] = False  # tamper
        assert exporter.verify_report(report) is False

    def test_save_to_file(self):
        from core.compliance_report_exporter import (ComplianceReportExporter,
                                                      ComplianceReport)
        report = ComplianceReport(tenant_id="t1")
        tmp = tempfile.mktemp(suffix=".json")
        ComplianceReportExporter.save_to_file(report, tmp)
        assert os.path.exists(tmp)
        with open(tmp) as f:
            data = json.load(f)
        assert data["tenant_id"] == "t1"
        os.unlink(tmp)

    def test_to_html_summary(self):
        from core.compliance_report_exporter import ComplianceReportExporter
        exporter = ComplianceReportExporter()
        report = asyncio.run(exporter.generate_report("t1", 30))
        html = ComplianceReportExporter.to_html_summary(report)
        assert "<html>" in html
        assert report.title in html
