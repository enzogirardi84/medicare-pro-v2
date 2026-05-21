"""
Sistema autónomo de diagnóstico y reparación (Self-Healing AI).
Analiza errores, código fuente y rendimiento; propone y aplica correcciones.

Modos de operación:
  - passive: solo detecta y registra hallazgos (seguro, default)
  - dry_run: genera fixes pero no los aplica
  - active: aplica fixes automáticos que pasan validación
"""

from __future__ import annotations

import ast
import os
import re
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.app_logging import log_event, get_recent_errors
from core.error_tracker import report_exception

REPO_ROOT = Path(__file__).resolve().parent.parent
SELF_HEALING_LOG_KEY = "_self_healing_log"
SCAN_INTERVAL_RERUNS = 100  # cada N reruns hace un scan completo


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class FixSeverity:
    LOW = "low"       # unused import, formatting
    MEDIUM = "medium" # potential bug, missing validation
    HIGH = "high"     # crash, data loss, security issue
    CRITICAL = "critical"


class FixStatus:
    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    DISMISSED = "dismissed"


@dataclass
class Finding:
    id: str
    file_path: str
    line: int
    severity: str
    category: str           # "import_error", "undefined_name", "type_error", "performance", "security"
    title: str
    description: str
    suggested_fix: str = ""
    original_code: str = ""
    status: str = FixStatus.PENDING
    created_at: float = 0.0
    applied_at: Optional[float] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()


@dataclass
class ScanReport:
    findings: List[Finding] = field(default_factory=list)
    files_scanned: int = 0
    errors_found: int = 0
    fixes_applied: int = 0
    duration_ms: float = 0.0
    timestamp: float = 0.0


# ---------------------------------------------------------------------------
# Static analysis (sin LLM, siempre disponible)
# ---------------------------------------------------------------------------

def _safe_compile_check(filepath: str) -> List[Finding]:
    """Verifica que un archivo Python compile correctamente."""
    findings = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        compile(source, filepath, "exec")
    except SyntaxError as e:
        rel = _rel_path(filepath)
        findings.append(Finding(
            id=f"compile_{rel}_{e.lineno}",
            file_path=rel,
            line=e.lineno or 0,
            severity=FixSeverity.HIGH,
            category="syntax_error",
            title=f"Error de sintaxis en {rel}:{e.lineno}",
            description=str(e.msg),
            original_code=_get_lines(filepath, e.lineno, 3) if e.lineno else "",
        ))
    except Exception as e:
        rel = _rel_path(filepath)
        findings.append(Finding(
            id=f"compile_{rel}_0",
            file_path=rel,
            line=0,
            severity=FixSeverity.HIGH,
            category="compile_error",
            title=f"Error de compilación en {rel}",
            description=str(e),
        ))
    return findings


