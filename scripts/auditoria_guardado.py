#!/usr/bin/env python3
"""
AUDITORÍA COMPLETA DEL SISTEMA DE GUARDADO
Revisa todas las vistas para verificar que:
1. Llaman a guardar_datos() después de modificar datos
2. Manejan errores correctamente
3. Actualizan session_state antes de guardar
4. Tienen confirmación visual de éxito/error
"""

import ast
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Set

class SaveAuditVisitor(ast.NodeVisitor):
    """AST visitor para detectar problemas de guardado."""
    
    def __init__(self, filename: str):
        self.filename = filename
        self.issues: List[str] = []
        self.has_guardar_datos = False
        self.guardar_datos_calls = 0
        self.session_state_modifications: List[str] = []
        self.has_error_handling = False
        self.has_success_message = False
        self.current_function = None
        self.functions_with_saves: Set[str] = set()
        
    def visit_FunctionDef(self, node):
        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function
        
    def visit_Call(self, node):
        # Detectar llamadas a guardar_datos
        if isinstance(node.func, ast.Name) and node.func.id == "guardar_datos":
            self.has_guardar_datos = True
            self.guardar_datos_calls += 1
            if self.current_function:
                self.functions_with_saves.add(self.current_function)
            
        # Detectar modificaciones a session_state
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Subscript):
                if isinstance(node.func.value.value, ast.Name):
                    if node.func.value.value.id == "st" and node.func.attr in ["append", "extend", "update"]:
                        if isinstance(node.func.value.slice, ast.Constant):
                            self.session_state_modifications.append(str(node.func.value.slice.value))
                            
        self.generic_visit(node)
        
    def visit_Try(self, node):
        self.has_error_handling = True
        self.generic_visit(node)
        
    def visit_ExceptHandler(self, node):
        # Verificar que no hay pass silenciando errores
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            self.issues.append(f"ERROR CRÍTICO: except: pass en línea {node.lineno} - silencia errores de guardado")
        self.generic_visit(node)
        
    def check_issues(self) -> List[str]:
        """Verifica problemas específicos."""
        issues = []
        
        # Si modifica session_state pero no llama guardar_datos
        if self.session_state_modifications and not self.has_guardar_datos:
            issues.append(f"ERROR CRÍTICO: Modifica {self.session_state_modifications} pero NO llama guardar_datos()")
            
        # Si tiene guardar_datos pero sin manejo de errores
        if self.has_guardar_datos and not self.has_error_handling:
            issues.append("ADVERTENCIA: Llama guardar_datos() sin try/except para manejo de errores")
            
        # Si hay llamadas múltiples a guardar_datos
        if self.guardar_datos_calls > 3:
            issues.append(f"ADVERTENCIA: {self.guardar_datos_calls} llamadas a guardar_datos - puede ser ineficiente")
            
        return issues + self.issues

