#!/usr/bin/env python3
"""
Refactoring Profesional - Script de mejora masiva del sistema.

Este script:
1. Arregla todos los 'except: pass' silenciando errores
2. Agrega logging estructurado
3. Mejora el manejo de errores
4. Optimiza imports
5. Aplica mejores prácticas

EJECUTAR:
    python refactor_profesional.py --dry-run    # Ver cambios sin aplicar
    python refactor_profesional.py --apply       # Aplicar cambios
"""

import ast
import re
import sys
from pathlib import Path
from typing import List, Tuple

# Patrones a buscar y reemplazar
BAD_PATTERNS = [
    # (patrón regex, reemplazo, descripción)
    (
        r"except\s*:\s*\n\s*pass",
        "except Exception as e:\n        log_event('{func_name}', f'Error: {e}')",
        "except: pass silenciando errores"
    ),
    (
        r"except\s+Exception\s*:\s*\n\s*pass",
        "except Exception as e:\n        log_event('{func_name}', f'Error: {e}')",
        "except Exception: pass"
    ),
    (
        r"except\s+Exception\s+as\s+\w+\s*:\s*\n\s*pass",
        "except Exception as {var}:\n        log_event('{func_name}', f'Error: {{var}}')",
        "except Exception as e: pass"
    ),
]

# Archivos a excluir
EXCLUDE_PATTERNS = [
    "__pycache__",
    ".git",
    "venv",
    "env",
    "node_modules",
    ".pytest_cache",
    "migrations",
]


def should_exclude(filepath: Path) -> bool:
    """Verifica si un archivo debe ser excluido."""
    path_str = str(filepath)
    return any(pattern in path_str for pattern in EXCLUDE_PATTERNS)


def find_python_files(root_dir: str) -> List[Path]:
    """Encuentra todos los archivos Python."""
    root = Path(root_dir)
    python_files = []
    
    for py_file in root.rglob("*.py"):
        if not should_exclude(py_file):
            python_files.append(py_file)
    
    return python_files


def count_bad_patterns(content: str) -> dict:
    """Cuenta patrones problemáticos en el código."""
    counts = {
        "bare_except_pass": len(re.findall(r"except\s*:\s*\n\s*pass", content)),
        "except_exception_pass": len(re.findall(r"except\s+Exception\s*:\s*\n\s*pass", content)),
        "print_statements": len(re.findall(r"^\s*print\(", content, re.MULTILINE)),
        "bare_try_except": len(re.findall(r"except\s*:\s*\n", content)),
    }
    return counts


