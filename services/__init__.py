"""
Integraciones externas (HTTP, APIs de terceros, webhooks).

Hoy la mayor parte vive en ``core/database.py`` (Supabase) y módulos puntuales.
Incluye:
- ``services.nominatim`` — geocodificación inversa (visitas / mapas).

Otros clientes REST o SDKs conviene agregarlos aquí e importarlos desde ``core`` o
``views`` sin acoplar la UI al transporte.
"""
