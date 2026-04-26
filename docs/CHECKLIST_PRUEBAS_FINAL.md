# Checklist Final de Pruebas — MediCare PRO

> Fecha: 2026-04-26  
> Versión: post-refactor `core/app_*.py` + nav grid + CSS robusto  
> Objetivo: validar estabilidad, rendimiento y UX tras el refactor modular.

---

## 1. Autenticación y Sesión

| # | Escenario | Pasos | Resultado Esperado | Estado |
|---|-----------|-------|-------------------|--------|
| 1.1 | **Login válido** | Ingresar usuario/contraseña correctos | Accede al dashboard, sidebar visible, datos cargados | ⬜ |
| 1.2 | **Login inválido** | Ingresar credenciales erróneas | Mensaje de error amigable, no crash | ⬜ |
| 1.3 | **Logout** | Click en "Cerrar sesión" | Limpia `u_actual`, vuelve a login, sin fugas de datos | ⬜ |
| 1.4 | **Inactividad** | Dejar la app inactiva por el tiempo configurado | Redirige a login, mantiene datos locales | ⬜ |
| 1.5 | **Recarga de página (F5)** | Presionar F5 estando logueado | Mantiene sesión, vuelve al módulo actual vía query params | ⬜ |

---

## 2. Pacientes

| # | Escenario | Pasos | Resultado Esperado | Estado |
|---|-----------|-------|-------------------|--------|
| 2.1 | **Cambiar paciente** | Seleccionar otro paciente del sidebar | Actualiza contexto clínico, vitales, alertas; sin doble rerun | ⬜ |
| 2.2 | **Buscar paciente** | Escribir en el campo de búsqueda del sidebar | Filtra lista en tiempo real, sin lag | ⬜ |
| 2.3 | **Paciente sin datos** | Seleccionar paciente sin evoluciones/vitales | Muestra estado vacío amigable, no error | ⬜ |
| 2.4 | **Selector móvil** | En viewport < 768px, usar selector flotante | Funciona igual que el sidebar, visible y usable | ⬜ |

---

## 3. Navegación y Módulos

| # | Escenario | Pasos | Resultado Esperado | Estado |
|---|-----------|-------|-------------------|--------|
| 3.1 | **Cambiar módulo** | Click en una cápsula de la grilla de navegación | Cambia de vista, URL `?modulo=` actualizado, módulo anterior guardado | ⬜ |
| 3.2 | **Módulo anterior** | Click en "← Anterior" o "← Volver a X" | Navega al módulo previo correctamente | ⬜ |
| 3.3 | **Módulo por query param** | Abrir URL directa `?modulo=recetas` | Carga el módulo si tiene permiso; si no, redirige a válido | ⬜ |
| 3.4 | **Módulo sin permiso** | Intentar acceder a módulo no permitido por rol | Redirige al primer módulo válido del menú, sin error crítico | ⬜ |
| 3.5 | **Módulo con error** | Forzar excepción en un módulo (mock) | Muestra mensaje amigable al usuario + detalle técnico colapsado, app no se rompe | ⬜ |
| 3.6 | **Grilla responsive PC** | En desktop, ver navegación | Cápsulas de 150–170 px, icono + texto, activo resaltado | ⬜ |
| 3.7 | **Grilla responsive móvil** | En mobile, ver navegación | 3 módulos por fila, icono visible, texto con ellipsis, activo resaltado | ⬜ |

---

## 4. Guardado y Datos

| # | Escenario | Pasos | Resultado Esperado | Estado |
|---|-----------|-------|-------------------|--------|
| 4.1 | **Guardar datos** | Click en "Guardar" del sidebar | Guarda en Supabase/local, muestra feedback, sin spinner si está forzado | ⬜ |
| 4.2 | **Abrir (recargar)** | Click en "Abrir" del sidebar | Recarga datos desde fuente, resetea caches, mantiene sesión | ⬜ |
| 4.3 | **Guardado offline** | Cortar conexión a Supabase, guardar | Guarda localmente, avisa modo offline, sin pérdida de datos | ⬜ |
| 4.4 | **Sin pérdida de datos clínicos** | Guardar con `evoluciones_db`, `vitales_db` cargados | No vacía las listas clínicas (regresión crítica previa corregida) | ⬜ |

---

## 5. Roles y Permisos

