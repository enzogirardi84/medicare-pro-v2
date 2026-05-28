"""AutoHeal — Sistema autónomo de análisis, corrección y testing para MediCare PRO.
Escanea código en busca de:
  - NoneType crashes (.get(key)[:N], subíndices sin guard)
  - UnboundLocalError (imports locales que sombrean globales)
  - st.error() sin log_event()
  - unsafe_allow_html=True sin html.escape()
  - Falta de verify_patient_access() en vistas con paciente_sel
  - Archivos sin tests unitarios

Modo de uso:
  python scripts/autoheal.py                           # Escanear + reportar
  python scripts/autoheal.py --fix                      # Escanear + corregir automático
  python scripts/autoheal.py --fix --create-tests       # + crear tests faltantes
  python scripts/autoheal.py --ci                       # Modo CI: exit 1 si hay issues
"""
from __future__ import annotations

import ast
import importlib
import inspect
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

# ── Configuración ─────────────────────────────────────────────────────

VIEWS_DIR = REPO_ROOT / "views"
CORE_DIR = REPO_ROOT / "core"
TESTS_DIR = REPO_ROOT / "tests"
IGNORE_DIRS = {"__pycache__", ".git", ".venv", "venv", "env", "node_modules"}

SEVERITY_COLORS = {
    "CRITICAL": "\033[91m",  # Red
    "HIGH": "\033[93m",      # Yellow
    "MEDIUM": "\033[94m",    # Blue
    "LOW": "\033[90m",       # Gray
    "OK": "\033[92m",        # Green
    "END": "\033[0m",
}

# ═══════════════════════════════════════════════════════════════════════
#  ESCÁNERES
# ═══════════════════════════════════════════════════════════════════════


class Finding:
    def __init__(self, file_path: str, line: int, severity: str, message: str, code: str = "", auto_fix: bool = False):
        self.file_path = file_path
        self.line = line
        self.severity = severity
        self.message = message
        self.code = code
        self.auto_fix = auto_fix

    def __repr__(self):
        color = SEVERITY_COLORS.get(self.severity, "")
        end = SEVERITY_COLORS["END"]
        return f"{color}[{self.severity}]{end} {self.file_path}:{self.line} — {self.message}"


