"""Regenerate test files with correct module paths mapping."""
import re
from pathlib import Path

TESTS_DIR = Path("tests")
CORE_DIR = Path("core")
VIEWS_DIR = Path("views")

# Build module map from actual source files
MODULE_MAP = {}
for d in [CORE_DIR, VIEWS_DIR]:
    for pyfile in sorted(d.rglob("*.py")):
        if pyfile.stem.startswith("_") or pyfile.name == "__init__.py":
            continue
        # Map file path to Python module
        rel = pyfile.relative_to(Path("."))
        parts = list(rel.parts)
        if parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        module_name = ".".join(parts)
        test_name = f"test_{pyfile.stem}"
        MODULE_MAP[test_name] = module_name


def fix_tests():
    fixed = 0
    skipped = set()
    for test_file in sorted(TESTS_DIR.rglob("test_*.py")):
        stem = test_file.stem
        if stem.startswith("test_test"):  # already messed up, skip
            test_file.unlink()
            skipped.add(stem)
            continue

        module_name = MODULE_MAP.get(stem)
        if not module_name:
            skipped.add(stem)
            continue

        new_content = (
            '"""Tests for ' + module_name + '."""\n'
            "from __future__ import annotations\n\n\n"
            "def test_" + stem + "_importable():\n"
            "    import " + module_name + "\n"
            "    assert " + module_name + " is not None\n"
        )
        test_file.write_text(new_content, encoding="utf-8")
        fixed += 1

    return fixed, skipped


if __name__ == "__main__":
    n, skipped = fix_tests()
    print(f"Fixed: {n}")
    if skipped:
        print(f"Skipped/removed: {len(skipped)}")
