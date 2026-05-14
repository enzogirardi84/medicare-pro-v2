"""SISTEMA AUTO-HEALING - Detecta y corrige errores automaticamente.
Ejecutar: python scripts/auto_healing.py
Recomendado: Programar en GitHub Actions (cada 6h) o Task Scheduler de Windows
"""
import ast
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # Para que los imports funcionen


def log(msg: str, nivel: str = "INFO"):
    ts = datetime.now().isoformat()
    print(f"[{ts}] [{nivel}] {msg}")


# ============================================================
# 1. DETECCION DE ERRORES DE SINTAXIS
# ============================================================
def escanear_sintaxis() -> list:
    """Revisa TODOS los .py en busca de errores de sintaxis."""
    errores = []
    for py in REPO.rglob("*.py"):
        rel = py.relative_to(REPO)
        if any(p in rel.parts for p in [".git", "nextgen_platform", "_gestion_ganadera_senasa_work", "node_modules"]):
            continue
        try:
            ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError as e:
            errores.append(f"{rel}:{e.lineno}: {e.msg}")
    return errores


# ============================================================
# 2. DETECCION DE IMPORTS ROTOS
# ============================================================
def escanear_imports() -> list:
    """Verifica que todos los imports de views/ y core/ funcionen."""
    errores = []
    # Solo verificar archivos que no dependen de streamlit
    for py in sorted((REPO / "core").glob("*.py")):
        if py.name.startswith("_") or py.name in ["ai_assistant.py", "auth.py", "database.py", "app_navigation.py"]:
            continue  # dependen de streamlit/supabase
        rel = py.relative_to(REPO)
        try:
            mod_name = f"core.{py.stem}"
            __import__(mod_name)
        except Exception as e:
            errores.append(f"{rel}: {type(e).__name__}: {str(e)[:80]}")
    for py in sorted((REPO / "views").glob("*.py")):
        if py.name.startswith("_"):
            continue  # views privadas dependen de streamlit
        rel = py.relative_to(REPO)
        try:
            mod_name = f"views.{py.stem}"
            __import__(mod_name)
        except Exception as e:
            errores.append(f"{rel}: {type(e).__name__}: {str(e)[:80]}")
    return errores


# ============================================================
# 3. VERIFICACION DE ARCHIVOS FALTANTES
# ============================================================
def verificar_archivos_criticos() -> list:
    """Verifica que archivos esenciales existan."""
    criticos = [
        "main.py", "main_medicare.py", "requirements.txt",
        "core/auth.py", "core/database.py", "core/app_navigation.py",
        "core/app_logging.py", "core/app_theme.py", "core/view_registry.py",
    ]
    faltantes = []
    for archivo in criticos:
        if not (REPO / archivo).exists():
            faltantes.append(f"ARCHIVO FALTANTE: {archivo}")
    return faltantes


# ============================================================
# 4. VERIFICACION DE LICENCIA / SECRETS EXPUESTOS
# ============================================================
def escanear_secrets() -> list:
    """Busca secrets expuestos en el codigo."""
    alertas = []
    patrones = [
        "sb_secret_", "sk-", "ghp_", "xoxb-", "xoxp-",
        "SUPABASE_SERVICE_ROLE_KEY", "api_key", "API_KEY",
    ]
    for py in REPO.rglob("*.py"):
        rel = py.relative_to(REPO)
        if any(p in rel.parts for p in [".git", "nextgen_platform", "_gestion_ganadera_senasa_work"]):
            continue
        texto = py.read_text(encoding="utf-8", errors="replace")
        for patron in patrones:
            if patron in texto:
                # Permitir archivos de test/seguridad
                if "test_security" in str(rel) or "security_checklist" in str(rel) or "security_middleware" in str(rel):
                    continue
                alertas.append(f"SECRET EXPUESTO: {rel} contiene '{patron}'")
    return alertas