class Scanner:
    """Escáner base. Cada método scan_* retorna una lista de Findings."""

    def __init__(self, fix: bool = False, create_tests: bool = False):
        self.fix = fix
        self.create_tests = create_tests
        self.findings: list[Finding] = []
        self.fixes_applied: int = 0

    def scan_file(self, filepath: Path):
        """Ejecuta todos los escáneres sobre un archivo."""
        rel = filepath.relative_to(REPO_ROOT).as_posix()
        content = filepath.read_text(encoding="utf-8")
        lines = content.split("\n")

        self._scan_get_key_slice(rel, content, lines)
        self._scan_unbound_local(rel, content, lines)
        self._scan_st_error_no_log(rel, content, lines)
        self._scan_unsafe_html_no_escape(rel, content, lines)
        self._scan_missing_verify_access(rel, content, lines)
        self._scan_subscript_in_loop(rel, content, lines)

    def _scan_get_key_slice(self, rel: str, content: str, lines: list[str]):
        """Busca .get("key", default)[:N] que crashea si key existe con None."""
        pattern = re.compile(r'\.(get)\(["\'](\w+)["\'],\s*["\']([^"\']*)["\']\)\[:(\d+)\]')
        for match in pattern.finditer(content):
            line_no = content[: match.start()].count("\n") + 1
            line_text = lines[line_no - 1].strip()
            key = match.group(2)
            self.findings.append(Finding(
                rel, line_no, "HIGH",
                f".get('{key}', ...)[:N] puede crash si key existe con None -> usar (d.get('{key}') or default)[:N]",
                code=line_text, auto_fix=True,
            ))

    def _scan_unbound_local(self, rel: str, content: str, lines: list[str]):
        """Busca funciones con import local de log_event que sombrea el global."""
        lines_with_local_import = set()
        func_defs: list[tuple[int, str]] = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r'^\s*from\s+core\.app_logging\s+import\s+log_event', stripped) and not line.startswith(" "):
                continue  # top-level import, ok
            if re.match(r'^\s*from\s+core\.app_logging\s+import\s+log_event', stripped) and line.startswith(" "):
                lines_with_local_import.add(i + 1)

        if not lines_with_local_import:
            return

        # Encontrar usos de log_event antes de la línea del import local
        for import_line in sorted(lines_with_local_import):
            for i in range(import_line - 20, import_line):
                if i < 0:
                    continue
                stripped = lines[i].strip()
                if stripped.startswith("log_event("):
                    func_name = self._find_function_name(lines, i)
                    self.findings.append(Finding(
                        rel, i + 1, "CRITICAL",
                        f"UnboundLocalError: log_event usado en línea {i+1} antes del import local en línea {import_line} en función '{func_name}'",
                        code=stripped, auto_fix=True,
                    ))

    def _scan_st_error_no_log(self, rel: str, content: str, lines: list[str]):
        """Busca st.error() sin log_event() cerca."""
        for i, line in enumerate(lines):
            if "st.error(" not in line:
                continue
            has_log = False
            for j in range(max(0, i - 10), i):
                if "log_event(" in lines[j]:
                    has_log = True
                    break
            for j in range(i + 1, min(len(lines), i + 10)):
                if "log_event(" in lines[j]:
                    has_log = True
                    break
            if not has_log:
                self.findings.append(Finding(
                    rel, i + 1, "HIGH",
                    "st.error() sin log_event() cerca",
                    code=line.strip(), auto_fix=False,
                ))

    def _scan_unsafe_html_no_escape(self, rel: str, content: str, lines: list[str]):
        """Busca unsafe_allow_html=True con f-strings que no usan html.escape."""
        for i, line in enumerate(lines):
            if "unsafe_allow_html=True" not in line:
                continue
            # Buscar f-string con variables
            if re.search(r'["\'].*\{.*\}.*["\']', line):
                # Verificar si usa safe_markdown o html.escape
                if "safe_markdown" not in line and "html.escape" not in line:
                    self.findings.append(Finding(
                        rel, i + 1, "HIGH",
                        "unsafe_allow_html=True con f-string sin html.escape() — posible XSS",
                        code=line.strip(), auto_fix=False,
                    ))

    def _scan_missing_verify_access(self, rel: str, content: str, lines: list[str]):
        """Busca vistas que reciben paciente_sel pero no llaman verify_patient_access."""
        if "paciente_sel" not in content and "paciente_id" not in content:
            return
        if "verify_patient_access" in content or "require_patient_access" in content:
            return
        if "def render_" in content:
            self.findings.append(Finding(
                rel, 0, "CRITICAL",
                "Vista recibe paciente_sel pero no llama verify_patient_access() — riesgo IDOR",
                auto_fix=False,
            ))

    def _scan_subscript_in_loop(self, rel: str, content: str, lines: list[str]):
        """Busca for i in X: ... i["key"] sin guard None."""
        for i, line in enumerate(lines):
            stripped = line.strip()
            m = re.match(r'for\s+(\w+)\s+in\s+', stripped)
            if not m:
                continue
            var = m.group(1)
            # Buscar i["key"] en las siguientes líneas dentro del mismo bloque
            j = i + 1
            while j < len(lines) and j < i + 15 and (lines[j].startswith("    ") or lines[j].strip() == ""):
                if re.search(rf'\b{var}\s*\[["\']', lines[j]) and "if " + var + " is None" not in content:
                    self.findings.append(Finding(
                        rel, j + 1, "MEDIUM",
                        f"Acceso subíndice {var}['key'] en bucle sin guard None",
                        code=lines[j].strip(), auto_fix=False,
                    ))
                    break
                j += 1

    def _find_function_name(self, lines: list[str], line_idx: int) -> str:
        for i in range(line_idx - 1, -1, -1):
            m = re.match(r'def\s+(\w+)', lines[i])
            if m:
                return m.group(1)
        return "desconocida"


# ═══════════════════════════════════════════════════════════════════════
#  GENERADOR DE TESTS
# ═══════════════════════════════════════════════════════════════════════


