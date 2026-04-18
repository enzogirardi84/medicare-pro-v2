#!/usr/bin/env python3
"""
DIAGNOSTICO TOTAL DE LA APLICACION
Identifica todos los errores criticos
"""

import sys
import os
from pathlib import Path

def diagnosticar():
    print("="*70)
    print("DIAGNOSTICO TOTAL - MEDICARE PRO")
    print("="*70)
    
    errores = []
    
    # 1. Verificar estructura de archivos
    print("\n1. Verificando archivos criticos...")
    archivos_criticos = [
        "main.py",
        "core/view_registry.py",
        "core/database.py",
        "core/guardado_simple.py",
        "views/clinica_emergencia.py",
        "views/evolucion.py",
        ".streamlit/secrets.toml"
    ]
    
    for archivo in archivos_criticos:
        if Path(archivo).exists():
            print(f"   [OK] {archivo}")
        else:
            print(f"   [ERROR] Falta: {archivo}")
            errores.append(f"Falta archivo: {archivo}")
    
    # 2. Verificar imports
    print("\n2. Verificando imports...")
    try:
        sys.path.insert(0, str(Path.cwd()))
        
        # Probar import de core modules
        try:
            from core import guardado_simple
            print("   [OK] core.guardado_simple")
        except Exception as e:
            print(f"   [ERROR] core.guardado_simple: {e}")
            errores.append(f"Import error guardado_simple: {e}")
        
        # Probar import de views
        try:
            from views import clinica_emergencia
            print("   [OK] views.clinica_emergencia")
        except Exception as e:
            print(f"   [ERROR] views.clinica_emergencia: {e}")
            errores.append(f"Import error clinica: {e}")
            
    except Exception as e:
        print(f"   [ERROR] General import error: {e}")
    
    # 3. Verificar funciones de guardado
    print("\n3. Verificando funciones de guardado...")
    try:
        from core.guardado_simple import guardar_historial_clinico
        print("   [OK] Funcion guardar_historial_clinico existe")
    except Exception as e:
        print(f"   [ERROR] {e}")
        errores.append(f"Funcion guardar_historial_clinico: {e}")
    
    # 4. Verificar view_registry
    print("\n4. Verificando view_registry...")
    try:
        from core.view_registry import VIEW_CONFIG
        print(f"   [OK] VIEW_CONFIG cargado - {len(VIEW_CONFIG)} modulos")
        for key in ['Clinica', 'Evolucion', 'Historial']:
            if key in VIEW_CONFIG:
                print(f"      [OK] {key}: {VIEW_CONFIG[key]}")
            else:
                print(f"      [ERROR] Falta modulo: {key}")
                errores.append(f"Falta modulo en VIEW_CONFIG: {key}")
    except Exception as e:
        print(f"   [ERROR] {e}")
        errores.append(f"VIEW_CONFIG error: {e}")
    
    # 5. Resumen
    print("\n" + "="*70)
    print("RESUMEN")
    print("="*70)
    
    if errores:
        print(f"\n[CRITICO] Se encontraron {len(errores)} errores:")
        for i, error in enumerate(errores, 1):
            print(f"{i}. {error}")
        return False
    else:
        print("\n[OK] No se encontraron errores criticos")
        return True

if __name__ == "__main__":
    exito = diagnosticar()
    sys.exit(0 if exito else 1)
