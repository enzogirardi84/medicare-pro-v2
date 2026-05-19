---
name: medicare-streamlit
description: >
  Reglas y contexto para el proyecto Medicare Pro: app Streamlit
  multi-tenant de gestion clinica con Supabase, fpdf2, Altair, OpenAI/Anthropic.
---

# Medicare Pro — Streamlit Health App

## Stack
- **Frontend**: Streamlit 1.40+
- **Backend**: Supabase (PostgREST) + JSONB monolith fallback local
- **Auth**: bcrypt + JWT, multi-tenant por empresa
- **PDF**: fpdf2 / reportlab
- **Excel**: openpyxl / xlsxwriter
- **Charts**: Altair + plotly
- **AI**: openai / anthropic
- **Testing**: pytest (49 archivos), CI con GitHub Actions

## Convenciones de código
- `from __future__ import annotations` al inicio de cada .py
- Type hints en todas las funciones
- Nombres en español (consistentes con el dominio salud)
- `st.session_state` como capa de caché primaria
- Logging via `core.app_logging.log_event`
- Errores capturados con `try/except` + `log_event`, NUNCA `st.error()` sin log

## Base de datos
- **pacientes**: JSONB monolith en `medicare_db` (id=1) o tabla normalizada
- **fecha_alta**: columna texto ISO (YYYY-MM-DD), presente en pacientes
- **checkin_asistencia**: tiene FK a `usuarios(id)` via `usuario_id`
- **auditoria_legal**: tiene FK a `usuarios(id)` via `usuario_id`, permite NULL
- Backfill: `scripts/backfill_fecha_alta.py` (--apply para escribir)

## Errores comunes al editar
1. `ArrowTypeError: Expected bytes, got 'int'` → hacer `pd.to_numeric` o stringify antes del DataFrame
2. `fpdf2 .encode()` falla en bytes → usar `pdf_output_bytes()` helper
3. `UnboundLocalError` → mover bloque después de la definición de la variable
4. `st.components.v1.html` deprecated → migrar a `st.html`
5. `max(alt.datum[col])` crash en Altair 6.x → usar `df[col].max()` en su lugar

## Views (routing)
- `core/view_registry.py` mapea nombre → módulo/función
- `core/view_roles.py` controla permisos por rol
- `core/app_navigation.py` maneja el dispatch

## PR Checklist
- [ ] `py_compile` pasa todos los archivos modificados
- [ ] No hay `st.components.v1.html` nuevos (usar `st.html`)
- [ ] fpdf2 output usa type-check: `isinstance(pdf_bytes, bytes)`
- [ ] try/except captura y loggea, no traga errores en silencio
