"""Servicio ARCA preparado para homologacion.

La emision real requiere CUIT, certificado, clave privada y alta del servicio
WSFEv1 en ARCA. Este modulo deja una interfaz estable para conectar el cliente
SOAP sin mezclar credenciales fiscales con la vista.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ArcaConfigStatus:
    listo: bool
    mensaje: str


def validar_configuracion_arca(config: Dict[str, Any]) -> ArcaConfigStatus:
    faltantes = []
    if not str(config.get("cuit", "")).strip():
        faltantes.append("CUIT emisor")
    if not int(config.get("punto_venta", 0) or 0):
        faltantes.append("punto de venta")
    if not bool(config.get("arca_certificado_configurado", False)):
        faltantes.append("certificado/clave privada")
    if faltantes:
        return ArcaConfigStatus(False, "Falta configurar: " + ", ".join(faltantes))
    return ArcaConfigStatus(True, "Configuracion lista para homologacion ARCA.")


def emitir_factura_homologacion(_factura: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    status = validar_configuracion_arca(config)
    if not status.listo:
        return {"ok": False, "mensaje": status.mensaje}
    return {
        "ok": False,
        "mensaje": "Cliente WSFEv1 pendiente de conectar. La factura quedo lista para homologacion.",
    }
