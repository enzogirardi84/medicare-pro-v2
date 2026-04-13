"""Interruptores de producto en un solo lugar (sin secrets).

Secrets (.streamlit/secrets.toml) siguen mandando en conexion Supabase, SMTP, etc.
"""

# False: no muestra el módulo «Alertas app paciente» ni sidebar/banner asociados.
ALERTAS_APP_PACIENTE_VISIBLE = False

# True: `guardar_datos()` muestra spinner «Guardando cambios...» salvo que se llame con spinner=False.
GUARDAR_DATOS_SPINNER_DEFAULT = True
