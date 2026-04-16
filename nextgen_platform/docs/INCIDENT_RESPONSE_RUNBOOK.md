# Incident Response Runbook

## Severidad

- **SEV-1**: caída total o pérdida de datos crítica.
- **SEV-2**: degradación fuerte de latencia/errores.
- **SEV-3**: degradación parcial sin impacto masivo.

## Protocolo inicial (0-10 min)

1. Confirmar incidente en dashboards/alertas.
2. Declarar severidad y abrir canal de incidente.
3. Asignar roles:
   - Incident commander
   - Operación infra
   - Aplicación/API
   - Comunicación

## Diagnóstico rápido por síntoma

- **p95/p99 alto + 5xx alto**:
  - revisar readiness de API
  - revisar saturación DB/Redis
  - escalar API temporalmente
- **backlog imports alto**:
  - revisar workers `imports`
  - aplicar `retry-failed` o `import-jobs/{id}/retry` si corresponde (query `reason` obligatorio; `change_ticket` obligatorio en producción)
  - escalar workers de import
- **backlog outbox**:
  - revisar workers `events`
  - ejecutar `outbox/flush` (mismo criterio `reason` / `change_ticket` en producción)
  - verificar dead-letter
- **errores operativos en cambios de resiliencia**:
  - revisar `GET /v1/system/resilience/status`
  - ejecutar `GET /v1/system/resilience/precheck` antes de `switch/rollback`
  - revisar historial `GET /v1/system/resilience/history`
  - confirmar `change_ticket` válido cuando el entorno es `production`
- **GitHub Actions: workflow cancelado o timeout sin error de test claro**:
  - revisar la tabla de **timeouts** por workflow en `docs/GITHUB_RELEASE_GUARDRAILS.md` y comparar con la duracion real del job
  - causas habituales: Compose lento, k6 largo, muchas rondas en post-release (`verify` / `watch`)
  - mitigacion: subir `timeout-minutes` en el YAML correspondiente mediante PR (evitar cambios urgentes sin revision)

## Mitigación estándar

- Reducir presión:
  - limitar operaciones batch/import
  - activar circuit breaker de tenant conflictivo
- Recuperar capacidad:
  - scale out API/workers
  - priorizar colas críticas
- Si persiste:
  - rollback al release anterior estable

## Respuesta rápida para resiliencia runtime

1. Verificar estado:
   - `GET /v1/system/resilience/status`
2. Validar acción sin aplicar:
   - `GET /v1/system/resilience/precheck?operation=...`
3. Aplicar cambio controlado:
   - `POST /v1/system/resilience/switch` (con `reason` y `change_ticket` si aplica)
4. Si el cambio empeora:
   - `POST /v1/system/resilience/rollback-last?confirm=true&reason=...`
5. Si se necesita un punto específico:
   - `POST /v1/system/resilience/rollback/{index}?confirm=true&reason=...`

## Monitoreo recomendado (resilience)

- Dashboard: `NextGen Resilience Operations Overview`
- Alertas clave:
  - `ResiliencePrecheckInvalidRateHigh`
  - `ResilienceRollbackRateHigh`
  - `ResilienceRollbackActivityHigh`
  - `ResilienceConfirmationMissingSpike`
  - `ApiBurstRateLimitBlocksHigh`
  - `ImportTenantThrottleHigh`
  - `ImportCircuitOpenSpike`
  - `ReadReplicaFallbackHigh`
  - `ReadReplicaFallbackRatioHigh`
  - `ReadReplicaUnavailable`
  - `ReadReplicaNotConfiguredUnderLoad`
  - `ApiBusyRejectionsHigh`
  - `ApiRequestTimeoutsHigh`
  - `ApiInflightSaturationHigh`
  - `ApiPayloadTooLargeSpike`
  - `ApiPayloadAbuseBlockedSpike`
  - `ApiAllowlistedPayloadTooLargeSpike`
  - `ApiExternalPayloadTooLargeSpike`
  - `ApiExternalPayloadRatioHigh`
  - `ApiHighErrorCodeRate`
  - `ApiSloBurnRateFast`
  - `ApiSloBurnRateSustained`
  - `ApiLatencyP99HighSustained`
  - `ApiTrafficSurgeHigh`
  - `ApiEndpointErrorRatioHigh`
  - `ApiRuntimeCpuHigh`
  - `ApiRuntimeMemoryHigh`
  - `ApiCapacityEfficiencyDrop`
  - `ApiWeeklyLatencyRegression`
  - `ApiMixedVersionActive`
  - `ApiBuildInfoStaleNode`
  - `ApiBuildInfoRegionHeartbeatMissing`
  - `ApiRegionalCapacityImbalanceHigh`
  - `ApiRegionalErrorRatioSkewHigh`
  - `ApiRegionalLatencySkewHigh`