| # | Escenario | Pasos | Resultado Esperado | Estado |
|---|-----------|-------|-------------------|--------|
| 5.1 | **Usuario Admin** | Loguear como admin/coordinador | Ve todos los módulos, métricas de admin en sidebar | ⬜ |
| 5.2 | **Usuario Operativo** | Loguear como operativo/enfermería | Ve solo módulos asistenciales permitidos | ⬜ |
| 5.3 | **Cambio de rol** | Cambiar rol del usuario en BD, recargar | Menú se adapta al nuevo rol sin reinicio completo | ⬜ |

---

## 6. Rendimiento y Cache

| # | Escenario | Pasos | Resultado Esperado | Estado |
|---|-----------|-------|-------------------|--------|
| 6.1 | **Carga lenta** | Simular conexión lenta (throttling) | App funciona, muestra estados de carga, no timeout | ⬜ |
| 6.2 | **Cache grande** | Acumular > 50 entradas de cache | Auto-limpieza se dispara, registra en logs, no afecta datos clínicos | ⬜ |
| 6.3 | **Rendimiento módulo** | Abrir módulo pesado (ej. historial) | Métricas admin muestran tiempo < 2s, sin bloqueo de UI | ⬜ |

---

## 7. Conectividad

| # | Escenario | Pasos | Resultado Esperado | Estado |
|---|-----------|-------|-------------------|--------|
| 7.1 | **Supabase conectado** | Conexión normal a internet | Carga datos de nube, guarda en nube, badge/modo offline oculto | ⬜ |
| 7.2 | **Modo offline** | Desconectar internet, refrescar | Detecta modo offline, usa datos locales, aviso amigable una sola vez | ⬜ |
| 7.3 | **Reconexión** | Volver a conectar internet | Próximo guardado intenta nube, recupera sincronización | ⬜ |

---

## 8. Estética y UX

| # | Escenario | Pasos | Resultado Esperado | Estado |
|---|-----------|-------|-------------------|--------|
| 8.1 | **Tema profesional aplicado** | Ver cualquier pantalla post-login | Colores corporativos, tipografía legible, sin FOUC | ⬜ |
| 8.2 | **Sin texto superpuesto** | Revisar formularios y tarjetas | No hay overlays solapados, botones no tapan contenido | ⬜ |
| 8.3 | **CSS robusto** | Abrir en Chrome, Firefox, Edge (PC) | Navegación en grilla visible, sin dependencia de `data-testid` frágil | ⬜ |
| 8.4 | **Compatibilidad `:has()`** | Revisar vistas compactas y recetas | Si el navegador no soporta `:has()`, fallback aceptable | ⬜ |

---

## 9. Regresiones Críticas (NO deben ocurrir)

| # | Escenario | Impacto si falla | Verificación Rápida | Estado |
|---|-----------|-----------------|---------------------|--------|
| 9.1 | `ENABLE_NEXTGEN_API_DUAL_WRITE` está `False` | Pérdida total de datos clínicos | Verificar `core/feature_flags.py` | ⬜ |
| 9.2 | `evoluciones_db` no se vacía al guardar | Pérdida de evoluciones | Crear evolución, guardar, recargar, verificar lista | ⬜ |
| 9.3 | `vitales_db` no se vacía al guardar | Pérdida de signos vitales | Crear vital, guardar, recargar, verificar lista | ⬜ |
| 9.4 | Sin doble `st.rerun()` al cambiar paciente | Loop infinito / flash | Cambiar paciente, contar reruns (debe ser 1) | ⬜ |
| 9.5 | `limpiar_cache_app` no borra flags de setup | Reinyección CSS/SEO constante | Verificar logs, no debe haber múltiples inyecciones | ⬜ |

---

## Instrucciones de Uso

1. Marcar cada ítem con ✅ (pasa), ❌ (falla) o ⬜ (pendiente).
2. Si un ítem falla, documentar:
   - Navegador / dispositivo
   - Usuario / rol usado
   - Módulo afectado
   - Captura de pantalla o log relevante
3. Al finalizar, sumar:
   - **Total:** ___
   - **Pasan:** ___
   - **Fallan:** ___
   - **Pendientes:** ___

> **Criterio de aceptación:** Todos los ítems de las secciones 1–7 deben pasar. Los ítems 8–9 son de calidad y regresión: cero fallas críticas permitidas.
