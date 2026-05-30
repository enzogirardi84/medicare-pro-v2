"""Bring Your Own Key (BYOK) para clientes corporativos.
Permite que clientes como prepagas usen su propia clave KMS en AWS.
Soporta cripto-borrado remoto: si el cliente deshabilita su clave
desde su panel de AWS, los datos se vuelven ilegibles instantaneamente.
"""
from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import streamlit as st

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. CONFIGURACION BYOK POR TENANT
# ═══════════════════════════════════════════════════════════════════

@dataclass
class BYOKConfig:
    """Configuracion BYOK para un tenant corporativo."""
    tenant_id: str
    kms_key_arn: str = ""  # ARN de la KMS en cuenta del cliente
    kms_region: str = "us-east-1"
    cross_account_role_arn: str = ""  # Rol IAM para acceso condicional
    habilitado: bool = False
    ultima_verificacion: float = 0.0
    clave_valida: bool = False
    modo_crypto_borrado: bool = False

    @classmethod
    def from_env(cls, tenant_id: str) -> BYOKConfig:
        prefix = tenant_id.upper().replace("-", "_")
        return cls(
            tenant_id=tenant_id,
            kms_key_arn=os.environ.get(f"{prefix}_KMS_KEY_ARN", ""),
            kms_region=os.environ.get(f"{prefix}_KMS_REGION", "us-east-1"),
            cross_account_role_arn=os.environ.get(f"{prefix}_KMS_ROLE_ARN", ""),
            habilitado=bool(os.environ.get(f"{prefix}_KMS_KEY_ARN", "")),
        )


# ═══════════════════════════════════════════════════════════════════
# 2. MANAGER BYOK
# ═══════════════════════════════════════════════════════════════════

