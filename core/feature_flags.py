"""Interruptores de producto en un solo lugar (sin secrets).

Secrets (.streamlit/secrets.toml) siguen mandando en conexion Supabase, SMTP, etc.
"""

# False: no muestra el módulo «Alertas app paciente» ni sidebar/banner asociados.
ALERTAS_APP_PACIENTE_VISIBLE = False

# False: no muestra spinner en cada guardado (login, toques rapidos en visitas, etc.).
# Los modulos con formularios grandes llaman `guardar_datos(spinner=True)` a proposito.
GUARDAR_DATOS_SPINNER_DEFAULT = False

# 0 = desactivado. Si el upsert/local supera estos segundos, se emite un log tecnico (sin UI extra).
GUARDAR_DATOS_LOG_LENTO_SEGUNDOS = 2.5

# Evita tormentas de guardado por clicks seguidos en pocos milisegundos.
# Se aplica en guardados no forzados (spinner=False/None). Formularios criticos con spinner=True no se limitan.
GUARDAR_DATOS_MIN_INTERVALO_SEGUNDOS = 0.8

# Reintentos de Supabase para picos transitorios de concurrencia/red.
SUPABASE_RETRY_ATTEMPTS = 3
SUPABASE_RETRY_BASE_DELAY_SEGUNDOS = 0.35

# Tope de eventos operativos en memoria que viajan en cada guardado.
# Mantiene los más recientes para evitar crecimiento indefinido del payload.
MAX_LOGS_DB_ENTRIES = 3000

# DESACTIVADO: La API NextGen (localhost:8000) no existe en produccion.
# Con True, el sistema borraba evoluciones/vitales de sesion y luego guardaba listas vacias en Supabase.
# Dejar en False para usar el guardado clasico via JSON blob en Supabase + guardado_universal local.
ENABLE_NEXTGEN_API_DUAL_WRITE = False