- Marcadores de release:
  - revisar `API Deployed Version` para confirmar versión activa en producción
  - revisar `API Deploy ID` para confirmar el identificador exacto de despliegue
  - revisar `API Git SHA` para mapear incidente a commit exacto
  - revisar `Release Changes (24h)` para validar si el incidente coincide con un despliegue reciente
  - revisar `Active API Nodes by Region` para detectar mix de versiones por región/nodo
  - revisar `Active API Versions by Region` para confirmar si el mix de versiones está concentrado en una región específica
  - revisar `API Build Info Staleness by Node` para detectar nodos sin heartbeat reciente de métricas
  - revisar `API Region Heartbeat Staleness (All Nodes)` para confirmar si una región completa dejó de reportar heartbeat
  - revisar `API Regional Capacity Share` para validar distribución saludable de capacidad entre regiones
  - revisar `API Regional 5xx Ratio` para detectar degradación concentrada en una región específica
  - revisar `API Regional Latency vs Global (p99)` para detectar degradación de latencia regional antes de impacto global
- Diagnóstico de fallback readonly:
  - revisar panel `Read DB Fallback by Reason`
  - `replica_unavailable`: investigar conectividad/salud de read replica
  - `replica_not_configured`: validar configuración `read_database_url` por entorno
- Diagnóstico de guardrails API:
  - revisar `API Guardrail Rejections Rate`
  - revisar `API Inflight Requests (current)` para saturación sostenida
  - si domina `inflight_limit_exceeded` o `priority_lane_reserved`: escalar réplicas API o ajustar `api_max_inflight_requests`
  - si domina `request_timeout`: revisar queries/límites por endpoint y dependencia degradada
  - si domina `payload_too_large`: validar clientes y límites `api_max_request_body_bytes`
  - si alerta `ApiPayloadTooLargeSpike`: identificar cliente emisor y corregir contrato/tamaño de request
  - si alerta `ApiPayloadAbuseBlockedSpike`: revisar IP/cliente bloqueado temporalmente por abuso y aplicar comunicación/corrección al integrador
  - si alerta `ApiAllowlistedPayloadTooLargeSpike`: revisar integraciones internas/allowlisted en panel `Payload Too Large by Allowlist`
  - si alerta `ApiExternalPayloadTooLargeSpike`: evaluar abuso externo, reforzar protección perimetral y coordinar mitigación con cliente externo
  - si alerta `ApiExternalPayloadRatioHigh`: priorizar mitigación externa inmediata (WAF/rate limits/upstream filtering)
  - contraste rápido con stats: `External Payload Too Large (1h)` y `Allowlisted Payload Too Large (1h)`
  - severidad ejecutiva rápida: `External Payload Ratio (5m)`
  - diagnóstico transversal de errores:
    - revisar `Top 5 API Error Codes (1h)` para identificar error dominante del incidente
    - revisar `API Error Codes Rate (Top 10)` para confirmar si el spike es sostenido y por `status` (4xx/5xx)
    - si alerta `ApiHighErrorCodeRate`: priorizar mitigación sobre el `code/status` con mayor tasa y abrir ticket técnico específico
  - diagnóstico SLO:
    - revisar `API SLO Burn Rate (5m)` para severidad inmediata (pico corto)
    - revisar `API SLO Burn Rate (1h)` para degradación sostenida
    - referencia operativa: `>14` en 5m = incidente crítico; `>6` en 1h = degradación sostenida que requiere mitigación
  - diagnóstico de latencia:
    - revisar `API Latency Global (p95/p99)` para confirmar si el problema es general
    - revisar `Top 5 Endpoint Latency (p99)` para identificar la ruta principal degradada
    - si alerta `ApiLatencyP99HighSustained`: aplicar mitigación en endpoint dominante (query tuning, cache, timeout/dependency control) y monitorear recuperación
  - diagnóstico de carga/tráfico:
    - revisar `API Throughput Global (RPS)` para detectar picos de tráfico reales
    - revisar `Top 10 Endpoint Throughput (RPS)` para identificar rutas dominantes en volumen
    - si alerta `ApiTrafficSurgeHigh`: priorizar escalado horizontal/API autoscaling y rate controls antes de optimización fina
  - diagnóstico de calidad por endpoint:
    - revisar `Top 10 Endpoint Error Ratio (5xx/total)` para ubicar rutas que fallan primero
    - correlacionar endpoint degradado contra `Top 10 Endpoint Throughput (RPS)` y `Top 5 Endpoint Latency (p99)`
    - si alerta `ApiEndpointErrorRatioHigh`: mitigar en el endpoint dominante (rollback focalizado, feature flag o degradación controlada) y confirmar caída de ratio
  - diagnóstico de saturación runtime:
    - revisar `API Runtime CPU Usage (cores)` para confirmar presión de CPU en procesos API
    - revisar `API Runtime Memory RSS` para detectar presión de memoria o fuga
    - si alerta `ApiRuntimeCpuHigh`: escalar réplicas, revisar consultas pesadas y limitar carga no crítica
    - si alerta `ApiRuntimeMemoryHigh`: revisar batch payloads/objetos grandes, validar límites y considerar restart controlado + ajuste de capacidad
  - diagnóstico de capacidad efectiva:
    - revisar `API Capacity Efficiency (RPS per Core)` para detectar pérdida de eficiencia
    - revisar `Error Ratio vs CPU Load` para validar si el aumento de errores acompaña la presión de CPU
    - si alerta `ApiCapacityEfficiencyDrop`: comparar con línea base histórica y decidir entre optimización de hot paths o escalado horizontal
  - diagnóstico contra baseline semanal:
    - revisar `Weekly Baseline: API p99 Latency` para comparar hora actual contra misma ventana de la semana pasada
    - revisar `Weekly Baseline: RPS per Core` para detectar si la eficiencia cayó respecto del baseline
    - si alerta `ApiWeeklyLatencyRegression`: tratar como regresión de performance, revisar cambios recientes y ejecutar rollback/mitigación focalizada si persiste
  - diagnóstico por release:
    - confirmar versión desplegada en `API Deployed Version`
    - confirmar correlación técnica con `API Deploy ID` y `API Git SHA`
    - si `Release Changes (24h)` > 0 y el inicio del incidente coincide temporalmente, priorizar análisis de cambio/release reciente
    - usar esta correlación para decidir rollback rápido o feature-flag disable en cambios de alto riesgo
    - si alerta `ApiMixedVersionActive`: validar estrategia de rollout/canary, confirmar nodos rezagados y completar rollback/rollforward consistente
    - si alerta `ApiBuildInfoStaleNode`: validar salud de scrape de Prometheus, estado del pod/nodo reportado y reinicio/reemplazo del nodo si no recupera heartbeat
    - si alerta `ApiBuildInfoRegionHeartbeatMissing`: tratar como incidente zonal (red/scrape/cluster), desviar tráfico de la región afectada y escalar a infraestructura de inmediato
    - si alerta `ApiRegionalCapacityImbalanceHigh`: revisar autoscaling por región, afinidad/topology spread y balanceador global para evitar concentración de capacidad en una sola región
    - si alerta `ApiRegionalErrorRatioSkewHigh`: comparar `API Regional 5xx Ratio` contra latencia/tráfico regional y aplicar failover parcial o ajuste de enrutamiento para aislar la región degradada
    - si alerta `ApiRegionalLatencySkewHigh`: confirmar región con p99 degradado en `API Regional Latency vs Global (p99)`, revisar dependencia local (DB/cache/red), y aplicar enruteo preferente hacia regiones sanas hasta normalizar
  - política de retry cliente:
    - `server_busy` (503): respetar `Retry-After` y aplicar backoff exponencial
    - `request_timeout` (504): respetar `Retry-After` y reducir concurrencia del cliente

