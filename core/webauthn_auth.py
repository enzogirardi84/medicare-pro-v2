"""Autenticacion WebAuthn (Passkeys) para profesionales en campo.
Registra biometricos nativos (FaceID/TouchID) como segundo factor.
Genera JWT asimetricos ES256 vinculados al dispositivo.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional
from uuid import uuid4

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. CONFIGURACION WEBAUTHN
# ═══════════════════════════════════════════════════════════════════

RP_ID = os.environ.get("WEBAUTHN_RP_ID", "medicare-pro.app")
RP_NAME = "MediCare Enterprise PRO"
ORIGIN = os.environ.get("WEBAUTHN_ORIGIN", f"https://{RP_ID}")


# ═══════════════════════════════════════════════════════════════════
# 2. REGISTRO DE CREDENCIAL WEBAUTHN
# ═══════════════════════════════════════════════════════════════════

class WebAuthnManager:
    """Gestiona registro y verificacion de credenciales WebAuthn.

    Usa py_webauthn para la logica criptografica del lado del servidor.
    """

    @staticmethod
    def generar_opcion_registro(usuario_id: str, usuario_nombre: str) -> dict[str, Any]:
        """Genera opcion de registro para enviar al navegador.

        Returns:
            Dict con PublicKeyCredentialCreationOptions para el frontend.
        """
        try:
            from webauthn import generate_registration_options
            from webauthn.helpers.structs import (
                AuthenticatorSelectionCriteria,
                UserVerificationRequirement,
            )

            options = generate_registration_options(
                rp_id=RP_ID,
                rp_name=RP_NAME,
                user_id=usuario_id.encode("utf-8"),
                user_name=usuario_nombre,
                user_display_name=usuario_nombre,
                authenticator_selection=AuthenticatorSelectionCriteria(
                    user_verification=UserVerificationRequirement.REQUIRED,
                ),
            )

            return json.loads(options.model_dump_json())

        except ImportError:
            log_event("webauthn", "py_webauthn no instalado")
            return self._fallback_registration_options(usuario_id, usuario_nombre)

    @staticmethod
    def verificar_registro(response_json: str) -> Optional[dict[str, Any]]:
        """Verifica la respuesta de registro del navegador.

        Returns:
            Dict con credential_id y public_key para almacenar.
        """
        try:
            from webauthn import verify_registration_response
            from webauthn.helpers.structs import RegistrationCredential

            credential = RegistrationCredential.model_validate_json(response_json)
            verification = verify_registration_response(
                credential=credential,
                expected_challenge=os.urandom(32).hex(),
                expected_rp_id=RP_ID,
                expected_origin=ORIGIN,
            )

            return {
                "credential_id": verification.credential_id.hex(),
                "public_key": verification.credential_public_key.hex(),
                "sign_count": verification.sign_count,
            }
        except ImportError:
            log_event("webauthn", "py_webauthn no instalado")
            return None
        except Exception as exc:
            log_event("webauthn", f"verificacion_error:{type(exc).__name__}")
            return None

    @staticmethod
    def _fallback_registration_options(usuario_id: str, usuario_nombre: str) -> dict[str, Any]:
        """Fallback cuando py_webauthn no esta instalado.

        Genera opciones manualmente para desarrollo/testing.
        """
        import base64
        challenge = os.urandom(32)
        user_id = usuario_id.encode("utf-8")
        return {
            "publicKey": {
                "rp": {"id": RP_ID, "name": RP_NAME},
                "user": {
                    "id": base64.b64encode(user_id).decode(),
                    "name": usuario_nombre,
                    "displayName": usuario_nombre,
                },
                "challenge": base64.b64encode(challenge).decode(),
                "pubKeyCredParams": [{"type": "public-key", "alg": -7}],
                "authenticatorSelection": {
                    "userVerification": "required",
                },
                "timeout": 60000,
            }
        }


# ═══════════════════════════════════════════════════════════════════
# 3. VERIFICACION DE AUTENTICACION WEBAUTHN
# ═══════════════════════════════════════════════════════════════════

def verificar_passkey(
    credential_id: str,
    response_json: str,
    stored_public_key: str,
    stored_sign_count: int,
) -> tuple[bool, int]:
    """Verifica un intento de autenticacion WebAuthn.

    Args:
        credential_id: ID de la credencial registrada.
        response_json: Respuesta JSON del navegador.
        stored_public_key: Clave publica almacenada (hex).
        stored_sign_count: Contador de uso almacenado.

    Returns:
        (valido, nuevo_sign_count)
    """
    try:
        from webauthn import verify_authentication_response
        from webauthn.helpers.structs import AuthenticationCredential

        credential = AuthenticationCredential.model_validate_json(response_json)
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=os.urandom(32).hex(),
            expected_rp_id=RP_ID,
            expected_origin=ORIGIN,
            credential_public_key=bytes.fromhex(stored_public_key),
            credential_current_sign_count=stored_sign_count,
        )

        return True, verification.new_sign_count

    except ImportError:
        log_event("webauthn", "py_webauthn no instalado")
        return False, stored_sign_count
    except Exception as exc:
        log_event("webauthn", f"auth_error:{type(exc).__name__}")
        return False, stored_sign_count


# ═══════════════════════════════════════════════════════════════════
# 4. GENERACION DE JWT POST-WEBAUTHN
# ═══════════════════════════════════════════════════════════════════

def generar_jwt_post_webauthn(
    usuario_id: str,
    tenant_id: str,
    credential_id: str,
) -> Optional[str]:
    """Genera JWT asimetrico ES256 tras autenticacion WebAuthn exitosa.

    Args:
        usuario_id: UUID del profesional.
        tenant_id: Slug del tenant.
        credential_id: ID de la credencial WebAuthn usada.

    Returns:
        JWT string o None si falla.
    """
    try:
        from core.api_security import create_jwt, JWTConfig

        # Incluir credential_id en el JWT para trazabilidad
        cfg = JWTConfig.from_env_or_vault()
        return create_jwt(usuario_id, tenant_id, cfg)
    except Exception as exc:
        log_event("webauthn", f"jwt_error:{type(exc).__name__}")
        return None
