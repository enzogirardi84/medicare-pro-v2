-- Alertas "a prueba de panico" desde app Flutter (triage Rojo / Amarillo / Verde).
-- Insert via Edge Function submit-alerta-paciente (mismo secreto PATIENT_ALERT_INGEST_SECRET).

create table if not exists public.alertas_pacientes (
    id uuid primary key default gen_random_uuid(),
    paciente_id text not null,
    sintoma text not null,
    nivel_urgencia text not null
        check (nivel_urgencia in ('Rojo', 'Amarillo', 'Verde')),
    latitud double precision,
    longitud double precision,
    precision_m double precision,
    empresa text,
    estado text not null default 'Pendiente'
        check (estado in ('Pendiente', 'En camino', 'Resuelto')),
    fecha_hora timestamptz not null default now(),
    atendido_por text,
    notas_equipo text,
    raw_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists alertas_pacientes_empresa_estado_idx
    on public.alertas_pacientes (empresa, estado);

create index if not exists alertas_pacientes_nivel_fecha_idx
    on public.alertas_pacientes (nivel_urgencia, fecha_hora desc);

create index if not exists alertas_pacientes_paciente_idx
    on public.alertas_pacientes (paciente_id);

comment on table public.alertas_pacientes is 'Urgencias app paciente con triage; ver Edge Function submit-alerta-paciente.';

alter table public.alertas_pacientes enable row level security;