## Playbook de alertas read-replica

1. `ReadReplicaUnavailable` (prioridad máxima):
   - confirmar estado de red/DNS/TLS hacia la réplica
   - validar credenciales y límites de conexión del nodo réplica
   - si persiste >15 min, escalar a infra DB y mantener monitoreo de `ReadReplicaFallbackRatioHigh`
2. `ReadReplicaFallbackRatioHigh`:
   - revisar ratio actual en `Read DB Fallback Ratio (5m)`
   - verificar si el motivo dominante en `Read DB Fallback by Reason` es `replica_unavailable` o `replica_not_configured`
   - si es `replica_unavailable`, tratar como incidente de capacidad/ruta de lectura
3. `ReadReplicaNotConfiguredUnderLoad`:
   - validar `read_database_url` en entorno afectado
   - revisar cambios recientes de secretos/config deploy
   - si fue cambio no intencional, revertir config y revalidar en dashboard
4. Criterio de cierre:
   - `ReadReplicaAvailable (1/0)` estable en `1`
   - `Read DB Fallback Ratio (5m)` por debajo del umbral operativo esperado
   - sin re-disparo de alertas en al menos 30 minutos

## Checklist pre/post deploy (read-replica)

- Pre-deploy:
  - confirmar `read_database_url` en variables del entorno objetivo
  - validar conectividad desde API hacia host/puerto de réplica
  - verificar credenciales y permisos de solo lectura
  - confirmar `read_db_fail_open` según política del entorno
- Post-deploy (primeros 15 minutos):
  - validar `Read Replica Available (1/0)` en `1`
  - validar que `Read DB Fallback Ratio (5m)` se mantenga en rango esperado
  - revisar panel `Read DB Fallback by Reason` sin crecimiento anómalo
  - confirmar ausencia de alertas `ReadReplicaUnavailable` y `ReadReplicaNotConfiguredUnderLoad`
- Gate de rollback operativo:
  - si `ReadReplicaUnavailable` persiste >15 minutos, evaluar rollback de configuración/release
  - si `ReadReplicaNotConfiguredUnderLoad` aparece tras deploy, revertir configuración de entorno
  - documentar decisión y evidencia en el timeline del incidente/cambio

## Cierre y postmortem

1. Registrar línea temporal del incidente.
2. Identificar causa raíz y acciones correctivas.
3. Definir acciones preventivas con fecha y dueño.
4. Actualizar runbooks/alertas según aprendizaje.
