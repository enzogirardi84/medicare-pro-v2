"""Repositorio de datos clinicos — evoluciones, vitales, estudios, recetas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

from core._db_sql_clinico import (
    get_evoluciones_by_paciente as _get_evoluciones,
    insert_evolucion as _insert_evolucion,
    get_indicaciones_activas as _get_indicaciones,
    insert_indicacion as _insert_indicacion,
    get_estudios_by_paciente as _get_estudios,
    insert_estudio as _insert_estudio,
    get_signos_vitales as _get_vitales,
    insert_signo_vital as _insert_vital,
    get_consentimientos_by_paciente as _get_consentimientos,
    insert_consentimiento as _insert_consentimiento,
    get_escalas_by_paciente as _get_escalas,
    insert_escala as _insert_escala,
)


@st.cache_data(ttl=60, show_spinner=False)
def get_evoluciones(paciente_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    return _get_evoluciones(paciente_id, limit)


def crear_evolucion(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    r = _insert_evolucion(datos)
    if r:
        get_evoluciones.clear()
    return r


@st.cache_data(ttl=60, show_spinner=False)
def get_indicaciones(paciente_id: str) -> List[Dict[str, Any]]:
    return _get_indicaciones(paciente_id)


def crear_indicacion(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    r = _insert_indicacion(datos)
    if r:
        get_indicaciones.clear()
    return r


@st.cache_data(ttl=60, show_spinner=False)
def get_estudios(paciente_id: str) -> List[Dict[str, Any]]:
    return _get_estudios(paciente_id)


def crear_estudio(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    r = _insert_estudio(datos)
    if r:
        get_estudios.clear()
    return r


@st.cache_data(ttl=60, show_spinner=False)
def get_vitales(paciente_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    return _get_vitales(paciente_id, limit)


def crear_vital(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    r = _insert_vital(datos)
    if r:
        get_vitales.clear()
    return r


@st.cache_data(ttl=60, show_spinner=False)
def get_consentimientos(paciente_id: str) -> List[Dict[str, Any]]:
    return _get_consentimientos(paciente_id)


def crear_consentimiento(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    r = _insert_consentimiento(datos)
    if r:
        get_consentimientos.clear()
    return r


@st.cache_data(ttl=60, show_spinner=False)
def get_escalas(paciente_id: str) -> List[Dict[str, Any]]:
    return _get_escalas(paciente_id)


def crear_escala(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    r = _insert_escala(datos)
    if r:
        get_escalas.clear()
    return r
