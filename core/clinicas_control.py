"""Registro logico de clinicas (empresas): alta/suspension y bloqueo de acceso para usuarios dependientes."""

from __future__ import annotations

from typing import Any, Dict, Optional

import streamlit as st

from core.norm_empresa import norm_empresa_key
from core.utils import ahora, mapa_detalles_pacientes


def _registro_default(nombre_display: str) -> Dict[str, Any]:
    return {
        "nombre_display": str(nombre_display or "").strip(),
        "estado": "Activa",
        "motivo_baja": "",
        "actualizado_en": "",
    }


def obtener_registro_clinica(session_state: dict, empresa: str) -> Optional[Dict[str, Any]]:
    db = session_state.get("clinicas_db") or {}
    if not isinstance(db, dict):
        return None
    return db.get(norm_empresa_key(empresa))


def clinica_suspendida(session_state: dict, empresa: str) -> bool:
    reg = obtener_registro_clinica(session_state, empresa)
    if not reg:
        return False
    return str(reg.get("estado", "Activa")).strip().lower() == "suspendida"


def rol_bypass_suspend_clinica(rol: Optional[str]) -> bool:
    return str(rol or "").strip().lower() in {"superadmin", "admin"}


def login_bloqueado_por_clinica(user_data: dict, session_state: Optional[dict] = None) -> bool:
    """True si el usuario no puede entrar porque su clinica esta suspendida."""
    if not isinstance(user_data, dict):
        return False
    if rol_bypass_suspend_clinica(user_data.get("rol")):
        return False
    ss = session_state if session_state is not None else st.session_state
    empresa = str(user_data.get("empresa", "") or "").strip()
    if not empresa:
        return False
    return clinica_suspendida(ss, empresa)


def sincronizar_clinicas_desde_datos(session_state: dict) -> None:
    """Asegura una ficha por cada empresa vista en usuarios o pacientes; nuevas quedan Activas."""
    session_state.setdefault("clinicas_db", {})
    db = session_state["clinicas_db"]
    if not isinstance(db, dict):
        session_state["clinicas_db"] = {}
        db = session_state["clinicas_db"]

    vistos = set()

    for u in (session_state.get("usuarios_db") or {}).values():
        if not isinstance(u, dict):
            continue
        emp = str(u.get("empresa", "") or "").strip()
        if not emp:
            continue
        k = norm_empresa_key(emp)
        vistos.add(k)
        if k not in db:
            db[k] = _registro_default(emp)

    for det in mapa_detalles_pacientes(session_state).values():
        emp = str(det.get("empresa", "") or "").strip()
        if not emp:
            continue
        k = norm_empresa_key(emp)
        if k not in db:
            db[k] = _registro_default(emp)

    for k, reg in list(db.items()):
        if not isinstance(reg, dict):
            continue
        if not str(reg.get("nombre_display", "")).strip() and k in vistos:
            reg["nombre_display"] = k


def suspender_clinica(session_state: dict, key_norm: str, motivo: str = "") -> None:
    session_state.setdefault("clinicas_db", {})
    db = session_state["clinicas_db"]
    if key_norm not in db:
        db[key_norm] = _registro_default(key_norm)
    db[key_norm]["estado"] = "Suspendida"
    db[key_norm]["motivo_baja"] = str(motivo or "").strip()
    db[key_norm]["actualizado_en"] = ahora().strftime("%d/%m/%Y %H:%M:%S")


def reactivar_clinica(session_state: dict, key_norm: str) -> None:
    session_state.setdefault("clinicas_db", {})
    db = session_state["clinicas_db"]
    if key_norm not in db:
        db[key_norm] = _registro_default(key_norm)
    db[key_norm]["estado"] = "Activa"
    db[key_norm]["motivo_baja"] = ""
    db[key_norm]["actualizado_en"] = ahora().strftime("%d/%m/%Y %H:%M:%S")


def contar_usuarios_por_clinica(session_state: dict) -> Dict[str, Dict[str, Any]]:
    """Devuelve mapa norm_key -> {total, coordinadores, operativos, administrativos, logins: [...]}."""
    out: Dict[str, Dict[str, Any]] = {}
    for login, u in (session_state.get("usuarios_db") or {}).items():
        if not isinstance(u, dict):
            continue
        if str(login).strip().lower() == "admin":
            continue
        rol = str(u.get("rol", "") or "").strip().lower()
        if rol in {"superadmin", "admin"}:
            continue
        emp = str(u.get("empresa", "") or "").strip()
        if not emp:
            continue
        k = norm_empresa_key(emp)
        if k not in out:
            out[k] = {
                "total": 0,
                "coordinadores": 0,
                "operativos": 0,
                "administrativos": 0,
                "logins": [],
            }
        bucket = out[k]
        bucket["total"] += 1
        bucket["logins"].append(str(login))
        if rol == "coordinador":
            bucket["coordinadores"] += 1
        elif rol == "administrativo":
            bucket["administrativos"] += 1
        elif rol in {"operativo", "medico", "enfermeria", "auditoria"}:
            bucket["operativos"] += 1
        else:
            bucket["operativos"] += 1
    return out
