# Autoscaling Policy (Target)

## Objetivo

Escalar recursos automaticamente segun carga real para mantener latencia y throughput.

## Señales principales

- API:
  - `http_req_duration` p95 > 800ms durante 10m.
  - `http_req_failed` rate > 2% durante 5m.
  - CPU promedio > 65% durante 10m.
- Worker imports:
  - `import_jobs_status_count{status="queued|running"}` en tendencia creciente.
  - backlog > 100 jobs durante 10m.
- Worker events:
  - `outbox_status_count{status="pending|retry"}` > 200 durante 10m.

## Reglas sugeridas de escala

1. API:
   - Scale out: +1 réplica cada 5m si p95/CPU superan umbral.
   - Scale in: -1 réplica cada 15m si p95 < 400ms y CPU < 40%.
2. Worker imports:
   - Scale out: +1 réplica si backlog imports > 100.
   - Scale in: -1 réplica si backlog < 20 por 20m.
3. Worker events:
   - Scale out: +1 réplica si outbox pending+retry > 200.
   - Scale in: -1 réplica si pending+retry < 30 por 20m.

## Límites operativos iniciales

- API: min 2 / max 12 réplicas.
- Worker imports: min 1 / max 10 réplicas.
- Worker events: min 1 / max 8 réplicas.

## Nota

Antes de habilitar autoscaling, validar alertas y dashboards estables por 1 semana en carga real.
