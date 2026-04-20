"""Interruptores de producto en un solo lugar (sin secrets).

Secrets (.streamlit/secrets.toml) siguen mandando en conexion Supabase, SMTP, etc.
"""

# False: no muestra el módulo «Alertas app paciente» ni sidebar/banner asociados.
ALERTAS_APP_PACIENTE_VISIBLE = False

# False: no muestra spinner en cada guardado (login, toques rapidos en visitas, etc.).
# Los modulos con formularios grandes llaman `guardar_datos(spinner=True)` a proposito.
GUARDAR_DATOS_SPINNER_DEFAULT = False

# True: ignora spinner=True en guardar_datos y usa el toast silencioso en su lugar.
# Elimina el bloqueo de pantalla en los 27 puntos de guardado critico.
# Cambiar a False para volver al comportamiento original con spinner visible.
GUARDAR_DATOS_FORZAR_SIN_SPINNER = True

# 0 = desactivado. Si el upsert/local supera estos segundos, se emite un log tecnico (sin UI extra).
# Ajustado a 3.5s porque con compresion gzip el guardado puede tardar ~300ms.
GUARDAR_DATOS_LOG_LENTO_SEGUNDOS = 3.5

# Evita tormentas de guardado. Con compresion, cada save cuesta menos pero igual throttleamos.
# 3s = balance entre frescura de datos y cantidad de upserts a Supabase.
GUARDAR_DATOS_MIN_INTERVALO_SEGUNDOS = 3.0

# Reintentos de Supabase. Con 2 intentos + 0.15s delay = maximo 150ms extra en caso de error transiente.
# Antes: 3 intentos x 0.35s = hasta 1.05s de delay acumulado.
SUPABASE_RETRY_ATTEMPTS = 2
SUPABASE_RETRY_BASE_DELAY_SEGUNDOS = 0.15

# Tope de eventos operativos en memoria que viajan en cada guardado.
# 500 entradas = ~50KB de logs vs 3000 = ~300KB. El payload comprimido ya es mas pequeno.
MAX_LOGS_DB_ENTRIES = 500

# TTL del cache de session_state para cargar_datos.
# Si se cargo hace menos de 300s (5 min), se devuelve el cache sin ir a Supabase.
# Esto evita re-fetches en cada rerun sin perder frescura.
# Aumentado de 90s para mejorar rendimiento en navegación entre módulos.
DB_CACHE_TTL_SEGUNDOS = 300

# DESACTIVADO: La API NextGen (localhost:8000) no existe en produccion.
# Con True, el sistema borraba evoluciones/vitales de sesion y luego guardaba listas vacias en Supabase.
# Dejar en False para usar el guardado clasico via JSON blob en Supabase + guardado_universal local.
ENABLE_NEXTGEN_API_DUAL_WRITE = False