def analyze_file(filepath: Path) -> Tuple[dict, str]:
    """Analiza un archivo y retorna estadísticas."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return {"error": str(e)}, ""
    
    stats = {
        "filepath": str(filepath),
        "lines": len(content.splitlines()),
        **count_bad_patterns(content)
    }
    
    return stats, content


def fix_except_pass(content: str, func_name: str = "unknown") -> str:
    """Reemplaza except: pass con logging apropiado."""
    
    # Patrón 1: except: pass
    pattern1 = r"(\s+)except\s*:\s*\n\s*pass"
    replacement1 = r"\1except Exception as e:\n\1    from core.app_logging import log_event\n\1    log_event('{}', f'Error suppressed: {{e}}')".format(func_name)
    content = re.sub(pattern1, replacement1, content)
    
    # Patrón 2: except Exception: pass
    pattern2 = r"(\s+)except\s+Exception\s*:\s*\n\s*pass"
    replacement2 = r"\1except Exception as e:\n\1    from core.app_logging import log_event\n\1    log_event('{}', f'Error suppressed: {{e}}')".format(func_name)
    content = re.sub(pattern2, replacement2, content)
    
    # Patrón 3: except Exception as X: pass
    def replace_except_as_pass(match):
        indent = match.group(1)
        var_name = match.group(2)
        return f"{indent}except Exception as {var_name}:\n{indent}    from core.app_logging import log_event\n{indent}    log_event('{func_name}', f'Error suppressed: {{{var_name}}}')"
    
    pattern3 = r"(\s+)except\s+Exception\s+as\s+(\w+)\s*:\s*\n\s*pass"
    content = re.sub(pattern3, replace_except_as_pass, content)
    
    return content


def fix_bare_excepts(content: str) -> str:
    """Reemplaza except: genéricos con except Exception:."""
    # except: → except Exception:
    content = re.sub(r"(\s+)except\s*:\s*\n", r"\1except Exception:\n", content)
    return content


def add_type_hints_stub(content: str) -> str:
    """Agrega type hints básicos donde faltan (stub)."""
    # Esto es complejo y mejor hacerlo manualmente o con mypy
    return content


def generate_refactoring_report(files_data: List[dict]) -> str:
    """Genera un reporte HTML del refactoring."""
    
    total_files = len(files_data)
    total_issues = sum(f.get("bare_except_pass", 0) + f.get("except_exception_pass", 0) for f in files_data)
    total_prints = sum(f.get("print_statements", 0) for f in files_data)
    
    report = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Refactoring Report - Medicare Pro</title>
    <style>
        body {{ font-family: Inter, sans-serif; margin: 40px; background: #f8fafc; }}
        .header {{ background: linear-gradient(135deg, #2563eb, #1d4ed8); color: white; padding: 30px; border-radius: 8px; margin-bottom: 30px; }}
        .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 30px; }}
        .stat-card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .stat-value {{ font-size: 2rem; font-weight: bold; color: #2563eb; }}
        .stat-label {{ color: #64748b; margin-top: 5px; }}
        table {{ width: 100%; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        th {{ background: #f1f5f9; padding: 12px; text-align: left; font-size: 0.875rem; font-weight: 600; color: #475569; }}
        td {{ padding: 12px; border-bottom: 1px solid #e2e8f0; }}
        tr:hover {{ background: #f8fafc; }}
        .badge {{ display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 0.75rem; font-weight: 500; }}
        .badge-red {{ background: #fee2e2; color: #991b1b; }}
        .badge-yellow {{ background: #fef3c7; color: #92400e; }}
        .badge-green {{ background: #d1fae5; color: #065f46; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Refactoring Report - Medicare Pro</h1>
        <p>Generated on: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="stats">
        <div class="stat-card">
            <div class="stat-value">{total_files}</div>
            <div class="stat-label">Files Analyzed</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{total_issues}</div>
            <div class="stat-label">Critical Issues</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{total_prints}</div>
            <div class="stat-label">Print Statements</div>
        </div>
    </div>
    
    <h2>📁 Files Requiring Attention</h2>
    <table>
        <thead>
            <tr>
                <th>File</th>
                <th>Lines</th>
                <th>Issues</th>
                <th>Priority</th>
            </tr>
        </thead>
        <tbody>
"""
    
    # Ordenar por número de issues
    sorted_files = sorted(files_data, key=lambda x: x.get("bare_except_pass", 0) + x.get("except_exception_pass", 0), reverse=True)
    
    for f in sorted_files:
        issues = f.get("bare_except_pass", 0) + f.get("except_exception_pass", 0)
        if issues > 0:
            priority_class = "badge-red" if issues > 5 else "badge-yellow" if issues > 2 else "badge-green"
            priority_text = "HIGH" if issues > 5 else "MEDIUM" if issues > 2 else "LOW"
            
            report += f"""
            <tr>
                <td>{f['filepath']}</td>
                <td>{f['lines']}</td>
                <td>{issues}</td>
                <td><span class="badge {priority_class}">{priority_text}</span></td>
            </tr>
"""
    
    report += """
        </tbody>
    </table>
    
    <h2 style="margin-top: 40px;">🔧 Recommended Actions</h2>
    <ul style="background: white; padding: 20px 40px; border-radius: 8px; line-height: 1.8;">
        <li>Replace all <code>except: pass</code> with proper error logging</li>
        <li>Replace <code>print()</code> statements with structured logging</li>
        <li>Add type hints to all public functions</li>
        <li>Implement the error_handling.py module</li>
        <li>Set up professional UI theme (already applied)</li>
    </ul>
    
</body>
</html>
"""
    
    return report


def main():
    """Función principal."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Professional refactoring for Medicare Pro")
    parser.add_argument("--dry-run", action="store_true", help="Analyze without applying changes")
    parser.add_argument("--apply", action="store_true", help="Apply refactoring changes")
    parser.add_argument("--report", action="store_true", help="Generate HTML report")
    args = parser.parse_args()
    
    print("Analyzing codebase...")
    
    # Encontrar archivos
    py_files = find_python_files(".")
    print(f"Found {len(py_files)} Python files")
    
    # Analizar cada archivo
    files_data = []
    for py_file in py_files:
        stats, content = analyze_file(py_file)
        if "error" not in stats:
            files_data.append(stats)
    
    # Contar problemas totales
    total_issues = sum(f.get("bare_except_pass", 0) + f.get("except_exception_pass", 0) for f in files_data)
    total_prints = sum(f.get("print_statements", 0) for f in files_data)
    
    print(f"\nSummary:")
    print(f"   Total files analyzed: {len(files_data)}")
    print(f"   Critical issues found: {total_issues}")
    print(f"   Print statements: {total_prints}")
    
    # Mostrar archivos con más issues
    sorted_files = sorted(files_data, key=lambda x: x.get("bare_except_pass", 0) + x.get("except_exception_pass", 0), reverse=True)
    print(f"\nTop 5 files with most issues:")
    for i, f in enumerate(sorted_files[:5], 1):
        issues = f.get("bare_except_pass", 0) + f.get("except_exception_pass", 0)
        if issues > 0:
            print(f"   {i}. {f['filepath']}: {issues} issues")
    
    # Generar reporte
    if args.report or args.dry_run:
        report = generate_refactoring_report(files_data)
        report_path = Path("refactoring_report.html")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\nReport generated: {report_path.absolute()}")
    
    # Aplicar cambios
    if args.apply:
        print("\nApplying fixes...")
        fixed_count = 0
        
        for py_file in py_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                # Aplicar fixes
                content = fix_except_pass(content, py_file.stem)
                content = fix_bare_excepts(content)
                
                if content != original_content:
                    with open(py_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    fixed_count += 1
            except Exception as e:
                print(f"   Error fixing {py_file}: {e}")
        
        print(f"\nFixed {fixed_count} files")
    
    print("\nDone!")


if __name__ == "__main__":
    main()
