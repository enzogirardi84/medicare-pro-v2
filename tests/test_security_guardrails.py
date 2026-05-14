import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ["main_medicare.py", "core", "views"]
ALLOWED_IMPORT_MODULE = {Path("core/app_navigation.py")}
SERVICE_ROLE_ALLOWED = {
    Path("core/diagnosticos.py"),
    Path("core/security_middleware.py"),
}


def _python_files():
    for entry in SCAN_DIRS:
        path = REPO_ROOT / entry
        if path.is_file():
            yield path
        else:
            yield from path.rglob("*.py")


def _rel(path: Path) -> Path:
    return path.relative_to(REPO_ROOT).as_posix()


def test_no_eval_exec_or_unsafe_deserialization_in_app_code():
    findings = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in {"eval", "exec", "__import__"}:
                    findings.append(f"{_rel(path)}:{node.lineno}:{func.id}")
                if isinstance(func, ast.Attribute) and func.attr == "loads":
                    owner = func.value
                    if isinstance(owner, ast.Name) and owner.id in {"pickle", "marshal"}:
                        findings.append(f"{_rel(path)}:{node.lineno}:{owner.id}.loads")
                if isinstance(func, ast.Attribute) and func.attr == "load":
                    owner = func.value
                    if isinstance(owner, ast.Name) and owner.id == "yaml":
                        findings.append(f"{_rel(path)}:{node.lineno}:yaml.load")

    assert findings == []


def test_dynamic_imports_are_limited_to_view_dispatcher():
    findings = []
    for path in _python_files():
        rel = path.relative_to(REPO_ROOT)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_import_module = (
                isinstance(func, ast.Name)
                and func.id == "import_module"
            ) or (
                isinstance(func, ast.Attribute)
                and func.attr == "import_module"
            )
            if is_import_module and rel not in ALLOWED_IMPORT_MODULE:
                findings.append(f"{_rel(path)}:{node.lineno}:import_module")

    assert findings == []


def test_service_role_key_is_not_used_in_views_or_public_app_entrypoints():
    findings = []
    for path in _python_files():
        rel = path.relative_to(REPO_ROOT)
        if rel in SERVICE_ROLE_ALLOWED:
            continue
        text = path.read_text(encoding="utf-8")
        if "SUPABASE_SERVICE_ROLE_KEY" in text or "sb_secret_" in text:
            findings.append(_rel(path))

    assert findings == []
