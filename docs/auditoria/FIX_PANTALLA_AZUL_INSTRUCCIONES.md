# Fix Pantalla Azul — Instrucciones de Deploy

**Fecha:** 2026-05-14
**Estado:** Código listo, falta subir a GitHub y verificar Streamlit Cloud

---

## ✅ Lo que ya hice (en tu carpeta local)

| # | Cambio | Archivo | Por qué |
|---|---|---|---|
| 1 | Backup defensivo `.bak` de los 5 archivos críticos | `_backups_fix_pantalla_azul/` | Rollback si algo sale mal |
| 2 | `showErrorDetails = true` | `.streamlit/config.toml` | Que se vea el traceback en pantalla, no fondo azul mudo |
| 3 | **`streamlit_app.py` nuevo** (entry point canónico) | `streamlit_app.py` | Streamlit Cloud lo autodetecta y prioriza sobre `main.py` legacy |
| 4 | **🚨 SyntaxError fatal arreglado** en bloque `__main__` truncado | `core/ui_professional.py:319` | El archivo estaba CORTADO en medio de una expresión → no se podía importar → boot rompía con pantalla azul. **Esta era la causa raíz real.** |
| 5 | Removido segundo `st.set_page_config()` muerto | `core/ui_professional.py:160` | Bomba de tiempo: dos llamadas a set_page_config lanzan StreamlitAPIException |
| 6 | Imports SQL al top con guard ImportError + fallback graceful | `views/_visitas_agenda.py` | Si Supabase/db_sql falla, cae a cache local con aviso visible (antes: explotaba con pantalla azul) |
| 7 | Wrapper de errores reforzado en `render_current_view` | `core/app_navigation.py:325-360` | Bloque blanco visible + traceback colapsable + log a error_tracker. **Nunca más pantalla azul muda.** |
| 8 | `.streamlit/` limpiada (8.2 MB → 8 KB) | `_backups_legacy/streamlit/` | Quitar 17 JSONs de backup que volaban en cada deploy |

---

## 🎯 Acciones tuyas en orden (15-20 min)

### Paso 1 — Verificar que el código compila localmente
```powershell
cd "C:\programa de salud optimizado"
python -c "import ast; [ast.parse(open(f).read()) for f in ['streamlit_app.py','main_medicare.py','core/ui_professional.py','core/app_navigation.py','views/_visitas_agenda.py','views/visitas.py']]; print('OK')"
```
Si imprime `OK` → seguís. Si imprime un `SyntaxError` → me avisás.

### Paso 2 — (Opcional pero recomendado) Levantar local primero
```powershell
streamlit run streamlit_app.py
```
Esperás que abra el navegador. Si llegás al login es 🟢. Si ves error rojo con traceback → es ÉXITO también, porque ahora se ve qué falla en vez de pantalla azul.

### Paso 3 — Subir a GitHub
```powershell
cd "C:\programa de salud optimizado"
git status
git add streamlit_app.py .streamlit/config.toml core/ui_professional.py core/app_navigation.py views/_visitas_agenda.py
git add AUDITORIA_PANTALLA_AZUL.md FIX_PANTALLA_AZUL_INSTRUCCIONES.md
git add -u   # registra los archivos que moví a _backups_legacy/
git commit -m "fix(visitas): pantalla azul - syntax error en ui_professional + entry point canonico

- core/ui_professional.py: cerrar parentesis truncado en bloque __main__ que rompia el import
- core/ui_professional.py: remover set_page_config duplicado en configure_professional_page
- streamlit_app.py: nuevo entry point canonico (apunta a main_medicare)
- .streamlit/config.toml: showErrorDetails=true para diagnosticar
- views/_visitas_agenda.py: imports SQL al top con guard + fallback graceful
- core/app_navigation.py: wrapper de errores con bloque blanco anti-pantalla-azul
- .streamlit/: mover 8.2MB de JSONs de backup a _backups_legacy/streamlit/

Refs: AUDITORIA_PANTALLA_AZUL.md"
git push origin main
```
> Si tu rama default no es `main`, usá la tuya (`master`, `dev`, etc.)

### Paso 4 — Configurar Streamlit Cloud (CRÍTICO)

1. Andá a https://share.streamlit.io/ → tu app `medicare-pro-v2-...`
2. Menú **⋮** (los tres puntitos) → **Settings**
3. En **"Main file path"** debe decir exactamente:
   ```
   streamlit_app.py
   ```
   Si dice `main.py` o `main_medicare.py`, **cambialo a `streamlit_app.py`** y guardás.
4. En **Secrets** (mismo Settings, otra pestaña): verificá que estén cargadas las claves de Supabase (`SUPABASE_URL`, `SUPABASE_KEY`, o como las llames). Copiá de tu `.streamlit/secrets.toml` local si falta algo.
5. Volvé al dashboard de la app → **Reboot app**.

### Paso 5 — Probar
1. Abrí `https://medicare-pro-v2-eyqvgkqwvd9e48r5z6klrf.streamlit.app/?modulo=Visitas+y+Agenda`
2. Esperás que cargue (30-60s en cold start).
3. Resultados esperados (en orden de mejor a peor):
   - 🟢 **Mejor caso:** ves el login. Entrás, navegás a Visitas → carga normal.
   - 🟡 **Caso medio:** ves un cartel blanco con traceback. **Copiámelo y te digo el siguiente fix.** Ya no es pantalla azul muda → progreso.
   - 🔴 **Caso peor:** sigue pantalla azul. Entonces el problema es del propio Streamlit Cloud (no de tu código) → revisar logs de "Manage app" y ver si dice "App reboot loop" o "Out of memory".

---

## 🔄 Rollback (si algo se rompe peor)

```powershell
cd "C:\programa de salud optimizado"
copy _backups_fix_pantalla_azul\config.toml.bak .streamlit\config.toml
copy _backups_fix_pantalla_azul\ui_professional.py.bak core\ui_professional.py
copy _backups_fix_pantalla_azul\_visitas_agenda.py.bak views\_visitas_agenda.py
copy _backups_fix_pantalla_azul\app_navigation.py.bak core\app_navigation.py
del streamlit_app.py
git checkout .
```

Los JSONs movidos a `_backups_legacy/streamlit/` se pueden volver si los necesitás:
```powershell
robocopy _backups_legacy\streamlit .streamlit\ /E /MOVE
```

---

## 📋 Próximos pasos (Fase 3 — después de que la app levante)

Cuando me confirmes que ya entra al programa, atacamos:
1. **Borrar `main.py` y `main_login_fixed.py`** (deuda técnica de entry points).
2. **Volver `showErrorDetails = false`** una vez estable.
3. **Mover `nextgen_platform/`** a un repo separado (no debería estar en el deploy de Streamlit).
4. **Lazy-load** de `reportlab`, `fpdf2`, `streamlit_drawable_canvas` para acelerar cold start.
5. **Tests de smoke** del módulo Visitas que corran en CI antes del deploy.

---

## 🆘 Si después de todo esto sigue rota

Mandame estos 3 datos y arreglo en la próxima sesión:
1. Captura del error rojo que aparezca (ahora sí debería verse uno con traceback).
2. Pegada de los logs de **Streamlit Cloud → Manage app → Logs** (últimas 50 líneas).
3. Confirmación del valor de **Settings → Main file path** (screenshot está bien).
