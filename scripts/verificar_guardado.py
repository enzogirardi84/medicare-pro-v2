#!/usr/bin/env python3
"""
VERIFICAR QUÉ DATOS SE GUARDAN Y QUÉ NO
Compara local_data.json vs Supabase
"""

import json
from pathlib import Path
from datetime import datetime

def verificar_guardado():
    """Verifica qué datos se están guardando correctamente."""
    
    print("="*70)
    print("VERIFICACIÓN DE GUARDADO - LOCAL vs SUPABASE")
    print("="*70)
    
    # 1. Verificar local_data.json
    local_file = Path(".streamlit/local_data.json")
    datos_locales = {}
    
    if local_file.exists():
        with open(local_file, 'r', encoding='utf-8') as f:
            datos_locales = json.load(f)
        
        print("\n📁 DATOS LOCALES (local_data.json):")
        print(f"  Pacientes: {len(datos_locales.get('pacientes_db', []))}")
        print(f"  Signos Vitales: {len(datos_locales.get('vitales_db', []))}")
        print(f"  Evoluciones: {len(datos_locales.get('evoluciones_db', []))}")
        print(f"  Recetas: {len(datos_locales.get('recetas_db', []))}")
        print(f"  Visitas: {len(datos_locales.get('visitas_db', []))}")
        print(f"  Usuarios: {len(datos_locales.get('usuarios_db', []))}")
    else:
        print("\n❌ No existe local_data.json")
    
    # 2. Verificar Supabase
    print("\n☁️ DATOS EN SUPABASE:")
    
    try:
        import toml
        from supabase import create_client
        
        secrets = toml.load('.streamlit/secrets.toml')
        supabase = create_client(secrets['SUPABASE_URL'], secrets['SUPABASE_KEY'])
        
        tablas_verificar = [
            ('pacientes', 'Pacientes'),
            ('signos_vitales', 'Signos Vitales'),
            ('evoluciones', 'Evoluciones'),
            ('recetas', 'Recetas'),
            ('visitas', 'Visitas'),
            ('usuarios', 'Usuarios'),
            ('inventario', 'Inventario'),
        ]
        
        resultados = {}
        
        for tabla, nombre in tablas_verificar:
            try:
                response = supabase.table(tabla).select("count", count="exact").execute()
                count = response.count if hasattr(response, 'count') else 0
                resultados[tabla] = count
                print(f"  {nombre}: {count}")
            except Exception as e:
                print(f"  {nombre}: ERROR - {str(e)[:40]}")
                resultados[tabla] = -1
        
        # 3. Comparación
        print("\n🔍 COMPARACIÓN LOCAL vs SUPABASE:")
        
        comparaciones = [
            ('pacientes', 'pacientes_db', 'Pacientes'),
            ('signos_vitales', 'vitales_db', 'Signos Vitales'),
            ('evoluciones', 'evoluciones_db', 'Evoluciones'),
            ('recetas', 'recetas_db', 'Recetas'),
            ('visitas', 'visitas_db', 'Visitas'),
        ]
        
        problemas = []
        
        for tabla_supa, key_local, nombre in comparaciones:
            count_supa = resultados.get(tabla_supa, 0)
            count_local = len(datos_locales.get(key_local, []))
            
            if count_supa == -1:
                print(f"  ⚠️ {nombre}: Tabla no existe en Supabase")
                problemas.append(f"Crear tabla '{tabla_supa}' en Supabase")
            elif count_local > count_supa:
                diferencia = count_local - count_supa
                print(f"  ❌ {nombre}: {diferencia} registros solo en local (no migrados)")
                problemas.append(f"Migrar {diferencia} {nombre} a Supabase")
            elif count_supa > count_local:
                print(f"  ✅ {nombre}: {count_supa} en nube (bien)")
            else:
                print(f"  ✅ {nombre}: Sincronizado ({count_supa})")
        
        # 4. Recomendaciones
        if problemas:
            print("\n🔧 ACCIONES REQUERIDAS:")
            for i, problema in enumerate(problemas, 1):
                print(f"  {i}. {problema}")
        else:
            print("\n✅ Todo sincronizado correctamente")
        
        # 5. Ver últimos registros
        print("\n📅 ÚLTIMOS REGISTROS EN SUPABASE:")
        
        for tabla, nombre in [('signos_vitales', 'Signos Vitales'), ('evoluciones', 'Evoluciones')]:
            try:
                response = supabase.table(tabla).select("*").order("created_at", desc=True).limit(3).execute()
                registros = response.data if hasattr(response, 'data') else []
                
                if registros:
                    print(f"\n  {nombre}:")
                    for r in registros:
                        fecha = r.get('created_at', 'N/A')[:16] if r.get('created_at') else 'N/A'
                        print(f"    - {fecha}: Paciente {r.get('paciente_id', 'N/A')[:8]}...")
                else:
                    print(f"  {nombre}: Sin registros")
                    
            except Exception as e:
                print(f"  {nombre}: Error - {e}")
        
    except Exception as e:
        print(f"\n❌ Error conectando a Supabase: {e}")

if __name__ == "__main__":
    verificar_guardado()
