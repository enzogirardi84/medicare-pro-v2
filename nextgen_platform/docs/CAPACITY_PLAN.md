# Capacity Plan (10k / 100k / 1M)

## Supuestos base

- Mix de tráfico:
  - 65% lectura (`patients`, `visits`)
  - 20% escritura normal/bulk
  - 10% auth/refresh
  - 5% operaciones administrativas/import/outbox
- Payload promedio moderado.
- Redis y PostgreSQL administrados con monitoreo activo.

## Nivel 1: 10k usuarios concurrentes

- API: 3-5 réplicas.
- Worker imports: 2 réplicas.
- Worker events: 2 réplicas.
- DB: instancia principal + 1 replica lectura.
- Objetivo: p95 < 800ms.

## Nivel 2: 100k usuarios concurrentes

- API: 10-16 réplicas.
- Worker imports: 4-8 réplicas.
- Worker events: 4-6 réplicas.
- DB: principal robusta + 2-3 réplicas + particionado activo.
- Redis: instancia dedicada con alta memoria y replica.
- Objetivo: p95 < 900ms.

## Nivel 3: 1M usuarios concurrentes

- API: 40+ réplicas distribuidas (multi-zona / multi-región según negocio).
- Worker imports: 12+ réplicas.
- Worker events: 10+ réplicas.
- DB:
  - particionado obligatorio por fecha y/o tenant,
  - read replicas por región,
  - estrategia de archivado histórico.
- Capa adicional:
  - CDN global,
  - gateway avanzado (WAF + rate limit global),
  - colas segmentadas por prioridad.
- Objetivo: mantener degradación controlada con SLO acordado.

## Checklist por etapa

1. Ejecutar benchmark reproducible y guardar resultados p95/p99.
2. Ajustar autoscaling con datos reales.
3. Validar runbooks de incidentes (DB, Redis, workers, cola).
4. Repetir pruebas de carga tras cada cambio estructural.
