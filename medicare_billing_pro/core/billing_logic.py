"""Reglas contables compartidas para Billing Pro."""
from __future__ import annotations

from typing import Any, Dict, List


COBROS_VALIDOS = {"cobrado", "parcial"}
PREFACTURAS_PENDIENTES = {"pendiente", "parcial"}


def money(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def estado_normalizado(value: Any) -> str:
    return str(value or "").strip().lower()


def cobros_validos(cobros: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [c for c in cobros if estado_normalizado(c.get("estado", "Cobrado")) in COBROS_VALIDOS]


def total_cobrado_prefactura(prefactura_id: str, cobros: List[Dict[str, Any]]) -> float:
    if not prefactura_id:
        return 0.0
    return sum(
        money(c.get("monto"))
        for c in cobros_validos(cobros)
        if str(c.get("prefactura_id", "")) == str(prefactura_id)
    )


def saldo_prefactura(prefactura: Dict[str, Any], cobros: List[Dict[str, Any]]) -> float:
    total = money(prefactura.get("total"))
    cobrado = total_cobrado_prefactura(str(prefactura.get("id", "")), cobros)
    return max(total - cobrado, 0.0)


def estado_prefactura_por_saldo(prefactura: Dict[str, Any], cobros: List[Dict[str, Any]]) -> str:
    estado_actual = estado_normalizado(prefactura.get("estado"))
    if estado_actual == "anulada":
        return "Anulada"
    total = money(prefactura.get("total"))
    cobrado = total_cobrado_prefactura(str(prefactura.get("id", "")), cobros)
    if total <= 0:
        return "Pendiente"
    if cobrado <= 0:
        return "Pendiente"
    if cobrado + 0.01 >= total:
        return "Cobrada"
    return "Parcial"


def enriquecer_prefacturas_con_saldo(
    prefacturas: List[Dict[str, Any]], cobros: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for prefactura in prefacturas:
        row = dict(prefactura)
        cobrado = total_cobrado_prefactura(str(row.get("id", "")), cobros)
        total = money(row.get("total"))
        row["cobrado"] = cobrado
        row["saldo"] = max(total - cobrado, 0.0)
        row["estado_calculado"] = estado_prefactura_por_saldo(row, cobros)
        enriched.append(row)
    return enriched


def prefacturas_con_saldo(prefacturas: List[Dict[str, Any]], cobros: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        p
        for p in enriquecer_prefacturas_con_saldo(prefacturas, cobros)
        if estado_normalizado(p.get("estado_calculado")) in PREFACTURAS_PENDIENTES and money(p.get("saldo")) > 0
    ]


def total_saldo_prefacturas(prefacturas: List[Dict[str, Any]], cobros: List[Dict[str, Any]]) -> float:
    return sum(money(p.get("saldo")) for p in prefacturas_con_saldo(prefacturas, cobros))
