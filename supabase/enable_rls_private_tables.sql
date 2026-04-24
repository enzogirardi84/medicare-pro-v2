-- Enable RLS on private application tables exposed in the `public` schema.
--
-- IMPORTANT:
-- 1. Apply this only after configuring the backend with
--    `SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_SECRET_KEY`.
-- 2. This script intentionally does NOT create anon/authenticated policies for
--    the private tables below. The goal is to stop public Data API exposure and
--    keep access limited to trusted backend code using a server-only key.
-- 3. Never expose the service role / secret key in the browser.

do $$
declare
    tbl text;
begin
    foreach tbl in array array[
        'public.medicare_db',
        'public.empresas',
        'public.usuarios',
        'public.pacientes',
        'public.detalles_paciente',
        'public.indicaciones',
        'public.evoluciones',
        'public.estudios',
        'public.emergencias',
        'public.cuidados_enfermeria',
        'public.escalas_clinicas',
        'public.consentimientos',
        'public.auditoria_legal',
        'public.app_login_lockout',
        'public.signos_vitales',
        'public.turnos',
        'public.administracion_med',
        'public.inventario',
        'public.inventario_movimientos',
        'public.facturacion',
        'public.balance',
        'public.checkin_asistencia',
        'public.pediatria',
        'public.recetas',
        'public.visitas'
    ]
    loop
        if to_regclass(tbl) is not null then
            execute format('alter table %s enable row level security', tbl);
        end if;
    end loop;
end $$;

-- Quick audit after running:
-- select schemaname, tablename, rowsecurity
-- from pg_tables
-- where schemaname = 'public'
-- order by tablename;
