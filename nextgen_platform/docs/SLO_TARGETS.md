# SLO Targets by Endpoint

## Objetivo

Definir objetivos de calidad (SLO) por tipo de endpoint para operación a gran escala.

## SLO globales

- Disponibilidad mensual API: `>= 99.9%`
- Error rate 5xx mensual: `<= 0.5%`
- Cumplimiento de p95 mensual por endpoint: `>= 95%` de ventanas

## SLO por categoría

1. Auth (`/v1/auth/*`)
   - p95: `<= 350 ms`
   - p99: `<= 700 ms`
   - error rate: `<= 0.8%`

2. Lectura clínica (`GET /v1/patients`, `GET /v1/visits`)
   - p95: `<= 500 ms`
   - p99: `<= 900 ms`
   - error rate: `<= 1.0%`

3. Escritura clínica (`POST /v1/patients`, `POST /v1/visits`, bulk)
   - p95: `<= 800 ms`
   - p99: `<= 1500 ms`
   - error rate: `<= 1.5%`

4. Operaciones async/import (`/v1/patients/import/csv`, `/v1/system/import-jobs/*`)
   - Aceptación de job p95: `<= 600 ms`
   - Tiempo a completitud (SLA orientativo): `<= 5 min` para CSV <= 2MB
   - porcentaje jobs fallidos: `<= 2%`

## Indicadores de error budget

- Error budget mensual 5xx: `0.5%`
- Regla de protección:
  - consumo > 50% del error budget en la primera mitad del mes => congelar cambios de riesgo
  - consumo > 80% => solo fixes de estabilidad/seguridad

## Instrumentación mínima requerida

- `http_requests_total` por status y endpoint.
- `http_request_duration_seconds_bucket` para p95/p99.
- `outbox_status_count` y `outbox_failed_total`.
- `import_jobs_status_count` e `import_jobs_retried_total`.
