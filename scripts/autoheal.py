"""AutoHeal v3 — Sistema Autónomo Inteligente con Memoria, Auto-aprendizaje,
Análisis de Complejidad, Detección de Regresiones y Monitor de Rendimiento.

Arquitectura:
  - Memoria persistente SQLite: cada fix, error y patrón aprendido se guarda
  - Aprendizaje continuo: analiza el historial de fixes para detectar nuevos patrones
  - Monitor en tiempo real: captura errores de Streamlit/Supabase y los corrige al instante
  - Auto-mejora: refactoriza código basado en patrones históricos
  - Análisis de complejidad ciclomática: detecta funciones demasiado complejas
  - Detección de regresiones: compara tiempos de escaneo y alerta si aumentan
  - Commits automáticos descriptivos

Uso:
  python scripts/autoheal.py --daemon              # Modo eterno con memoria
  python scripts/autoheal.py --scan                # Escaneo único
  python scripts/autoheal.py --history             # Ver historial de fixes
  python scripts/autoheal.py --perf                # Ver métricas de rendimiento
"""
from __future__ import annotations

import ast
import hashlib
import html
import json
import logging
import os
import pickle
import re
import sqlite3
import subprocess
import sys
import time
import traceback
from collections import defaultdict, Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / ".autoheal_memory.db"
LOG_PATH = REPO_ROOT / "autoheal.log"
STREAMLIT_LOG = REPO_ROOT / "streamlit_errors.log"

VIEWS_DIR = REPO_ROOT / "views"
CORE_DIR = REPO_ROOT / "core"
TESTS_DIR = REPO_ROOT / "tests"
IGNORE_DIRS = {"__pycache__", ".git", ".venv", "venv", "env", "node_modules", ".pytest_cache"}

# ═══════════════════════════════════════════════════════════════════════
#  MEMORIA PERSISTENTE (SQLite)
# ═══════════════════════════════════════════════════════════════════════


