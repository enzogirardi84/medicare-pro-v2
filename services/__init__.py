"""
Integraciones externas (HTTP, APIs de terceros, webhooks).

Hoy la mayor parte vive en ``core/database.py`` (Supabase) y módulos puntuales.
Nuevos clientes REST o SDKs conviene ubicarlos aquí, p. ej. ``services/nominatim.py``,
e importarlos desde ``core`` o ``views`` sin acoplar la UI al transporte.
"""
