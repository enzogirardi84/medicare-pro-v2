# Multi-Region Rollout Plan

## Objetivo

Escalar de una región a múltiples regiones minimizando latencia y riesgo operativo.

## Fase 1 - Preparación (single-region hardened)

- Consolidar SLO y alertas estables.
- Verificar runbooks (outbox, escalado, incidentes DB/Redis).
- Confirmar backups/restores probados.

## Fase 2 - Región secundaria pasiva

- Replicar infraestructura en región B (API, workers, observabilidad).
- Mantener tráfico principal en región A.
- DB con réplica de lectura o DR según proveedor.

## Fase 3 - Active/Passive con failover controlado

- DNS/Gateway con failover manual asistido.
- Pruebas periódicas de conmutación (drills).
- Monitorear RPO/RTO reales.

## Fase 4 - Active/Active gradual

- Habilitar porcentaje de tráfico en región B (canary por tenant).
- Definir estrategia de datos:
  - opción 1: writer único + readers regionales
  - opción 2: partición por tenant/región
- Sincronización y consistencia explícitas para eventos async.

## Decisiones críticas

1. Estrategia de datos multi-región (consistencia vs latencia).
2. Política de afinidad por tenant (stickiness regional).
3. Resolución de conflictos en procesos async/outbox.

## Métricas de éxito

- p95 regional dentro de objetivo.
- error rate estable en ambas regiones.
- failover validado sin pérdida relevante de datos.
- tiempo de recuperación dentro de RTO objetivo.
