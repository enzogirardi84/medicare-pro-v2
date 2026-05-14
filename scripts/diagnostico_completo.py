"""
DIAGNOSTICO COMPLETO - Medicare Pro
Ejecutar: python scripts/diagnostico_completo.py
Genera reporte JSON con todos los errores encontrados.
"""
import ast
import importlib
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

REPORTE = {
    "timestamp": datetime.now().isoformat(),
    "errores": [],
    "advertencias": [],
    "ok": [],
}


def error(cat, msg, archivo=None, linea=None):
    e = {"categoria": cat, "mensaje": msg}
    if archivo: e["archivo"] = str(archivo)
    if linea: e["linea"] = linea
    REPORTE["errores"].append(e)
    print(f"  ERROR [{cat}]: {msg}")


def warning(cat, msg, archivo=None, linea=None):
    e = {"categoria": cat, "mensaje": msg}
    if archivo: e["archivo"] = str(archivo)
    if linea: e["linea"] = linea
    REPORTE["advertencias"].append(e)
    print(f"  WARN  [{cat}]: {msg}")


def ok(msg):
    REPORTE["ok"].append(msg)
    print(f"  OK    {msg}")


def escanear(patron="*.py", excluir=None):
    """Escanea archivos con un patron."""
    excluir = excluir or {".git", "nextgen_platform", "_gestion_ganadera_senasa_work",
                          "_backups_legacy", "node_modules", "__pycache__"}
    archivos = []
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in excluir]
        for f in files:
            if f.endswith(patron.replace("*", "")):
                archivos.append(Path(root) / f)
    return archivos


print("=" * 70)
print("DIAGNOSTICO COMPLETO - MEDICARE PRO")
print("=" * 70)

