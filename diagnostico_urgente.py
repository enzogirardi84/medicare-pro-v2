#!/usr/bin/env python3
"""
DIAGNÓSTICO URGENTE - Por qué no se guardan los datos
"""

import sys
from pathlib import Path

def diagnostico_completo():
    """Diagnostica por qué no se guardan los datos."""
    
    print("="*70)
    print("DIAGNÓSTICO URGENTE - SISTEMA DE GUARDADO")
    print("="*70)
    
    errores = []
    
    # 1. Verificar archivo de configuración
    print("\n1. Verificando configuración...")
    secrets_file = Path(".streamlit/secrets.toml")
    if not secrets_file.exists():
        errores.append("[ERROR] No existe .streamlit/secrets.toml")
        print("   [ERROR] No existe secrets.toml")
    else:
        with open(secrets_file, 'r') as f:
            content = f.read()
            if 'SUPABASE_URL' in content and 'SUPABASE_KEY' in content:
                print("   [OK] Credenciales de Supabase configuradas")
            else:
                errores.append("[ERROR] Faltan credenciales de Supabase en secrets.toml")
                print("   [ERROR] Faltan credenciales")
    
    # 2. Verificar local_data.json
    print("\n2. Verificando local_data.json...")
    local_file = Path(".streamlit/local_data.json")
    if local_file.exists():
        import json
        with open(local_file, 'r') as f:
            data = json.load(f)
        print(f"   [OK] Existe local_data.json")
        print(f"      - Pacientes: {len(data.get('pacientes_db', []))}")
        print(f"      - Signos vitales: {len(data.get('vitales_db', []))}")
        print(f"      - Evoluciones: {len(data.get('evoluciones_db', []))}")
        
        # Guardar backup de emergencia
        backup_file = Path(".streamlit/local_data_backup_urgente.json")
        with open(backup_file, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"   [BACKUP] Backup creado: {backup_file}")
    else:
        errores.append("[WARN] No existe local_data.json - Datos podrian estar en riesgo")
        print("   [WARN] No existe local_data.json")
    
    # 3. Probar conexión a Supabase
    print("\n3. Probando conexión a Supabase...")
    try:
        import toml
        from supabase import create_client
        
        secrets = toml.load('.streamlit/secrets.toml')
        supabase = create_client(
            secrets['SUPABASE_URL'],
            secrets['SUPABASE_KEY']
        )
        
        # Probar consulta simple
        response = supabase.table('pacientes').select('count', count='exact').execute()
        count = response.count if hasattr(response, 'count') else 0
        print(f"   [OK] Conexion OK - {count} pacientes en Supabase")
        
    except Exception as e:
        errores.append(f"[ERROR] Error conectando a Supabase: {e}")
        print(f"   [ERROR] Error: {e}")
    
    # 4. Verificar que las tablas existen
    print("\n4. Verificando tablas en Supabase...")
    try:
        tablas_necesarias = [
            'pacientes', 'signos_vitales', 'evoluciones', 'recetas', 'usuarios'
        ]
        
        for tabla in tablas_necesarias:
            try:
                response = supabase.table(tabla).select('id').limit(1).execute()
                print(f"   [OK] Tabla '{tabla}' existe")
            except Exception as e:
                errores.append(f"[ERROR] Tabla '{tabla}' no existe o tiene error: {e}")
                print(f"   [ERROR] Tabla '{tabla}' - ERROR")
                
    except Exception as e:
        errores.append(f"[ERROR] Error verificando tablas: {e}")
    
    # 5. Resumen
    print("\n" + "="*70)
    print("RESUMEN DEL DIAGNÓSTICO")
    print("="*70)
    
    if errores:
        print(f"\n[CRITICAL] SE ENCONTRARON {len(errores)} PROBLEMAS CRITICOS:\n")
        for i, error in enumerate(errores, 1):
            print(f"{i}. {error}")
        
        print("\n" + "="*70)
        print("SOLUCIONES INMEDIATAS:")
        print("="*70)
        print("""
OPCIÓN A - Modo Local Temporal (Funciona AHORA):
1. Desactivar guardado en Supabase
2. Guardar solo en local_data.json
3. Funciona inmediatamente

OPCIÓN B - Arreglar Supabase (Requiere tiempo):
1. Crear tablas faltantes
2. Verificar permisos RLS
3. Probar conexión
        """)
        
        return False
    else:
        print("\n[OK] No se encontraron problemas obvios")
        print("El sistema debería funcionar. Si no guarda, el error está en el código.")
        return True


if __name__ == "__main__":
    diagnostico_completo()
