"""Repositorio de pacientes — queries a Supabase con RLS."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import streamlit as st

from core.app_logging import log_event
from services.telemetria_service import track_time
from core._db_sql_pacientes import (
    get_pacientes_by_empresa as _get_pacientes_by_empresa,
    get_pacientes_globales as _get_pacientes_globales,
    get_paciente_by_dni_empresa as _get_paciente_by_dni_empresa,
    insert_paciente as _insert_paciente,
    update_paciente as _update_paciente,
)


@st.cache_data(ttl=30, show_spinner=False)
def get_pacientes(empresa_id: str, limit: int = 100, solo_activos: bool = True) -> List[Dict[str, Any]]:
    """Obtiene pacientes de una empresa con cache cross-session."""
    return _get_pacientes_by_empresa(empresa_id, limit, solo_activos)


@st.cache_data(ttl=120, show_spinner=False)
def get_all_pacientes(limit: int = 500) -> List[Dict[str, Any]]:
    """Obtiene todos los pacientes (admin). Cache 120s."""
    return _get_pacientes_globales(limit)


@st.cache_data(ttl=60, show_spinner=False)
def get_paciente_by_dni(dni: str, empresa_id: str) -> Optional[Dict[str, Any]]:
    """Busca paciente por DNI en una empresa."""
    return _get_paciente_by_dni_empresa(dni, empresa_id)


def crear_paciente(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Crea un nuevo paciente. Invalida cache."""
    resultado = _insert_paciente(datos)
    if resultado:
        get_pacientes.clear()
    return resultado


def actualizar_paciente(paciente_id: str, datos: Dict[str, Any]) -> bool:
    """Actualiza datos de un paciente. Invalida cache."""
    resultado = _update_paciente(paciente_id, datos)
    if resultado:
        get_pacientes.clear()
        get_paciente_by_dni.clear()
    return resultado
