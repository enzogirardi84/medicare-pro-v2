-- ============================================================
-- FIX para Medicare Pro - Corregir esquema Supabase
-- Ejecutar en: Supabase Dashboard → SQL Editor
-- ============================================================

-- 1. Verificar que la columna nombre_completo existe en pacientes
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_schema = 'public' AND table_name = 'pacientes' AND column_name = 'nombre_completo'
  ) THEN
    ALTER TABLE public.pacientes ADD COLUMN nombre_completo text;
  END IF;
END $$;

-- 2. Verificar columnas en pacientes
ALTER TABLE public.pacientes ADD COLUMN IF NOT EXISTS dni text;
ALTER TABLE public.pacientes ADD COLUMN IF NOT EXISTS empresa text;
ALTER TABLE public.pacientes ADD COLUMN IF NOT EXISTS estado text DEFAULT 'Activo';
ALTER TABLE public.pacientes ADD COLUMN IF NOT EXISTS telefono text;
ALTER TABLE public.pacientes ADD COLUMN IF NOT EXISTS obra_social text;
ALTER TABLE public.pacientes ADD COLUMN IF NOT EXISTS direccion text;
ALTER TABLE public.pacientes ADD COLUMN IF NOT EXISTS fecha_nacimiento text;
ALTER TABLE public.pacientes ADD COLUMN IF NOT EXISTS sexo text;
ALTER TABLE public.pacientes ADD COLUMN IF NOT EXISTS alergias text;
ALTER TABLE public.pacientes ADD COLUMN IF NOT EXISTS patologias text;
ALTER TABLE public.pacientes ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();
ALTER TABLE public.pacientes ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

-- 3. Verificar tablas y FK
CREATE TABLE IF NOT EXISTS public.turnos (
    id uuid primary key default gen_random_uuid(),
    paciente_id uuid references public.pacientes(id) on delete cascade,
    empresa_id uuid references public.empresas(id) on delete cascade,
    profesional text,
    fecha_hora timestamptz,
    tipo text,
    estado text default 'Pendiente',
    created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS public.checkin_asistencia (
    id uuid primary key default gen_random_uuid(),
    paciente_id uuid references public.pacientes(id) on delete cascade,
    empresa_id uuid references public.empresas(id) on delete cascade,
    tipo text,
    fecha_hora timestamptz,
    latitud float,
    longitud float,
    created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS public.emergencias (
    id uuid primary key default gen_random_uuid(),
    paciente_id uuid references public.pacientes(id) on delete cascade,
    empresa_id uuid references public.empresas(id) on delete cascade,
    prioridad text,
    fecha_llamado timestamptz,
    created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS public.facturacion (
    id uuid primary key default gen_random_uuid(),
    paciente_id uuid references public.pacientes(id) on delete cascade,
    empresa_id uuid references public.empresas(id) on delete cascade,
    concepto text,
    monto_total numeric(12,2),
    estado text,
    observaciones text,
    fecha_emision timestamptz,
    created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS public.evoluciones (
    id uuid primary key default gen_random_uuid(),
    paciente_id uuid references public.pacientes(id) on delete cascade,
    empresa_id uuid references public.empresas(id) on delete cascade,
    contenido text,
    created_at timestamptz default now()
);
