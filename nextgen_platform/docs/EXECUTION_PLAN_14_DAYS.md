# Execution Plan - 14 Days (Local to Internet)

## Día 1 - Baseline técnico

- Levantar stack local completo.
- Verificar `health/live/ready`.
- Ejecutar tests de contrato.
- Guardar benchmark inicial (p95/p99/error-rate).

## Día 2 - Hardening de configuración

- Crear secretos en entorno objetivo.
- Preparar `.env.production` desde template.
- Validar rotación de `JWT_SECRET`.
- Revisar límites de rate limit y circuit breakers.

## Día 3 - Observabilidad operativa

- Confirmar dashboards en Grafana.
- Probar alertas críticas (simulación controlada).
- Validar que runbooks estén accesibles al equipo.

## Día 4 - Base de datos y resiliencia

- Verificar migraciones en staging.
- Ejecutar backup + restore test en staging.
- Confirmar índices y RLS.

## Día 5 - Carga en staging (fase 1)

- Ejecutar `k6_smoke` y `k6_api_flow`.
- Ajustar parámetros de workers por cola.
- Guardar resultados.

## Día 6 - Carga en staging (fase 2)

- Ejecutar `k6_bulk_flow` y `k6_mixed_scale`.
- Ajustar límites de concurrencia y colas.
- Confirmar que p95/p99 cumplan objetivos.

## Día 7 - Chaos test y recuperación

- Ejecutar `scripts/chaos_test.ps1`.
- Medir tiempo de recuperación.
- Ajustar runbook de incidentes según hallazgos.

## Día 8 - Go-live rehearsal (simulado)

- Simular despliegue productivo completo en staging.
- Simular rollback.
- Revisar checklist de go-live.

## Día 9 - Migración piloto (tenant 1)

- Migrar tenant de bajo riesgo.
- Validar integridad de datos.
- Habilitar tenant con feature flag.

## Día 10 - Observación piloto

- Monitorear métricas 24h.
- Resolver incidencias menores.
- Documentar lecciones.

## Día 11 - Cohorte 1 (tenants pequeños)

- Migrar 3-5 tenants.
- Validar KPI por tenant.
- Mantener opción de rollback.

## Día 12 - Cohorte 2 (tenants medianos)

- Migrar siguiente grupo.
- Repetir validación y observación.

## Día 13 - Go-live general controlado

- Abrir tráfico progresivo restante.
- Monitoreo intensivo (war room).
- Ajustes rápidos de réplicas/concurrency.

## Día 14 - Cierre de transición

- Revisar SLO de primera semana.
- Confirmar estabilidad operativa.
- Plan de mejoras post-go-live (30 días).

## Criterios de avance entre días

- CI verde.
- Tests de contrato verdes.
- SLO mínimos cumplidos en benchmark.
- Sin alertas críticas abiertas.
