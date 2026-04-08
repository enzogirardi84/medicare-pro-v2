create extension if not exists pgcrypto;

-- FASE 1: compatibilidad inmediata con la app actual
create table if not exists public.medicare_db (
    id bigint primary key,
    datos jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);

insert into public.medicare_db (id, datos)
values (1, '{}'::jsonb)
on conflict (id) do nothing;

-- FASE 2: estructura normalizada para crecimiento real

create table if not exists public.empresas (
    id uuid primary key default gen_random_uuid(),
    nombre text not null,
    created_at timestamptz not null default now()
);

create table if not exists public.usuarios (
    id uuid primary key default gen_random_uuid(),
    username text unique not null,
    nombre text not null,
    rol text not null,
    empresa text,
    matricula text,
    dni text,
    titulo text,
    estado text default 'Activo',
    created_at timestamptz not null default now()
);

create table if not exists public.pacientes (
    id uuid primary key default gen_random_uuid(),
    codigo_local text unique,
    nombre_completo text not null,
    dni text,
    empresa text,
    estado text default 'Activo',
    created_at timestamptz not null default now()
);

create table if not exists public.detalles_paciente (
    paciente_id uuid primary key references public.pacientes(id) on delete cascade,
    fecha_nacimiento text,
    sexo text,
    telefono text,
    obra_social text,
    direccion text,
    alergias text,
    patologias text,
    updated_at timestamptz not null default now()
);

create table if not exists public.indicaciones (
    id uuid primary key default gen_random_uuid(),
    paciente_id uuid references public.pacientes(id) on delete cascade,
    fecha text,
    medicacion text,
    dias_duracion integer,
    medico_nombre text,
    medico_matricula text,
    firmado_por text,
    estado_clinico text,
    estado_receta text,
    fecha_estado text,
    profesional_estado text,
    matricula_estado text,
    motivo_estado text,
    firma_path text,
    created_at timestamptz not null default now()
);

create table if not exists public.evoluciones (
    id uuid primary key default gen_random_uuid(),
    paciente_id uuid references public.pacientes(id) on delete cascade,
    fecha text,
    firma text,
    contenido jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.estudios (
    id uuid primary key default gen_random_uuid(),
    paciente_id uuid references public.pacientes(id) on delete cascade,
    fecha text,
    tipo text,
    detalle text,
    firma text,
    archivo_path text,
    extension text,
    created_at timestamptz not null default now()
);

create table if not exists public.emergencias (
    id uuid primary key default gen_random_uuid(),
    paciente_id uuid references public.pacientes(id) on delete cascade,
    fecha_evento text,
    hora_evento text,
    categoria_evento text,
    tipo_evento text,
    tipo_traslado text,
    triage_grado text,
    prioridad text,
    codigo_alerta text,
    motivo text,
    direccion_evento text,
    presion_arterial text,
    fc text,
    saturacion text,
    temperatura text,
    glucemia text,
    dolor text,
    conciencia text,
    observaciones text,
    ambulancia_solicitada boolean default false,
    movil text,
    hora_solicitud text,
    hora_arribo text,
    hora_salida text,
    destino text,
    receptor text,
    familiar_notificado text,
    procedimientos text,
    medicacion_administrada text,
    respuesta text,
    observaciones_legales text,
    profesional text,
    matricula text,
    firma_path text,
    created_at timestamptz not null default now()
);

create table if not exists public.cuidados_enfermeria (
    id uuid primary key default gen_random_uuid(),
    paciente_id uuid references public.pacientes(id) on delete cascade,
    fecha text,
    tipo_cuidado text,
    turno text,
    prioridad text,
    riesgo_caidas text,
    riesgo_upp text,
    dolor text,
    objetivo text,
    intervencion text,
    respuesta text,
    observaciones text,
    incidente boolean default false,
    detalle_incidente text,
    zona text,
    aspecto text,
    dolor_curacion text,
    profesional text,
    matricula text,
    created_at timestamptz not null default now()
);

create table if not exists public.escalas_clinicas (
    id uuid primary key default gen_random_uuid(),
    paciente_id uuid references public.pacientes(id) on delete cascade,
    fecha text,
    escala text,
    puntaje numeric,
    interpretacion text,
    observaciones text,
    profesional text,
    matricula text,
    created_at timestamptz not null default now()
);

create table if not exists public.consentimientos (
    id uuid primary key default gen_random_uuid(),
    paciente_id uuid references public.pacientes(id) on delete cascade,
    fecha text,
    firmante text,
    dni_firmante text,
    vinculo text,
    telefono text,
    observaciones text,
    profesional text,
    matricula_profesional text,
    firma_path text,
    created_at timestamptz not null default now()
);

create table if not exists public.auditoria_legal (
    id uuid primary key default gen_random_uuid(),
    fecha text,
    tipo_evento text,
    paciente text,
    accion text,
    actor text,
    matricula text,
    detalle text,
    referencia text,
    extra jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_pacientes_dni on public.pacientes(dni);
create index if not exists idx_indicaciones_paciente on public.indicaciones(paciente_id);
create index if not exists idx_evoluciones_paciente on public.evoluciones(paciente_id);
create index if not exists idx_estudios_paciente on public.estudios(paciente_id);
create index if not exists idx_emergencias_paciente on public.emergencias(paciente_id);
create index if not exists idx_cuidados_paciente on public.cuidados_enfermeria(paciente_id);
create index if not exists idx_escalas_paciente on public.escalas_clinicas(paciente_id);
create index if not exists idx_consentimientos_paciente on public.consentimientos(paciente_id);
create index if not exists idx_auditoria_legal_paciente on public.auditoria_legal(paciente);
