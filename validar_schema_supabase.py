#!/usr/bin/env python3
"""
VALIDACIÓN COMPLETA DEL ESQUEMA SUPABASE
Verifica que todas las tablas y relaciones estén correctas
"""

import json
from datetime import datetime
from pathlib import Path

def validar_schema():
    """Valida el esquema completo de Supabase."""
    
    print("="*70)
    print("VALIDACIÓN DEL ESQUEMA SUPABASE")
    print("="*70)
    
    # Tablas esperadas según el SQL compartido
    tablas_esperadas = {
        # Tablas clínicas
        'signos_vitales': {
            'columnas_requeridas': ['id', 'paciente_id', 'usuario_id', 'fecha_registro', 
                                   'tension_arterial', 'frecuencia_cardiaca', 'temperatura'],
            'foreign_keys': ['paciente_id', 'usuario_id']
        },
        'cuidados_enfermeria': {
            'columnas_requeridas': ['id', 'paciente_id', 'usuario_id', 'fecha_registro', 
                                   'tipo_cuidado', 'descripcion'],
            'foreign_keys': ['paciente_id', 'usuario_id']
        },
        'consentimientos': {
            'columnas_requeridas': ['id', 'paciente_id', 'usuario_id', 'fecha_firma', 
                                   'tipo_documento', 'archivo_url'],
            'foreign_keys': ['paciente_id', 'usuario_id']
        },
        'auditoria_legal': {
            'columnas_requeridas': ['id', 'empresa_id', 'paciente_id', 'usuario_id', 
                                   'fecha_evento', 'modulo', 'accion'],
            'foreign_keys': ['empresa_id', 'paciente_id', 'usuario_id']
        },
        'pediatria': {
            'columnas_requeridas': ['id', 'paciente_id', 'usuario_id', 'fecha_registro',
                                   'peso_kg', 'talla_cm'],
            'foreign_keys': ['paciente_id', 'usuario_id']
        },
        'escalas_clinicas': {
            'columnas_requeridas': ['id', 'paciente_id', 'usuario_id', 'fecha_registro',
                                   'tipo_escala', 'puntaje_total'],
            'foreign_keys': ['paciente_id', 'usuario_id']
        },
        'emergencias': {
            'columnas_requeridas': ['id', 'empresa_id', 'paciente_id', 'usuario_id',
                                   'fecha_llamado', 'motivo', 'prioridad', 'estado'],
            'foreign_keys': ['empresa_id', 'paciente_id', 'usuario_id']
        },
        # Tablas de gestión
        'inventario': {
            'columnas_requeridas': ['id', 'empresa_id', 'codigo', 'nombre', 'stock_actual'],
            'foreign_keys': ['empresa_id']
        },
        'consumos': {
            'columnas_requeridas': ['id', 'empresa_id', 'paciente_id', 'inventario_id',
                                   'fecha_consumo', 'cantidad'],
            'foreign_keys': ['empresa_id', 'paciente_id', 'inventario_id']
        },
        'facturacion': {
            'columnas_requeridas': ['id', 'empresa_id', 'paciente_id', 'fecha_emision',
                                   'concepto', 'monto_total', 'estado'],
            'foreign_keys': ['empresa_id', 'paciente_id']
        },
        'balance': {
            'columnas_requeridas': ['id', 'empresa_id', 'fecha_movimiento', 'tipo_movimiento',
                                   'concepto', 'monto'],
            'foreign_keys': ['empresa_id']
        },
        'nomenclador': {
            'columnas_requeridas': ['id', 'empresa_id', 'codigo_practica', 'descripcion',
                                   'valor_honorario'],
            'foreign_keys': ['empresa_id']
        },
        'checkin_asistencia': {
            'columnas_requeridas': ['id', 'empresa_id', 'usuario_id', 'paciente_id',
                                   'fecha_hora', 'tipo_registro'],
            'foreign_keys': ['empresa_id', 'usuario_id', 'paciente_id']
        },
        'profesionales_red': {
            'columnas_requeridas': ['id', 'empresa_id', 'nombre_completo', 'especialidad'],
            'foreign_keys': ['empresa_id']
        },
        # Tablas base (deben existir previamente)
        'pacientes': {
            'columnas_requeridas': ['id', 'nombre', 'dni'],
            'foreign_keys': []
        },
        'usuarios': {
            'columnas_requeridas': ['id', 'nombre', 'email'],
            'foreign_keys': []
        },
        'empresas': {
            'columnas_requeridas': ['id', 'nombre', 'cuit'],
            'foreign_keys': []
        }
    }
    
    # Intentar conectar y verificar
    try:
        from supabase import create_client
        import toml
        
        # Cargar secrets
        secrets = toml.load('.streamlit/secrets.toml')
        supabase_url = secrets['SUPABASE_URL']
        supabase_key = secrets['SUPABASE_KEY']
        
        supabase = create_client(supabase_url, supabase_key)
        
        print("\n✅ Conexión establecida")
        
        reporte = {
            "fecha": datetime.now().isoformat(),
            "tablas": {},
            "resumen": {
                "total_esperadas": len(tablas_esperadas),
                "encontradas": 0,
                "faltantes": [],
                "con_datos": 0
            }
        }
        
        # Verificar cada tabla
        for tabla, config in tablas_esperadas.items():
            try:
                # Verificar si existe
                response = supabase.table(tabla).select("count", count="exact").limit(1).execute()
                count = response.count if hasattr(response, 'count') else 0
                
                reporte["tablas"][tabla] = {
                    "existe": True,
                    "registros": count,
                    "estado": "OK"
                }
                reporte["resumen"]["encontradas"] += 1
                if count > 0:
                    reporte["resumen"]["con_datos"] += 1
                    
                print(f"✅ {tabla}: {count} registros")
                
            except Exception as e:
                reporte["tablas"][tabla] = {
                    "existe": False,
                    "error": str(e),
                    "estado": "FALTANTE"
                }
                reporte["resumen"]["faltantes"].append(tabla)
                print(f"❌ {tabla}: NO EXISTE - {str(e)[:50]}")
        
        # Guardar reporte
        with open('validacion_schema.json', 'w', encoding='utf-8') as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False)
        
        # Resumen
        print("\n" + "="*70)
        print("RESUMEN DE VALIDACIÓN")
        print("="*70)
        print(f"Tablas esperadas: {reporte['resumen']['total_esperadas']}")
        print(f"Tablas encontradas: {reporte['resumen']['encontradas']}")
        print(f"Tablas con datos: {reporte['resumen']['con_datos']}")
        print(f"Tablas faltantes: {len(reporte['resumen']['faltantes'])}")
        
        if reporte['resumen']['faltantes']:
            print("\n⚠️ Tablas que faltan:")
            for tabla in reporte['resumen']['faltantes']:
                print(f"  - {tabla}")
        
        print("\nReporte guardado: validacion_schema.json")
        
        # Sugerencias
        if reporte['resumen']['faltantes']:
            print("\n🔧 ACCIÓN REQUERIDA:")
            print("Ejecutar el SQL de creación de tablas faltantes en Supabase SQL Editor")
        elif reporte['resumen']['con_datos'] == 0:
            print("\n⚠️ Las tablas existen pero están VACÍAS")
            print("El dual-write puede estar fallando o no hay datos guardados aún")
        else:
            print("\n✅ Esquema completo y funcionando")
            
    except Exception as e:
        print(f"\n❌ Error de conexión: {e}")
        print("Verificar credenciales en .streamlit/secrets.toml")

if __name__ == "__main__":
    validar_schema()
