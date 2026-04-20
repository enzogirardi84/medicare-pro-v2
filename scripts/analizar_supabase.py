#!/usr/bin/env python3
"""
ANALISIS COMPLETO DE SUPABASE
Genera un reporte detallado de tablas, columnas y configuración
"""

import json
from datetime import datetime
from pathlib import Path

def analizar_supabase():
    """Analiza la configuración de Supabase."""
    
    # Cargar credenciales
    try:
        with open('.streamlit/secrets.toml', 'r') as f:
            secrets = f.read()
    except:
        print("No se encontró secrets.toml")
        return
    
    print("="*70)
    print("ANALISIS DE SUPABASE")
    print("="*70)
    
    # Intentar conectar
    try:
        from supabase import create_client
        
        # Buscar credenciales en secrets
        supabase_url = None
        supabase_key = None
        
        for line in secrets.split('\n'):
            if 'SUPABASE_URL' in line and '=' in line:
                supabase_url = line.split('=')[1].strip().strip('"').strip("'")
            if 'SUPABASE_KEY' in line and '=' in line:
                supabase_key = line.split('=')[1].strip().strip('"').strip("'")
        
        if not supabase_url or not supabase_key:
            print("No se encontraron credenciales de Supabase")
            return
        
        print(f"\nConectando a: {supabase_url[:30]}...")
        
        supabase = create_client(supabase_url, supabase_key)
        
        # Tablas a verificar
        tablas_clinicas = [
            'pacientes',
            'evoluciones', 
            'signos_vitales',
            'recetas',
            'usuarios',
            'empresas',
            'auditoria_legal'
        ]
        
        reporte = {
            "fecha": datetime.now().isoformat(),
            "supabase_url": supabase_url,
            "tablas": {}
        }
        
        print("\nVerificando tablas...")
        for tabla in tablas_clinicas:
            try:
                # Verificar si tabla existe
                response = supabase.table(tabla).select("count", count="exact").limit(1).execute()
                count = response.count if hasattr(response, 'count') else '?'
                
                reporte["tablas"][tabla] = {
                    "existe": True,
                    "registros": count
                }
                print(f"  [OK] {tabla}: {count} registros")
                
            except Exception as e:
                reporte["tablas"][tabla] = {
                    "existe": False,
                    "error": str(e)
                }
                print(f"  [ERROR] {tabla}: {str(e)[:50]}")
        
        # Guardar reporte
        with open('reporte_supabase.json', 'w', encoding='utf-8') as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False)
        
        print("\n" + "="*70)
        print("Reporte guardado: reporte_supabase.json")
        print("="*70)
        print("\nPuedes compartir este archivo para revisión")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analizar_supabase()
