from __future__ import annotations

"""Interruptores de producto en un solo lugar (sin secrets).

Secrets (.streamlit/secrets.toml) siguen mandando en conexion Supabase, SMTP, etc.
"""

# False: no muestra el módulo «Alertas app paciente» ni sidebar/banner asociados.
ALERTAS_APP_PACIENTE_VISIBLE = False

# False: no muestra spinner en cada guardado (login, toques rapidos en visitas, etc.).
# Los modulos con formularios grandes llaman `guardar_datos(spinner=True)` a proposito.
GUARDAR_DATOS_SPINNER_DEFAULT = False

# True: ignora spinner=True en guardar_datos y usa el toast silencioso en su lugar.
# Elimina el bloqueo de pantalla en los puntos de guardado critico.
# Cambiar a False para volver al comportamiento original con spinner visible.
GUARDAR_DATOS_FORZAR_SIN_SPINNER = True

# 0 = desactivado. Si el upsert/local supera estos segundos, se emite un log tecnico (sin UI extra).
# En telefonos/red lenta conviene registrar a partir de 2.5s para detectar cuellos de botella reales.
GUARDAR_DATOS_LOG_LENTO_SEGUNDOS = 2.5

# Evita tormentas de guardado. 5s agrupa toques rápidos en medicación/stock y baja la carga a Supabase.
# El guardado pendiente se procesa automáticamente en reruns posteriores.
GUARDAR_DATOS_MIN_INTERVALO_SEGUNDOS = 5.0

# Reintentos de Supabase. Con 2 intentos + 0.15s delay = maximo 150ms extra en caso de error transiente.
SUPABASE_RETRY_ATTEMPTS = 2
SUPABASE_RETRY_BASE_DELAY_SEGUNDOS = 0.15

# Tope de eventos operativos en memoria que viajan en cada guardado.
# 350 entradas reduce payload y mantiene historial operativo reciente.
MAX_LOGS_DB_ENTRIES = 350

# TTL del cache de session_state para cargar_datos.
# 10 min mejora la navegacion entre modulos en telefonos/tablets sin ir a Supabase en cada rerun.
DB_CACHE_TTL_SEGUNDOS = 600

# DESACTIVADO: La API NextGen (localhost:8000) no existe en produccion.
# Con True, el sistema podia borrar evoluciones/vitales de sesion y luego guardar listas vacias en Supabase.
# Dejar en False para usar el guardado clasico via JSON blob en Supabase + guardado_universal local.
ENABLE_NEXTGEN_API_DUAL_WRITE = False

# True: activa el Vigía de Errores (captura centralizada con panel de diagnóstico).
ERROR_TRACKER_ENABLED = True

# Tope global de items por cada lista _db en session_state (excepto logs_db que usa MAX_LOGS_DB_ENTRIES).
# Se deja amplio para no recortar datos clinicos utiles; la optimizacion fuerte debe venir por shards/SQL.
MAX_LIST_ITEMS_GLOBAL = 1000

# Self-Healing IA: diagnóstico y reparación autónoma del código.
# passive: solo detecta y registra (seguro)
# dry_run: genera fixes pero no los aplica automáticamente
# active: aplica fixes que pasan validación
SELF_HEALING_MODE = "passive"
