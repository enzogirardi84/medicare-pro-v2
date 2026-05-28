"""Tests para core.document_manager."""
from __future__ import annotations

import pytest


class TestDocumentManager:
    """Tests para funciones públicas de core.document_manager."""

    def test_document_manager_importable(self):
        import core.document_manager
        assert core.document_manager is not None

    def test_functions_exist(self):
        import core.document_manager
        assert callable(core.document_manager.get_document_manager)
        assert callable(core.document_manager.upload_document)
        assert callable(core.document_manager.get_document)
        assert callable(core.document_manager.get_patient_documents)
        assert callable(core.document_manager.get_document_content)
        assert callable(core.document_manager.delete_document)
        assert callable(core.document_manager.search_documents)
        assert callable(core.document_manager.render_document_gallery)
        assert callable(core.document_manager.render_upload_form)
