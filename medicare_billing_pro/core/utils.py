"""Utilidades generales para Medicare Billing Pro."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import streamlit as st


def generar_id() -> str:
    return uuid.uuid4().hex[:12]


def hoy() -> date:
    return date.today()


def ahora() -> datetime:
    return datetime.now()


def fmt_moneda(monto: float) -> str:
    return f"${monto:,.2f}"


def fmt_fecha(fecha_str: str) -> str:
    if not fecha_str:
        return "—"
    try:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(str(fecha_str)[:10], fmt).strftime("%d/%m/%Y")
            except ValueError:
                continue
        return str(fecha_str)[:10]
    except Exception:
        return str(fecha_str)[:10]


def safe_text(text: str) -> str:
    """Reemplaza caracteres no-latin1 por equivalentes seguros."""
    if not text:
        return ""
    replacements = {
        "ñ": "n", "Ñ": "N", "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "ü": "u", "Ü": "U",
        "€": "EUR", "–": "-", "—": "-", "\u201c": '"', "\u201d": '"',
        "\u2018": "'", "\u2019": "'",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def sanitize_filename(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in " _-.").strip()[:80]


def seleccionar_limite_registros(label: str, total: int, default: int = 50) -> int:
    return st.selectbox(
        label,
        options=[10, 25, 50, 100, 200, 500],
        index=2 if default == 50 else 0,
        key=f"limite_{label.replace(' ', '_')}"
    )


def bloque_estado_vacio(titulo: str, mensaje: str, sugerencia: str = "") -> None:
    st.info(f"**{titulo}**\n\n{mensaje}" + (f"\n\n💡 {sugerencia}" if sugerencia else ""))


def calcular_total(items: List[Dict], campo: str = "monto") -> float:
    return sum(float(item.get(campo, 0) or 0) for item in items)


def agrupar_por_mes(items: List[Dict], fecha_campo: str = "fecha") -> Dict[str, List[Dict]]:
    grupos: Dict[str, List[Dict]] = {}
    for item in items:
        fecha = item.get(fecha_campo, "")
        if fecha:
            clave = str(fecha)[:7]
            grupos.setdefault(clave, []).append(item)
    return dict(sorted(grupos.items(), reverse=True))
