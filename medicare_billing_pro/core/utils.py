"""Utilidades generales para Medicare Billing Pro."""
from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import date, datetime
from typing import Any, Dict, List

import streamlit as st


def generar_id() -> str:
    return uuid.uuid4().hex[:12]


def hoy() -> date:
    return date.today()


def ahora() -> datetime:
    return datetime.now()


def fmt_moneda(monto: float | int | str | None) -> str:
    try:
        value = float(monto or 0)
    except Exception:
        value = 0.0
    return f"${value:,.2f}"


def fmt_fecha(fecha_str: str) -> str:
    if not fecha_str:
        return "-"
    try:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(str(fecha_str)[:10], fmt).strftime("%d/%m/%Y")
            except ValueError:
                continue
        return str(fecha_str)[:10]
    except Exception:
        return str(fecha_str)[:10]


def safe_text(text: Any) -> str:
    """Convierte a texto compatible con PDF latin-1."""
    if text is None:
        return ""
    value = str(text)
    replacements = {
        "€": "EUR",
        "–": "-",
        "—": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "•": "-",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return unicodedata.normalize("NFKD", value).encode("latin-1", "ignore").decode("latin-1")


def sanitize_filename(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name or "archivo")).encode("ascii", "ignore").decode()
    text = re.sub(r"[^A-Za-z0-9 _.-]+", "", text).strip()
    return (text or "archivo")[:80]


def normalize_document(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z-]", "", str(value or "").strip())


def normalize_phone(value: str) -> str:
    return re.sub(r"[^0-9+() -]", "", str(value or "").strip())


def is_valid_email(value: str) -> bool:
    value = str(value or "").strip()
    if not value:
        return True
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value))


def bloque_estado_vacio(titulo: str, mensaje: str, sugerencia: str = "") -> None:
    st.info(f"**{titulo}**\n\n{mensaje}" + (f"\n\n{sugerencia}" if sugerencia else ""))


def mostrar_error_db(accion: str = "realizar la operacion") -> None:
    from core import db_sql

    detalle = db_sql.last_db_error or "Revisa la configuracion de Supabase."
    lower = detalle.lower()
    if "row-level security" in lower:
        st.error(
            f"No se pudo {accion}: Supabase bloqueo la operacion por RLS. "
            "Configura SUPABASE_SERVICE_ROLE_KEY en el servidor o ajusta las politicas de la tabla."
        )
    elif "could not find the table" in lower or "does not exist" in lower:
        st.error(
            f"No se pudo {accion}: faltan tablas de Billing Pro en Supabase. "
            "Ejecuta medicare_billing_pro/migracion_supabase.sql."
        )
    else:
        st.error(f"No se pudo {accion}. {detalle}")


def calcular_total(items: List[Dict], campo: str = "monto") -> float:
    total = 0.0
    for item in items:
        try:
            total += float(item.get(campo, 0) or 0)
        except Exception:
            continue
    return total


def agrupar_por_mes(items: List[Dict], fecha_campo: str = "fecha") -> Dict[str, List[Dict]]:
    grupos: Dict[str, List[Dict]] = {}
    for item in items:
        fecha = item.get(fecha_campo, "")
        if fecha:
            clave = str(fecha)[:7]
            grupos.setdefault(clave, []).append(item)
    return dict(sorted(grupos.items(), reverse=True))
