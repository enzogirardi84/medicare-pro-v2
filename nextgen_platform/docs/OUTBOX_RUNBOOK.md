# Outbox Runbook

## Objetivo

Operar eventos de dominio de forma confiable en alta concurrencia.

## Señales clave

- Endpoint: `GET /v1/system/outbox/status`
- Métricas:
  - `outbox_published_total`
  - `outbox_failed_total`
  - `outbox_status_count{status="pending|retry|published|dead_letter"}`

## Flujo normal

1. Evento entra en `outbox_events` con estado `pending`.
2. Scheduler automático intenta publicar a Celery.
3. Si publica: `published`.
4. Si falla: `retry` con backoff.
5. Si supera intentos máximos: `dead_letter`.

## Acciones operativas

- Si `dead_letter` sube:
  1. Revisar `last_error` en DB.
  2. Corregir integracion/worker.
  3. Reencolar manualmente cambiando estado a `retry` y `attempts=0`.

- Si `pending` crece sostenidamente:
  1. Revisar salud de Redis/Celery.
  2. Subir `outbox_flush_batch_size`.
  3. Escalar workers.

## Comando util local

- Flush manual por tenant admin:
  - `POST /v1/system/outbox/flush?limit=200&reason=<motivo-min-8-chars>` (en produccion agregar `change_ticket=ABC-1234`)
