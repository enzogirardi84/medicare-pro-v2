#!/usr/bin/env python3
"""
Limpia pacientes duplicados después de la recuperación.
Convierte todos a formato consistente y elimina duplicados.
"""

import json
from pathlib import Path
from datetime import datetime


def parse_paciente_string(paciente_str):
    """Parsea un string de paciente en formato 'Nombre - DNI'."""
    if not isinstance(paciente_str, str):
        return None
    
    # Formato típico: "Juan Perez - 12345678"
    if ' - ' in paciente_str:
        parts = paciente_str.rsplit(' - ', 1)
        nombre = parts[0].strip()
        dni = parts[1].strip()
        return {'n': nombre, 'd': dni, 'o': '', 'e': ''}
    
    # Solo nombre
    return {'n': paciente_str, 'd': '', 'o': '', 'e': ''}


def limpiar_pacientes():
    """Limpia la lista de pacientes eliminando duplicados."""
    
    local_file = Path('.streamlit/local_data.json')
    
    if not local_file.exists():
        print("No existe local_data.json")
        return
    
    # Cargar datos
    with open(local_file, 'r', encoding='utf-8') as f:
        datos = json.load(f)
    
    pacientes_originales = datos.get('pacientes_db', [])
    print(f"Pacientes antes de limpieza: {len(pacientes_originales)}")
    
    # Convertir todos a formato diccionario y eliminar duplicados
    pacientes_limpios = []
    dnis_vistos = set()
    nombres_vistos = set()
    
    for paciente in pacientes_originales:
        if isinstance(paciente, dict):
            # Ya es diccionario
            dni = paciente.get('d', '')
            nombre = paciente.get('n', '')
        elif isinstance(paciente, str):
            # Convertir de string a dict
            parsed = parse_paciente_string(paciente)
            if parsed:
                dni = parsed['d']
                nombre = parsed['n']
                paciente = parsed
            else:
                continue
        else:
            continue
        
        # Evitar duplicados por DNI
        if dni and dni in dnis_vistos:
            continue
        
        # Si no tiene DNI, evitar por nombre
        if not dni and nombre in nombres_vistos:
            continue
        
        # Agregar a la lista limpia
        pacientes_limpios.append(paciente)
        if dni:
            dnis_vistos.add(dni)
        if nombre:
            nombres_vistos.add(nombre)
    
    print(f"Pacientes después de limpieza: {len(pacientes_limpios)}")
    print(f"Eliminados: {len(pacientes_originales) - len(pacientes_limpios)}")
    
    # Actualizar datos
    datos['pacientes_db'] = pacientes_limpios
    
    # Crear backup
    backup_name = f".streamlit/backup_antes_limpieza_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(backup_name, 'w', encoding='utf-8') as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
    print(f"\nBackup creado: {backup_name}")
    
    # Guardar datos limpios
    with open(local_file, 'w', encoding='utf-8') as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
    
    print(f"Datos limpios guardados en: {local_file}")
    
    # Mostrar pacientes finales
    print("\nPacientes finales:")
    for i, p in enumerate(pacientes_limpios, 1):
        nombre = p.get('n', 'N/A')
        dni = p.get('d', 'N/A')
        print(f"  {i}. {nombre} (DNI: {dni})")


if __name__ == "__main__":
    limpiar_pacientes()
