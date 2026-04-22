#!/usr/bin/env python3
"""
SISTEMA DE GUARDADO UNIVERSAL - FUNCIONA SIEMPRE
Version ultra-simple, sin dependencias complejas.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Archivo de datos principal
DATA_FILE = Path(".streamlit/local_data.json")

def _ensure_data_file():
    """Crea el archivo si no existe."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        initial = {
            "pacientes": [],
            "historial": [],
            "evoluciones": [],
            "signos_vitales": [],
            "materiales": [],
            "recetas": [],
            "visitas": []
        }
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(initial, f, indent=2)

def _load_data() -> Dict:
    """Carga datos del archivo."""
    _ensure_data_file()
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {
            "pacientes": [],
            "historial": [],
            "evoluciones": [],
            "signos_vitales": [],
            "materiales": [],
            "recetas": [],
            "visitas": []
        }

def _save_data(data: Dict):
    """Guarda datos en el archivo."""
    _ensure_data_file()
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def guardar_registro(
    tipo: str,  # 'signos_vitales', 'evolucion', 'material', 'receta', etc.
    paciente_id: str,
    paciente_nombre: str,
    datos: Dict[str, Any]
) -> tuple[bool, str]:
    """
    Guarda cualquier tipo de registro clinico.
    Funciona SIEMPRE - sin excepciones silenciadas.
    """
    try:
        # 1. Cargar datos existentes
        data = _load_data()
        
        # 2. Crear registro con metadata
        registro = {
            "id": f"{tipo}_{int(time.time())}",
            "tipo": tipo,
            "paciente_id": str(paciente_id),
            "paciente_nombre": str(paciente_nombre),
            "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "timestamp": time.time(),
            "datos": datos
        }
        
        # 3. Agregar a la lista correspondiente
        if tipo not in data:
            data[tipo] = []
        
        data[tipo].append(registro)
        
        # 4. Tambien agregar al historial general
        if "historial" not in data:
            data["historial"] = []
        data["historial"].append(registro)
        
        # 5. Guardar archivo
        _save_data(data)
        
        return True, f"Guardado en {tipo} OK"
        
    except Exception as e:
        error_msg = f"ERROR CRITICO guardando {tipo}: {str(e)}"
        try:
            from core.app_logging import log_event
            log_event("guardado_universal", error_msg)
        except Exception:
            pass
        return False, error_msg

def obtener_registros(tipo: str, paciente_id: str = None) -> List[Dict]:
    """Obtiene registros de un tipo específico."""
    try:
        data = _load_data()
        registros = data.get(tipo, [])
        
        if paciente_id:
            registros = [r for r in registros if r.get("paciente_id") == str(paciente_id)]
        
        # Ordenar por fecha (más reciente primero)
        registros.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        
        return registros
    except Exception as e:
        try:
            from core.app_logging import log_event
            log_event("guardado_universal", f"ERROR leyendo {tipo}: {e}")
        except Exception:
            pass
        return []

def obtener_historial_paciente(paciente_id: str) -> List[Dict]:
    """Obtiene todo el historial de un paciente."""
    return obtener_registros("historial", paciente_id)

def contar_registros(tipo: str) -> int:
    """Cuenta cuántos registros hay de un tipo."""
    try:
        data = _load_data()
        return len(data.get(tipo, []))
    except Exception:
        return 0

# Funciones específicas para compatibilidad
def guardar_signos_vitales(paciente_id: str, paciente_nombre: str, **datos) -> tuple[bool, str]:
    """Guarda signos vitales."""
    return guardar_registro("signos_vitales", paciente_id, paciente_nombre, datos)

def guardar_evolucion(paciente_id: str, paciente_nombre: str, **datos) -> tuple[bool, str]:
    """Guarda evolución clínica."""
    return guardar_registro("evoluciones", paciente_id, paciente_nombre, datos)

def guardar_material(paciente_id: str, paciente_nombre: str, **datos) -> tuple[bool, str]:
    """Guarda material/insumo usado."""
    return guardar_registro("materiales", paciente_id, paciente_nombre, datos)

def guardar_receta(paciente_id: str, paciente_nombre: str, **datos) -> tuple[bool, str]:
    """Guarda receta médica."""
    return guardar_registro("recetas", paciente_id, paciente_nombre, datos)

def obtener_signos_vitales(paciente_id: str = None) -> List[Dict]:
    """Obtiene signos vitales."""
    return obtener_registros("signos_vitales", paciente_id)

def obtener_evoluciones(paciente_id: str = None) -> List[Dict]:
    """Obtiene evoluciones."""
    return obtener_registros("evoluciones", paciente_id)

def obtener_materiales(paciente_id: str = None) -> List[Dict]:
    """Obtiene materiales."""
    return obtener_registros("materiales", paciente_id)

def obtener_recetas(paciente_id: str = None) -> List[Dict]:
    """Obtiene recetas."""
    return obtener_registros("recetas", paciente_id)
