#!/usr/bin/env python3
"""
ARREGLO CRÍTICO: Reemplaza 'except: pass' con logging apropiado
"""

import re
from pathlib import Path

def fix_except_pass(filepath: Path) -> int:
    """Reemplaza except: pass con logging."""
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Patrón 1: except: pass (sin tipo de excepción)
    pattern1 = r'(\s+)except\s*:\s*\n\s*pass'
    
    def replacement1(match):
        indent = match.group(1)
        return f"{indent}except Exception as e:\n{indent}    from core.app_logging import log_event\n{indent}    log_event('{filepath.stem}_error', f'Error: {{e}}')"
    
    content = re.sub(pattern1, replacement1, content)
    
    # Patrón 2: except Exception: pass
    pattern2 = r'(\s+)except\s+Exception\s*:\s*\n\s*pass'
    
    def replacement2(match):
        indent = match.group(1)
        return f"{indent}except Exception as e:\n{indent}    from core.app_logging import log_event\n{indent}    log_event('{filepath.stem}_error', f'Error: {{e}}')"
    
    content = re.sub(pattern2, replacement2, content)
    
    # Patrón 3: except Exception as X: pass
    def replacement3(match):
        indent = match.group(1)
        var_name = match.group(2)
        return f"{indent}except Exception as {var_name}:\n{indent}    from core.app_logging import log_event\n{indent}    log_event('{filepath.stem}_error', f'Error: {{{var_name}}}')"
    
    pattern3 = r'(\s+)except\s+Exception\s+as\s+(\w+)\s*:\s*\n\s*pass'
    content = re.sub(pattern3, replacement3, content)
    
    # Guardar si hubo cambios
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return 1
    
    return 0

def main():
    """Arregla todas las vistas críticas."""
    
    # Archivos críticos a arreglar
    critical_files = [
        "views/alertas_paciente_app.py",
        "views/auditoria.py",
        "views/caja.py",
        "views/cierre_diario.py",
        "views/clinica.py",
        "views/dashboard.py",
        "views/emergencias.py",
        "views/evolucion.py",
        "views/historial.py",
        "views/pdf_view.py",
        "views/recetas.py",
        "views/rrhh.py",
    ]
    
    print("="*70)
    print("ARREGLO CRÍTICO: Reemplazando except: pass")
    print("="*70)
    
    fixed_count = 0
    
    for file_path in critical_files:
        path = Path(file_path)
        if path.exists():
            try:
                changes = fix_except_pass(path)
                if changes:
                    print(f"[OK] {path.name} - Arreglado")
                    fixed_count += 1
                else:
                    print(f"[WARN] {path.name} - No se encontro 'except: pass'")
            except Exception as e:
                print(f"[ERROR] {path.name} - Error: {e}")
        else:
            print(f"[ERROR] {path.name} - Archivo no encontrado")
    
    print("\n" + "="*70)
    print(f"ARREGLO COMPLETADO: {fixed_count} archivos modificados")
    print("="*70)
    print("\nIMPORTANTE: Revisar manualmente los cambios antes de hacer commit")
    print("Algunos 'except: pass' pueden ser intencionales y necesitar lógica diferente.")

if __name__ == "__main__":
    main()
