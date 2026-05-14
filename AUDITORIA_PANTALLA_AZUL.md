# Auditoría — Pantalla azul en módulo "Visitas y Agenda"

**Proyecto:** MediCare Enterprise PRO (`medicare-pro-v2`)
**Deploy auditado:** `medicare-pro-v2-eyqvgkqwvd9e48r5z6klrf.streamlit.app/?modulo=Visitas+y+Agenda`
**Repo identificado en código:** `github.com/enzogirardi84/medicare-pro-v2`
**Fecha:** 2026-05-14
**Modo:** Auditoría primero — sin tocar código todavía

---

## TL;DR — Causa raíz más probable

La "pantalla azul" no es un crash visible. Es el **`backgroundColor = "#0f172a"` del tema oscuro quedando expuesto cuando el contenido no se renderiza**, combinado con **`showErrorDetails = false`** en `.streamlit/config.toml` que oculta el traceback.

El crash subyacente más probable es **uno de estos tres (en orden de probabilidad)**:

| # | Hipótesis | Evidencia | Confianza |
|---|---|---|---|
| **H1** | Streamlit Cloud está sirviendo el **`main.py` equivocado** (apunta a `medicare_billing_pro/billing_app`, no a `main_medicare.py`). El querystring `?modulo=Visitas+y+Agenda` no significa nada en billing → render vacío. | `main.py` literalmente importa `billing_app`. Hay 3 entry points en el repo. | **Alta** |
| **H2** | Excepción no capturada en `core.app_navigation.render_current_view()` al cargar `views.visitas` dinámicamente. Los imports lazy `from core.db_sql import get_turnos_by_empresa` y `from core.nextgen_sync import _obtener_uuid_empresa` dentro de `_agenda_empresa()` pueden fallar en runtime si Supabase no responde. | `render_current_view` tiene `except Exception as exc: st.exception(exc)` (línea 325-328), pero `showErrorDetails=false` puede silenciar el render. | Media-alta |
| **H3** | `apply_professional_theme()` o algún `st.html(CUSTOM_CSS)` inyecta CSS que rompe el layout cuando se navega al módulo. | El theme se aplica con flag de session_state, así que un primer render con error puede dejar el flag activo y el siguiente render solo muestra fondo. | Media |

---

## Hallazgos detallados

### 🔴 P0 — Bloqueantes (causan o amplifican la pantalla azul)

#### 1. Tres entry points distintos, ambigüedad de deploy
```
main.py              → importa medicare_billing_pro.billing_app (NO el programa principal)
main_medicare.py     → entry point real del programa
main_login_fixed.py  → otro entry point con st.set_page_config propio
```
- Si Streamlit Cloud está configurado con `main.py` como archivo principal, está corriendo el billing, no MediCare.
- **Verificar inmediato:** Streamlit Cloud → tu app → Settings → "Main file path".

#### 2. `showErrorDetails = false` en producción
```toml
# .streamlit/config.toml
[client]
showErrorDetails = false
```
- Esto **oculta cualquier traceback** al usuario y al dev. Es la razón por la que ves solo azul en vez de un error rojo.
- Combina con `backgroundColor = "#0f172a"` para producir el efecto de "pantalla azul vacía".

#### 3. Múltiples `st.set_page_config()` en el repo
6 archivos llaman `st.set_page_config()`:
```
core/ui_professional.py:160      (dentro de configure_professional_page)
main_login_fixed.py:18
main_medicare.py:63              (correcto - primer call)
medicare_billing_pro/billing_app.py:14
_gestion_ganadera_senasa_work/Sanidad.py:1705
_gestion_ganadera_senasa_work/web/index.py:3
```
- Streamlit **falla con `StreamlitAPIException`** si se llama dos veces en el mismo run.
- `configure_professional_page()` no se invoca desde main_medicare hoy, pero es una bomba de tiempo.

#### 4. `.streamlit/` contaminada con datos de producción
```
.streamlit/local_data.json
.streamlit/local_data_backup_urgente.json
.streamlit/backup_*.json (10+ archivos)
.streamlit/data_store/
.streamlit/recovery_sql_export_*.json
.streamlit/strong_recovery_*.json
```
- El `.gitignore` excluye estos archivos del repo (✅ bien), pero **siguen subiendo al deploy** si están en el working tree cuando se hace push, dependiendo de cómo despliegues.
- Si Streamlit Cloud lee toda la carpeta `.streamlit/`, puede tardar más en arrancar y registrar timeouts.

---

### 🟡 P1 — Riesgos serios pero no inmediatos