def generate_test_for_module(module_path: Path) -> Optional[str]:
    """Genera un test unitario básico para un módulo dado."""
    rel = module_path.relative_to(REPO_ROOT)
    module_name = str(rel.with_suffix("")).replace(os.sep, ".")

    # Derivar el test path
    if module_path.parent.name == "core":
        test_name = f"test_{module_path.stem}.py"
        test_path = TESTS_DIR / test_name
    elif module_path.parent.name == "views":
        test_name = f"test_{module_path.stem}.py"
        test_path = TESTS_DIR / test_name
    else:
        test_path = TESTS_DIR / module_path.parent.name / f"test_{module_path.stem}.py"

    if test_path.exists():
        return None  # ya existe

    # Parsear funciones públicas
    try:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return None

    funcs = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")]

    if not funcs:
        # Test de importación mínimo
        test_content = f'''"""Tests para {module_name}."""
from __future__ import annotations


def test_{module_path.stem}_importable():
    import {module_name}
    assert {module_name} is not None
'''
    else:
        fns = "\n".join(f'    assert callable({module_name}.{f.name})' for f in funcs[:5])
        test_content = f'''"""Tests para {module_name}."""
from __future__ import annotations

import pytest


class Test{module_path.stem.title().replace("_", "")}:
    """Tests para funciones públicas de {module_name}."""

    def test_{module_path.stem}_importable(self):
        import {module_name}
        assert {module_name} is not None

    def test_functions_exist(self):
        import {module_name}
{chr(10).join(f'        assert callable({module_name}.{f.name})' for f in funcs[:10])}
'''
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text(test_content, encoding="utf-8")
    return str(test_path)


# ═══════════════════════════════════════════════════════════════════════
#  REPORTE
# ═══════════════════════════════════════════════════════════════════════


def print_report(findings: list[Finding]):
    """Imprime reporte formateado por severidad."""
    by_severity: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_severity[f.severity].append(f)

    total = len(findings)
    print(f"\n{'=' * 60}")
    print(f"  📊 REPORTE AUTOMÁTICO — {datetime.now():%Y-%m-%d %H:%M}")
    print(f"  Total hallazgos: {total}")
    print(f"{'=' * 60}\n")

    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        items = by_severity.get(sev, [])
        if not items:
            continue
        color = SEVERITY_COLORS.get(sev, "")
        end = SEVERITY_COLORS["END"]
        print(f"  {color}▶ {sev}: {len(items)} hallazgo(s){end}")
        print(f"  {'─' * 56}")
        for f in items:
            print(f"    {color}•{end} {f.file_path}:{f.line}")
            if f.code:
                print(f"      {f.code[:100]}")
        print()

    # Resumen
    crit_count = len(by_severity.get("CRITICAL", []))
    high_count = len(by_severity.get("HIGH", []))
    if crit_count > 0 or high_count > 0:
        print(f"  ⚠️  {crit_count} críticos, {high_count} altos — revisar antes de producción")
    else:
        print(f"  ✅ Sin issues críticos ni altos")
    print()


# ═══════════════════════════════════════════════════════════════════════
#  AUTO-FIX
# ═══════════════════════════════════════════════════════════════════════


