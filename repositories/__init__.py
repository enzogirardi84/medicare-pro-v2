"""Repositorios de datos con inyeccion RLS multi-tenant.

Cada repositorio encapsula las consultas a Supabase para una tabla/dominio,
inyecta el contexto de tenant (SET LOCAL app.current_empresa_id) para RLS,
y utiliza @st.cache_data para cache cross-session.
"""
