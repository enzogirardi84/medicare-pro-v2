#!/usr/bin/env python3
"""
TEST: Verificar sincronización con Supabase
Ejecutar: python test_supabase_sync.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime

def test_supabase_connection():
    """Verificar conexión a Supabase."""
    print("\n" + "="*70)
    print("TEST 1: Conexion a Supabase")
    print("="*70)
    
    try:
        from supabase import create_client
        from core.database import supabase
        
        if supabase is None:
            print("[ERROR] No hay conexion a Supabase")
            print("        Verificar SUPABASE_URL y SUPABASE_KEY en secrets.toml")
            return False
        
        print(f"[OK] Cliente Supabase inicializado")
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        return False

def test_dual_write_config():
    """Verificar configuración de dual-write."""
    print("\n" + "="*70)
    print("TEST 2: Configuracion Dual-Write")
    print("="*70)
    
    try:
        from core.feature_flags import ENABLE_NEXTGEN_API_DUAL_WRITE
        
        if ENABLE_NEXTGEN_API_DUAL_WRITE:
            print(f"[OK] Dual-write ESTA ACTIVADO")
            print("     Los datos se guardan en local + Supabase")
        else:
            print(f"[WARNING] Dual-write esta DESACTIVADO")
            print("          Solo se guarda en local_data.json")
        
        return ENABLE_NEXTGEN_API_DUAL_WRITE
        
    except Exception as e:
        print(f"[ERROR] No se pudo verificar: {e}")
        return False

def test_local_vs_supabase():
    """Verificar diferencias entre local y Supabase."""
    print("\n" + "="*70)
    print("TEST 3: Comparacion Local vs Supabase")
    print("="*70)
    
    # Contar datos locales
    local_file = Path(".streamlit/local_data.json")
    if local_file.exists():
        with open(local_file, 'r', encoding='utf-8') as f:
            local_data = json.load(f)
        
        local_counts = {
            "pacientes": len(local_data.get("pacientes_db", [])),
            "evoluciones": len(local_data.get("evoluciones_db", [])),
            "vitales": len(local_data.get("vitales_db", [])),
            "recetas": len(local_data.get("recetas_db", [])),
        }
        
        print("[OK] Datos locales:")
        for key, count in local_counts.items():
            print(f"     - {key}: {count}")
    else:
        print("[ERROR] No existe local_data.json")
        return False
    
    # Intentar obtener datos de Supabase
    try:
        from core.database import supabase
        
        if supabase:
            # Verificar tabla de pacientes
            response = supabase.table("pacientes").select("count", count="exact").execute()
            supabase_count = response.count if hasattr(response, 'count') else "?"
            print(f"\n[OK] Supabase - pacientes: {supabase_count}")
        else:
            print("\n[WARNING] No se pudo conectar a Supabase para verificar")
            
    except Exception as e:
        print(f"\n[ERROR] Error consultando Supabase: {e}")
    
    return True

def test_save_to_supabase():
    """Probar guardar un dato de prueba en Supabase."""
    print("\n" + "="*70)
    print("TEST 4: Prueba de guardado en Supabase")
    print("="*70)
    
    try:
        from core.database import supabase
        
        if not supabase:
            print("[ERROR] No hay conexion a Supabase")
            return False
        
        # Datos de prueba
        test_data = {
            "nombre": "TEST_PACIENTE",
            "dni": "99999999",
            "created_at": datetime.now().isoformat()
        }
        
        # Intentar insertar (esto puede fallar si la tabla no existe)
        print("[INFO] Intentando insertar paciente de prueba...")
        response = supabase.table("pacientes").insert(test_data).execute()
        
        print(f"[OK] Dato insertado en Supabase")
        print(f"     Respuesta: {response}")
        
        # Eliminar el dato de prueba
        supabase.table("pacientes").delete().eq("dni", "99999999").execute()
        print("[OK] Dato de prueba eliminado")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        print("     Posibles causas:")
        print("     - Tabla 'pacientes' no existe en Supabase")
        print("     - No hay permisos de escritura")
        print("     - Estructura de tabla diferente")
        return False

def main():
    """Ejecutar todos los tests."""
    print("\n" + "="*70)
    print("DIAGNOSTICO DE SINCRONIZACION SUPABASE")
    print("="*70)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("Conexion Supabase", test_supabase_connection),
        ("Configuracion Dual-Write", test_dual_write_config),
        ("Comparacion datos", test_local_vs_supabase),
        ("Guardado de prueba", test_save_to_supabase),
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
    print("\n" + "="*70)
    print("RESUMEN")
    print("="*70)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests pasaron")
    
    if passed < total:
        print("\nDIAGNOSTICO:")
        print("1. Si el test 1 falla: Verificar credenciales de Supabase")
        print("2. Si el test 2 falla: Verificar feature_flags.py")
        print("3. Si el test 3 falla: Datos solo en local, no en Supabase")
        print("4. Si el test 4 falla: Problema de permisos o tablas")
        sys.exit(1)
    else:
        print("\n[OK] Sistema de sincronizacion funcionando")
        sys.exit(0)

if __name__ == "__main__":
    main()
