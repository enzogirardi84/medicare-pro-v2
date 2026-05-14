"""Checklist rapido de seguridad para CI.

Falla si detecta secretos reales versionados o patrones de ejecucion dinamica en
codigo de aplicacion. Es deliberadamente simple para que corra rapido en PRs.
"""

from __future__ import annotations

import re
import ast
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_SUFFIXES = {".py"}
SECRET_PATTERNS = {
    "supabase_service_role": re.compile(r"sb_" + r"secret_[A-Za-z0-9_\-]+"),
    "postgres_url_with_password": re.compile(r"postgresql://postgres:[^@\s]+@db\."),
    "legacy_secret_key": re.compile(r"(sk|jwt|audit)-medicare-[A-Za-z0-9_\-]+"),
}
ALLOWLIST_FILES = {
    Path("scripts/security_checklist.py"),
    Path("tests/test_security_guardrails.py"),
}


def tracked_files() -> list[Path]:
    raw = subprocess.check_output(["git", "ls-files"], cwd=REPO_ROOT, text=True)
    return [REPO_ROOT / line for line in raw.splitlines() if line.strip()]


def scan_file(path: Path) -> list[str]:
    rel = path.relative_to(REPO_ROOT)
    if rel in ALLOWLIST_FILES:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError, OSError):
        return []

    findings: list[str] = []
    for name, pattern in SECRET_PATTERNS.items():
        if pattern.search(text):
            findings.append(f"{rel}: secreto versionado ({name})")
    if path.suffix in SOURCE_SUFFIXES:
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            findings.append(f"{rel}: no parsea para auditoria AST ({exc.lineno})")
            return findings
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id in {"eval", "exec", "__import__"}:
                findings.append(f"{rel}: ejecucion dinamica no permitida ({func.id})")
            if isinstance(func, ast.Attribute) and func.attr == "loads":
                owner = func.value
                if isinstance(owner, ast.Name) and owner.id in {"pickle", "marshal"}:
                    findings.append(f"{rel}: deserializacion no permitida ({owner.id}.loads)")
            if isinstance(func, ast.Attribute) and func.attr == "load":
                owner = func.value
                if isinstance(owner, ast.Name) and owner.id == "yaml":
                    findings.append(f"{rel}: yaml.load no seguro")
    return findings


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        findings.extend(scan_file(path))

    if findings:
        print("Checklist de seguridad fallo:")
        for item in findings:
            print(f"- {item}")
        return 1

    print("Checklist de seguridad OK: sin secretos reales ni ejecucion dinamica prohibida.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
