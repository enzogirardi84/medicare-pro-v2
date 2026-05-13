-- Auditoria RLS tabla por tabla para Medicare PRO.
-- Ejecutar en Supabase SQL Editor antes de habilitar nuevos modulos en produccion.

-- 1) Estado RLS por tabla publica.
select
  t.schemaname,
  t.tablename,
  t.rowsecurity as rls_enabled,
  t.forcerowsecurity as rls_forced,
  case
    when t.rowsecurity then 'OK_RLS_ENABLED'
    else 'REVISAR_RLS_DESACTIVADO'
  end as estado
from pg_tables t
where t.schemaname = 'public'
order by t.tablename;

-- 2) Politicas declaradas por tabla.
select
  p.schemaname,
  p.tablename,
  p.policyname,
  p.permissive,
  p.roles,
  p.cmd,
  p.qual,
  p.with_check
from pg_policies p
where p.schemaname = 'public'
order by p.tablename, p.policyname;

-- 3) Tablas con RLS activo pero sin politica explicita.
select
  t.tablename
from pg_tables t
left join pg_policies p
  on p.schemaname = t.schemaname
 and p.tablename = t.tablename
where t.schemaname = 'public'
  and t.rowsecurity = true
  and p.policyname is null
order by t.tablename;

-- 4) Tablas privadas esperadas con RLS obligatorio.
with tablas_criticas(tablename) as (
  values
    ('usuarios'),
    ('empresas'),
    ('pacientes'),
    ('visitas'),
    ('evoluciones'),
    ('recetas'),
    ('signos_vitales'),
    ('caja'),
    ('auditoria_legal'),
    ('billing_clientes'),
    ('billing_presupuestos'),
    ('billing_prefacturas'),
    ('billing_cobros'),
    ('billing_facturas_arca')
)
select
  c.tablename,
  coalesce(t.rowsecurity, false) as rls_enabled,
  coalesce(count(p.policyname), 0) as policies_count
from tablas_criticas c
left join pg_tables t
  on t.schemaname = 'public'
 and t.tablename = c.tablename
left join pg_policies p
  on p.schemaname = 'public'
 and p.tablename = c.tablename
group by c.tablename, t.rowsecurity
order by c.tablename;