def apply_fixes(findings: list[Finding]) -> int:
    """Aplica correcciones automáticas para hallazgos con auto_fix=True."""
    fixes = 0
    for f in findings:
        if not f.auto_fix:
            continue
        filepath = REPO_ROOT / f.file_path
        if not filepath.exists():
            continue

        content = filepath.read_text(encoding="utf-8")
        lines = content.split("\n")
        if f.line < 1 or f.line > len(lines):
            continue

        # Fix .get("key", default)[:N] → (d.get("key") or default)[:N]
        pattern = re.compile(r'\.(get)\(["\'](\w+)["\'],\s*["\']([^"\']*)["\']\)\[:(\d+)\]')
        new_content = pattern.sub(r'.get("\2") or "\3")[:(\4]', content)
        # Revertir el replace incorrecto — es más simple reemplazar exacto
        old_line = lines[f.line - 1]
        m = re.search(r"\.get\([\"'](\w+)[\"'],\s*[\"']([^\"']*)[\"']\)\[:(\d+)\]", old_line)
        if m:
            key, default, count = m.group(1), m.group(2), m.group(3)
            new_line = old_line.replace(
                f'.get("{key}", "{default}")[:{count}]',
                f'({m.string.split(".get")[0].strip()}.get("{key}") or "{default}")[:{count}]',
            )
            if new_line == old_line:
                # Try single quotes
                new_line = old_line.replace(
                    f".get('{key}', '{default}')[:{count}]",
                    f"({m.string.split('.get')[0].strip()}.get('{key}') or '{default}')[:{count}]",
                )

            if new_line != old_line:
                lines[f.line - 1] = new_line
                filepath.write_text("\n".join(lines), encoding="utf-8")
                fixes += 1
                print(f"  🔧 Fixed: {f.file_path}:{f.line}")

    return fixes


# ═══════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════


def run_tests() -> tuple[int, int]:
    """Ejecuta tests y retorna (passed, failed)."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short", "-k", "not e2e and not stress"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    passed = result.stdout.count("PASSED") + result.stdout.count("passed")
    failed = result.stdout.count("FAILED") + result.stdout.count("failed")
    return passed, failed


def main():
    import argparse

    parser = argparse.ArgumentParser(description="AutoHeal — Analiza, corrige y testea MediCare PRO")
    parser.add_argument("--fix", action="store_true", help="Aplicar correcciones automáticas")
    parser.add_argument("--create-tests", action="store_true", help="Crear tests para módulos sin cobertura")
    parser.add_argument("--ci", action="store_true", help="Modo CI: exit 1 si hay issues críticos")
    parser.add_argument("--path", type=str, default="", help="Archivo o directorio específico a escanear")
    parser.add_argument("--run-tests", action="store_true", help="Ejecutar test suite al final")
    args = parser.parse_args()

    scanner = Scanner(fix=args.fix, create_tests=args.create_tests)

    # Determinar archivos a escanear
    if args.path:
        target = REPO_ROOT / args.path
        files = [target] if target.is_file() else list(target.rglob("*.py"))
    else:
        files = list(VIEWS_DIR.rglob("*.py")) + list(CORE_DIR.rglob("*.py"))

    # Excluir ignorados
    files = [f for f in files if not any(ign in f.parts for ign in IGNORE_DIRS)]

    print(f"🔍 Escaneando {len(files)} archivos...")
    t0 = time.time()

    for f in files:
        scanner.scan_file(f)

    elapsed = time.time() - t0

    # Mostrar reporte
    print_report(scanner.findings)

    # Crear tests faltantes
    tests_created = 0
    if args.create_tests:
        print("📝 Creando tests faltantes...")
        for f in files:
            test_path = generate_test_for_module(f)
            if test_path:
                print(f"  ✅ Test creado: {test_path}")
                tests_created += 1
        if tests_created == 0:
            print("  ✅ Todos los módulos ya tienen tests")
        print()

    # Aplicar fixes
    if args.fix:
        print("🔧 Aplicando correcciones automáticas...")
        fixes = apply_fixes(scanner.findings)
        print(f"  {fixes} corrección(es) aplicada(s)\n")

    # Tests
    if args.run_tests:
        print("🧪 Ejecutando test suite...")
        passed, failed = run_tests()
        print(f"  ✅ {passed} passed, ❌ {failed} failed\n")

    print(f"⏱️  Escaneo completado en {elapsed:.2f}s")

    # CI mode
    if args.ci:
        crit = sum(1 for f in scanner.findings if f.severity == "CRITICAL")
        high = sum(1 for f in scanner.findings if f.severity == "HIGH")
        if crit > 0:
            print(f"\n❌ CI FAILED: {crit} hallazgos críticos")
            sys.exit(1)
        if high > 5:
            print(f"\n❌ CI FAILED: {high} hallazgos altos (límite 5)")
            sys.exit(1)
        print("\n✅ CI PASSED")


if __name__ == "__main__":
    main()
