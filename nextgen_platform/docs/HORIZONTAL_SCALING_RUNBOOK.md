# Horizontal Scaling Runbook

## Objetivo

Escalar API y workers de forma controlada ante picos concurrentes.

## Señales para escalar

- `http_req_duration` p95 > objetivo por mas de 10 minutos.
- `outbox_status_count{status="pending|retry"}` en crecimiento sostenido.
- `import_jobs_status_count{status="queued|running"}` con backlog creciente.

## Acciones sugeridas

1. Escalar API:
   - Aumentar replicas de servicio API.
   - Verificar DB pool y limites de conexiones.
2. Escalar workers de imports:
   - Priorizar cola `imports` con mas replicas.
3. Escalar workers de eventos:
   - Ajustar cola `events,reports` por separado.
4. Revisar cache/redis:
   - Confirmar latencia y memoria sin saturación.

## Configuracion base local

- `worker_imports`: dedicado a cola `imports`.
- `worker_events`: dedicado a colas `events,reports`.

## Verificacion post-escalado

- p95/p99 mejora dentro del objetivo.
- backlog de outbox/import vuelve a tendencia descendente.
- error rate estable.