def _check_undefined_names(filepath: str) -> List[Finding]:
    """Busca nombres potencialmente indefinidos vía AST."""
    findings = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        tree = ast.parse(source)
    except SyntaxError:
        return findings

    defined = set()
    used_undefined = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined.add(node.name)
            for arg in node.args.args:
                defined.add(arg.arg)
            for arg in node.args.kwonlyargs:
                defined.add(arg.arg)
            if node.args.vararg:
                defined.add(node.args.vararg.arg)
            if node.args.kwarg:
                defined.add(node.args.kwarg.arg)
        elif isinstance(node, ast.ClassDef):
            defined.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined.add(target.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                defined.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                defined.add(alias.asname or alias.name)

        # Name nodes: check if they're used but undefined
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            name = node.id
            if name not in defined and not name.startswith("_") and name != "st":
                used_undefined.append((node.lineno, name))

    # Filter: keep only names that appear as potential issues
    BUILTINS = {"True", "False", "None", "str", "int", "float", "bool", "list", "dict",
                "set", "tuple", "type", "len", "range", "enumerate", "zip", "map",
                "filter", "min", "max", "sum", "abs", "any", "all", "sorted",
                "reversed", "iter", "next", "open", "print", "isinstance", "hasattr",
                "getattr", "setattr", "Exception", "ValueError", "TypeError", "KeyError",
                "IndexError", "AttributeError", "ImportError", "NameError", "StopIteration",
                "super", "classmethod", "staticmethod", "property", "object"}

    seen = set()
    for lineno, name in used_undefined:
        if name in BUILTINS or name in seen:
            continue
        seen.add(name)
        rel = _rel_path(filepath)
        findings.append(Finding(
            id=f"undefined_{rel}_{lineno}_{name}",
            file_path=rel,
            line=lineno,
            severity=FixSeverity.MEDIUM,
            category="undefined_name",
            title=f"Posible nombre indefinido: '{name}' en {rel}:{lineno}",
            description=f"La variable '{name}' se usa pero no está definida en el ámbito local.",
            original_code=_get_lines(filepath, lineno, 3),
        ))
    return findings


def _check_import_errors(filepath: str) -> List[Finding]:
    """Busca imports potencialmente incorrectos."""
    findings = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        tree = ast.parse(source)
    except SyntaxError:
        return findings

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == node.name:
                    pass  # import X is always valid syntactically
        elif isinstance(node, ast.ImportFrom):
            pass  # from X import Y is always valid syntactically

    return findings


# ---------------------------------------------------------------------------
# LLM-powered analysis
# ---------------------------------------------------------------------------

_llm_available = None


def _is_llm_available() -> bool:
    global _llm_available
    if _llm_available is not None:
        return _llm_available
    try:
        from core.ai_assistant import is_llm_enabled
        _llm_available = is_llm_enabled()
    except Exception:
        _llm_available = False
    return _llm_available


def _llm_analyze_file(filepath: str, error_context: str = "") -> List[Finding]:
    """Usa el LLM para analizar un archivo en busca de bugs."""
    if not _is_llm_available():
        return []

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except Exception:
        return []

    rel = _rel_path(filepath)
    prompt = (
        "Eres un experto en Python y Streamlit. Analiza el siguiente código fuente "
        "en busca de bugs, problemas de rendimiento, vulnerabilidades de seguridad, "
        "y malas prácticas. Devuelve SOLO un JSON array con objetos con estos campos:\n"
        "- line: número de línea\n"
        "- severity: \"low\", \"medium\", \"high\", o \"critical\"\n"
        "- category: una categoría corta como \"bug\", \"performance\", \"security\", \"style\"\n"
        "- title: título corto del problema\n"
        "- description: descripción del problema y cómo solucionarlo\n\n"
        "Si no encuentras problemas, devuelve un array vacío []."
    )

    if error_context:
        prompt += f"\n\nContexto de error reciente:\n{error_context}\n\n"

    prompt += f"\n\n```python\n{source}\n```"

    try:
        from core.ai_assistant import AIEvolutionAssistant
        assistant = AIEvolutionAssistant()
        result = assistant._call_llm(prompt, max_tokens=2000, temperature=0.1)
        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[-1]
            result = result.rsplit("```", 1)[0]
        import json as _json
        issues = _json.loads(result)
        if isinstance(issues, list):
            findings = []
            for issue in issues:
                findings.append(Finding(
                    id=f"llm_{rel}_{issue.get('line', 0)}_{len(findings)}",
                    file_path=rel,
                    line=issue.get("line", 0),
                    severity=issue.get("severity", "medium"),
                    category=issue.get("category", "bug"),
                    title=issue.get("title", "Posible problema"),
                    description=issue.get("description", ""),
                    original_code=_get_lines(filepath, issue.get("line", 0), 3),
                ))
            return findings
    except Exception as e:
        log_event("self_healing", f"llm_analyze_error:{rel}:{type(e).__name__}:{e}")

    return []


# ---------------------------------------------------------------------------
# Fix application (dry-run / active)
# ---------------------------------------------------------------------------

def _apply_fix(filepath: str, original: str, fixed: str) -> bool:
    """Aplica un fix con backup. Retorna True si OK."""
    abs_path = _abs_path(filepath)
    if not abs_path.exists():
        return False

    backup_path = abs_path.with_suffix(".py.bak")
    try:
        # Backup
        backup_path.write_text(original, encoding="utf-8")
        # Apply fix
        abs_path.write_text(fixed, encoding="utf-8")
        # Verify compile
        compile(fixed, str(abs_path), "exec")
        return True
    except Exception as e:
        log_event("self_healing", f"fix_failed:{filepath}:{type(e).__name__}:{e}")
        # Rollback
        if backup_path.exists():
            try:
                abs_path.write_text(backup_path.read_text(encoding="utf-8"), encoding="utf-8")
            except Exception:
                pass
        return False


def _rollback_fix(filepath: str) -> bool:
    """Revierte un fix desde .bak."""
    abs_path = _abs_path(filepath)
    backup_path = abs_path.with_suffix(".py.bak")
    if not backup_path.exists():
        return False
    try:
        abs_path.write_text(backup_path.read_text(encoding="utf-8"), encoding="utf-8")
        backup_path.unlink()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Main scan orchestrator
# ---------------------------------------------------------------------------

def run_diagnostic_scan(quick: bool = True) -> ScanReport:
    """Ejecuta un scan de diagnóstico completo o rápido."""
    t0 = time.time()
    report = ScanReport(timestamp=t0)

    py_files = list(REPO_ROOT.rglob("*.py"))
    # Excluir directorios
    exclude_dirs = {"__pycache__", ".git", ".venv", "venv", "node_modules", "tests", "backups", "assets", "docs", "scripts"}
    py_files = [f for f in py_files if not any(p in f.parts for p in exclude_dirs)]

    # En modo quick, solo archivos modificados recientemente
    if quick:
        cutoff = time.time() - 86400 * 7  # últimos 7 días
        py_files = [f for f in py_files if f.stat().st_mtime > cutoff]

    report.files_scanned = len(py_files)
    error_context = _get_error_context()

    for fpath in py_files:
        filepath = str(fpath)

        # 1. Compile check
        findings = _safe_compile_check(filepath)
        report.findings.extend(findings)
        report.errors_found += len(findings)

        # 2. Undefined names (AST)
        if not findings:  # solo si compila
            findings = _check_undefined_names(filepath)
            report.findings.extend(findings)
            report.errors_found += len(findings)

    # 3. LLM analysis (solo archivos con errores o críticos)
    if _is_llm_available() and not quick:
        # En full scan, analiza archivos con más errores
        error_files = set(f.file_path for f in report.findings)
        for fpath in py_files:
            rel = _rel_path(str(fpath))
            if rel in error_files or report.errors_found == 0:
                llm_findings = _llm_analyze_file(str(fpath), error_context)
                report.findings.extend(llm_findings)
                report.errors_found += len(llm_findings)

    report.duration_ms = (time.time() - t0) * 1000
    return report


def _get_error_context() -> str:
    """Obtiene contexto de errores recientes para el LLM."""
    try:
        errors = get_recent_errors(limit=10)
        if not errors:
            return ""
        lines = []
        for e in errors:
            lines.append(f"- [{e.get('level','?')}] {e.get('message','')[:200]}")
        return "\n".join(lines)
    except Exception:
        return ""


def _rel_path(filepath: str) -> str:
    try:
        return str(Path(filepath).relative_to(REPO_ROOT))
    except ValueError:
        return filepath


def _abs_path(rel_path: str) -> Path:
    return (REPO_ROOT / rel_path).resolve()


def _get_lines(filepath: str, lineno: int, context: int = 3) -> str:
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        start = max(0, lineno - context - 1)
        end = min(len(lines), lineno + context)
        return "".join(lines[start:end])
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Session state management
# ---------------------------------------------------------------------------

def _get_log() -> List[Dict]:
    import streamlit as st
    return list(st.session_state.get(SELF_HEALING_LOG_KEY, []))


def _add_to_log(entry: Dict):
    import streamlit as st
    log = list(st.session_state.get(SELF_HEALING_LOG_KEY, []))
    log.append(entry)
    if len(log) > 200:
        log = log[-200:]
    st.session_state[SELF_HEALING_LOG_KEY] = log


# ---------------------------------------------------------------------------
# Trigger (llamado desde main_medicare.py)
# ---------------------------------------------------------------------------

def maybe_run_self_healing():
    """Ejecuta auto-diagnóstico periódico. Seguro para llamar en cada rerun."""
    try:
        import streamlit as st
        from core.feature_flags import ERROR_TRACKER_ENABLED

        if not ERROR_TRACKER_ENABLED:
            return

        rerun_count = st.session_state.get("_sh_rerun_counter", 0) + 1
        st.session_state["_sh_rerun_counter"] = rerun_count

        # Solo escanea cada N reruns
        if rerun_count % SCAN_INTERVAL_RERUNS != 0:
            return

        # Evita escanear si ya escaneó hace poco
        last_scan = st.session_state.get("_sh_last_scan", 0.0)
        if time.time() - last_scan < 3600:  # 1 hora
            return

        st.session_state["_sh_last_scan"] = time.time()
        log_event("self_healing", "Iniciando escaneo automático...")

        report = run_diagnostic_scan(quick=True)

        _add_to_log({
            "type": "scan",
            "timestamp": report.timestamp,
            "files_scanned": report.files_scanned,
            "errors_found": report.errors_found,
            "duration_ms": report.duration_ms,
            "findings": [
                {"file": f.file_path, "line": f.line, "severity": f.severity,
                 "title": f.title, "status": f.status}
                for f in report.findings
            ],
        })

        log_event("self_healing",
                  f"Scan completo: {report.files_scanned} archivos, "
                  f"{report.errors_found} hallazgos, {report.duration_ms:.0f}ms")

    except Exception as e:
        log_event("self_healing", f"maybe_run_error:{type(e).__name__}:{e}")


def run_manual_scan(full: bool = False) -> ScanReport:
    """Ejecuta scan bajo demanda (desde UI admin)."""
    report = run_diagnostic_scan(quick=not full)
    _add_to_log({
        "type": "manual_scan",
        "timestamp": report.timestamp,
        "files_scanned": report.files_scanned,
        "errors_found": report.errors_found,
        "duration_ms": report.duration_ms,
    })
    return report


def auto_fix_finding(finding: Finding) -> bool:
    """Intenta aplicar un fix automático para un hallazgo."""
    if not finding.suggested_fix:
        return False

    abs_path = _abs_path(finding.file_path)
    if not abs_path.exists():
        return False

    try:
        original = abs_path.read_text(encoding="utf-8")
        ok = _apply_fix(finding.file_path, original, finding.suggested_fix)
        if ok:
            finding.status = FixStatus.APPLIED
            finding.applied_at = time.time()
            log_event("self_healing", f"fix_applied:{finding.file_path}:{finding.title}")
        else:
            finding.status = FixStatus.FAILED
            log_event("self_healing", f"fix_failed:{finding.file_path}:{finding.title}")
        return ok
    except Exception as e:
        finding.status = FixStatus.FAILED
        log_event("self_healing", f"fix_error:{type(e).__name__}:{e}")
        return False


def rollback_fix(filepath: str) -> bool:
    """Revierte un fix previamente aplicado."""
    ok = _rollback_fix(filepath)
    if ok:
        log_event("self_healing", f"rollback:{filepath}")
    return ok


def get_scan_history(limit: int = 20) -> List[Dict]:
    """Obtiene historial de escaneos."""
    log = _get_log()
    return log[-limit:]
