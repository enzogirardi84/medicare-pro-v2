"""Tests para core/digital_signature.py — RSA 2048, SHA-256, Ley 25.506.
Cubre: key generation, sign, verify, tamper detection, key persistence.
"""
from __future__ import annotations

import copy
import json
from unittest.mock import MagicMock, patch

import pytest

from core.digital_signature import (
    DigitalSignatureManager,
    DocumentType,
    SignatureMetadata,
    SignedDocument,
    get_signature_manager,
    setup_user_keys,
    sign_evolucion,
    verify_document_signature,
)


@pytest.fixture(autouse=True)
def mock_settings():
    """Mockea get_settings() para que devuelva un SECRET_KEY válido."""
    with patch("core.digital_signature.get_settings") as mock:
        fake_settings = MagicMock()
        fake_secret = MagicMock()
        fake_secret.get_secret_value.return_value = "test-secret-key-32-bytes-long!!"
        fake_settings.secret_key = fake_secret
        mock.return_value = fake_settings
        yield mock


@pytest.fixture
def fresh_manager():
    """Retorna un manager limpio (sin keystore previo)."""
    mgr = DigitalSignatureManager()
    mgr._keystore = {}
    mgr._signed_documents = {}
    return mgr


@pytest.fixture
def sample_document():
    return {
        "paciente": "Juan Perez - 12345678",
        "nota": "Paciente evoluciona favorablemente",
        "fecha": "27/05/2026 10:30",
        "profesional": "Dr. Garcia",
    }


# ═══════════════════════════════════════════════════════════════════════
#  KEY GENERATION
# ═══════════════════════════════════════════════════════════════════════

class TestKeyGeneration:
    def test_generate_keypair_returns_encrypted_private_and_public(self, fresh_manager):
        mgr = fresh_manager
        priv, pub = mgr.generate_keypair("dr.garcia")
        assert isinstance(priv, bytes)
        assert isinstance(pub, bytes)
        assert len(priv) > 100  # encrypted PEM
        assert pub.startswith(b"-----BEGIN PUBLIC KEY-----")

    def test_has_keypair_after_generation(self, fresh_manager):
        mgr = fresh_manager
        assert mgr.has_keypair("dr.garcia") is False
        mgr.generate_keypair("dr.garcia")
        assert mgr.has_keypair("dr.garcia") is True

    def test_generate_keypair_stores_fingerprint(self, fresh_manager):
        mgr = fresh_manager
        mgr.generate_keypair("dr.garcia")
        entry = mgr._keystore["dr.garcia"]
        assert "fingerprint" in entry
        assert len(entry["fingerprint"]) == 16

    def test_keypair_persistence_in_session_state(self, fresh_manager):
        mgr = fresh_manager
        mgr.generate_keypair("user1")
        mgr._save_keystore()
        # Simular nueva instancia
        mgr2 = DigitalSignatureManager()
        assert mgr2.has_keypair("user1") is True


# ═══════════════════════════════════════════════════════════════════════
#  SIGNING
# ═══════════════════════════════════════════════════════════════════════

class TestSignDocument:
    def test_sign_document_returns_signed_doc(self, fresh_manager, sample_document):
        mgr = fresh_manager
        mgr.generate_keypair("dr.garcia")
        signed = mgr.sign_document(
            document=sample_document,
            doc_type=DocumentType.EVOLUCION,
            signer_id="dr.garcia",
            signer_name="Dr. Garcia",
            signer_role="Medico",
        )
        assert isinstance(signed, SignedDocument)
        assert signed.document_type == "evolucion"
        assert signed.signature.signer_id == "dr.garcia"
        assert signed.signature.document_hash is not None
        assert signed.signature.signature_value is not None

    def test_sign_without_keys_raises_error(self, fresh_manager, sample_document):
        mgr = fresh_manager
        with pytest.raises(ValueError, match="no tiene clave privada"):
            mgr.sign_document(
                document=sample_document,
                doc_type=DocumentType.EVOLUCION,
                signer_id="sin.claves",
                signer_name="Sin Claves",
                signer_role="Medico",
            )

    def test_sign_evolucion_helper_generates_keys_auto(self, sample_document):
        # Limpiar singleton
        import core.digital_signature as ds
        ds._signature_manager = None
        mgr = get_signature_manager()
        mgr._keystore = {}

        signed = sign_evolucion(sample_document, "dr.test", "Dr. Test")
        assert signed.document_type == "evolucion"
        assert mgr.has_keypair("dr.test") is True