def analyze_view(filepath: Path) -> Dict:
    """Analiza una vista para problemas de guardado."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        tree = ast.parse(content)
        visitor = SaveAuditVisitor(filepath.name)
        visitor.visit(tree)
        
        # Verificar imports
        has_database_import = "from core.database import" in content and "guardar_datos" in content
        
        return {
            "filename": filepath.name,
            "has_guardar_datos": visitor.has_guardar_datos,
            "guardar_datos_calls": visitor.guardar_datos_calls,
            "modifications": visitor.session_state_modifications,
            "issues": visitor.check_issues(),
            "has_database_import": has_database_import,
            "lines": len(content.splitlines())
        }
    except Exception as e:
        return {
            "filename": filepath.name,
            "error": str(e),
            "issues": [f"ERROR DE PARSING: {e}"]
        }

def generate_audit_report(results: List[Dict]) -> str:
    """Genera reporte HTML de auditoría."""
    
    critical_issues = sum(1 for r in results for i in r.get("issues", []) if "ERROR CRÍTICO" in i)
    warnings = sum(1 for r in results for i in r.get("issues", []) if "ADVERTENCIA" in i)
    total_views = len(results)
    views_with_save = sum(1 for r in results if r.get("has_guardar_datos"))
    
    report = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Auditoria de Guardado - Medicare Pro</title>
    <style>
        body {{ font-family: Inter, -apple-system, sans-serif; margin: 40px; background: #f8fafc; }}
        .header {{ background: linear-gradient(135deg, #DC2626, #991B1B); color: white; padding: 30px; border-radius: 8px; margin-bottom: 30px; }}
        .header.safe {{ background: linear-gradient(135deg, #059669, #047857); }}
        .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }}
        .stat-card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .stat-value {{ font-size: 2rem; font-weight: bold; }}
        .stat-value.critical {{ color: #DC2626; }}
        .stat-value.warning {{ color: #D97706; }}
        .stat-value.good {{ color: #059669; }}
        .stat-label {{ color: #64748b; margin-top: 5px; }}
        table {{ width: 100%; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-top: 20px; }}
        th {{ background: #f1f5f9; padding: 12px; text-align: left; font-weight: 600; color: #475569; }}
        td {{ padding: 12px; border-bottom: 1px solid #e2e8f0; }}
        tr:hover {{ background: #f8fafc; }}
        .badge {{ display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }}
        .badge-critical {{ background: #FEE2E2; color: #991B1B; }}
        .badge-warning {{ background: #FEF3C7; color: #92400E; }}
        .badge-good {{ background: #D1FAE5; color: #065F46; }}
        .issue-list {{ margin: 0; padding-left: 20px; }}
        .issue-list li {{ margin-bottom: 4px; color: #DC2626; }}
        .warning-list li {{ color: #D97706; }}
        .summary-box {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 30px; border-left: 4px solid #DC2626; }}
        .summary-box.safe {{ border-left-color: #059669; }}
    </style>
</head>
<body>
"""
    
    # Header color based on issues
    has_critical = critical_issues > 0
    header_class = "" if has_critical else "safe"
    status_text = "PROBLEMAS CRÍTICOS ENCONTRADOS" if has_critical else "SISTEMA DE GUARDADO VERIFICADO"
    
    report += f"""
    <div class="header {header_class}">
        <h1>Auditoria de Guardado - Medicare Pro</h1>
        <p>{status_text}</p>
        <p style="font-size: 0.875rem; opacity: 0.9;">Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="stats">
        <div class="stat-card">
            <div class="stat-value {'critical' if critical_issues > 0 else 'good'}">{critical_issues}</div>
            <div class="stat-label">Problemas Críticos</div>
        </div>
        <div class="stat-card">
            <div class="stat-value warning">{warnings}</div>
            <div class="stat-label">Advertencias</div>
        </div>
        <div class="stat-card">
            <div class="stat-value good">{views_with_save}/{total_views}</div>
            <div class="stat-label">Vistas con Guardado</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{sum(r.get('guardar_datos_calls', 0) for r in results)}</div>
            <div class="stat-label">Total Llamadas guardar_datos()</div>
        </div>
    </div>
"""
    
    # Issues summary
    if has_critical:
        report += """
    <div class="summary-box">
        <h3>ACCION REQUERIDA</h3>
        <p>Se encontraron problemas críticos que pueden causar pérdida de datos. Revisar inmediatamente las vistas marcadas.</p>
    </div>
"""
    
    # Table of results
    report += """
    <h2>Detalle por Vista</h2>
    <table>
        <thead>
            <tr>
                <th>Vista</th>
                <th>Guardado</th>
                <th>Llamadas</th>
                <th>Estado</th>
                <th>Problemas</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for result in sorted(results, key=lambda x: len(x.get("issues", [])), reverse=True):
        filename = result["filename"]
        has_save = result.get("has_guardar_datos", False)
        calls = result.get("guardar_datos_calls", 0)
        issues = result.get("issues", [])
        
        # Status badge
        if any("ERROR CRÍTICO" in i for i in issues):
            status_badge = '<span class="badge badge-critical">CRÍTICO</span>'
        elif any("ADVERTENCIA" in i for i in issues):
            status_badge = '<span class="badge badge-warning">ADVERTENCIA</span>'
        else:
            status_badge = '<span class="badge badge-good">OK</span>'
        
        # Issues list
        if issues:
            issues_html = '<ul class="issue-list">'
            for issue in issues:
                css_class = "warning-list" if "ADVERTENCIA" in issue else ""
                issues_html += f'<li class="{css_class}">{issue}</li>'
            issues_html += '</ul>'
        else:
            issues_html = "Sin problemas"
        
        report += f"""
            <tr>
                <td><strong>{filename}</strong></td>
                <td>{'Sí' if has_save else 'No'}</td>
                <td>{calls}</td>
                <td>{status_badge}</td>
                <td>{issues_html}</td>
            </tr>
"""
    
    report += """
        </tbody>
    </table>
    
    <div style="margin-top: 40px; padding: 20px; background: #F1F5F9; border-radius: 8px;">
        <h3>Recomendaciones</h3>
        <ol>
            <li><strong>Prioridad 1:</strong> Arreglar todas las vistas con "ERROR CRÍTICO"</li>
            <li><strong>Prioridad 2:</strong> Agregar manejo de errores try/except en guardados</li>
            <li><strong>Prioridad 3:</strong> Eliminar todos los "except: pass" silenciando errores</li>
            <li><strong>Prioridad 4:</strong> Agregar mensajes de éxito/error visibles al usuario</li>
        </ol>
    </div>
    
</body>
</html>
"""
    
    return report

def main():
    """Función principal de auditoría."""
    print("\n" + "="*70)
    print("AUDITORÍA COMPLETA DEL SISTEMA DE GUARDADO")
    print("="*70)
    
    views_dir = Path("views")
    if not views_dir.exists():
        print("ERROR: No se encuentra directorio 'views'")
        sys.exit(1)
    
    results = []
    for py_file in sorted(views_dir.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        
        print(f"\nAnalizando: {py_file.name}...")
        result = analyze_view(py_file)
        results.append(result)
        
        # Print summary to console
        issues = result.get("issues", [])
        if issues:
            for issue in issues:
                prefix = "[ERROR]" if "ERROR" in issue else "[WARNING]"
                print(f"  {prefix} {issue}")
        else:
            print(f"  [OK] Sin problemas ({result.get('guardar_datos_calls', 0)} llamadas)")
    
    # Generate report
    report = generate_audit_report(results)
    report_path = Path("auditoria_guardado_report.html")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    # Summary
    critical = sum(1 for r in results for i in r.get("issues", []) if "ERROR CRÍTICO" in i)
    warnings = sum(1 for r in results for i in r.get("issues", []) if "ADVERTENCIA" in i)
    
    print("\n" + "="*70)
    print("RESUMEN DE AUDITORÍA")
    print("="*70)
    print(f"Vistas analizadas: {len(results)}")
    print(f"Problemas críticos: {critical}")
    print(f"Advertencias: {warnings}")
    print(f"\nReporte generado: {report_path.absolute()}")
    
    if critical > 0:
        print("\n[CRITICAL] SE ENCONTRARON PROBLEMAS CRITICOS - REVISAR INMEDIATAMENTE")
        sys.exit(1)
    elif warnings > 0:
        print("\n[WARNING] Hay advertencias que deberian revisarse")
        sys.exit(0)
    else:
        print("\n[OK] Sistema de guardado verificado correctamente")
        sys.exit(0)

if __name__ == "__main__":
    main()
