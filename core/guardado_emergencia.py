"""
SISTEMA DE GUARDADO DE EMERGENCIA
Guarda datos localmente de forma segura mientras se arregla Supabase
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import streamlit as st


def guardar_signos_vitales_local(
    paciente_id: str,
    paciente_nombre: str,
    tension_arterial: str,
    frecuencia_cardiaca: int,
    frecuencia_respiratoria: int,
    temperatura: float,
    saturacion_oxigeno: int,
    glucemia: str,
    observaciones: str = ""
) -> tuple[bool, str]:
    """
    Guarda signos vitales en local_data.json (modo emergencia).
    Funciona sin internet, sin Supabase, inmediatamente.
    """
    
    try:
        local_file = Path(".streamlit/local_data.json")
        
        # Cargar datos existentes
        if local_file.exists():
            with open(local_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {
                "pacientes_db": [],
                "vitales_db": [],
                "evoluciones_db": [],
                "recetas_db": [],
                "usuarios_db": []
            }
        
        # Crear registro
        registro = {
            "id": f"sv_{int(time.time())}",
            "paciente_id": paciente_id,
            "paciente_nombre": paciente_nombre,
            "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "ta": tension_arterial,
            "fc": frecuencia_cardiaca,
            "fr": frecuencia_respiratoria,
            "temp": temperatura,
            "sat": saturacion_oxigeno,
            "hgt": glucemia,
            "observaciones": observaciones,
            "created_at": datetime.now().isoformat()
        }
        
        # Agregar a vitales_db
        if "vitales_db" not in data:
            data["vitales_db"] = []
        
        data["vitales_db"].append(registro)
        
        # Guardar archivo
        with open(local_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Crear backup de seguridad
        backup_file = Path(f".streamlit/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return True, f"Signos vitales guardados localmente (backup: {backup_file.name})"
        
    except Exception as e:
        return False, f"Error guardando localmente: {e}"


def guardar_evolucion_local(
    paciente_id: str,
    paciente_nombre: str,
    evolucion: str,
    indicaciones: str = ""
) -> tuple[bool, str]:
    """Guarda evolución en local_data.json."""
    
    try:
        local_file = Path(".streamlit/local_data.json")
        
        if local_file.exists():
            with open(local_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {
                "pacientes_db": [],
                "vitales_db": [],
                "evoluciones_db": [],
                "recetas_db": [],
                "usuarios_db": []
            }
        
        registro = {
            "id": f"ev_{int(time.time())}",
            "paciente_id": paciente_id,
            "paciente_nombre": paciente_nombre,
            "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "evolucion": evolucion,
            "indicaciones": indicaciones,
            "created_at": datetime.now().isoformat()
        }
        
        if "evoluciones_db" not in data:
            data["evoluciones_db"] = []
        
        data["evoluciones_db"].append(registro)
        
        with open(local_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return True, "Evolucion guardada localmente"
        
    except Exception as e:
        return False, f"Error: {e}"


def obtener_signos_vitales_local(paciente_id: str) -> List[Dict]:
    """Obtiene signos vitales del archivo local."""
    
    try:
        local_file = Path(".streamlit/local_data.json")
        
        if not local_file.exists():
            return []
        
        with open(local_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        vitales = data.get("vitales_db", [])
        
        # Filtrar por paciente
        return [v for v in vitales if v.get("paciente_id") == paciente_id or v.get("dni") == paciente_id]
        
    except Exception as e:
        print(f"Error leyendo local: {e}")
        return []


def obtener_evoluciones_local(paciente_id: str) -> List[Dict]:
    """Obtiene evoluciones del archivo local."""
    
    try:
        local_file = Path(".streamlit/local_data.json")
        
        if not local_file.exists():
            return []
        
        with open(local_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        evoluciones = data.get("evoluciones_db", [])
        
        return [e for e in evoluciones if e.get("paciente_id") == paciente_id or e.get("dni") == paciente_id]
        
    except Exception as e:
        print(f"Error leyendo local: {e}")
        return []