# ═══════════════════════════════════════════════════════════════════════
#  VERIFICATION
# ═══════════════════════════════════════════════════════════════════════

class TestVerifySignature:
    def test_verify_valid_signature(self, fresh_manager, sample_document):
        mgr = fresh_manager
        mgr.generate_keypair("dr.garcia")
        signed = mgr.sign_document(sample_document, DocumentType.EVOLUCION, "dr.garcia", "Dr. Garcia", "Medico")
        is_valid, msg = mgr.verify_signature(signed)
        assert is_valid is True
        assert "válida" in msg.lower()

    def test_verify_tampered_content(self, fresh_manager, sample_document):
        mgr = fresh_manager
        mgr.generate_keypair("dr.garcia")
        signed = mgr.sign_document(sample_document, DocumentType.EVOLUCION, "dr.garcia", "Dr. Garcia", "Medico")
        # Modificar contenido
        signed.content["nota"] = "CONTENIDO MODIFICADO"
        is_valid, msg = mgr.verify_signature(signed)
        assert is_valid is False
        assert "modificado" in msg.lower() or "fallida" in msg.lower()

    def test_verify_tampered_hash(self, fresh_manager, sample_document):
        mgr = fresh_manager
        mgr.generate_keypair("dr.garcia")
        signed = mgr.sign_document(sample_document, DocumentType.EVOLUCION, "dr.garcia", "Dr. Garcia", "Medico")
        signed.signature.document_hash = "ffff" * 16  # hash falso
        is_valid, msg = mgr.verify_signature(signed)
        assert is_valid is False

    def test_verify_wrong_signer(self, fresh_manager, sample_document):
        mgr = fresh_manager
        mgr.generate_keypair("dr.garcia")
        mgr.generate_keypair("dr.otro")
        signed = mgr.sign_document(sample_document, DocumentType.EVOLUCION, "dr.garcia", "Dr. Garcia", "Medico")
        # Firmado por dr.garcia, verificar con otro
        signed.signature.public_key_fingerprint = mgr._keystore["dr.otro"]["fingerprint"]
        is_valid, msg = mgr.verify_signature(signed)
        assert is_valid is False

    def test_verify_unknown_signer(self, fresh_manager, sample_document):
        mgr = fresh_manager
        mgr.generate_keypair("dr.garcia")
        signed = mgr.sign_document(sample_document, DocumentType.EVOLUCION, "dr.garcia", "Dr. Garcia", "Medico")
        signed.signature.signer_id = "unknown"
        is_valid, msg = mgr.verify_signature(signed)
        assert is_valid is False


