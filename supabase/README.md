# Supabase Setup

## Objetivo

Esta carpeta prepara dos modos de trabajo:

1. Compatibilidad inmediata con la app actual
2. Migracion seria a estructura normalizada para escalar

## Archivos

- `schema.sql`: tabla compatible + tablas normalizadas
- `storage.sql`: buckets sugeridos para adjuntos, firmas y documentos legales

## Estrategia

### Fase 1

Ejecutar `schema.sql` y usar la tabla `medicare_db`.
Con esto la app actual puede funcionar con Supabase sin reescribir todo el backend.

### Fase 2

Migrar gradualmente a tablas:

- pacientes
- detalles_paciente
- indicaciones
- evoluciones
- estudios
- emergencias
- cuidados_enfermeria
- escalas_clinicas
- auditoria_legal
- consentimientos

## Alertas app paciente (Flutter → MediCare)

### Flujo actual (triage Rojo / Amarillo / Verde)

1. SQL: ejecutar **`alertas_pacientes.sql`** (tabla `alertas_pacientes`).
2. Secreto: **Project Settings → Edge Functions → Secrets** → `PATIENT_ALERT_INGEST_SECRET` (misma cadena en la app).
3. Deploy Edge Function:

```bash
supabase functions deploy submit-alerta-paciente --no-verify-jwt
```

4. App Flutter: pantalla **NECESITO AYUDA** → sintomas con iconos → cuenta 3 s → envio a `submit-alerta-paciente` con GPS.
5. MediCare: sidebar y banner si hay **Rojo + Pendiente**; modulo **Alertas app paciente** para gestionar.

### Tabla legacy (opcional)

Si usaste antes `patient_alerts.sql` + `submit-patient-alert`, puede convivir; el panel web lee solo **`alertas_pacientes`**.

---

## Alertas legacy `patient_alerts` (solo si ya lo tenias)

1. SQL **`patient_alerts.sql`**
2. `supabase functions deploy submit-patient-alert --no-verify-jwt`

## Storage

Usar buckets separados para:

- estudios e imagenes
- firmas
- pdfs y respaldos legales
