"""AUTO-FIX - Corrige automaticamente problemas comunes detectados por auto_healing.py
Ejecutar: python scripts/auto_fix.py
"""
import ast
import json
import re
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

def log(msg):
    print(f"[{datetime.now().isoformat()}] {msg}")

# ============================================================
# 1. AUTO-FIX: use_container_width -> width (si quedaron)
# ============================================================
def fix_use_container_width() -> list:
    """Reemplaza use_container_width=True/False por width='stretch'/'content'"""
    fixes = []
    for py in REPO.rglob("*.py"):
        rel = py.relative_to(REPO)
        if any(p in rel.parts for p in [".git", "nextgen_platform", "_gestion_ganadera_senasa_work"]):
            continue
        texto = py.read_text(encoding="utf-8", errors="replace")
        if "use_container_width" not in texto:
            continue
        nuevo = texto.replace("use_container_width=True", "width='stretch'")
        nuevo = nuevo.replace("use_container_width=False", "width='content'")
        if nuevo != texto:
            py.write_text(nuevo, encoding="utf-8")
            fixes.append(str(rel))
    return fixes

# ============================================================
# 2. AUTO-FIX: Spanish keywords en codigo (importar, intentar)
# ============================================================
def fix_spanish_keywords() -> list:
    """Detecta palabras clave en espanol usadas como identificadores."""
    fixes = []
    spanish = ["importar", "intentar", "Lista[", "Dict[", "definicion"]
    for py in REPO.rglob("*.py"):
        rel = py.relative_to(REPO)
        if any(p in rel.parts for p in [".git", "nextgen_platform", "_gestion_ganadera_senasa_work"]):
            continue
        texto = py.read_text(encoding="utf-8", errors="replace")
        # Solo revisar fuera de strings y comentarios
        try:
            tree = ast.parse(texto)
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id in spanish:
                    fixes.append(f"{rel}:{node.lineno}: {node.id}")
        except SyntaxError:
            pass
    return fixes

# ============================================================
# 3. AUTO-FIX: Lineas muy largas (>120 chars)
# ============================================================
def fix_long_lines(max_line=120) -> list:
    """Reporta lineas demasiado largas (no las corrige, solo reporta)."""
    report = []
    for py in REPO.rglob("*.py"):
        rel = py.relative_to(REPO)
        if any(p in rel.parts for p in [".git", "nextgen_platform", "_gestion_ganadera_senasa_work"]):
            continue
        lines = py.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines, 1):
            if len(line) > max_line:
                report.append(f"{rel}:{i}: {len(line)} chars")
                if len(report) > 50:
                    return report
    return report

# ============================================================
# 4. AUTO-FIX: Espacios en blanco al final de linea
# ============================================================
def fix_trailing_whitespace() -> list:
    """Elimina espacios en blanco al final de cada linea."""
    fixes = []
    for py in REPO.rglob("*.py"):
        rel = py.relative_to(REPO)
        if any(p in rel.parts for p in [".git", "nextgen_platform", "_gestion_ganadera_senasa_work"]):
            continue
        lines = py.read_text(encoding="utf-8").splitlines(keepends=True)
        new_lines = []
        changed = False
        for line in lines:
            stripped = line.rstrip() + "\n"
            if stripped != line:
                changed = True
            new_lines.append(stripped)
        if changed:
            py.write_text("".join(new_lines), encoding="utf-8")
            fixes.append(str(rel))
    return fixes

# ============================================================
# 5. METRICAS DE CODIGO
# ============================================================
def code_metrics() -> dict:
    """Genera metricas del codigo fuente."""
    total_lines = 0
    total_files = 0
    total_classes = 0
    total_functions = 0
    for py in REPO.rglob("*.py"):
        rel = py.relative_to(REPO)
        if any(p in rel.parts for p in [".git", "nextgen_platform", "_gestion_ganadera_senasa_work"]):
            continue
        total_files += 1
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
            total_lines += len(py.read_text(encoding="utf-8").splitlines())
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    total_classes += 1
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    total_functions += 1
        except SyntaxError:
            pass
    return {
        "archivos_py": total_files,
        "lineas_codigo": total_lines,
        "clases": total_classes,
        "funciones": total_functions,
        "timestamp": datetime.now().isoformat(),
    }

# ============================================================
# 6. ACTUALIZACION DE DEPENDENCIAS (reporte)
# ============================================================
def check_dependencies() -> list:
    """Verifica versiones de dependencias vs lo instalado."""
    report = []
    req_path = REPO / "requirements.txt"
    if not req_path.exists():
        return ["requirements.txt no encontrado"]
    reqs = req_path.read_text(encoding="utf-8").splitlines()
    for req in reqs:
        req = req.strip()
        if not req or req.startswith("#"):
            continue
        if ">=" in req:
            pkg, ver = req.split(">=", 1)
            report.append(f"{pkg} minima: {ver}")
    return report

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 70)
    print("AUTO-FIX - MEDICARE PRO")
    print("=" * 70)

    log("Corrigiendo use_container_width residual...")
    f1 = fix_use_container_width()
    log(f"  {len(f1)} archivos corregidos")

    log("Buscando keywords en espanol...")
    f2 = fix_spanish_keywords()
    for item in f2:
        log(f"  POSIBLE ISSUE: {item}")

    log("Reportando lineas largas...")
    f3 = fix_long_lines()
    log(f"  {len(f3)} lineas > 120 chars")
    for item in f3[:10]:
        log(f"    {item}")

    log("Corrigiendo trailing whitespace...")
    f4 = fix_trailing_whitespace()
    log(f"  {len(f4)} archivos corregidos")

    log("Generando metricas de codigo...")
    metrics = code_metrics()
    log(f"  {metrics['archivos_py']} archivos, {metrics['lineas_codigo']} lineas")
    log(f"  {metrics['clases']} clases, {metrics['funciones']} funciones")

    log("Verificando dependencias...")
    deps = check_dependencies()
    log(f"  {len(deps)} dependencias registradas")

    # Guardar metricas
    reporte = {
        "timestamp": datetime.now().isoformat(),
        "archivos_corregidos": len(f1) + len(f4),
        "lineas_largas": len(f3),
        "metricas": metrics,
    }
    reporte_path = REPO / "scripts" / "auto_fix_report.json"
    reporte_path.write_text(json.dumps(reporte, indent=2))
    log(f"\nReporte guardado en: {reporte_path}")
