"""Tests para core.secure_deletion — Shredding + Temp GC."""
from __future__ import annotations

import asyncio
import os
import tempfile
import time
from unittest.mock import patch

import pytest


class TestCryptographicShredder:
    def test_shred_file_removes_file(self):
        from core.secure_deletion import CryptographicShredder
        tmp = tempfile.mktemp(suffix=".audit.db")
        with open(tmp, "wb") as f:
            f.write(b"sensitive PHI data x" * 100)
        assert os.path.exists(tmp)
        result = CryptographicShredder.shred_file(tmp)
        assert result is True
        assert not os.path.exists(tmp)

    def test_shred_nonexistent_file(self):
        from core.secure_deletion import CryptographicShredder
        result = CryptographicShredder.shred_file("/nonexistent/path.db")
        assert result is False


class TestTempAuditFile:
    def test_defaults(self):
        from core.secure_deletion import TempAuditFile
        taf = TempAuditFile(path="/tmp/test.db")
        assert taf.ttl_seconds == 3600.0
        assert taf.shredded is False
        assert taf.downloaded is False

    def test_expired(self):
        from core.secure_deletion import TempAuditFile
        taf = TempAuditFile(path="/tmp/test.db", ttl_seconds=0.01, created_at=time.time() - 1)
        assert taf.expired is True

    def test_not_expired(self):
        from core.secure_deletion import TempAuditFile
        taf = TempAuditFile(path="/tmp/test.db", ttl_seconds=3600)
        assert taf.expired is False


class TestTempFileGarbageCollector:
    def test_register_file(self):
        from core.secure_deletion import TempFileGarbageCollector
        gc = TempFileGarbageCollector()
        tmp = tempfile.mktemp()
        with open(tmp, "w") as f:
            f.write("data")
        taf = gc.register_file(tmp, ttl=3600, tenant_id="t1", auditor_id="aud-1")
        assert taf.tenant_id == "t1"
        assert taf.original_size > 0
        os.unlink(tmp)

    def test_mark_downloaded_destroys(self):
        from core.secure_deletion import TempFileGarbageCollector
        gc = TempFileGarbageCollector()
        tmp = tempfile.mktemp(suffix=".audit.db")
        with open(tmp, "wb") as f:
            f.write(b"data")
        taf = gc.register_file(tmp, ttl=3600)
        assert gc.mark_downloaded(taf.file_id) is True
        assert taf.shredded is True

    def test_get_stats(self):
        from core.secure_deletion import TempFileGarbageCollector
        gc = TempFileGarbageCollector()
        stats = gc.get_stats()
        assert stats["total_registered"] == 0
        assert stats["shredded"] == 0