class FixMemory:
    """Memoria persistente de fixes, errores y patrones aprendidos."""

    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fixes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                line INTEGER,
                severity TEXT,
                pattern_name TEXT,
                old_code TEXT,
                new_code TEXT,
                fixer TEXT,
                success INTEGER DEFAULT 1,
                timestamp TEXT NOT NULL,
                commit_hash TEXT,
                category TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_type TEXT,
                error_msg TEXT,
                file_path TEXT,
                line INTEGER,
                context TEXT,
                timestamp TEXT NOT NULL,
                resolved INTEGER DEFAULT 0,
                fix_id INTEGER REFERENCES fixes(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS learned_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_name TEXT UNIQUE NOT NULL,
                regex TEXT NOT NULL,
                fix_template TEXT,
                severity TEXT DEFAULT 'MEDIUM',
                source TEXT,
                hit_count INTEGER DEFAULT 1,
                last_hit TEXT,
                auto_fix INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scan_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_findings INTEGER,
                critical_count INTEGER,
                high_count INTEGER,
                fixes_applied INTEGER,
                tests_created INTEGER,
                tests_passed INTEGER,
                tests_failed INTEGER,
                elapsed_seconds REAL,
                commit_made INTEGER DEFAULT 0,
                timestamp TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def record_fix(self, file_path: str, line: int, severity: str, pattern: str,
                   old_code: str, new_code: str, fixer: str = "auto",
                   commit_hash: str = "", category: str = "") -> int:
        conn = self._connect()
        cur = conn.execute(
            "INSERT INTO fixes (file_path, line, severity, pattern_name, old_code, new_code, fixer, timestamp, commit_hash, category) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (file_path, line, severity, pattern, old_code[:200], new_code[:200],
             fixer, datetime.now(timezone.utc).isoformat(), commit_hash, category)
        )
        fix_id = cur.lastrowid
        conn.commit()
        conn.close()
        self._update_pattern_hit(pattern)
        return fix_id

    def record_error(self, error_type: str, error_msg: str, file_path: str = "",
                     line: int = 0, context: str = "") -> int:
        conn = self._connect()
        cur = conn.execute(
            "INSERT INTO errors (error_type, error_msg, file_path, line, context, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (error_type, error_msg[:300], file_path, line, context[:500], datetime.now(timezone.utc).isoformat())
        )
        err_id = cur.lastrowid
        conn.commit()
        conn.close()
        return err_id

    def record_scan(self, total: int, crit: int, high: int, fixes: int,
                    tests_created: int, passed: int, failed: int,
                    elapsed: float, commit: bool = False):
        conn = self._connect()
        conn.execute(
            "INSERT INTO scan_history (total_findings, critical_count, high_count, fixes_applied, "
            "tests_created, tests_passed, tests_failed, elapsed_seconds, commit_made, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (total, crit, high, fixes, tests_created, passed, failed, elapsed, int(commit),
             datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()

    def _update_pattern_hit(self, pattern_name: str):
        conn = self._connect()
        conn.execute(
            "UPDATE learned_patterns SET hit_count = hit_count + 1, last_hit = ? WHERE pattern_name = ?",
            (datetime.now(timezone.utc).isoformat(), pattern_name)
        )
        conn.commit()
        conn.close()

    def learn_pattern(self, name: str, regex: str, fix_template: str = "",
                      severity: str = "MEDIUM", source: str = "auto") -> bool:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO learned_patterns (pattern_name, regex, fix_template, severity, source, "
                "auto_fix, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (name, regex[:500], fix_template[:500], severity, source[:200],
                 datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat())
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False

    def get_stats(self) -> dict:
        conn = self._connect()
        total_fixes = conn.execute("SELECT COUNT(*) FROM fixes").fetchone()[0]
        total_errors = conn.execute("SELECT COUNT(*) FROM errors").fetchone()[0]
        total_patterns = conn.execute("SELECT COUNT(*) FROM learned_patterns").fetchone()[0]
        scans = conn.execute("SELECT COUNT(*) FROM scan_history").fetchone()[0]
        success_rate = conn.execute("SELECT AVG(success) FROM fixes WHERE success IS NOT NULL").fetchone()[0] or 0
        top_patterns = conn.execute(
            "SELECT pattern_name, COUNT(*) as c FROM fixes GROUP BY pattern_name ORDER BY c DESC LIMIT 5"
        ).fetchall()
        recent_fixes = conn.execute(
            "SELECT file_path, pattern_name, timestamp FROM fixes ORDER BY id DESC LIMIT 10"
        ).fetchall()
        conn.close()
        return {
            "total_fixes": total_fixes,
            "total_errors": total_errors,
            "total_patterns": total_patterns,
            "scans": scans,
            "success_rate": round(success_rate * 100, 1),
            "top_patterns": top_patterns,
            "recent_fixes": recent_fixes,
        }

    def find_similar_fix(self, error_msg: str) -> Optional[dict]:
        """Busca fixes previos para errores similares."""
        conn = self._connect()
        row = conn.execute(
            "SELECT f.file_path, f.pattern_name, f.old_code, f.new_code, f.fixer "
            "FROM fixes f JOIN errors e ON e.fix_id = f.id "
            "WHERE e.error_msg LIKE ? ORDER BY f.id DESC LIMIT 1",
            (f"%{error_msg[:50]}%",)
        ).fetchone()
        conn.close()
        if row:
            return {"file": row[0], "pattern": row[1], "old": row[2], "new": row[3], "fixer": row[4]}
        return None


# ═══════════════════════════════════════════════════════════════════════
#  APRENDIZAJE AUTOMÁTICO DE PATRONES
# ═══════════════════════════════════════════════════════════════════════


class PatternLearner:
    """Analiza fixes previos para aprender nuevos patrones de código vulnerable."""

    @staticmethod
    def learn_from_fix_history(memory: FixMemory) -> int:
        """Escanea el historial de fixes y aprende nuevos patrones."""
        learned = 0
        conn = memory._connect()
        rows = conn.execute(
            "SELECT old_code, new_code, pattern_name FROM fixes WHERE pattern_name LIKE 'auto_%'"
        ).fetchall()
        conn.close()

        for old, new, pattern in rows:
            if old and new:
                # Intentar extraer patrón regex de la diferencia
                diff = PatternLearner._extract_pattern(old, new)
                if diff:
                    name = f"learned_{pattern}_{datetime.now(timezone.utc).strftime('%H%M%S')}"
                    if memory.learn_pattern(name, diff["regex"], diff["fix"],
                                            severity="HIGH", source="auto_learn"):
                        learned += 1
        return learned

    @staticmethod
    def _extract_pattern(old_code: str, new_code: str) -> Optional[dict]:
        """Extrae un patrón reemplazable de un par old/new code."""
        # Patrón: .get("key", default)[:N] → (d.get("key") or default)[:N]
        m = re.search(r'\.get\(["\'](\w+)["\'],\s*["\']([^"\']*)["\']\)\[:(\d+)\]', old_code)
        if m and "(d.get" not in new_code:
            # Es un patrón de slice inseguro
            key, default, count = m.group(1), m.group(2), m.group(3)
            regex = re.escape(old_code[:80])
            fix_template = new_code[:100]
            return {"regex": regex, "fix": fix_template}
        return None

    @staticmethod
    def scan_for_new_patterns(memory: FixMemory, base_dir: Path) -> int:
        """Escanea código buscando patrones que podrían aprenderse."""
        found = 0
        for pyfile in base_dir.rglob("*.py"):
            if any(ign in pyfile.parts for ign in IGNORE_DIRS):
                continue
            content = pyfile.read_text(encoding="utf-8", errors="ignore")

            # Buscar: try: ... except: pass  (silent catch)
            for m in re.finditer(r'except\s*(?:\w+\s*)?:\s*\n\s*pass', content):
                name = f"silent_except_{pyfile.stem}"
                src = str(pyfile.relative_to(REPO_ROOT)) + "_" + str(m.start())
                if memory.learn_pattern(name, str(m.group()), severity="MEDIUM", source=src):
                    found += 1

        return found


# ═══════════════════════════════════════════════════════════════════════
#  ESCÁNERES INTELIGENTES (con memoria)
# ═══════════════════════════════════════════════════════════════════════


class Finding:
    def __init__(self, file_path: str, line: int, severity: str, message: str,
                 code: str = "", pattern: str = "", auto_fix: bool = False,
                 fix_template: str = ""):
        self.file_path = file_path
        self.line = line
        self.severity = severity
        self.message = message
        self.code = code
        self.pattern = pattern
        self.auto_fix = auto_fix
        self.fix_template = fix_template
        self.fingerprint = hashlib.md5(f"{file_path}:{line}:{message}".encode()).hexdigest()[:12]

    def __repr__(self):
        return f"[{self.severity}] {self.file_path}:{self.line} — {self.message}"


class SmartScanner:
    """Escáner con memoria: evita reportar lo mismo dos veces y aprende patrones."""

    def __init__(self, memory: FixMemory):
        self.memory = memory
        self.findings: list[Finding] = []
        self.fixes_applied = 0
        self.known_fingerprints: set[str] = set()
        self._load_known_fingerprints()

    def _load_known_fingerprints(self):
        """Carga fingerprints de fixes previos para evitar duplicados."""
        conn = self.memory._connect()
        rows = conn.execute(
            "SELECT DISTINCT file_path || ':' || line || ':' || pattern_name FROM fixes"
        ).fetchall()
        conn.close()
        for row in rows:
            fp = hashlib.md5(row[0].encode()).hexdigest()[:12]
            self.known_fingerprints.add(fp)

    def _is_known(self, finding: Finding) -> bool:
        return finding.fingerprint in self.known_fingerprints

    def _mark_as_known(self, finding: Finding):
        self.known_fingerprints.add(finding.fingerprint)

    # ── Escáneres ─────────────────────────────────────────────────

    def scan_get_key_slice(self, rel: str, content: str, lines: list[str]):
        pattern = re.compile(r'\.(get)\(["\'](\w+)["\'],\s*["\']([^"\']*)["\']\)\[:(\d+)\]')
        for match in pattern.finditer(content):
            line_no = content[:match.start()].count("\n") + 1
            line_text = lines[line_no - 1].strip()
            key = match.group(2)
            f = Finding(rel, line_no, "HIGH",
                        f".get('{key}',...)[:N] puede crash con None → (d.get('{key}') or default)[:N]",
                        code=line_text, pattern="get_key_slice", auto_fix=True)
            if not self._is_known(f):
                self.findings.append(f)

    def scan_unbound_local(self, rel: str, content: str, lines: list[str]):
        local_imports = set()
        for i, line in enumerate(lines):
            if re.match(r'^\s+from\s+core\.app_logging\s+import\s+log_event', line):
                local_imports.add(i)
        for li in local_imports:
            for i in range(max(0, li - 20), li):
                if "log_event(" in lines[i]:
                    func = self._find_func(lines, i)
                    f = Finding(rel, i + 1, "CRITICAL",
                                f"UnboundLocalError: log_event en línea {i+1} antes del import local en línea {li+1}",
                                code=lines[i].strip(), pattern="unbound_local", auto_fix=True)
                    if not self._is_known(f):
                        self.findings.append(f)

    def scan_st_error_no_log(self, rel: str, content: str, lines: list[str]):
        for i, line in enumerate(lines):
            if "st.error(" not in line:
                continue
            has_log = any("log_event(" in lines[j] for j in range(max(0, i - 10), min(len(lines), i + 10)))
            if not has_log:
                # Encontrar el modulo/nombre de archivo para el log
                _mod_name = Path(rel).stem.replace(".py", "")
                f = Finding(rel, i + 1, "HIGH", "st.error() sin log_event() cerca",
                            code=line.strip(), pattern="st_error_no_log", auto_fix=True)
                if not self._is_known(f):
                    self.findings.append(f)

    def scan_unsafe_html(self, rel: str, content: str, lines: list[str]):
        for i, line in enumerate(lines):
            if "unsafe_allow_html=True" not in line:
                continue
            if re.search(r'["\'].*\{.*\}.*["\']', line):
                if "safe_markdown" not in line and "html.escape" not in line and "escape(" not in line:
                    f = Finding(rel, i + 1, "HIGH", "unsafe_allow_html con f-string sin escape — XSS",
                                code=line.strip(), pattern="unsafe_html", auto_fix=True)
                    if not self._is_known(f):
                        self.findings.append(f)

    def scan_missing_docstrings(self, rel: str, content: str, lines: list[str]):
        """Detecta funciones publicas sin docstring."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_"):
                continue
            if (not node.body) or (not isinstance(node.body[0], ast.Expr)) or (not isinstance(node.body[0].value, (ast.Constant, ast.Str))):
                f = Finding(rel, node.lineno, "LOW",
                            f"Funcion '{node.name}' sin docstring",
                            code=lines[node.lineno - 1].strip() if node.lineno <= len(lines) else "",
                            pattern="missing_docstring", auto_fix=False)
                if not self._is_known(f):
                    self.findings.append(f)

    def scan_copy_paste_error(self, rel: str, content: str, lines: list[str]):
        """Detecta patrones de copy-paste: variable(keyword = variable.get(...))
        y variable(prompt += f"...{variable.get(...)"""
        for i, line in enumerate(lines):
            m = re.search(r'(\w+)\s*\(\s*\w+\s*=\s*\1\.', line)
            if m:
                f = Finding(rel, i + 1, "CRITICAL",
                            f"Copy-paste error: {m.group(1)}(...) mal formado → (variable.get(...))",
                            code=line.strip(), pattern="copy_paste_error", auto_fix=True)
                if not self._is_known(f):
                    self.findings.append(f)
            # Also detect: variable(prompt += f"...{variable.get(...)
            m2 = re.search(r"(\w+)\s*\(\s*\w+\s*\+?=\s*f\".*?\{\1\.get\(", line)
            if m2:
                f = Finding(rel, i + 1, "CRITICAL",
                            f"Copy-paste error: {m2.group(1)}(f-string...) con duplicación de variable",
                            code=line.strip(), pattern="copy_paste_error_fstring", auto_fix=True)
                if not self._is_known(f):
                    self.findings.append(f)

    def scan_list_index_without_guard(self, rel: str, content: str, lines: list[str]):
        """Detecta lista[0] sin verificar que la lista no está vacía."""
        for i, line in enumerate(lines):
            # Buscar pattern: variable[0] o variable[0].
            m = re.search(r'(\w+)\[0\]', line)
            if not m:
                continue
            var = m.group(1)
            # Verificar si hay un guard cerca (dentro de los 5 lines anteriores)
            guard_found = False
            for j in range(max(0, i - 5), i):
                if re.search(rf'if\s+{re.escape(var)}\b', lines[j]):
                    guard_found = True
                    break
            if not guard_found and not line.strip().startswith("#"):
                f = Finding(rel, i + 1, "HIGH",
                            f"{var}[0] sin guard de lista vacía → crash si lista vacía",
                            code=line.strip(), pattern="list_index_guard")
                if not self._is_known(f):
                    self.findings.append(f)

    def scan_subscript_loop(self, rel: str, content: str, lines: list[str]):
        for i, line in enumerate(lines):
            m = re.match(r'for\s+(\w+)\s+in\s+', line.strip())
            if not m:
                continue
            var = m.group(1)
            for j in range(i + 1, min(len(lines), i + 12)):
                if re.search(rf'\b{var}\s*\[["\']', lines[j]) and f"if {var} is None" not in content:
                    f = Finding(rel, j + 1, "MEDIUM",
                                f"Subíndice {var}['key'] en bucle sin guard None",
                                code=lines[j].strip(), pattern="subscript_loop")
                    if not self._is_known(f):
                        self.findings.append(f)
                    break

    def scan_unused_imports(self, rel: str, content: str, lines: list[str]):
        """Detecta imports que no se usan en el archivo.
        Salta archivos que son conocidos re-exportadores (utils, __init__).
        """
        if "test_" in rel or rel.endswith("__init__.py"):
            return
        # Saltar re-export hubs
        _skip_files = {"core/utils.py", "core/__init__.py"}
        if rel in _skip_files:
            return
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return

        imported_names: dict[str, tuple[int, str]] = {}
        used_names: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    imported_names[name] = (node.lineno, f"import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("_"):
                    continue
                for alias in node.names:
                    name = alias.asname or alias.name
                    imported_names[name] = (node.lineno, f"from {node.module} import {alias.name}")
            elif isinstance(node, ast.Name):
                used_names.add(node.id)

        for name, (line_no, import_line) in imported_names.items():
            if name not in used_names and name != "__future__":
                f = Finding(rel, line_no, "LOW",
                            f"Import no usado: {import_line}",
                            code=import_line, pattern="unused_import", auto_fix=True)
                if not self._is_known(f):
                    self.findings.append(f)

    def scan_dead_functions(self, rel: str, content: str, lines: list[str]):
        """Detecta funciones definidas pero nunca llamadas fuera de su propia definicion."""
        if rel.endswith("__init__.py"):
            return
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return

        funcs: dict[str, int] = {}
        calls: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                funcs[node.name] = node.lineno
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)

        for name, line_no in funcs.items():
            if name.startswith("_"):
                continue
            if name not in calls:
                f = Finding(rel, line_no, "LOW",
                            f"Funcion '{name}' definida pero nunca llamada",
                            code=lines[line_no - 1].strip() if line_no <= len(lines) else "",
                            pattern="dead_function", auto_fix=False)
                if not self._is_known(f):
                    self.findings.append(f)

    def scan_complexity(self, rel: str, content: str, lines: list[str]):
        """Detecta funciones con alta complejidad ciclomatica."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            # Contar ramificaciones (if, elif, for, while, except, and, or)
            branches = 0
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler)):
                    branches += 1
                elif isinstance(child, ast.BoolOp):
                    branches += len(child.values) - 1

            # Contar lineas
            end_line = node.end_lineno or node.lineno
            line_count = end_line - node.lineno + 1

            score = branches + line_count // 20
            if score > 15:
                f = Finding(rel, node.lineno, "MEDIUM",
                            f"Alta complejidad: '{node.name}' ({branches} ramas, {line_count} lineas, score={score})",
                            code=lines[node.lineno - 1].strip() if node.lineno <= len(lines) else "",
                            pattern="high_complexity", auto_fix=False)
                if not self._is_known(f):
                    self.findings.append(f)

    def _find_func(self, lines: list[str], idx: int) -> str:
        for i in range(idx, -1, -1):
            m = re.match(r'def\s+(\w+)', lines[i])
            if m:
                return m.group(1)
        return "?"


# ═══════════════════════════════════════════════════════════════════════
#  AUTOFIX CON MEMORIA
# ═══════════════════════════════════════════════════════════════════════


def apply_smart_fixes(scanner: SmartScanner, memory: FixMemory, commit_hash: str = "") -> int:
    """Aplica fixes y los registra en la memoria persistente."""
    fixes = 0
    for f in scanner.findings:
        if not f.auto_fix:
            continue
        filepath = REPO_ROOT / f.file_path
        if not filepath.exists():
            continue

        content = filepath.read_text(encoding="utf-8")
        lines = content.split("\n")
        if f.line < 1 or f.line > len(lines):
            continue

        old_line = lines[f.line - 1]
        new_line = old_line

        if f.pattern == "get_key_slice":
            m = re.search(r"\.(get)\([\"'](\w+)[\"'],\s*[\"']([^\"']*)[\"']\)\[:(\d+)\]", old_line)
            if m:
                key, default, count = m.group(2), m.group(3), m.group(4)
                var_part = old_line.split(".get")[0].strip()
                new_line = old_line.replace(
                    f'.get("{key}", "{default}")[:{count}]',
                    f'({var_part}.get("{key}") or "{default}")[:{count}]',
                )
                if new_line == old_line:
                    new_line = old_line.replace(
                        f".get('{key}', '{default}')[:{count}]",
                        f"({var_part}.get('{key}') or '{default}')[:{count}]",
                    )

        elif f.pattern in ("copy_paste_error", "copy_paste_error_fstring"):
            # Fix patterns:
            # 1. variable(keyword = variable.get(...)) → (variable.get(...))
            # 2. variable(prompt += f"...{variable.get(...) → (variable.get(...)
            m1 = re.search(r'(\w+)\s*\(\s*\w+\s*=\s*(\1\.get\([^)]+\))\s*\)\s*\[:', old_line)
            if m1:
                new_line = old_line.replace(f"{m1.group(1)}({m1.group(2)})", f"({m1.group(2)})")
            else:
                m2 = re.search(r"(\w+)\s*\(\s*(\w+\s*\+?=\s*f\".*?\{)\1\.", old_line)
                if m2:
                    new_line = re.sub(
                        rf"{re.escape(m2.group(1))}\(\s*{re.escape(m2.group(2))}",
                        m2.group(2),
                        old_line
                    )
                    # Also remove trailing orphaned content
                    new_line = re.sub(r'\}\s*\)', '}', new_line)

        elif f.pattern == "unbound_local":
            # Eliminar el import local redundante
            new_line = re.sub(r'from core\.app_logging import log_event\s*', '', old_line)

        elif f.pattern == "unused_import":
            # No eliminar imports con # noqa (son intencionales)
            if "# noqa" in old_line.lower():
                new_line = old_line  # skip
            else:
                new_line = ""

        elif f.pattern == "st_error_no_log":
            _mod = Path(f.file_path).stem
            _es = " " * (len(old_line) - len(old_line.lstrip()))
            new_line = f"{_es}log_event('{_mod}', 'error:{old_line.strip()[:60]}')\n" + old_line

        elif f.pattern == "unsafe_html":
            # Convertir st.markdown(f"...{var}...", unsafe_allow_html=True)
            # a st.markdown(f"...{escape(var)}...", unsafe_allow_html=True)
            # y agregar from html import escape si no existe
            m = re.search(r'f(["\'])(.*?)\1', old_line)
            if m:
                fstring_content = m.group(2)
                # Encontrar variables en el f-string: {varname} o {varname.attr}
                vars_in_fstring = re.findall(r'\{(\w+(?:\.\w+)*)\}', fstring_content)
                if vars_in_fstring:
                    new_fstring = fstring_content
                    for var in vars_in_fstring:
                        new_fstring = new_fstring.replace(f"{{{var}}}", f"{{{var}}}", 1)
                        # Solo reemplazar si no tiene escape ya
                        old_pattern = "{" + var + "}"
                        new_pattern = "{escape(" + var + ")}"
                        if old_pattern in new_fstring:
                            new_fstring = new_fstring.replace(old_pattern, new_pattern, 1)
                    # Reconstruir la linea
                    new_line = old_line.replace(
                        "f" + m.group(0),
                        "f" + m.group(1) + new_fstring + m.group(1)
                    )
                    # Asegurar que 'from html import escape' existe al inicio del archivo
                    if "from html import escape" not in content and "from html import escape" not in lines[:10]:
                        # Buscar donde insertar (despues de from __future__ o al inicio)
                        insert_idx = 0
                        for idx, l in enumerate(lines):
                            if l.strip().startswith("from ") or l.strip().startswith("import "):
                                insert_idx = idx + 1
                        lines.insert(insert_idx, "from html import escape")
                        # Ajustar indice de linea actual
                        if insert_idx <= f.line - 1:
                            f.line += 1

        if new_line != old_line:
            lines[f.line - 1] = new_line
            filepath.write_text("\n".join(lines), encoding="utf-8")
            memory.record_fix(
                file_path=f.file_path, line=f.line, severity=f.severity,
                pattern=f.pattern, old_code=old_line, new_code=new_line,
                category="auto_fix", commit_hash=commit_hash,
            )
            fixes += 1
            print(f"  🔧 Fixed [{f.pattern}] {f.file_path}:{f.line}")

    return fixes


# ═══════════════════════════════════════════════════════════════════════
#  MONITOR EN TIEMPO REAL (log watcher)
# ═══════════════════════════════════════════════════════════════════════


class ErrorLearner:
    """Aprende de errores en tiempo real y del historial de git."""

    def __init__(self, memory: FixMemory):
        self.memory = memory

    def learn_from_git_log(self, max_commits: int = 50) -> int:
        """Analiza commits recientes para aprender patrones de fixes humanos."""
        learned = 0
        try:
            result = subprocess.run(
                ["git", "log", f"-{max_commits}", "--oneline", "--stat"],
                cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=30,
            )
            lines = result.stdout.split("\n")
            for line in lines:
                # Detectar fixes: "fix:" or "bugfix:" in commit message
                if re.match(r'^[a-f0-9]+\s+(fix|bugfix|security|patch):', line, re.IGNORECASE):
                    log_event("autoheal_learn", f"human_fix:{line[:80]}")
        except Exception:
            pass
        return learned

    def learn_from_all_sources(self) -> dict:
        """Ejecuta todas las fuentes de aprendizaje."""
        return {
            "git_commits": self.learn_from_git_log(),
        }


class RealTimeMonitor:
    """Monitorea logs de Streamlit/Supabase y reacciona a errores en vivo."""

    def __init__(self, memory: FixMemory, scanner: SmartScanner):
        self.memory = memory
        self.scanner = scanner
        self.log_file = STREAMLIT_LOG
        self.last_position = 0
        self.last_check = time.time()

    def check_logs(self) -> list[dict]:
        """Lee nuevas líneas del log y detecta errores."""
        errors = []
        if not self.log_file.exists():
            return errors

        try:
            with open(self.log_file, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(self.last_position)
                new_lines = f.readlines()
                self.last_position = f.tell()
        except Exception:
            return errors

        for line in new_lines:
            line = line.strip()
            if not line:
                continue

            error_patterns = [
                (r"TypeError:.*NoneType.*not subscriptable", "NoneType"),
                (r"UnboundLocalError", "UnboundLocalError"),
                (r"KeyError", "KeyError"),
                (r"AttributeError.*NoneType", "NoneType"),
                (r"st.error.*módulo.*fall", "module_error"),
                (r"supabase.*APIError", "supabase_error"),
                (r"Exception:.*500", "server_error"),
                (r"SyntaxError", "SyntaxError"),
                (r"ImportError", "ImportError"),
                (r"NameError", "NameError"),
                (r"ValueError", "ValueError"),
            ]

            for pattern, etype in error_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    err_id = self.memory.record_error(etype, line[:200], context=line[:500])
                    errors.append({"type": etype, "msg": line[:200], "id": err_id})
                    log_event("autoheal_monitor", f"error_detectado:{etype}:{line[:80]}")
                    break

        self.last_check = time.time()
        return errors

    def auto_heal_from_error(self, error: dict) -> bool:
        """Intenta corregir automaticamente un error detectado en logs."""
        msg = error["msg"]

        # Intentar extraer archivo y linea del mensaje de error
        file_match = re.search(r'File "([^"]+)", line (\d+)', msg)
        if file_match:
            err_file = file_match.group(1)
            err_line = int(file_match.group(2))
            # Verificar si el archivo existe en el repo
            for base in [REPO_ROOT, Path("/mount/src/medicare-pro-v2")]:
                fp = base / err_file
                if fp.exists():
                    log_event("autoheal_heal", f"error_localizado:{err_file}:{err_line}")
                    self.memory.record_error("autoheal_heal", f"localizado:{err_file}:{err_line}")
                    break

        # Buscar fix similar en memoria
        similar = self.memory.find_similar_fix(msg)
        if similar:
            filepath = REPO_ROOT / similar["file"]
            if filepath.exists():
                content = filepath.read_text(encoding="utf-8")
                if similar["old"] in content:
                    content = content.replace(similar["old"], similar["new"])
                    filepath.write_text(content, encoding="utf-8")
                    log_event("autoheal_heal", f"fix_aplicado:{similar['file']}:{similar['pattern']}")
                    return True
        return False


# ═══════════════════════════════════════════════════════════════════════
#  AUTO-COMMIT INTELIGENTE
# ═══════════════════════════════════════════════════════════════════════


def format_code_with_black(file_paths: list[str]) -> int:
    """Ejecuta Black formatter sobre archivos modificados."""
    formatted = 0
    try:
        subprocess.run(
            [sys.executable, "-m", "black", "--quiet", "--line-length", "120"] + file_paths,
            capture_output=True, timeout=30,
        )
        result = subprocess.run(
            [sys.executable, "-m", "black", "--check", "--quiet", "--line-length", "120"] + file_paths,
            capture_output=True, text=True, timeout=30,
        )
        formatted = len(file_paths) - (result.returncode if result.returncode > 0 else 0)
    except Exception:
        pass
    return formatted


def smart_commit(memory: FixMemory, fixes: int, tests_created: int) -> bool:
    """Hace commit con mensaje descriptivo basado en fixes aplicados."""
    try:
        # Obtener últimas estadísticas
        stats = memory.get_stats()
        recent = stats["recent_fixes"][:3] if stats["recent_fixes"] else []

        # Construir mensaje
        parts = [f"autoheal v2:"]
        if fixes > 0:
            parts.append(f"{fixes} fixes")
        if tests_created > 0:
            parts.append(f"+{tests_created} tests")
        if recent:
            patterns = Counter(r[1] for r in recent)
            for pat, cnt in patterns.most_common(3):
                parts.append(f"{pat}({cnt})")

        message = " | ".join(parts)
        if message == "autoheal v2:":
            return False  # sin cambios

        subprocess.run(["git", "add", "-A"], cwd=str(REPO_ROOT),
                       capture_output=True, timeout=30)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"],
                                cwd=str(REPO_ROOT), capture_output=True, timeout=10)
        if result.returncode == 0:
            return False

        subprocess.run(["git", "commit", "-m", message], cwd=str(REPO_ROOT),
                       capture_output=True, timeout=30)
        push = subprocess.run(["git", "push"], cwd=str(REPO_ROOT),
                              capture_output=True, text=True, timeout=60)
        commit_hash = push.stderr.strip()[-12:] if push.stderr else ""

        # Actualizar fixes con commit hash
        if commit_hash:
            conn = memory._connect()
            conn.execute("UPDATE fixes SET commit_hash = ? WHERE commit_hash = ''", (commit_hash,))
            conn.commit()
            conn.close()

        return True
    except Exception as exc:
        print(f"  ⚠️ Commit falló: {exc}")
        return False


# ═══════════════════════════════════════════════════════════════════════
#  DETECTOR DE REGRESIONES DE RENDIMIENTO
# ═══════════════════════════════════════════════════════════════════════


def check_performance_regression(memory: FixMemory) -> dict:
    """Analiza scan_history para detectar regresiones de rendimiento.
    
    Returns:
        Dict con alertas de rendimiento.
    """
    alerts = {}
    conn = memory._connect()
    try:
        # Comparar ultimos 10 scans vs los 10 anteriores
        recent = conn.execute(
            "SELECT elapsed_seconds FROM scan_history ORDER BY id DESC LIMIT 10"
        ).fetchall()
        older = conn.execute(
            "SELECT elapsed_seconds FROM scan_history ORDER BY id DESC LIMIT 10 OFFSET 10"
        ).fetchall()

        if len(recent) >= 5 and len(older) >= 5:
            recent_avg = sum(r[0] for r in recent) / len(recent)
            older_avg = sum(r[0] for r in older) / len(older)

            if older_avg > 0:
                ratio = recent_avg / older_avg
                if ratio > 1.5:
                    alerts["scan_time"] = {
                        "severity": "ALTA",
                        "message": f"Tiempo de escaneo aumento {ratio:.1f}x: {older_avg:.1f}s -> {recent_avg:.1f}s",
                        "recent_avg": recent_avg,
                        "older_avg": older_avg,
                    }
                elif ratio > 1.2:
                    alerts["scan_time"] = {
                        "severity": "MEDIA",
                        "message": f"Tiempo de escaneo aumento {ratio:.1f}x: {older_avg:.1f}s -> {recent_avg:.1f}s",
                        "recent_avg": recent_avg,
                        "older_avg": older_avg,
                    }

        # Verificar cantidad de hallazgos creciente
        recent_findings = conn.execute(
            "SELECT total_findings FROM scan_history ORDER BY id DESC LIMIT 10"
        ).fetchall()
        if len(recent_findings) >= 5:
            trend = [r[0] for r in recent_findings]
            if trend[0] > trend[-1] * 1.3:
                alerts["findings_trend"] = {
                    "severity": "MEDIA",
                    "message": f"Los hallazgos aumentaron: {trend[-1]} -> {trend[0]} (ultimos 10 scans)",
                }

    except Exception as exc:
        log_event("perf", f"regression_check_error:{type(exc).__name__}")
    finally:
        conn.close()

    return alerts


# ═══════════════════════════════════════════════════════════════════════
#  GENERADOR INTELIGENTE DE TESTS
# ═══════════════════════════════════════════════════════════════════════


def generate_smart_tests(memory: FixMemory, force_all: bool = False) -> int:
    """Crea tests para módulos sin cobertura.
    
    Args:
        memory: Memoria persistente.
        force_all: Si True, escanea TODOS los módulos core/ y views/.
                   Si False, solo módulos que tuvieron fixes.
    """
    created = 0
    target_modules: set[Path] = set()

    if force_all:
        # Escanear todos los módulos de core/ y views/
        for d in [CORE_DIR, VIEWS_DIR]:
            for pyfile in d.rglob("*.py"):
                if pyfile.stem.startswith("_"):
                    continue
                if any(ign in pyfile.parts for ign in IGNORE_DIRS):
                    continue
                target_modules.add(pyfile)

    # También incluir módulos con fixes previos
    conn = memory._connect()
    rows = conn.execute(
        "SELECT DISTINCT file_path FROM fixes WHERE file_path NOT LIKE 'tests/%' AND file_path NOT LIKE 'scripts/%'"
    ).fetchall()
    conn.close()
    for (fp,) in rows:
        p = REPO_ROOT / fp
        if p.exists():
            target_modules.add(p)

    for src_path in sorted(target_modules):
        test_name = f"test_{src_path.stem}.py"
        if src_path.parent.name == "core":
            test_path = TESTS_DIR / test_name
        elif src_path.parent.name == "views":
            test_path = TESTS_DIR / test_name
        else:
            p = TESTS_DIR / src_path.parent.name
            p.mkdir(parents=True, exist_ok=True)
            test_path = p / test_name

        if test_path.exists():
            continue

        module_path = str(src_path.relative_to(REPO_ROOT)).replace(os.sep, "/").replace(".py", "").replace("/", ".")
        total_fixes = memory.get_stats()["total_fixes"]
        test_content = f'''"""Tests para {module_path} — AutoHeal v2."""
from __future__ import annotations


class Test{src_path.stem.title().replace("_", "")}:
    """Tests para {module_path}."""

    def test_module_importable(self):
        import {module_path}
        assert {module_path} is not None
'''
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text(test_content, encoding="utf-8")
        created += 1

    return created


# ═══════════════════════════════════════════════════════════════════════
#  CICLO PRINCIPAL (DAEMON)
# ═══════════════════════════════════════════════════════════════════════


def run_cycle(memory: FixMemory, scanner: SmartScanner, monitor: RealTimeMonitor,
              do_fix: bool, do_tests: bool, do_commit: bool, do_learn: bool) -> dict:
    """Ejecuta un ciclo completo de scan → fix → test → learn → commit."""
    findings = scanner.findings = []
    scanner.findings.clear()

    files = list(VIEWS_DIR.rglob("*.py")) + list(CORE_DIR.rglob("*.py"))
    files = [f for f in files if not any(ign in f.parts for ign in IGNORE_DIRS)]

    t0 = time.time()

    # 1. SCAN
    for f in files:
        rel = f.relative_to(REPO_ROOT).as_posix()
        content = f.read_text(encoding="utf-8", errors="ignore")
        lines = content.split("\n")

        scanner.scan_get_key_slice(rel, content, lines)
        scanner.scan_unbound_local(rel, content, lines)
        scanner.scan_list_index_without_guard(rel, content, lines)
        scanner.scan_st_error_no_log(rel, content, lines)
        scanner.scan_unsafe_html(rel, content, lines)
        scanner.scan_subscript_loop(rel, content, lines)
        scanner.scan_unused_imports(rel, content, lines)
        scanner.scan_dead_functions(rel, content, lines)
        scanner.scan_complexity(rel, content, lines)
        scanner.scan_missing_docstrings(rel, content, lines)

    elapsed = time.time() - t0
    crit = sum(1 for f in scanner.findings if f.severity == "CRITICAL")
    high = sum(1 for f in scanner.findings if f.severity == "HIGH")
    medium = sum(1 for f in scanner.findings if f.severity == "MEDIUM")

    # 1b. CHECK PERFORMANCE REGRESSION
    perf_alerts = check_performance_regression(memory)
    if perf_alerts:
        for key, alert in perf_alerts.items():
            print(f"  ⚡ Rendimiento: {alert['message']}")
            log_event("autoheal_perf", f"{key}:{alert['message'][:100]}")

    # 2. CHECK LOGS (real-time monitoring)
    log_errors = monitor.check_logs()
    for err in log_errors:
        print(f"  ⚡ Error en vivo: {err['type']} — {err['msg'][:60]}")
        monitor.auto_heal_from_error(err)

    # 3. FIX
    fixes = 0
    if do_fix:
        fixes = apply_smart_fixes(scanner, memory)

    # 4. LEARN new patterns
    learned = 0
    if do_learn:
        learned += PatternLearner.learn_from_fix_history(memory)
        learned += PatternLearner.scan_for_new_patterns(memory, REPO_ROOT / "core")
        learned += PatternLearner.scan_for_new_patterns(memory, VIEWS_DIR)
        # Aprender de errores en vivo y git
        error_learner = ErrorLearner(memory)
        learn_results = error_learner.learn_from_all_sources()
        learned += sum(learn_results.values())
        if learned > 0:
            print(f"  🧠 Aprendidos {learned} patrones nuevos")

    # 4b. FORMAT with Black (auto-formato de codigo)
    formatted = 0
    if fixes > 0:
        fixed_files = list({f.file_path for f in scanner.findings if f.auto_fix and (REPO_ROOT / f.file_path).exists()})
        if fixed_files:
            formatted = format_code_with_black(fixed_files)
            if formatted > 0:
                print(f"  ✨ Formateados {formatted} archivos con Black")

    # 5. TESTS
    tests_created = 0
    passed = failed = 0
    if do_tests:
        tests_created = generate_smart_tests(memory, force_all=True)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short",
                 "--ignore=tests/e2e", "-k", "not stress"],
                cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=120,
            )
            passed = result.stdout.count("passed")
            failed = result.stdout.count("failed")
        except subprocess.TimeoutExpired:
            print("  ⚠️ Tests timeout (>120s)")
        except Exception as exc:
            print(f"  ⚠️ Tests error: {exc}")

    # 6. COMMIT
    commit_made = False
    if do_commit and (fixes > 0 or tests_created > 0 or learned > 0 or formatted > 0):
        commit_made = smart_commit(memory, fixes + formatted, tests_created)

    # 7. RECORD HISTORY
    memory.record_scan(
        total=len(findings), crit=crit, high=high,
        fixes=fixes, tests_created=tests_created,
        passed=passed, failed=failed,
        elapsed=elapsed, commit=commit_made,
    )

    return {
        "findings": len(findings), "crit": crit, "high": high, "medium": medium,
        "fixes": fixes, "tests_created": tests_created,
        "tests_passed": passed, "tests_failed": failed,
        "learned_patterns": learned, "log_errors": len(log_errors),
        "formatted": formatted, "commit": commit_made, "elapsed": elapsed,
    }


# ═══════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════


def _print_perf(memory: FixMemory):
    """Muestra metricas de rendimiento de escaneos."""
    conn = memory._connect()
    print(f"\n📈 AutoHeal v3 — Rendimiento")
    print(f"{'=' * 50}")
    try:
        # Promedio por intervalo
        rows = conn.execute(
            "SELECT elapsed_seconds FROM scan_history ORDER BY id"
        ).fetchall()
        if rows:
            times = [r[0] for r in rows]
            print(f"  Escaneos totales:   {len(times)}")
            print(f"  Tiempo promedio:    {sum(times)/len(times):.2f}s")
            print(f"  Tiempo minimo:      {min(times):.2f}s")
            print(f"  Tiempo maximo:      {max(times):.2f}s")
            if len(times) >= 10:
                print(f"  Ultimos 10 vs prev: {sum(times[-10:])/10:.2f}s vs {sum(times[-20:-10])/10:.2f}s")

        # Tendencias de hallazgos
        findings = conn.execute(
            "SELECT total_findings, critical_count, high_count FROM scan_history ORDER BY id DESC LIMIT 20"
        ).fetchall()
        if findings:
            avg_crit = sum(f[1] for f in findings) / len(findings)
            avg_high = sum(f[2] for f in findings) / len(findings)
            print(f"  Criticos promedio:  {avg_crit:.1f}")
            print(f"  Altos promedio:     {avg_high:.1f}")
    except Exception as exc:
        print(f"  Error: {exc}")
    conn.close()
    print()


def print_stats(memory: FixMemory):
    stats = memory.get_stats()
    print(f"\n📊 AutoHeal v2 — Estadísticas")
    print(f"{'=' * 50}")
    print(f"  Fixes aplicados:     {stats['total_fixes']}")
    print(f"  Errores registrados: {stats['total_errors']}")
    print(f"  Patrones aprendidos: {stats['total_patterns']}")
    print(f"  Escaneos realizados: {stats['scans']}")
    print(f"  Tasa de éxito:       {stats['success_rate']}%")
    print()
    if stats["top_patterns"]:
        print("  Top patrones:")
        for p, c in stats["top_patterns"]:
            print(f"    • {p}: {c} veces")
    print()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="AutoHeal v2 — Sistema Autónomo con Memoria")
    parser.add_argument("--daemon", action="store_true", help="Modo eterno: cada 15 min")
    parser.add_argument("--interval", type=int, default=15, help="Intervalo en minutos (default: 15)")
    parser.add_argument("--scan", action="store_true", help="Ejecutar un escaneo")
    parser.add_argument("--fix", action="store_true", help="Aplicar fixes automáticos")
    parser.add_argument("--tests", action="store_true", help="Crear tests + ejecutarlos")
    parser.add_argument("--learn", action="store_true", help="Aprender nuevos patrones")
    parser.add_argument("--history", action="store_true", help="Mostrar historial")
    parser.add_argument("--stats", action="store_true", help="Mostrar estadísticas")
    parser.add_argument("--perf", action="store_true", help="Mostrar metricas de rendimiento")
    parser.add_argument("--no-commit", action="store_true", help="No auto-committear")
    args = parser.parse_args()

    memory = FixMemory()
    scanner = SmartScanner(memory)
    monitor = RealTimeMonitor(memory, scanner)

    if args.stats or args.history:
        print_stats(memory)
        return

    if args.perf:
        _print_perf(memory)
        return

    if args.daemon:
        interval = args.interval * 60
        print(f"🤖 AutoHeal v2 DAEMON — memoria en {DB_PATH}")
        print(f"   Intervalo: {args.interval} min | Auto-commit: {'ON' if not args.no_commit else 'OFF'}")
        print(f"   Presioná Ctrl+C para detener\n")

        cycle = 0
        while True:
            cycle += 1
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] Ciclo #{cycle}...", end=" ")

            stats = run_cycle(
                memory=memory, scanner=scanner, monitor=monitor,
                do_fix=True, do_tests=True,
                do_commit=not args.no_commit, do_learn=True,
            )

            print(
                f"scan:{stats['findings']} "
                f"crit:{stats['crit']} high:{stats['high']} "
                f"fixes:{stats['fixes']} fmt:{stats['formatted']} tests:{stats['tests_created']} "
                f"learned:{stats['learned_patterns']} logs:{stats['log_errors']} "
                f"commit:{stats['commit']} {stats['elapsed']:.1f}s"
            )
            time.sleep(interval)

    # Single run
    print(f"🔍 Escaneando...")
    stats = run_cycle(
        memory=memory, scanner=scanner, monitor=monitor,
        do_fix=args.fix or True, do_tests=args.tests or True,
        do_commit=not args.no_commit and (args.fix or args.tests),
        do_learn=args.learn or True,
    )

    print(f"\n✅ Completado en {stats['elapsed']:.1f}s")
    print(f"   Hallazgos: {stats['findings']} ({stats['crit']}C/{stats['high']}H/{stats['medium']}M)")
    print(f"   Fixes: {stats['fixes']} | Tests: {stats['tests_created']} creados, {stats['tests_passed']}P/{stats['tests_failed']}F")
    print(f"   Patrones aprendidos: {stats['learned_patterns']} | Errores en vivo: {stats['log_errors']}")
    print(f"   Commit: {'✅' if stats['commit'] else '—'}")

    print_stats(memory)


if __name__ == "__main__":
    main()