# ============================================================
# 5. DETECCION DE ARCHIVOS BASURA (logs, backups viejos)
# ============================================================
def limpiar_archivos_temporales() -> list:
    """Limpia archivos temporales y backups viejos."""
    limpiados = []
    for f in (REPO / ".streamlit").glob("backup_*.json"):
        edad = time.time() - f.stat().st_mtime
        if edad > 86400:  # >24h
            dest = REPO / "_backups_legacy" / "streamlit" / f.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.rename(str(f), str(dest))
            limpiados.append(f"Backup movido: {f.name}")
    for f in (REPO / ".streamlit").glob("strong_recovery_*.json"):
        edad = time.time() - f.stat().st_mtime
        if edad > 86400:
            dest = REPO / "_backups_legacy" / "streamlit" / f.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.rename(str(f), str(dest))
            limpiados.append(f"Recovery movido: {f.name}")
    for f in REPO.glob("*.log"):
        if f.stat().st_size > 10 * 1024 * 1024:
            f.unlink()
            limpiados.append(f"Log >10MB eliminado: {f.name}")
    return limpiados


# ============================================================
# 6. VERIFICACION DE DEPENDENCIAS (requirements.txt vs instaladas)
# ============================================================
def verificar_dependencias() -> list:
    """Verifica que todas las dependencias esten instaladas."""
    alertas = []
    req_path = REPO / "requirements.txt"
    if not req_path.exists():
        return ["requirements.txt no encontrado"]
    reqs = req_path.read_text(encoding="utf-8").splitlines()
    for req in reqs:
        req = req.strip()
        if not req or req.startswith("#"):
            continue
        pkg = req.split(">=")[0].split("==")[0].split("[")[0].strip()
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            alertas.append(f"Dependencia faltante: {pkg}")
    return alertas


# ============================================================
# 7. OPTIMIZACION - Reducir payload session_state
# ============================================================
def optimizar_session_state() -> list:
    """Simula optimizacion de session_state (solo reporta)."""
    sugerencias = []
    data_path = REPO / ".streamlit" / "local_data.json"
    if data_path.exists():
        size_mb = data_path.stat().st_size / (1024 * 1024)
        if size_mb > 5:
            sugerencias.append(f"local_data.json: {size_mb:.1f}MB - considerar limpieza")
    return sugerencias


# ============================================================
# MAIN - REPORTE COMPLETO
# ============================================================
if __name__ == "__main__":
    print("=" * 70)
    print("SISTEMA AUTO-HEALING - MEDICARE PRO")
    print("=" * 70)

    resultados = {}

    log("Escaneando sintaxis...")
    resultados["errores_sintaxis"] = escanear_sintaxis()

    log("Verificando imports...")
    resultados["errores_imports"] = escanear_imports()

    log("Verificando archivos criticos...")
    resultados["archivos_faltantes"] = verificar_archivos_criticos()

    log("Escaneando secrets expuestos...")
    resultados["secrets_expuestos"] = escanear_secrets()

    log("Limpiando archivos temporales...")
    resultados["archivos_limpiados"] = limpiar_archivos_temporales()

    log("Verificando dependencias...")
    resultados["dependencias_faltantes"] = verificar_dependencias()

    log("Analizando optimizacion...")
    resultados["sugerencias_optimizacion"] = optimizar_session_state()

    # Reporte
    total_errores = (
        len(resultados["errores_sintaxis"])
        + len(resultados["errores_imports"])
        + len(resultados["archivos_faltantes"])
        + len(resultados["secrets_expuestos"])
        + len(resultados["dependencias_faltantes"])
    )

    print(f"\n{'='*70}")
    print(f"RESUMEN: {total_errores} problemas | {len(resultados['archivos_limpiados'])} archivos limpiados")
    print(f"{'='*70}")

    for categoria, items in resultados.items():
        if not items:
            continue
        print(f"\n  [{categoria}]")
        for item in items:
            print(f"    - {item}")

    # Guardar reporte
    reporte_path = REPO / "scripts" / "auto_healing_report.json"
    reporte_path.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "resultados": {k: len(v) for k, v in resultados.items()},
        "total_problemas": total_errores,
    }, indent=2))
    print(f"\nReporte guardado en: {reporte_path}")

    # Exit code para CI
    sys.exit(1 if total_errores > 0 else 0)
