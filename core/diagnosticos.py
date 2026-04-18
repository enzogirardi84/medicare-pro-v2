"""
SISTEMA DE DIAGNOSTICO DE BASE DE DATOS Y ERRORES
Verifica el estado de Supabase, tablas SQL y datos locales.
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


# Tablas SQL que NextGen creo - verificamos su existencia y schema
TABLAS_SQL = [
    "empresas",
    "pacientes",
    "evoluciones",
    "indicaciones",
    "signos_vitales",
    "cuidados_enfermeria",
    "auditoria_legal",
    "turnos",
    "estudios",
    "usuarios",
    "medicare_db",
]

# Columnas esperadas por tabla (las que el codigo usa)
COLUMNAS_ESPERADAS = {
    "empresas":           ["id", "nombre"],
    "pacientes":          ["id", "empresa_id", "nombre_completo", "dni", "estado"],
    "evoluciones":        ["id", "paciente_id", "nota", "firma_medico", "fecha_registro"],
    "indicaciones":       ["id", "paciente_id", "medicamento", "estado"],
    "signos_vitales":     ["id", "paciente_id", "fecha_registro"],
    "cuidados_enfermeria":["id", "paciente_id", "fecha_registro"],
    "auditoria_legal":    ["id", "empresa_id", "fecha_evento"],
    "turnos":             ["id", "empresa_id", "fecha_hora_programada"],
    "medicare_db":        ["id", "tenant_key", "datos"],
}


def diagnosticar_supabase() -> Dict[str, Any]:
    """
    Realiza un diagnostico completo del estado de Supabase y las tablas SQL.
    Devuelve un dict con resultados detallados.
    """
    resultado = {
        "timestamp": datetime.now().isoformat(),
        "conexion_ok": False,
        "error_conexion": None,
        "tablas": {},
        "empresas_registradas": [],
        "medicare_db_rows": 0,
        "local_data_ok": False,
        "local_data_path": None,
        "local_data_size_kb": 0,
    }

    # --- 1. Verificar conexion ---
    try:
        from core.database import supabase
        if not supabase:
            resultado["error_conexion"] = "Cliente Supabase no inicializado (verificar SUPABASE_URL y SUPABASE_KEY en secrets)"
            return resultado
        resultado["conexion_ok"] = True
    except Exception as e:
        resultado["error_conexion"] = str(e)
        return resultado

    # --- 2. Verificar cada tabla ---
    for tabla in TABLAS_SQL:
        info = {"existe": False, "filas": 0, "columnas_ok": True, "columnas_faltantes": [], "error": None}
        try:
            resp = supabase.table(tabla).select("*").limit(1).execute()
            info["existe"] = True
            # Contar filas (Supabase no tiene COUNT directo sin head=True)
            try:
                resp_count = supabase.table(tabla).select("id", count="exact").execute()
                info["filas"] = resp_count.count if hasattr(resp_count, "count") and resp_count.count is not None else len(resp_count.data or [])
            except Exception:
                info["filas"] = len(resp.data or [])
            # Verificar columnas
            if resp.data:
                cols_presentes = set(resp.data[0].keys())
                cols_esperadas = set(COLUMNAS_ESPERADAS.get(tabla, []))
                faltantes = cols_esperadas - cols_presentes
                if faltantes:
                    info["columnas_ok"] = False
                    info["columnas_faltantes"] = list(faltantes)
        except Exception as e:
            err_str = str(e)
            if "does not exist" in err_str or "relation" in err_str:
                info["existe"] = False
                info["error"] = "Tabla no existe en Supabase"
            else:
                info["error"] = err_str
        resultado["tablas"][tabla] = info

    # --- 3. Leer empresas registradas ---
    try:
        resp_emp = supabase.table("empresas").select("id,nombre").execute()
        resultado["empresas_registradas"] = [
            {"id": e.get("id", ""), "nombre": e.get("nombre", "")}
            for e in (resp_emp.data or [])
        ]
    except Exception as e:
        resultado["empresas_registradas"] = [{"error": str(e)}]

    # --- 4. Contar filas de medicare_db ---
    try:
        resp_mdb = supabase.table("medicare_db").select("id", count="exact").execute()
        resultado["medicare_db_rows"] = resp_mdb.count if hasattr(resp_mdb, "count") and resp_mdb.count is not None else len(resp_mdb.data or [])
    except Exception as e:
        resultado["medicare_db_rows"] = f"Error: {e}"

    # --- 5. Verificar archivo local ---
    local_path = Path(".streamlit/local_data.json")
    resultado["local_data_path"] = str(local_path.absolute())
    if local_path.exists():
        resultado["local_data_ok"] = True
        resultado["local_data_size_kb"] = round(local_path.stat().st_size / 1024, 1)
    
    return resultado


def diagnosticar_empresa_en_supabase(nombre_empresa: str) -> Dict[str, Any]:
    """
    Verifica si una empresa existe en Supabase y puede guardar pacientes.
    Este es el punto de falla mas comun.
    """
    resultado = {
        "nombre_empresa": nombre_empresa,
        "empresa_encontrada": False,
        "empresa_id": None,
        "puede_guardar_pacientes": False,
        "error": None
    }
    try:
        from core.database import supabase
        if not supabase:
            resultado["error"] = "Sin conexion a Supabase"
            return resultado
        
        resp = supabase.table("empresas").select("id,nombre").eq("nombre", nombre_empresa).execute()
        if resp.data:
            resultado["empresa_encontrada"] = True
            resultado["empresa_id"] = resp.data[0]["id"]
            resultado["puede_guardar_pacientes"] = True
        else:
            resultado["error"] = (
                f"La empresa '{nombre_empresa}' NO existe en la tabla 'empresas' de Supabase. "
                "Los pacientes NO pueden guardarse en las tablas SQL (solo en medicare_db JSON blob)."
            )
    except Exception as e:
        resultado["error"] = str(e)
    return resultado


def insertar_empresa_en_supabase(nombre_empresa: str) -> Dict[str, Any]:
    """
    Inserta una empresa en la tabla empresas de Supabase si no existe.
    Retorna el resultado de la operación.
    """
    resultado = {
        "nombre_empresa": nombre_empresa,
        "insertado": False,
        "empresa_id": None,
        "error": None
    }
    try:
        from core.database import supabase
        if not supabase:
            resultado["error"] = "Sin conexion a Supabase"
            return resultado
        
        # Verificar si ya existe
        resp = supabase.table("empresas").select("id,nombre").eq("nombre", nombre_empresa).execute()
        if resp.data:
            resultado["insertado"] = True
            resultado["empresa_id"] = resp.data[0]["id"]
            resultado["error"] = "La empresa ya existe en Supabase"
            return resultado
        
        # Insertar la empresa
        insert_resp = supabase.table("empresas").insert({"nombre": nombre_empresa}).execute()
        if insert_resp.data:
            resultado["insertado"] = True
            resultado["empresa_id"] = insert_resp.data[0]["id"]
        else:
            resultado["error"] = "No se pudo insertar la empresa (respuesta vacía)"
    except Exception as e:
        resultado["error"] = str(e)
    return resultado


def obtener_schema_tabla(tabla: str) -> Dict[str, Any]:
    """Obtiene el schema real de una tabla en Supabase leyendo la primera fila."""
    resultado = {"tabla": tabla, "columnas": [], "muestra": None, "error": None}
    try:
        from core.database import supabase
        if not supabase:
            resultado["error"] = "Sin conexion"
            return resultado
        resp = supabase.table(tabla).select("*").limit(1).execute()
        if resp.data:
            resultado["columnas"] = list(resp.data[0].keys())
            resultado["muestra"] = resp.data[0]
        else:
            resultado["columnas"] = []
            resultado["error"] = "Tabla vacia - no se puede determinar schema"
    except Exception as e:
        resultado["error"] = str(e)
    return resultado