#### 5. `secrets.toml` en `.streamlit/` (gitignored, OK)
- Bien excluido del repo. **Pero verificá:** ¿ya está cargado en Streamlit Cloud → Settings → Secrets?
- Si Supabase no tiene credenciales, todas las queries fallan → H2 se activa.

#### 6. Imports lazy dentro de funciones críticas
```python
# views/_visitas_agenda.py
def _agenda_empresa(mi_empresa, rol):
    from core.db_sql import get_turnos_by_empresa
    from core.nextgen_sync import _obtener_uuid_empresa
```
- Si estos módulos tienen un error de import en producción, **explota recién al abrir el módulo Visitas**, no al boot.
- Ambos archivos existen (`core/db_sql.py`, `core/nextgen_sync.py`), pero hay que verificar que sus deps de runtime funcionen contra el Supabase real.

#### 7. Versión de Python forzada
```
# runtime.txt
python-3.12.8
```
- Python 3.12 + `streamlit>=1.40.0` debería funcionar. Confirmar que Streamlit Cloud soporte 3.12.8 (a veces solo soportan minor 3.11).

#### 8. 339 archivos .py + arquitectura `nextgen_platform/` paralela
- Hay una segunda app FastAPI (`nextgen_platform/apps/api`) que **no necesita estar en el deploy de Streamlit**. Sumas peso de imports y conflicto potencial con `pydantic-settings`.

---

### 🟢 P2 — Calidad / mantenibilidad

#### 9. `core/utils.py` como fachada de 4 submódulos (utils_roles, utils_pacientes, utils_fechas, utils_ui)
- ✅ Bien hecho — reexports correctos y completos para `views/visitas.py`.
- Considerar `__all__` explícito para evitar imports accidentales en pruebas.

#### 10. `from typing_extensions` con `python>=3.12` en deps
- No es bloqueante, pero `typing_extensions` ya no es necesario en 3.12 para la mayoría de tipos.

#### 11. `streamlit-drawable-canvas>=0.9.0`, `fpdf2`, `reportlab`, `xlsxwriter`, `openpyxl`
- Libs pesadas. Si solo se usan en algunos módulos, considerar lazy import para acelerar cold start.

---

## Plan de acción (para próxima sesión — fase código)

Cuando me digas que arranque, voy en este orden:

### Fase 1 (15 min) — Confirmar causa raíz real
1. **Necesito que me pases**:
   - Captura/copia del log de Streamlit Cloud (Manage app → Logs)
   - Captura de Settings → Main file path
   - Confirmación de que tenés cargados secrets en Streamlit Cloud
2. **Cambio temporal**: `showErrorDetails = true` en `.streamlit/config.toml` y deploy → ver traceback real.

### Fase 2 (30-45 min) — Fix P0
3. Renombrar `main.py` → `main_billing.py`. Renombrar `main_medicare.py` → `main.py` (o configurar Streamlit Cloud para apuntar al entry correcto).
4. Limpiar `.streamlit/` de JSON de backup (moverlos a `backups/` raíz).
5. Eliminar `st.set_page_config()` muerto en `core/ui_professional.py:160` (o moverlo a un guard `if __name__ == "__main__"`).
6. Wrapper try/except global en `render_current_view` con **logging a Supabase + st.error visible** aunque `showErrorDetails=false`.

### Fase 3 (1-2 hs) — Robustez del módulo Visitas
7. Mover imports lazy críticos (`db_sql`, `nextgen_sync`) al top con manejo explícito de `ImportError`.
8. Hacer fallback graceful: si SQL no responde en 3s, mostrar estado cache + warning en pantalla en vez de explotar.
9. Test de smoke: levantar Streamlit local con `secrets.toml` real apuntando a Supabase → confirmar que `render_visitas` carga sin excepción.

### Fase 4 — Cleanup (opcional, P1/P2)
10. Mover `nextgen_platform/` a un repo aparte o agregar `.streamlitignore` (no existe oficialmente, pero podés excluir subiendo solo lo necesario).
11. Lazy-load de libs pesadas (`reportlab`, `fpdf2`, etc.) dentro de funciones que las usan.

---

## Qué necesito de vos para arrancar la Fase 1

1. **Log de Streamlit Cloud** del último crash. Estructura: ir a tu app → menú "..." → "Manage app" → pestaña "Logs" → copiar las últimas 100 líneas, especialmente las que digan `ERROR` o `Traceback`.
2. **Confirmar entry point**: en Streamlit Cloud → Settings, ¿qué dice "Main file path"?
3. **Permiso explícito** para tocar `.streamlit/config.toml` (cambio temporal de `showErrorDetails`) y para reordenar los `main*.py`.

Cuando tengas eso, decime "dale fase 1" y arrancamos con código.
