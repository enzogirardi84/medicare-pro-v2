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
