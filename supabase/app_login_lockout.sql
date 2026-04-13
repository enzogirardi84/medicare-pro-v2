-- Bloqueo anti fuerza bruta compartido entre sesiones (opcional).
-- Ejecutar en el SQL editor de Supabase si usás LOGIN_LOCKOUT_PERSIST = supabase en secrets.
--
-- Recomendación: la app debe usar una clave con permisos suficientes (p. ej. service_role)
-- para upsert/delete en esta tabla. Si usás solo la anon key, definí políticas RLS acordes.

create table if not exists public.app_login_lockout (
    login_key text primary key,
    fail_count integer not null default 0,
    locked_until double precision,
    updated_at timestamptz not null default now()
);

create index if not exists idx_app_login_lockout_locked_until
    on public.app_login_lockout (locked_until)
    where locked_until is not null;

comment on table public.app_login_lockout is
    'Contador de intentos fallidos de login por usuario normalizado; locked_until es epoch UNIX.';
