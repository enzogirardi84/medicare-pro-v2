"""Helpers de datos, búsqueda y utilidades para el módulo Historial.

Extraído de views/historial.py.
"""
import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from features.historial.fechas import parse_registro_fecha_hora

LIMITES_REGISTROS = {
    "Últimos 10 registros": 10,
    "Últimos 30 registros": 30,
    "Últimos 50 registros": 50,
    "Últimos 100 registros": 100,
    "Modo liviano (200 máx)": 200,
}

HISTORIAL_PANEL_SCROLL_PX = 680

SECCIONES_TABLA = {
    "Auditoria de Presencia",
    "Visitas y Agenda",
    "Emergencias y Ambulancia",
    "Enfermeria y Plan de Cuidados",
    "Escalas Clinicas",
    "Auditoria Legal",
    "Procedimientos y Evoluciones",
    "Materiales Utilizados",
    "Signos Vitales",
    "Control Percentilo",
    "Balance Hidrico",
}

COLUMNAS_EXCLUIDAS_TABLA = ["paciente", "empresa", "imagen", "base64_foto", "firma_b64", "firma_img"]

CLAVES_EXCLUIDAS_GENERICAS = {
    "paciente", "empresa", "fecha", "firma", "firmado_por", "firma_b64",
    "adjunto_papel_b64", "adjunto_papel_tipo", "adjunto_papel_nombre",
    "_id_local", "_fecha_dt", "estado_calc",
}


def _resumen_linea_tiempo(seccion: str, reg: Dict[str, Any]) -> str:
    if seccion == "Signos Vitales":
        return f"TA {reg.get('TA', '-')} | FC {reg.get('FC', '-')} | Sat {reg.get('Sat', '-')}%"
    if seccion == "Visitas y Agenda":
        return f"{reg.get('profesional', '-')} | {reg.get('estado', '-')}"
    if seccion == "Balance Hidrico":
        return f"In {reg.get('ingresos', '-')} | Eg {reg.get('egresos', '-')} | Bal {reg.get('balance', '-')}"
    if seccion == "Emergencias y Ambulancia":
        return f"{reg.get('categoria_evento', reg.get('tipo', '-'))} → {reg.get('destino', '-')}"[:120]
    if seccion == "Procedimientos y Evoluciones":
        txt = str(
            reg.get("nota") or reg.get("intervencion") or reg.get("descripcion")
            or reg.get("texto") or reg.get("detalle") or ""
        )[:140]
        return txt or (reg.get("tipo") or "Evolución")
    if seccion == "Estudios Complementarios":
        return f"{reg.get('tipo', '-')} — {str(reg.get('detalle', ''))[:100]}"
    if seccion == "Plan Terapeutico":
        return f"{reg.get('med', '-')} {reg.get('dosis', '')}"[:120]
    if seccion == "Materiales Utilizados":
        return f"{reg.get('material', reg.get('item', '-'))} x{reg.get('cantidad', '')}"
    piezas = [
        str(reg.get("tipo", "")), str(reg.get("profesional", "")), str(reg.get("titulo", "")),
        str(reg.get("nota", ""))[:80], str(reg.get("intervencion", ""))[:80],
        str(reg.get("descripcion", ""))[:80], str(reg.get("detalle", ""))[:80],
    ]
    t = " | ".join(p for p in piezas if p and p != "None")
    return (t[:160] if t else seccion)[:180]


@st.cache_data(show_spinner=False)
def _actividad_reciente_filas(
    secciones: Dict[str, List[Dict[str, Any]]], limite: int
) -> List[Dict[str, str]]:
    filas: List[Tuple[datetime, str, str, str]] = []
    for nombre_sec, regs in secciones.items():
        for reg in regs:
            dt = parse_registro_fecha_hora(reg)
            if not dt:
                continue
            filas.append((dt, nombre_sec, dt.strftime("%d/%m/%Y %H:%M"), _resumen_linea_tiempo(nombre_sec, reg)))
    filas.sort(key=lambda x: x[0], reverse=True)
    return [{"Fecha": f_str, "Sección": sec, "Resumen": res} for _, sec, f_str, res in filas[:limite]]


def _ultimo_evento_global(secciones: Dict[str, List[Dict[str, Any]]]) -> Optional[datetime]:
    ultimo: Optional[datetime] = None
    for regs in secciones.values():
        for reg in regs:
            dt = parse_registro_fecha_hora(reg)
            if dt and (ultimo is None or dt > ultimo):
                ultimo = dt
    return ultimo


def _resumen_ejecutivo_secciones(secciones: Dict[str, List[Dict[str, Any]]]) -> pd.DataFrame:
    filas = []
    for nombre, regs in sorted(secciones.items(), key=lambda x: -len(x[1])):
        if not regs:
            continue
        ultimo_dt: Optional[datetime] = None
        for reg in regs:
            dt = parse_registro_fecha_hora(reg)
            if dt and (ultimo_dt is None or dt > ultimo_dt):
                ultimo_dt = dt
        filas.append({
            "Sección": nombre,
            "Registros": len(regs),
            "Último evento": ultimo_dt.strftime("%d/%m/%Y %H:%M") if ultimo_dt else "S/D",
        })
    return pd.DataFrame(filas)


def _registro_coincide_busqueda(registro: Dict[str, Any], query: str) -> bool:
    q = query.strip().lower()
    if not q:
        return True
    for v in registro.values():
        if v is None:
            continue
        if q in str(v).lower():
            return True
    return False


@st.cache_data(show_spinner=False)
def _busqueda_global_resultados(
    secciones: Dict[str, List[Dict[str, Any]]],
    query: str,
    limite: int,
) -> List[Dict[str, Any]]:
    q = query.strip()
    if not q:
        return []
    out: List[Dict[str, Any]] = []
    for sec, regs in secciones.items():
        for reg in regs:
            if not _registro_coincide_busqueda(reg, q):
                continue
            dt = parse_registro_fecha_hora(reg)
            fe = dt.strftime("%d/%m/%Y %H:%M") if dt else "S/D"
            out.append({"seccion": sec, "fecha": fe, "resumen": _resumen_linea_tiempo(sec, reg)[:220]})
            if len(out) >= limite:
                return out
    return out


def _dataframe_seccion_a_csv(registros: List[Dict[str, Any]]) -> Optional[bytes]:
    if not registros:
        return None
    drop_csv = {"imagen", "base64_foto", "firma_b64", "adjunto_papel_b64", "firma_img"}
    try:
        df = pd.DataFrame(registros)
        df = df.drop(columns=["paciente", "empresa"], errors="ignore")
        df = df.drop(columns=[c for c in drop_csv if c in df.columns], errors="ignore")
        return df.to_csv(index=False).encode("utf-8-sig")
    except Exception:
        return None


def _nombre_archivo_seguro(texto: str, max_len: int = 50) -> str:
    t = re.sub(r"[^\w\-]+", "_", str(texto or "").strip(), flags=re.UNICODE)
    return (t or "archivo")[:max_len]


def _fecha_en_rango_tl(fecha_str: str, desde, hasta) -> bool:
    if fecha_str == "S/D":
        return True
    try:
        dt = datetime.strptime(fecha_str, "%d/%m/%Y %H:%M")
        return desde <= dt.date() <= hasta
    except Exception:
        return True
