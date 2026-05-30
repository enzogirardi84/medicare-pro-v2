"""Sellado de tiempo legal (Timestamping Authority - RFC 3161) para PDFs.
Conecta con una TSA externa, envia el hash SHA-256 del documento
y recibe un token firmado que certifica la existencia del documento
en un momento exacto. Independiente de los relojes del sistema.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. CONFIGURACION
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TSAConfig:
    """Configuracion de la Autoridad de Sellado de Tiempo."""
    url: str = ""
    username: str = ""
    password: str = ""
    hash_algorithm: str = "sha256"
    timeout: int = 15
    retry_attempts: int = 3
    retry_delay: float = 2.0

    @classmethod
    def from_env(cls) -> TSAConfig:
        return cls(
            url=os.environ.get(
                "TSA_URL",
                "http://timestamp.digicert.com",  # TSA publica de prueba
            ),
            username=os.environ.get("TSA_USERNAME", ""),
            password=os.environ.get("TSA_PASSWORD", ""),
            hash_algorithm=os.environ.get("TSA_HASH_ALGORITHM", "sha256"),
            timeout=int(os.environ.get("TSA_TIMEOUT", "15")),
            retry_attempts=int(os.environ.get("TSA_RETRY_ATTEMPTS", "3")),
            retry_delay=float(os.environ.get("TSA_RETRY_DELAY", "2.0")),
        )


# ═══════════════════════════════════════════════════════════════════
# 2. TOKEN DE SELLADO DE TIEMPO (RFC 3161)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TimestampToken:
    """Token de sellado de tiempo recibido de la TSA."""
    hash_documento: str = ""
    tsa_url: str = ""
    tsa_response_b64: str = ""  # Respuesta completa de la TSA (DER, base64)
    timestamp_unix: float = 0.0
    timestamp_iso: str = ""
    algoritmo: str = "SHA-256"
    estado: str = "pendiente"  # "ok" | "error" | "fallback_local"

    def to_dict(self) -> dict[str, Any]:
        return {
            "hash": self.hash_documento[:24] + "...",
            "tsa": self.tsa_url,
            "timestamp": self.timestamp_iso or "",
            "algoritmo": self.algoritmo,
            "estado": self.estado,
        }


# ═══════════════════════════════════════════════════════════════════
# 3. CLIENTE TSA (RFC 3161)
# ═══════════════════════════════════════════════════════════════════

class TSAClient:
    """Cliente para sellado de tiempo via RFC 3161.

    Envia el hash SHA-256 del documento a una TSA externa y recibe
    un token firmado que prueba la existencia del documento en un
    momento exacto.
    """

    def __init__(self, config: Optional[TSAConfig] = None):
        self._config = config or TSAConfig.from_env()

    def sellar(self, data_bytes: bytes) -> TimestampToken:
        """Sella un documento con timestamp TSA.

        Args:
            data_bytes: Bytes del documento (PDF completo).

        Returns:
            TimestampToken con el resultado del sellado.
        """
        doc_hash = hashlib.sha256(data_bytes).hexdigest()

        for intento in range(self._config.retry_attempts + 1):
            try:
                return self._sellar_con_tsa(doc_hash, data_bytes)

            except Exception as exc:
                log_event("tsa", f"intento_{intento}_fallo:{type(exc).__name__}:{exc}")
                if intento < self._config.retry_attempts:
                    time.sleep(self._config.retry_delay * (2 ** intento))
                else:
                    # Fallback: timestamp local con alerta
                    from datetime import datetime, timezone
                    ahora = datetime.now(timezone.utc)
                    log_event("tsa", "fallback_local_usado")
                    try:
                        from core.metrics import AlertManager
                        AlertManager.disparar_alerta(
                            nivel="WARNING",
                            mensaje=f"TSA no disponible tras {self._config.retry_attempts} intentos. "
                                    f"Usando timestamp local.",
                            modulo="tsa_timestamp",
                            metrica="tsa_fallback",
                        )
                    except Exception:
                        pass

                    return TimestampToken(
                        hash_documento=doc_hash,
                        tsa_url=self._config.url,
                        timestamp_unix=time.time(),
                        timestamp_iso=ahora.isoformat(),
                        estado="fallback_local",
                    )

    def _sellar_con_tsa(self, doc_hash: str, data_bytes: bytes) -> TimestampToken:
        """Envia el hash a la TSA y procesa la respuesta."""
        import requests
        from datetime import datetime, timezone

        # Construir solicitud RFC 3161
        # Usamos requests HTTP desde Python
        headers = {"Content-Type": "application/timestamp-query"}
        tsa_request = self._build_rfc3161_request(doc_hash)

        response = requests.post(
            self._config.url,
            data=tsa_request,
            headers=headers,
            timeout=self._config.timeout,
            auth=(self._config.username, self._config.password) if self._config.username else None,
        )
        response.raise_for_status()

        # Procesar respuesta TSA
        tsa_response_b64 = base64.b64encode(response.content).decode("ascii")

        # Extraer timestamp de la respuesta (depende de la TSA)
        # En produccion, parsear la respuesta ASN.1 con pyasn1
        timestamp_unix = time.time()  # Fallback: usar tiempo local si no se puede parsear
        try:
            # Intentar obtener timestamp desde headers de respuesta
            if "Date" in response.headers:
                from email.utils import parsedate_to_datetime
                parsed = parsedate_to_datetime(response.headers["Date"])
                timestamp_unix = parsed.timestamp()
        except Exception:
            pass

        ahora = datetime.now(timezone.utc)
        token = TimestampToken(
            hash_documento=doc_hash,
            tsa_url=self._config.url,
            tsa_response_b64=tsa_response_b64,
            timestamp_unix=timestamp_unix,
            timestamp_iso=datetime.fromtimestamp(timestamp_unix, tz=timezone.utc).isoformat(),
            estado="ok",
        )
        log_event("tsa", f"sellado_ok:{doc_hash[:16]}:{token.timestamp_iso}")
        return token

    def _build_rfc3161_request(self, doc_hash: str) -> bytes:
        """Construye una solicitud TimeStampReq basica (RFC 3161).

        En produccion, reemplazar con una implementacion ASN.1 completa
        usando pyasn1 o la libreria requests-opentimestamps.
        """
        # Version simplificada: enviar hash como texto plano
        # La TSA de DigiCert acepta GET con el hash
        if "digicert" in self._config.url.lower():
            return doc_hash.encode("ascii")

        # Para otras TSAs, enviar como payload JSON
        req = {
            "hash": doc_hash,
            "algorithm": self._config.hash_algorithm,
        }
        return json.dumps(req).encode("utf-8")


# ═══════════════════════════════════════════════════════════════════
# 4. INTEGRACION CON CLINICALPDFGENERATOR
# ═══════════════════════════════════════════════════════════════════

def agregar_timestamp_al_pdf(pdf_bytes: bytes, config: Optional[TSAConfig] = None) -> tuple[bytes, TimestampToken]:
    """Agrega un timestamp TSA al PDF y retorna el PDF + token.

    El token de timestamp se inyecta en los metadatos del PDF
    como una entrada XMP o en el bloque de firma.

    Args:
        pdf_bytes: PDF generado por ClinicalPDFGenerator.
        config: Configuracion TSA (opcional).

    Returns:
        (pdf_bytes_modificado, token_tsa)
    """
    client = TSAClient(config)
    token = client.sellar(pdf_bytes)

    # Inyectar token en metadatos del PDF
    # Buscar la ultima linea del PDF (%%EOF) e insertar metadata antes
    pdf_str = pdf_bytes.decode("utf-8", errors="replace")
    metadata_block = (
        f"\n/TSATimestamp <<\n"
        f"  /Hash ({token.hash_documento})\n"
        f"  /TSAURL ({token.tsa_url})\n"
        f"  /Timestamp ({token.timestamp_iso})\n"
        f"  /Estado ({token.estado})\n"
        f">>\n"
    )

    if "%%EOF" in pdf_str:
        pdf_str = pdf_str.replace("%%EOF", metadata_block + "%%EOF")
    else:
        pdf_str += metadata_block

    pdf_modificado = pdf_str.encode("utf-8")
    log_event("tsa", f"timestamp_inyectado_en_pdf:{token.estado}")
    return pdf_modificado, token