# ============================================================
# 1. SINTAXIS - Todos los archivos .py
# ============================================================
print("\n[1/10] VERIFICANDO SINTAXIS...")
archivos_py = escanear("*.py")
ok(f"{len(archivos_py)} archivos Python encontrados")
for py in archivos_py:
    try:
        ast.parse(py.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError as e:
        error("SINTAXIS", f"Error de sintaxis: {e.msg}", py, e.lineno)

# ============================================================
# 2. IMPORTS - Todos los modulos deben importar
# ============================================================
print("\n[2/10] VERIFICANDO IMPORTS...")
for py in sorted((REPO / "core").glob("*.py")):
    if py.name.startswith("_"):
        continue
    try:
        importlib.import_module(f"core.{py.stem}")
    except Exception as e:
        error("IMPORT", f"No se puede importar: {e}", py)

for py in sorted((REPO / "views").glob("*.py")):
    if py.name.startswith("_"):
        continue
    try:
        importlib.import_module(f"views.{py.stem}")
    except Exception as e:
        error("IMPORT", f"No se puede importar: {e}", py)

# ============================================================
# 3. MAIN - Verificar flujo de entrada
# ============================================================
print("\n[3/10] VERIFICANDO ENTRY POINT...")
if (REPO / "main.py").exists():
    ok("main.py existe")
if (REPO / "main_medicare.py").exists():
    ok("main_medicare.py existe")
if (REPO / "requirements.txt").exists():
    ok("requirements.txt existe")

# Verificar set_page_config unico
set_page_count = 0
for py in archivos_py:
    content = py.read_text(encoding="utf-8", errors="replace")
    set_page_count += content.count("set_page_config")
if set_page_count > 1:
    warning("CONFIG", f"set_page_config aparece {set_page_count} veces (deberia ser 1)")

# ============================================================
# 4. MODULOS - Verificar registro en VIEW_CONFIG
# ============================================================
print("\n[4/10] VERIFICANDO REGISTRO DE MODULOS...")
try:
    from core.view_registry import VIEW_CONFIG_BASE
    for nombre, (mod_path, func_name) in VIEW_CONFIG_BASE.items():
        try:
            mod = importlib.import_module(mod_path)
            fn = getattr(mod, func_name, None)
            if fn and callable(fn):
                ok(f"Modulo '{nombre}' -> {mod_path}.{func_name} OK")
            else:
                error("MODULO", f"Funcion '{func_name}' no encontrada en {mod_path}", Path(mod_path + ".py"))
        except Exception as e:
            error("MODULO", f"No se puede cargar '{nombre}': {e}", Path(mod_path + ".py"))
except Exception as e:
    error("CRITICO", f"No se puede leer view_registry: {e}")

# ============================================================
# 5. PERMISOS - Verificar roles
# ============================================================
print("\n[5/10] VERIFICANDO PERMISOS DE ROLES...")
try:
    from core.view_roles import MODULO_ROLES_PERMITIDOS
    for nombre in VIEW_CONFIG_BASE:
        if nombre not in MODULO_ROLES_PERMITIDOS:
            warning("PERMISOS", f"'{nombre}' no tiene roles asignados en MODULO_ROLES_PERMITIDOS")
    ok(f"{len(MODULO_ROLES_PERMITIDOS)} modulos con permisos")
except Exception as e:
    error("PERMISOS", f"Error: {e}")

# ============================================================
# 6. SECRETS - Verificar que no haya expuestos
# ============================================================
print("\n[6/10] BUSCANDO SECRETS EXPUESTOS...")
patrones_secret = ["sb_secret_", "sk-", "ghp_", "xoxb-", "xoxp-"]
for py in archivos_py:
    try:
        rel = py.relative_to(REPO)
    except ValueError:
        continue
    if any(p in str(rel) for p in ["test_security", "security_checklist", "security_middleware", "auto_healing", "diagnostico"]):
        continue
    content = py.read_text(encoding="utf-8", errors="replace")
    for patron in patrones_secret:
        if patron in content:
            warning("SECRET", f"Posible secret expuesto: '{patron}' en {rel}")

# ============================================================
# 7. CSS - Verificar balance de llaves
# ============================================================
print("\n[7/10] VERIFICANDO CSS...")
css_files = list((REPO / "core").glob("app_theme.py"))
for css_file in css_files:
    content = css_file.read_text(encoding="utf-8")
    opens = content.count("{")
    closes = content.count("}")
    if opens != closes:
        error("CSS", f"Llaves desbalanceadas: {opens} abiertas, {closes} cerradas", css_file)

# ============================================================
# 8. TEMPLATES JS - Verificar </script> en cadenas
# ============================================================
print("\n[8/10] VERIFICANDO TEMPLATES JS...")
for py in archivos_py:
    content = py.read_text(encoding="utf-8", errors="replace")
    if getattr(py, 'suffix', '.py') != '.py':
        continue
    # Buscar </script> dentro de cadenas Python
    if '</script>' in content:
        warning("JS", f"</script> encontrado en {py.relative_to(REPO)} - puede romper HTML")

# ============================================================
# 9. FILES - Archivos criticos faltantes
# ============================================================
print("\n[9/10] VERIFICANDO ARCHIVOS CRITICOS...")
criticos = [
    "main.py", "main_medicare.py", "requirements.txt",
    "core/auth.py", "core/database.py", "core/app_navigation.py",
    "core/app_logging.py", "core/app_theme.py", "core/view_registry.py",
    "core/view_roles.py", "core/seguridad_extendida.py",
    ".github/workflows/medicare-pro-ci.yml",
    "assets/logo_medicare_pro.jpeg",
]
for archivo in criticos:
    if (REPO / archivo).exists():
        ok(f"Archivo: {archivo}")
    else:
        error("CRITICO", f"Archivo faltante: {archivo}")

# ============================================================
# 10. Supabase - Verificar conexion
# ============================================================
print("\n[10/10] VERIFICANDO CONEXION SUPABASE...")
try:
    import requests
    # No podemos probar sin la key real, solo verificar que la libreria existe
    ok("requests disponible")
except:
    warning("SUPABASE", "requests no instalado")

# ============================================================
# REPORTE FINAL
# ============================================================
total_errores = len(REPORTE["errores"])
total_warns = len(REPORTE["advertencias"])
total_ok = len(REPORTE["ok"])

print(f"\n{'='*70}")
print(f"RESUMEN: {total_errores} errores, {total_warns} advertencias, {total_ok} OK")
print(f"{'='*70}")

if total_errores > 0:
    print(f"\nERRORES ({total_errores}):")
    for e in REPORTE["errores"]:
        print(f"  [{e['categoria']}] {e['mensaje']}")
        if 'archivo' in e:
            print(f"    Archivo: {e['archivo']}")

if total_warns > 0:
    print(f"\nADVERTENCIAS ({total_warns}):")
    for w in REPORTE["advertencias"]:
        print(f"  [{w['categoria']}] {w['mensaje']}")

# Guardar reporte
reporte_path = REPO / "scripts" / "diagnostico_report.json"
reporte_path.write_text(json.dumps(REPORTE, indent=2, ensure_ascii=False))
print(f"\nReporte guardado en: {reporte_path}")
