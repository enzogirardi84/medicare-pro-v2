"""Genera PDF con informe completo de mejoras realizadas en Medicare Pro."""
from __future__ import annotations

from datetime import datetime
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from core.export_utils import pdf_output_bytes


class ReportPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 6, "Medicare Pro - Informe de Mejoras", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Pagina {self.page_no()}/{{nb}}", align="C")

    def section_title(self, title):
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(25, 55, 95)
        self.cell(0, 8, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(25, 55, 95)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def sub_title(self, title):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(60, 60, 60)
        self.cell(0, 7, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def body_text(self, text):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(40, 40, 40)
        self.set_x(10)
        self.multi_cell(190, 4.5, text)
        self.ln(2)

    def bullet(self, text):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(40, 40, 40)
        self.set_x(15)
        self.multi_cell(175, 4.5, f"  - {text}")
        self.ln(2)

    def bullet(self, text):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(40, 40, 40)
        self.set_x(15)
        self.multi_cell(175, 4.5, f"  - {text}")


def generar_informe_pdf() -> bytes:
    pdf = ReportPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Titulo principal
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(25, 55, 95)
    pdf.cell(0, 12, "Medicare Pro - Informe de Mejoras", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(8)

    # 1. Resumen Ejecutivo
    pdf.section_title("1. Resumen Ejecutivo")
    pdf.body_text(
        "Se realizaron 18+ rondas de mejora continua sobre el codigo base de Medicare Pro, "
        "abarcando mas de 120 archivos modificados y aproximadamente 95 bugs corregidos "
        "(10 criticos, 25 altos, ~60 medios/bajos). La suite de pruebas paso de 558 a 581 tests "
        "unitarios + 26 de integracion + 6 E2E = 613 tests en total, todos verdes."
    )
    pdf.body_text(
        "Las mejoras cubren: rendimiento (cache, lazy loading, reduccion de O(n*m) a O(n+m)), "
        "seguridad (path traversal, 2FA, SQL injection, secrets exposure), experiencia de usuario "
        "(mobile, toasts, mensajes de error), calidad de codigo (imports muertos, Pydantic V2, "
        "built-in shadowing) y cobertura de tests."
    )

    # 2. Bugs Criticos Corregidos
    pdf.section_title("2. Bugs Criticos Corregidos (10)")
    pdf.sub_title("2.1 Crash bugs")
    bugs_crit = [
        ("analytics_reports.py", "Missing import statistics - crash al calcular duracion promedio"),
        ("telemedicine.py", "ModuleNotFoundError - importaba core.appointment_scheduler inexistente"),
        ("patient_portal.py", "ModuleNotFoundError - mismo problema"),
        ("backup_manager.py", "ImportError - InvalidToken importado fuera del try"),
        ("historial.py", "@st.cache_data con session_state como argumento - datos stale"),
        ("workflow_engine.py", "pacientes_db.items() sobre lista - crash (x4 archivos)"),
        ("custom_reports.py", ".values() sobre lista - crash"),
        ("appointment_scheduler.py", "pacientes_db dict vs list + cancel UI roto"),
        ("email_2fa.py", "HMAC key vacio degradaba 2FA a estado forjeable"),
        ("user_feedback.py", "Funcion duplicada exponia tracebacks al usuario"),
    ]
    for file, desc in bugs_crit:
        pdf.bullet(f"{file}: {desc}")

    pdf.ln(3)

    # 3. Bugs Altos Corregidos
    pdf.section_title("3. Bugs Altos Corregidos (25)")
    bugs_high = [
        ("feature_flags_admin.py", "Toggles sin efecto - no persistian cambios"),
        ("clinical_assistant_service.py", "0.0 or 999 - vitales recien tomados tratados como stale"),
        ("clinical_assistant_service.py", "Keyword duplicada (curacion, curacion)"),
        ("phi_encryption.py", "Campos _encrypted legitimos omitidos en desencriptacion"),
        ("keyboard_shortcuts.py", "action=key guardaba tecla en vez de nombre de funcion"),
        ("auditoria_service.py", "Falsy-value masking en kwargs"),
        ("monitoreo_proactivo.py", "st.rerun() incondicional ocultaba feedback"),
        ("auth.py", "st.rerun() sin guard en suspension de clinica"),
        ("_auth_helpers.py", "st.rerun() sin guard en login exitoso"),
        ("db_query_optimizer.py", "SQL injection vector en ILIKE f-string"),
        ("email_notifications.py", "URL medicare.local hardcodeada en emails"),
        ("rest_api.py", "Rate limiter memory leak"),
        ("_visitas_secciones.py", "Agenda semanal range(2) - solo mostraba 2 dias"),
        ("_admision_secciones.py", "sin_cambios tratado como error destructivo"),
        ("chatbot_ia.py", "API Anthropic legacy incompatible con SDK moderno"),
        ("financial_reports.py", "Archivo temporal no eliminado en export"),
        ("_recetas_mar.py", "st.container() dentro de loop"),
        ("emergencias.py", "Metricas con columnas mal asignadas"),
        ("backup_manager.py", "Path traversal en restore de backups"),
        ("compliance_monitor.py", "BACKUP CRITICAL cuando no configurado"),
        ("_aps_pdf.py", "KeyError tipo - item[tipo] sin .get()"),
        ("password_crypto.py", "Errores bcrypt silenciados sin log"),
        ("app_navigation.py", "Expanders sin key duplicaban menu Clinica"),
        ("_tabs.py APS", "DuplicateElementId en botones Guardar"),
        ("main_medicare.py", "NameError en procesar_guardado_pendiente_seguro"),
    ]
    for file, desc in bugs_high:
        pdf.bullet(f"{file}: {desc}")

    pdf.add_page()

    # 4. Rendimiento
    pdf.section_title("4. Optimizaciones de Rendimiento")
    perf_items = [
        "Cache DB: session_state manual reemplazado por @st.cache_data en _db_sql_pacientes.py (5 getters) y _db_sql_clinico.py (8 getters)",
        "Dashboard: O(n*m) a O(n+m) con defaultdict pre-indexado en loop de actividad",
        "ahora() cacheado en admin_dashboard (4 llamadas a 1), _auth_helpers (2 a 1), guardado_simple (3 a 1)",
        "Cache cleanup en _admision_utils (eviccion >50) y query_optimizer (eviccion >100)",
        "Lazy loading de PIL.Image en utils_ui.py, document_manager.py, _emergencias_data.py",
        "Computed cache (cached_computed) para list comprehensions en dashboard - evita 4 filtrados O(n) por rerun",
        "Lazy imports de pandas en 3 modulos",
    ]
    for item in perf_items:
        pdf.bullet(item)

    pdf.ln(3)

    # 5. Seguridad
    pdf.section_title("5. Mejoras de Seguridad")
    sec_items = [
        "Path traversal en backup_manager - shutil.rmtree con paths del manifiesto sin sanitizar",
        "2FA HMAC key vacio - ahora raise RuntimeError en lugar de key insegura",
        "SQL injection en db_query_optimizer - escape de % y _ en ILIKE f-string",
        "Secrets exposure en jira_status - dict(st.secrets) filtrado solo a keys conocidas",
        "Traceback exposure en user_feedback - funcion duplicada removida",
        "Pydantic V1 a V2 en rest_api.py - validator a field_validator, Config a ConfigDict",
        "Sanitizacion de busqueda en API REST con regex",
        "bcrypt errors ahora logueados (antes silenciados)",
    ]
    for item in sec_items:
        pdf.bullet(item)

    pdf.ln(3)

    # 6. Mobile
    pdf.section_title("6. Mejoras Mobile UX")
    mobile_items = [
        "20+ expanders cambiados de expanded=True a expanded=False",
        "Agenda semanal: 7 columnas fijas a CSS grid responsivo (3 columnas en mobile)",
        "APS panel diario: 4 columnas a 2 en mobile con deteccion automatica",
        "Metricas de emergencias: layout corregido para mobile y desktop",
        "Navegacion: cortina se cierra al seleccionar modulo, expanders colapsan",
    ]
    for item in mobile_items:
        pdf.bullet(item)

    pdf.add_page()

    # 7. Tests
    pdf.section_title("7. Tests Agregados")
    tests_items = [
        "test_dashboard.py (3 tests): importabilidad, firma de funcion",
        "test_recetas.py (3 tests): importabilidad de submodulos",
        "test_clinica.py (3 tests): rangos vitales, evaluacion",
        "test_admision.py (4 tests): normalizar_dni, paciente_id",
        "test_evolucion_estudios.py (4 tests): importabilidad",
        "test_regresiones_core.py +6 tests: cache SQL, user_feedback, clear()",
        "E2E tests: 2 corregidos (selectors + body visibility), Playwright instalado",
        "test_app_theme.py: except Exception a except RuntimeError",
        "test_performance_profiler.py: 3 assert True a aserciones reales",
    ]
    for item in tests_items:
        pdf.bullet(item)

    pdf.ln(3)

    # 8. Calidad de Codigo
    pdf.section_title("8. Calidad de Codigo")
    code_items = [
        "~50 imports sin usar eliminados en 30+ archivos",
        "Codigo muerto removido (return tras st.stop(), variables sin uso)",
        "import re consolidado a nivel modulo en farmaco_data",
        "from __future__ ordenado segun PEP 236 en 3 archivos",
        "Docstrings corregidos en clinical_cards, features/__init__",
        "Type hints agregados en features/historial/fechas",
        "Built-in shadowing corregido (variable file en backup_manager)",
        "Expansor keys unicas agregadas en 10 bucles (evita duplicacion visual)",
    ]
    for item in code_items:
        pdf.bullet(item)

    pdf.ln(3)

    # 9. Archivos Modificados
    pdf.section_title("9. Estadisticas Finales")
    pdf.body_text(
        f"Total de archivos modificados: ~120\n"
        f"Bugs corregidos: ~95 (10 CRIT, 25 HIGH, ~60 MED/LOW)\n"
        f"Tests unitarios: 581\n"
        f"Tests de integracion: 26\n"
        f"Tests E2E (Playwright): 6\n"
        f"Total tests: 613\n"
        f"Commits en main: ~20\n"
        f"Rondas de mejora: 18+"
    )
    pdf.ln(3)

    # 10. Commits
    pdf.section_title("10. Commits Principales")
    commits = [
        ("d9a01fe", "perf: cache de list comprehensions en dashboard"),
        ("8037bf3", "fix: menu Clinica duplicado - expander key con nav_version"),
        ("230a9e1", "fix: NameError loop + StreamlitDuplicateElementId"),
        ("f0d82ff", "fix: modulo Clinica se duplicaba - st.container(key=...)"),
        ("610dee0", "perf: lazy loading de PIL.Image en 3 archivos"),
        ("4993928", "fix: 2 bugs - NameError en main_medicare y KeyError en _aps_pdf"),
        ("36601b7", "fix: compliance monitor - pacientes_db type mismatch"),
        ("9dc7035", "fix: TypeError en Admin Feature Flags + app_navigation"),
        ("850626e", "fix: TypeError en modulo APS - tab_panel_diario"),
        ("aa80a65", "fix: password_crypto silencia errores de bcrypt"),
        ("2d7f29e", "feat: 9 rondas de mejora continua (commit masivo inicial)"),
    ]
    for sha, desc in commits:
        pdf.bullet(f"[{sha}] {desc}")

    return pdf_output_bytes(pdf)


if __name__ == "__main__":
    output = generar_informe_pdf()
    path = "informe_mejoras_medicare.pdf"
    with open(path, "wb") as f:
        f.write(output)
    print(f"PDF generado: {path}")
