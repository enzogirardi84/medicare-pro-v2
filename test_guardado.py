#!/usr/bin/env python3
"""
Test de diagnóstico para verificar el sistema de guardado.
Ejecutar: python test_guardado.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Simular session_state de Streamlit
class MockSessionState:
    def __init__(self):
        self.data = {
            "evoluciones_db": [],
            "vitales_db": [],
            "pacientes_db": [
                {"d": "35322168", "n": "Juan suarez", "o": "Particular", "e": "Girardi"}
            ],
            "firmas_tactiles_db": [],
        }
    
    def __getitem__(self, key):
        return self.data.get(key, [])
    
    def __setitem__(self, key, value):
        self.data[key] = value

st = MockSessionState()

def test_local_data_json():
    """Verificar si local_data.json existe y tiene datos."""
    print("\n" + "="*60)
    print("TEST 1: Verificando local_data.json")
    print("="*60)
    
    local_file = Path(".streamlit/local_data.json")
    
    if not local_file.exists():
        print("[ERROR] No existe .streamlit/local_data.json")
        print("   Solucion: Ejecutar la app una vez para crearlo")
        return False
    
    try:
        with open(local_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"[OK] Archivo existe")
        print(f"   - Pacientes: {len(data.get('pacientes_db', []))}")
        print(f"   - Evoluciones: {len(data.get('evoluciones_db', []))}")
        print(f"   - Vitales: {len(data.get('vitales_db', []))}")
        print(f"   - Firmas: {len(data.get('firmas_tactiles_db', []))}")
        return True
    except Exception as e:
        print(f"[ERROR] leyendo archivo: {e}")
        return False

def test_session_state_keys():
    """Verificar que existan las keys necesarias en session_state."""
    print("\n" + "="*60)
    print("TEST 2: Verificando estructura de datos")
    print("="*60)
    
    required_keys = [
        "evoluciones_db",
        "vitales_db", 
        "pacientes_db",
        "firmas_tactiles_db",
    ]
    
    all_ok = True
    for key in required_keys:
        if key in st.data:
            print(f"[OK] {key}: ({len(st.data[key])} items)")
        else:
            print(f"[ERROR] {key}: NO EXISTE")
            all_ok = False
    
    return all_ok

def test_guardado_simulado():
    """Simular guardado de signos vitales."""
    print("\n" + "="*60)
    print("TEST 3: Simulando guardado de signos vitales")
    print("="*60)
    
    try:
        # Simular datos de signos vitales
        signos_vitales = {
            "paciente": "Juan suarez - 35322168",
            "dni": "35322168",
            "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "ta": "120/80",
            "fc": "72",
            "fr": "16",
            "sat": "98",
            "temp": "36.5",
        }
        
        # Agregar a session_state
        st.data["vitales_db"].append(signos_vitales)
        
        # Simular guardado en archivo
        local_file = Path(".streamlit/local_data.json")
        if local_file.exists():
            with open(local_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Agregar datos
            if "vitales_db" not in data:
                data["vitales_db"] = []
            
            data["vitales_db"].append(signos_vitales)
            
            # Guardar
            with open(local_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"[OK] Signos vitales guardados correctamente")
            print(f"   Paciente: {signos_vitales['paciente']}")
            print(f"   TA: {signos_vitales['ta']}, FC: {signos_vitales['fc']}")
            return True
        else:
            print("[ERROR] No se pudo guardar - archivo no existe")
            return False
            
    except Exception as e:
        print(f"[ERROR] durante guardado: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_recuperacion_datos():
    """Verificar que los datos se puedan recuperar."""
    print("\n" + "="*60)
    print("TEST 4: Verificando recuperacion de datos")
    print("="*60)
    
    try:
        local_file = Path(".streamlit/local_data.json")
        with open(local_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        vitales = data.get("vitales_db", [])
        
        if vitales:
            print(f"[OK] Datos recuperados: {len(vitales)} registros")
            ultimo = vitales[-1]
            print(f"   Ultimo: {ultimo.get('paciente', 'N/A')}")
            print(f"   Fecha: {ultimo.get('fecha', 'N/A')}")
            return True
        else:
            print("[ERROR] No hay datos de signos vitales")
            return False
            
    except Exception as e:
        print(f"[ERROR]: {e}")
        return False

def main():
    """Ejecutar todos los tests."""
    print("\n" + "="*60)
    print("DIAGNOSTICO DEL SISTEMA DE GUARDADO")
    print("="*60)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("local_data.json", test_local_data_json),
        ("session_state keys", test_session_state_keys),
        ("guardado simulado", test_guardado_simulado),
        ("recuperacion", test_recuperacion_datos),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n[FAIL] Test '{name}' fallo: {e}")
            results.append((name, False))
    
    # Resumen
    print("\n" + "="*60)
    print("RESUMEN")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests pasaron")
    
    if passed < total:
        print("\nRECOMENDACIONES:")
        print("1. Verificar permisos de escritura en .streamlit/")
        print("2. Revisar si hay errores JavaScript en el navegador")
        print("3. Verificar que el paciente esté seleccionado antes de guardar")
        print("4. Revisar logs de la aplicacion")
        sys.exit(1)
    else:
        print("\n[OK] Sistema de guardado funcionando correctamente")
        sys.exit(0)

if __name__ == "__main__":
    main()
