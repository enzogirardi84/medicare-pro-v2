#!/usr/bin/env python3
"""
DIAGNOSTICO Y ARREGLO DE SUPABASE
Paso a paso para hacer funcionar Supabase
"""

import json
import sys
from pathlib import Path
from datetime import datetime

def diagnosticar_problema():
    """Diagnostica el problema especifico con Supabase."""
    
    print("="*70)
    print("DIAGNOSTICO DE SUPABASE - PASO A PASO")
    print("="*70)
    
    # 1. Verificar credenciales
    print("\n1. Verificando credenciales...")
    try:
        import toml
        secrets = toml.load('.streamlit/secrets.toml')
        supabase_url = secrets.get('SUPABASE_URL', '')
        supabase_key = secrets.get('SUPABASE_KEY', '')
        
        if supabase_url and supabase_key:
            print(f"   [OK] URL: {supabase_url[:30]}...")
            print(f"   [OK] Key: {supabase_key[:20]}...")
        else:
            print("   [ERROR] Faltan credenciales")
            return False
            
    except Exception as e:
        print(f"   [ERROR] {e}")
        return False
    
    # 2. Probar conexion
    print("\n2. Probando conexion a Supabase...")
    try:
        from supabase import create_client
        supabase = create_client(supabase_url, supabase_key)
        
        # Probar consulta simple
        response = supabase.table('pacientes').select('*').limit(1).execute()
        print(f"   [OK] Conexion exitosa")
        print(f"   [OK] Respuesta: {len(response.data)} registros")
        
    except Exception as e:
        error_msg = str(e)
        print(f"   [ERROR] {error_msg[:100]}")
        
        # Analizar error especifico
        if "does not exist" in error_msg:
            print("\n   [DIAGNOSTICO] La tabla 'pacientes' no existe en Supabase")
            print("   [SOLUCION] Necesitas crear las tablas primero")
        elif "permission denied" in error_msg or "row-level security" in error_msg.lower():
            print("\n   [DIAGNOSTICO] Problema de permisos (RLS)")
            print("   [SOLUCION] Desactivar Row Level Security en Supabase")
        elif "network" in error_msg.lower() or "connection" in error_msg.lower():
            print("\n   [DIAGNOSTICO] Problema de red/conexion")
            print("   [SOLUCION] Verificar internet y URL de Supabase")
        else:
            print("\n   [DIAGNOSTICO] Error desconocido")
        
        return False
    
    return True


def verificar_tablas():
    """Verifica que todas las tablas necesarias existen."""
    
    print("\n3. Verificando tablas...")
    
    try:
        import toml
        from supabase import create_client
        
        secrets = toml.load('.streamlit/secrets.toml')
        supabase = create_client(secrets['SUPABASE_URL'], secrets['SUPABASE_KEY'])
        
        tablas_necesarias = [
            'pacientes', 'usuarios', 'empresas',
            'signos_vitales', 'evoluciones', 'recetas', 'visitas'
        ]
        
        tablas_faltantes = []
        
        for tabla in tablas_necesarias:
            try:
                response = supabase.table(tabla).select('count', count='exact').execute()
                count = response.count if hasattr(response, 'count') else 0
                print(f"   [OK] {tabla}: {count} registros")
            except Exception as e:
                print(f"   [ERROR] {tabla}: NO EXISTE")
                tablas_faltantes.append(tabla)
        
        if tablas_faltantes:
            print(f"\n   [CRITICAL] Faltan {len(tablas_faltantes)} tablas:")
            for t in tablas_faltantes:
                print(f"      - {t}")
            return False
        
        return True
        
    except Exception as e:
        print(f"   [ERROR] {e}")
        return False


def probar_guardado():
    """Prueba guardar un dato de prueba."""
    
    print("\n4. Probando guardado de prueba...")
    
    try:
        import toml
        from supabase import create_client
        
        secrets = toml.load('.streamlit/secrets.toml')
        supabase = create_client(secrets['SUPABASE_URL'], secrets['SUPABASE_KEY'])
        
        # Intentar insertar paciente de prueba
        test_paciente = {
            "dni": "99999999",
            "nombre": "TEST_PACIENTE",
            "apellido": "BORRAR",
            "obra_social": "Test",
            "estado": "Activo"
        }
        
        response = supabase.table('pacientes').insert(test_paciente).execute()
        
        if hasattr(response, 'data') and response.data:
            print("   [OK] Insert funcionando")
            
            # Borrar dato de prueba
            supabase.table('pacientes').delete().eq('dni', '99999999').execute()
            print("   [OK] Delete funcionando")
            
            return True
        else:
            print("   [ERROR] No se confirmo la insercion")
            return False
            
    except Exception as e:
        print(f"   [ERROR] {e}")
        return False


def main():
    """Ejecuta diagnostico completo."""
    
    print("\n" + "="*70)
    print("INICIANDO DIAGNOSTICO COMPLETO")
    print("="*70)
    
    paso1 = diagnosticar_problema()
    paso2 = verificar_tablas() if paso1 else False
    paso3 = probar_guardado() if paso2 else False
    
    print("\n" + "="*70)
    print("RESULTADO DEL DIAGNOSTICO")
    print("="*70)
    
    if paso1 and paso2 and paso3:
        print("\n   [OK] Supabase esta funcionando correctamente")
        print("\n   [ACCION] Puedes desactivar el modo emergencia")
        print("   Cambiar en core/view_registry.py:")
        print('   "Clinica": ("views.clinica_emergencia", "render")')
        print('   a:')
        print('   "Clinica": ("views.clinica", "render_clinica")')
        return True
    else:
        print("\n   [ERROR] Hay problemas con Supabase")
        
        if not paso1:
            print("\n   [SOLUCION 1] Verificar credenciales en .streamlit/secrets.toml")
        
        if not paso2:
            print("\n   [SOLUCION 2] Ejecutar el SQL para crear tablas en Supabase:")
            print("   - Ir a SQL Editor en Supabase")
            print("   - Ejecutar supabase_clean.sql")
        
        if not paso3:
            print("\n   [SOLUCION 3] Verificar permisos RLS:")
            print("   - Ir a Table Editor → Signos vitales → Policies")
            print("   - Desactivar RLS o crear politica allow all")
        
        return False


if __name__ == "__main__":
    exito = main()
    sys.exit(0 if exito else 1)