class BYOKManager:
    """Gestiona claves KMS externas de clientes corporativos.

    BYOK (Bring Your Own Key):
    - El cliente nos proporciona un ARN de su KMS
    - Nosotros asumimos un rol IAM para usar la clave
    - Si el cliente revoca el permiso, los datos se vuelven ilegibles

    Crypto-borrado remoto:
    - Verificamos periodicamente que la clave siga accesible
    - Si la clave no responde, activamos modo de emergencia
    - Los datos cifrados con esa clave no pueden desencriptarse
    """

    BYOK_CONFIG_KEY = "_byok_config"
    VERIFY_INTERVAL = 300  # 5 minutos entre verificaciones

    def __init__(self, tenant_id: str):
        self._tenant_id = tenant_id
        self._config = self._load_config()
        self._kms_client = None
        self._sts_client = None

    def _load_config(self) -> BYOKConfig:
        """Carga configuracion BYOK desde session_state o env."""
        import streamlit as st
        config = st.session_state.get(f"{self.BYOK_CONFIG_KEY}_{self._tenant_id}")
        if config:
            return config
        # Cargar desde variables de entorno
        env_config = BYOKConfig.from_env(self._tenant_id)
        if env_config.habilitado:
            st.session_state[f"{self.BYOK_CONFIG_KEY}_{self._tenant_id}"] = env_config
        return env_config

    def _save_config(self) -> None:
        st.session_state[f"{self.BYOK_CONFIG_KEY}_{self._tenant_id}"] = self._config

    def _init_clients(self) -> bool:
        """Inicializa clientes AWS STS + KMS con asuncion de rol."""
        try:
            import boto3

            if self._config.cross_account_role_arn:
                # Asumir rol cross-account
                sts = boto3.client("sts")
                response = sts.assume_role(
                    RoleArn=self._config.cross_account_role_arn,
                    RoleSessionName=f"medicare-byok-{self._tenant_id}",
                    DurationSeconds=3600,
                )
                creds = response["Credentials"]
                self._kms_client = boto3.client(
                    "kms",
                    region_name=self._config.kms_region,
                    aws_access_key_id=creds["AccessKeyId"],
                    aws_secret_access_key=creds["SecretAccessKey"],
                    aws_session_token=creds["SessionToken"],
                )
            else:
                # Acceso directo (misma cuenta)
                self._kms_client = boto3.client(
                    "kms", region_name=self._config.kms_region
                )
            return True
        except Exception as exc:
            log_event("byok", f"init_clients_error:{type(exc).__name__}:{exc}")
            return False

    # ── Verificacion de clave ─────────────────────────────────

    def verificar_clave(self) -> bool:
        """Verifica que la KMS del cliente siga accesible y habilitada.

        Returns:
            True si la clave esta disponible, False si fue revocada/deshabilitada.
        """
        if not self._config.habilitado or not self._config.kms_key_arn:
            return True  # No usa BYOK

        ahora = time.time()
        if ahora - self._config.ultima_verificacion < self.VERIFY_INTERVAL:
            return self._config.clave_valida

        self._config.ultima_verificacion = ahora

        if not self._init_clients():
            self._config.clave_valida = False
            self._config.modo_crypto_borrado = True
            self._save_config()
            return False

        try:
            response = self._kms_client.describe_key(KeyId=self._config.kms_key_arn)
            key_state = response["KeyMetadata"]["KeyState"]

            if key_state == "Enabled":
                self._config.clave_valida = True
                self._config.modo_crypto_borrado = False
                log_event("byok", f"clave_verificada_ok:{self._tenant_id}")
            elif key_state == "Disabled":
                # CRYPTO-BORRADO: el cliente deshabilito su clave
                self._config.clave_valida = False
                self._config.modo_crypto_borrado = True
                log_event("byok", f"CRYPTO_BORRADO:{self._tenant_id}:clave_deshabilitada")
                self._alertar_crypto_borrado()
            elif key_state == "PendingDeletion":
                self._config.clave_valida = False
                self._config.modo_crypto_borrado = True
                log_event("byok", f"CRYPTO_BORRADO:{self._tenant_id}:clave_eliminada")
                self._alertar_crypto_borrado()
            else:
                self._config.clave_valida = False
                log_event("byok", f"clave_estado_desconocido:{key_state}")

        except Exception as exc:
            # Error de conexion = posible revocacion de permisos
            self._config.clave_valida = False
            self._config.modo_crypto_borrado = True
            log_event("byok", f"CRYPTO_BORRADO:{self._tenant_id}:{type(exc).__name__}")
            self._alertar_crypto_borrado()

        self._save_config()
        return self._config.clave_valida

    # ── Encriptacion/Desencriptacion con KMS externa ─────────

    def encriptar(self, plaintext: str, context: Optional[dict[str, str]] = None) -> Optional[str]:
        """Encripta datos usando la KMS del cliente.

        Args:
            plaintext: Texto a encriptar.
            context: Contexto de encriptacion (para binding de datos).

        Returns:
            Base64 del ciphertext, o None si fallo.
        """
        if not self.verificar_clave() or not self._kms_client:
            return None

        try:
            response = self._kms_client.encrypt(
                KeyId=self._config.kms_key_arn,
                Plaintext=plaintext.encode("utf-8"),
                EncryptionContext=context or {"tenant": self._tenant_id},
            )
            return base64.b64encode(response["CiphertextBlob"]).decode("ascii")
        except Exception as exc:
            log_event("byok", f"encriptar_error:{type(exc).__name__}:{exc}")
            return None

    def desencriptar(self, ciphertext_b64: str, context: Optional[dict[str, str]] = None) -> Optional[str]:
        """Desencripta datos usando la KMS del cliente.

        Returns:
            Texto plano, o None si no se puede desencriptar.
        """
        if not self.verificar_clave() or not self._kms_client:
            return None

        try:
            response = self._kms_client.decrypt(
                CiphertextBlob=base64.b64decode(ciphertext_b64),
                EncryptionContext=context or {"tenant": self._tenant_id},
            )
            return response["Plaintext"].decode("utf-8")
        except Exception as exc:
            log_event("byok", f"desencriptar_error:{type(exc).__name__}:{exc}")
            return None

    # ── Crypto-borrado remoto ────────────────────────────────

    def _alertar_crypto_borrado(self) -> None:
        """Dispara alerta CRITICAL cuando la clave del cliente deja de funcionar.

        Esto significa que los datos del tenant NO pueden desencriptarse.
        """
        try:
            from core.metrics import AlertManager
            AlertManager.disparar_alerta(
                nivel="CRITICAL",
                mensaje=(
                    f"CRYPTO-BORRADO REMOTO: El tenant {self._tenant_id} "
                    f"deshabilito su clave KMS. Los datos cifrados son "
                    f"ilegibles. Se requiere intervencion inmediata."
                ),
                modulo="byok_manager",
                metrica="crypto_borrado",
            )
        except Exception as exc:
            log_event("byok", f"alert_error:{type(exc).__name__}")

        # Registrar en audit trail
        try:
            from core.audit_trail_immutable import ImmutableAuditTrail
            auditor = ImmutableAuditTrail()
            auditor.registrar(
                usuario="__byok__",
                accion="CRYPTO_BORRADO",
                recurso=f"byok:{self._tenant_id}",
                detalle=f"Clave KMS del cliente {self._tenant_id} deshabilitada. Datos ilegibles.",
            )
        except Exception as exc:
            log_event("byok", f"audit_error:{type(exc).__name__}")

    # ── Estado BYOK para la UI ───────────────────────────────

    def render_status(self) -> None:
        """Muestra el estado BYOK en la UI del tenant."""
        if not self._config.habilitado:
            st.caption("Cifrado: Clave administrada por MediCare (KMS propia)")
            return

        if self._config.modo_crypto_borrado:
            st.error(
                "CRYPTO-BORRADO REMOTO ACTIVO. "
                "La clave KMS del cliente no esta accesible. "
                "Los datos cifrados no pueden desencriptarse."
            )
            return

        if self._config.clave_valida:
            st.success("BYOK activo. Clave KMS del cliente verificada.")
            st.caption(f"ARN: {self._config.kms_key_arn[:40]}...")
        else:
            st.warning("BYOK configurado pero no verificado.")
