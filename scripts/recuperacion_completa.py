#!/usr/bin/env python3
"""
Script de recuperación forense completa para Medicare Pro.

Busca usuarios y pacientes en:
1. Archivos de backup existentes
2. Archivos JSON en el directorio
3. Archivos de recuperación anteriores
4. Datos locales actuales
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Aseguramos que Python encuentre los módulos del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import supabase, guardar_datos
from core.db_serialize import loads_json_any


def encontrar_archivos_json(directorio: str = ".") -> List[Path]:
    """Encuentra todos los archivos JSON recursivamente."""
    json_files = []
    
    # Directorios a excluir
    exclude_dirs = {'.git', '__pycache__', 'node_modules', '.pytest_cache'}
    
    for root, dirs, files in os.walk(directorio):
        # Filtrar directorios excluidos
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if file.endswith('.json'):
                json_files.append(Path(root) / file)
    
    return sorted(json_files, key=lambda p: p.stat().st_size, reverse=True)


def extraer_usuarios(datos: Any) -> Dict[str, Any]:
    """Extrae usuarios de estructuras de datos variadas."""
    usuarios = {}
    
    if not isinstance(datos, dict):
        return usuarios
    
    # Caso 1: Estructura directa con usuarios_db
    if 'usuarios_db' in datos and isinstance(datos['usuarios_db'], dict):
        for login, user_data in datos['usuarios_db'].items():
            if isinstance(user_data, dict) and login:
                usuarios[login] = user_data
    
    # Caso 2: Lista de usuarios
    if 'usuarios' in datos and isinstance(datos['usuarios'], list):
        for user in datos['usuarios']:
            if isinstance(user, dict):
                login = user.get('usuario_login') or user.get('login') or user.get('dni')
                if login:
                    usuarios[str(login)] = user
    
    # Caso 3: Estructura anidada en 'datos'
    if 'datos' in datos and isinstance(datos['datos'], dict):
        nested_users = extraer_usuarios(datos['datos'])
        usuarios.update(nested_users)
    
    return usuarios


def extraer_pacientes(datos: Any) -> List[Dict]:
    """Extrae pacientes de estructuras de datos variadas."""
    pacientes = []
    
    if not isinstance(datos, dict):
        return pacientes
    
    # Caso 1: Estructura directa con pacientes_db (lista)
    if 'pacientes_db' in datos and isinstance(datos['pacientes_db'], list):
        for paciente in datos['pacientes_db']:
            if isinstance(paciente, dict) and paciente.get('n'):
                pacientes.append(paciente)
    
    # Caso 2: Diccionario de pacientes por ID
    if 'detalles_pacientes_db' in datos and isinstance(datos['detalles_pacientes_db'], dict):
        for paciente_id, detalles in datos['detalles_pacientes_db'].items():
            if isinstance(detalles, dict):
                # Intentar reconstruir paciente desde detalles
                paciente = {
                    'n': detalles.get('nombre_completo', paciente_id.split(' - ')[0] if ' - ' in paciente_id else paciente_id),
                    'd': detalles.get('dni', ''),
                    'o': detalles.get('obra_social', ''),
                    'e': detalles.get('empresa', ''),
                }
                if paciente['n']:
                    pacientes.append(paciente)
    
    # Caso 3: Estructura anidada
    if 'datos' in datos and isinstance(datos['datos'], dict):
        nested_pacientes = extraer_pacientes(datos['datos'])
        pacientes.extend(nested_pacientes)
    
    # Eliminar duplicados por DNI
    seen_dnis = set()
    unique_pacientes = []
    for p in pacientes:
        dni = p.get('d', '') or p.get('dni', '')
        if dni and dni not in seen_dnis:
            seen_dnis.add(dni)
            unique_pacientes.append(p)
        elif not dni and p.get('n'):
            # Si no tiene DNI, usar nombre como key
            nombre = p.get('n', '')
            if nombre not in seen_dnis:
                seen_dnis.add(nombre)
                unique_pacientes.append(p)
    
    return unique_pacientes


def analizar_archivo(filepath: Path) -> Optional[Dict[str, Any]]:
    """Analiza un archivo JSON buscando datos de usuarios y pacientes."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        # Intentar parsear
        try:
            datos = json.loads(contenido)
        except json.JSONDecodeError:
            # Intentar con el parser flexible
            try:
                datos = loads_json_any(contenido.encode('utf-8'))
            except:
                return None
        
        usuarios = extraer_usuarios(datos)
        pacientes = extraer_pacientes(datos)
        
        if usuarios or pacientes:
            return {
                'archivo': str(filepath),
                'tamano_mb': round(filepath.stat().st_size / (1024*1024), 2),
                'usuarios_count': len(usuarios),
                'pacientes_count': len(pacientes),
                'usuarios': usuarios,
                'pacientes': pacientes,
            }
        
    except Exception as e:
        return None
    
    return None