# ═══════════════════════════════════════════════════════════════════════
#  EDGE CASES
# ═══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_empty_document_signs_successfully(self, fresh_manager):
        mgr = fresh_manager
        mgr.generate_keypair("dr.test")
        signed = mgr.sign_document({}, DocumentType.EVOLUCION, "dr.test", "Dr", "M")
        is_valid, _ = mgr.verify_signature(signed)
        assert is_valid is True

    def test_large_document_signs_and_verifies(self, fresh_manager):
        mgr = fresh_manager
        mgr.generate_keypair("dr.test")
        large_doc = {"data": "x" * 10000, "paciente": "Test"}
        signed = mgr.sign_document(large_doc, DocumentType.EVOLUCION, "dr.test", "Dr", "M")
        is_valid, _ = mgr.verify_signature(signed)
        assert is_valid is True

    def test_sign_after_key_regeneration(self, fresh_manager, sample_document):
        mgr = fresh_manager
        mgr.generate_keypair("dr.garcia")
        signed1 = mgr.sign_document(sample_document, DocumentType.EVOLUCION, "dr.garcia", "Dr", "M")
        # Regenerar claves
        mgr.generate_keypair("dr.garcia")
        signed2 = mgr.sign_document(sample_document, DocumentType.EVOLUCION, "dr.garcia", "Dr", "M")
        # La firma anterior con clave vieja debe fallar
        is_valid, _ = mgr.verify_signature(signed1)
        assert is_valid is False
        # La firma nueva debe pasar
        is_valid, _ = mgr.verify_signature(signed2)
        assert is_valid is True

    def test_multiple_signers(self, fresh_manager, sample_document):
        mgr = fresh_manager
        mgr.generate_keypair("medico1")
        mgr.generate_keypair("medico2")
        s1 = mgr.sign_document(sample_document, DocumentType.EVOLUCION, "medico1", "Dr1", "M")
        s2 = mgr.sign_document(sample_document, DocumentType.EVOLUCION, "medico2", "Dr2", "M")
        assert s1.signature.signer_id == "medico1"
        assert s2.signature.signer_id == "medico2"
        v1, _ = mgr.verify_signature(s1)
        v2, _ = mgr.verify_signature(s2)
        assert v1 and v2

    def test_get_signed_documents_filter(self, fresh_manager, sample_document):
        mgr = fresh_manager
        mgr.generate_keypair("dr.test")
        mgr.sign_document(sample_document, DocumentType.EVOLUCION, "dr.test", "Dr", "M")
        mgr.sign_document(sample_document, DocumentType.RECETA, "dr.test", "Dr", "M")
        docs_evol = mgr.get_signed_documents(doc_type=DocumentType.EVOLUCION)
        docs_rec = mgr.get_signed_documents(doc_type=DocumentType.RECETA)
        assert len(docs_evol) == 1
        assert len(docs_rec) == 1
        assert docs_evol[0].document_type == "evolucion"
        assert docs_rec[0].document_type == "receta"

    def test_export_certificate(self, fresh_manager, sample_document):
        mgr = fresh_manager
        mgr.generate_keypair("dr.test")
        signed = mgr.sign_document(sample_document, DocumentType.EVOLUCION, "dr.test", "Dr", "M")
        cert = mgr.export_signature_certificate(signed.document_id)
        assert cert is not None
        assert cert["document_id"] == signed.document_id
        assert cert["signer"]["id"] == "dr.test"
        assert cert["signature"] == signed.signature.signature_value

    def test_repeated_document_different_hash(self, fresh_manager):
        """Mismo contenido pero diferente metadata debe producir diferente hash."""
        mgr = fresh_manager
        mgr.generate_keypair("dr.test")
        doc1 = {"paciente": "P1", "fecha": "01/01/2026"}
        doc2 = {"paciente": "P1", "fecha": "02/01/2026"}
        s1 = mgr.sign_document(doc1, DocumentType.EVOLUCION, "dr.test", "Dr", "M")
        s2 = mgr.sign_document(doc2, DocumentType.EVOLUCION, "dr.test", "Dr", "M")
        assert s1.signature.document_hash != s2.signature.document_hash


# ═══════════════════════════════════════════════════════════════════════
#  FLUJO COMPLETO: Ley 25.506
# ═══════════════════════════════════════════════════════════════════════

class TestFlujoCompleto:
    """Simula el flujo real: profesional firma evolución, se verifica, se detecta manipulación."""

    def test_flujo_completo_evolucion(self):
        import core.digital_signature as ds
        ds._signature_manager = None

        # 1. Crear evolución
        evolucion = {
            "paciente": "Maria Lopez - 87654321",
            "nota": "Paciente con fractura de cadera. Se realizó reducción cerrada. Evolución favorable.",
            "fecha": "27/05/2026 14:30",
            "profesional": "Dr. Garcia",
            "matricula": "MP 12345",
        }

        # 2. Firmar
        signed = sign_evolucion(evolucion, "dr.garcia", "Dr. Garcia")
        assert signed.signature.document_hash is not None

        # 3. Verificar
        is_valid, msg = verify_document_signature(signed.document_id)
        assert is_valid is True, f"Firma debería ser válida: {msg}"

        # 4. Alguien modifica la nota
        signed.content["nota"] = "Nota modificada maliciosamente"

        # 5. Verificar detecta manipulación
        is_valid, msg = verify_document_signature(signed.document_id)
        assert is_valid is False, "Firma debería detectar manipulación"
        assert "modificado" in msg.lower()
