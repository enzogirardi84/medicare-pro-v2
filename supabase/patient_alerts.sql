-- Alertas desde la app Flutter "MediCare paciente" → Edge Function → esta tabla.
-- Streamlit (clave service_role o con políticas adecuadas) lee y actualiza estado.

create table if not exists public.patient_alerts (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    patient_token text not null,
    patient_name text,
    reason_code text not null,
    reason_label text not null,
    note text,
    latitude double precision,
    longitude double precision,
    accuracy_meters double precision,
    sent_at timestamptz,
    source text not null default 'medicare_paciente_alerta_flutter',
    empresa text,
    status text not null default 'nueva'
        check (status in ('nueva', 'en_curso', 'cerrada')),
    atendido_por text,
    notas_equipo text,
    raw_payload jsonb not null default '{}'::jsonb
);

create index if not exists patient_alerts_created_at_idx
    on public.patient_alerts (created_at desc);

create index if not exists patient_alerts_empresa_status_idx
    on public.patient_alerts (empresa, status);

create index if not exists patient_alerts_patient_token_idx
    on public.patient_alerts (patient_token);

comment on table public.patient_alerts is 'Alertas SOS / clinica enviadas desde app paciente; insert via Edge Function submit-patient-alert.';

alter table public.patient_alerts enable row level security;

-- Sin políticas para anon/authenticated: solo service_role (Edge Function + servidor con service key) accede.
-- Si usás anon en Streamlit, agregá políticas explícitas (no recomendado para PHI).