def buscar_en_todos_los_backups() -> List[Dict[str, Any]]:
    """Busca datos en todos los archivos JSON del proyecto."""
    print("Buscando en todos los archivos JSON...")
    print("=" * 60)
    
    resultados = []
    
    # Buscar archivos JSON
    json_files = encontrar_archivos_json(".")
    
    print(f"Se encontraron {len(json_files)} archivos JSON")
    print()
    
    # Analizar cada archivo
    for i, filepath in enumerate(json_files, 1):
        if i % 10 == 0:
            print(f"  Procesando {i}/{len(json_files)}...")
        
        resultado = analizar_archivo(filepath)
        if resultado and (resultado['usuarios_count'] > 0 or resultado['pacientes_count'] > 0):
            resultados.append(resultado)
    
    # Ordenar por cantidad de datos (más usuarios primero)
    resultados.sort(key=lambda x: (x['usuarios_count'], x['pacientes_count']), reverse=True)
    
    return resultados


def fusionar_datos(resultados: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Fusiona datos de múltiples fuentes, priorizando los más completos."""
    
    usuarios_fusionados = {}
    pacientes_fusionados = []
    pacientes_por_dni = {}
    
    print("\n[FUSION] Fusionando datos de todas las fuentes...")
    print("=" * 60)
    
    for resultado in resultados:
        archivo = resultado['archivo']
        
        # Fusionar usuarios
        for login, user_data in resultado['usuarios'].items():
            if login not in usuarios_fusionados:
                usuarios_fusionados[login] = user_data
                print(f"  [+] Usuario agregado: {login}")
            else:
                # Combinar datos si el usuario ya existe
                existing = usuarios_fusionados[login]
                if isinstance(user_data, dict):
                    for key, value in user_data.items():
                        if key not in existing or not existing[key]:
                            existing[key] = value
        
        # Fusionar pacientes
        for paciente in resultado['pacientes']:
            dni = paciente.get('d', '') or paciente.get('dni', '')
            nombre = paciente.get('n', '') or paciente.get('nombre', '')
            
            key = dni if dni else nombre
            if key and key not in pacientes_por_dni:
                pacientes_fusionados.append(paciente)
                pacientes_por_dni[key] = paciente
                print(f"  [+] Paciente agregado: {nombre[:30]}...")
    
    return {
        'usuarios': usuarios_fusionados,
        'pacientes': pacientes_fusionados,
    }


def guardar_recuperacion(datos: Dict[str, Any], filename: str = None):
    """Guarda los datos recuperados en un archivo."""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recuperacion_completa_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
    
    print(f"\n[DISK] Datos guardados en: {filename}")
    return filename


def restaurar_en_local_data(datos: Dict[str, Any], solo_verificar: bool = False):
    """Restaura los datos en local_data.json."""
    
    local_file = Path('.streamlit/local_data.json')
    
    # Cargar datos actuales
    if local_file.exists():
        with open(local_file, 'r', encoding='utf-8') as f:
            actuales = json.load(f)
    else:
        actuales = {}
    
    # Contar antes
    usuarios_antes = len(actuales.get('usuarios_db', {}))
    pacientes_antes = len(actuales.get('pacientes_db', []))
    
    # Fusionar
    if 'usuarios' in datos and datos['usuarios']:
        if 'usuarios_db' not in actuales:
            actuales['usuarios_db'] = {}
        
        for login, user_data in datos['usuarios'].items():
            if login not in actuales['usuarios_db']:
                actuales['usuarios_db'][login] = user_data
    
    if 'pacientes' in datos and datos['pacientes']:
        if 'pacientes_db' not in actuales:
            actuales['pacientes_db'] = []
        
        # Agregar pacientes que no existan
        dnis_existentes = set()
        for p in actuales['pacientes_db']:
            if isinstance(p, dict):
                dnis_existentes.add(p.get('d', ''))
            elif isinstance(p, str):
                dnis_existentes.add(p)
        
        for paciente in datos['pacientes']:
            if isinstance(paciente, dict):
                dni = paciente.get('d', '')
                if dni and dni not in dnis_existentes:
                    actuales['pacientes_db'].append(paciente)
                    dnis_existentes.add(dni)
    
    # Contar después
    usuarios_despues = len(actuales['usuarios_db'])
    pacientes_despues = len(actuales['pacientes_db'])
    
    print("\nRESUMEN DE RESTAURACION:")
    print("=" * 60)
    print(f"Usuarios: {usuarios_antes} -> {usuarios_despues} (+{usuarios_despues - usuarios_antes})")
    print(f"Pacientes: {pacientes_antes} -> {pacientes_despues} (+{pacientes_despues - pacientes_antes})")
    
    if not solo_verificar:
        # Crear backup antes de modificar
        backup_name = f".streamlit/backup_antes_recuperacion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_name, 'w', encoding='utf-8') as f:
            json.dump(actuales, f, indent=2, ensure_ascii=False)
        print(f"\n[BACKUP] Backup creado: {backup_name}")
        
        # Guardar datos restaurados
        with open(local_file, 'w', encoding='utf-8') as f:
            json.dump(actuales, f, indent=2, ensure_ascii=False)
        
        print(f"\n[OK] Datos restaurados en: {local_file}")
        print("[INFO] Reinicia la aplicacion para ver los cambios")
    else:
        print("\n[INFO] Modo verificacion - No se guardaron cambios")
        print("   Usa --restaurar para aplicar los cambios")
    
    return actuales


def main():
    """Función principal de recuperación."""
    
    print("=" * 60)
    print("RECUPERACION FORENSE - Medicare Pro")
    print("=" * 60)
    print()
    
    # Verificar argumentos
    modo_verificar = '--restaurar' not in sys.argv
    
    # Buscar en todos los backups
    resultados = buscar_en_todos_los_backups()
    
    if not resultados:
        print("\n[WARNING] No se encontraron datos en ningun archivo JSON")
        print("\nSugerencias:")
        print("1. Verifica si hay archivos .bak o .backup")
        print("2. Revisa la papelera de reciclaje")
        print("3. Contacta a soporte si los datos estaban en Supabase")
        return
    
    # Mostrar resultados
    print(f"\n[OK] Se encontraron {len(resultados)} archivos con datos:")
    print("=" * 60)
    
    for i, resultado in enumerate(resultados[:10], 1):  # Mostrar top 10
        print(f"\n{i}. {resultado['archivo']}")
        print(f"   Tamaño: {resultado['tamano_mb']} MB")
        print(f"   Usuarios: {resultado['usuarios_count']}")
        print(f"   Pacientes: {resultado['pacientes_count']}")
        
        if resultado['usuarios_count'] > 0:
            usuarios_list = list(resultado['usuarios'].keys())[:5]
            print(f"   Usuarios: {', '.join(usuarios_list)}")
    
    # Fusionar datos
    datos_fusionados = fusionar_datos(resultados)
    
    # Guardar recuperación
    archivo_recuperacion = guardar_recuperacion(datos_fusionados)
    
    # Mostrar resumen de fusión
    print("\nRESUMEN DE FUSION:")
    print("=" * 60)
    print(f"Total usuarios únicos: {len(datos_fusionados['usuarios'])}")
    print(f"Total pacientes únicos: {len(datos_fusionados['pacientes'])}")
    
    if datos_fusionados['usuarios']:
        print("\nUsuarios encontrados:")
        for login in list(datos_fusionados['usuarios'].keys()):
            user_data = datos_fusionados['usuarios'][login]
            nombre = user_data.get('nombre', 'N/A') if isinstance(user_data, dict) else 'N/A'
            print(f"  - {login}: {nombre}")
    
    if datos_fusionados['pacientes']:
        print(f"\nPacientes encontrados: {len(datos_fusionados['pacientes'])}")
        for paciente in datos_fusionados['pacientes'][:5]:
            nombre = paciente.get('n', 'N/A')
            dni = paciente.get('d', 'N/A')
            print(f"  - {nombre} (DNI: {dni})")
        if len(datos_fusionados['pacientes']) > 5:
            print(f"  ... y {len(datos_fusionados['pacientes']) - 5} más")
    
    # Restaurar
    print("\n" + "=" * 60)
    if modo_verificar:
        print("\n[INFO] MODO VERIFICACION (no se guardaron cambios)")
        print("   Ejecuta con: python recuperacion_completa.py --restaurar")
    else:
        print("[WORK] RESTAURANDO DATOS...")
    
    restaurar_en_local_data(datos_fusionados, solo_verificar=modo_verificar)
    
    print("\n" + "=" * 60)
    print("[OK] Proceso completado")
    print("=" * 60)


if __name__ == "__main__":
    main()
