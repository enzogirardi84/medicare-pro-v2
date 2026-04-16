# NextGen Platform (base escalable)

Este modulo es un sistema nuevo en paralelo para evolucionar MediCare sin romper el sistema actual.

## Objetivo

- Soportar miles de usuarios concurrentes.
- Desacoplar UI, reglas de negocio y persistencia.
- Probar local primero, despues desplegar en internet.

## Stack sugerido

- API: FastAPI
- DB: PostgreSQL
- Cache/colas: Redis
- Workers: Celery
- Proxy/API gateway local: Nginx
- Observabilidad local: Prometheus + Grafana

## Estructura

- `apps/api`: API principal versionada.
- `apps/worker`: workers asincronos.
- `apps/backoffice`: UI administrativa futura (opcional).
- `libs`: paquetes compartidos (dominio, auth, utilidades).
- `infra`: docker-compose, configuraciones y scripts de entorno.
- `infra/k8s`: manifiestos base para despliegue en Kubernetes.
- `tests`: pruebas unitarias, integracion y carga.
- `docs`: arquitectura y plan de migracion.

## Arranque local

1. Copiar variables:
   - `cp infra/env/.env.example infra/env/.env`
2. Levantar stack:
   - `docker compose -f infra/docker/docker-compose.yml up --build`
   - Contextos de imagen acotados con `apps/api/.dockerignore` y `apps/worker/.dockerignore` (menos bytes enviados al daemon en cada build).
   - Imagenes API/worker ejecutan como usuario no root (`nextgenapi` / `nextgenworker`), con `PYTHONUNBUFFERED`, `PYTHONDONTWRITEBYTECODE` y `PIP_DISABLE_PIP_VERSION_CHECK` para logs claros y menos ruido en build/runtime. En GitHub Actions el composite `nextgen-stack-up` activa **BuildKit** (`DOCKER_BUILDKIT=1`) para builds mas eficientes.
3. Endpoints:
   - API: `http://localhost:8000/health`
   - Liveness: `http://localhost:8000/live`
   - Readiness: `http://localhost:8000/ready`
   - Grafana: `http://localhost:3000`
   - Prometheus: `http://localhost:9090`

## API inicial implementada

- Auth:
  - `POST /v1/auth/register`
  - `POST /v1/auth/login`
  - `POST /v1/auth/refresh`
- Patients:
  - `POST /v1/patients`
  - `POST /v1/patients/bulk`
  - `POST /v1/patients/import/csv` (async, queue worker)
  - `GET /v1/patients` (`limit`, `offset`, `search`)
  - `GET /v1/patients/{patient_id}`
- Visits:
  - `POST /v1/visits`
  - `POST /v1/visits/bulk`
  - `GET /v1/visits` (`limit`, `offset`, `patient_id`)
- Audit:
  - `GET /v1/audit` (roles: `admin`, `auditor`)
- System:
  - `POST /v1/system/outbox/flush` (role: `admin`, `reason` requerido; `change_ticket` obligatorio en produccion)
  - `GET /v1/system/outbox/status` (role: `admin`)
  - `GET /v1/system/tasks/{task_id}` (roles: `admin`, `doctor`)
  - `GET /v1/system/import-jobs/{import_job_id}` (roles: `admin`, `doctor`)
  - `GET /v1/system/import-jobs/{import_job_id}/errors` (roles: `admin`, `doctor`)
  - `GET /v1/system/import-jobs/{import_job_id}/errors.csv` (roles: `admin`, `doctor`)
  - `POST /v1/system/import-jobs/{import_job_id}/retry` (roles: `admin`, `doctor`, `reason` requerido; `change_ticket` obligatorio en produccion)
  - `POST /v1/system/import-jobs/retry-failed` (role: `admin`, `reason` requerido; `change_ticket` obligatorio en produccion)
  - `GET /v1/system/tenant/metrics` (roles: `admin`, `doctor`)
  - `GET /v1/system/self-heal/status` (role: `admin`)
  - `POST /v1/system/self-heal/run` (role: `admin`, `reason` requerido; `change_ticket` obligatorio en produccion; audit)
- `POST /v1/system/self-heal/reset-cooldown` (role: `admin`, `reason` y `change_ticket` requeridos)
  - estado incluye `cooldown_remaining_seconds`, `last_change_utc` y `next_allowed_action_utc`

Autenticacion: `Authorization: Bearer <token>`

## Mejoras enterprise agregadas

- Refresh tokens con rotacion basica.
- Revocacion de token por `jti` usando Redis.
- Logout con revocacion de access + refresh token.
- Auditoria legal (`audit_logs`) al crear pacientes y visitas.
- Control de permisos por rol en endpoints de escritura.
- Rate limiting por usuario/tenant/IP en endpoints principales.
- Idempotencia en escrituras con header `Idempotency-Key`.
- Migraciones versionadas con Alembic.
- SQL base de RLS por tenant: `infra/sql/rls_policies.sql`.
- Guía base de particionado: `infra/sql/partitioning_strategy.sql`.
- Importación CSV asíncrona con tracking persistente (`import_jobs`).
- Tabla `import_job_errors` para errores detallados por fila.
- Unicidad fuerte de pacientes por tenant+document (`ux_patients_tenant_doc_unique`).
- Dashboard de imports: `NextGen Import Jobs Overview`.
- Dashboard unificado: `NextGen Platform Overview`.
- Alertas de import jobs en `infra/monitoring/rules/alerts.yml`.
- Locks anti-colisión en operaciones críticas (`outbox flush`, `retry-failed`).
- Circuit breaker por tenant para imports/outbox ante fallas repetidas.
- Queue partitioning (`imports`, `events`, `reports`) con workers dedicados.
- Outbox pattern base (`outbox_events`) + publicacion API->Celery.
- Reintentos de outbox con backoff + estado `dead_letter`.
- Estandar basico de errores JSON (`error.code`, `error.message`).
- Scheduler automatico de outbox en API (configurable por settings).
- Runbook operativo: `docs/OUTBOX_RUNBOOK.md`.
- Grafana provisionado con dashboard: `NextGen Outbox Overview`.
- Grafana provisionado con dashboard SLO: `NextGen SLO Overview`.
- Alertas Prometheus: `infra/monitoring/rules/alerts.yml`.
- Tuning de DB pool + `statement_timeout` configurable por settings para alta concurrencia.
- Read/Write split opcional (`read_database_url`) para enviar lecturas a réplica sin cambiar endpoints.
- Fallback automático de lecturas a primary si la réplica falla (`read_db_fail_open`, `read_db_healthcheck_interval_seconds`).
- Guardrail por tenant en imports (`import_max_pending_per_tenant`) para evitar monopolio de cola.
- Priorización de imports por tenant configurable (`import_priority_tenant_ids`, `import_priority_high`, `import_priority_default`) manteniendo la misma cola.
- Circuit breaker automático de imports por tenant ante throttling repetido (`import_circuit_breaker_*`).
- Rate limiting con control de burst configurable (`rate_limit_burst_window_seconds`, `rate_limit_burst_multiplier`, `rate_limit_burst_min_requests`) para picos extremos.
- Autopilot de self-healing para dependencias (`self_heal_*`): activa fail-open temporal, aplica cooldown anti-oscilación y revierte automáticamente al recuperarse DB/Redis.

## Tests de integracion (contrato)

1. Instalar deps:
   - `pip install -r requirements-dev.txt`
2. Definir base URL:
   - `set NEXTGEN_BASE_URL=http://localhost:8000` (Windows)
3. Ejecutar:
  - `python -m pytest tests/integration/test_auth_contract.py tests/integration/test_outbox_contract.py tests/integration/test_outbox_scheduler_contract.py tests/integration/test_import_csv_contract.py tests/integration/test_system_resilience_contract.py tests/integration/test_api_guardrails_contract.py -q`

### Runner rapido (PowerShell)

- Script:
  - `scripts/run_integration_contracts.ps1`
- Ejemplo (suite completa):
  - `powershell -ExecutionPolicy Bypass -File scripts/run_integration_contracts.ps1 -BaseUrl http://localhost:8000`
- Modo `-Quick`: solo cuatro tests alineados con el PR gate (sin scheduler ni import CSV).

### Smoke suite (rapido pre-deploy)

- Script:
  - `scripts/run_smoke_suite.ps1`
- Por defecto (core): mismos **cuatro** tests que el smoke PR (`auth`, `outbox`, `system resilience`, `API guardrails`); equivalente a `run_integration_contracts.ps1 -Quick`.
- Modo extendido (`-Extended`): anade scheduler de outbox e import CSV (retry unitario y batch); equivale al suite completo de `run_integration_contracts.ps1`.
- Ejemplos:
  - `powershell -ExecutionPolicy Bypass -File scripts/run_smoke_suite.ps1 -BaseUrl http://localhost:8000`
  - `powershell -ExecutionPolicy Bypass -File scripts/run_smoke_suite.ps1 -BaseUrl http://localhost:8000 -Extended`

## Prueba de carga rapida

- Archivo: `tests/load/k6_smoke.js`
- Ejecucion:
  - `k6 run tests/load/k6_smoke.js`

## Prueba de carga de flujo API

- Archivo: `tests/load/k6_api_flow.js`
- Ejecucion:
  - `k6 run tests/load/k6_api_flow.js`

## Prueba de carga bulk

- Archivo: `tests/load/k6_bulk_flow.js`
- Ejecucion:
  - `k6 run tests/load/k6_bulk_flow.js`

## Prueba de carga mixta (read + bulk + refresh)

- Archivo: `tests/load/k6_mixed_scale.js`
- Ejecucion:
  - `k6 run tests/load/k6_mixed_scale.js`

## Prueba de resiliencia de guardrails (busy/timeout/payload)

- Archivo: `tests/load/k6_guardrails_resilience.js`
- Ejecucion:
  - `k6 run tests/load/k6_guardrails_resilience.js`

## Benchmark reproducible

- Script PowerShell:
  - `scripts/run_benchmark.ps1`
- Resume automáticamente p95/p99/error-rate:
  - `scripts/summarize_benchmark.py`

## Preflight y comandos de go-live

- Preflight local:
  - `scripts/preflight_check.ps1`
  - rapido: `powershell -ExecutionPolicy Bypass -File scripts/preflight_check.ps1 -Mode quick`
  - completo: `powershell -ExecutionPolicy Bypass -File scripts/preflight_check.ps1 -Mode full -StrictGit`
- Comandos de referencia:
  - `docs/GO_LIVE_COMMANDS.md`
  - `docs/GITHUB_RELEASE_GUARDRAILS.md`

## Chaos test básico

- Script:
  - `scripts/chaos_test.ps1`
- Simula caída temporal del worker de eventos y recuperación.

## CI

- Dependabot (repo): actualizaciones semanales de pip para `/`, `nextgen_platform/apps/api`, `nextgen_platform/apps/worker` y `nextgen_platform` (`requirements-dev.txt`); acciones GitHub agrupadas mensualmente (`.github/dependabot.yml`).
- Disparadores: los workflows NextGen listados abajo suelen incluir en `paths` `nextgen_platform/**`, `.github/workflows/**` y `.github/actions/**` (ver `docs/GITHUB_RELEASE_GUARDRAILS.md`).
- Smoke PR: `.github/workflows/nextgen-smoke-pr.yml`
  - Ejecuta build con Docker Compose + smoke contracts (`auth`, `outbox`, `resilience`, `api guardrails`) en pull requests.
- Full contracts (main/master): `.github/workflows/nextgen-ci.yml`
  - Push a `main`/`master`: `actionlint` → `pip-audit` → `bandit` → Docker Compose + seis contratos (`auth`, `outbox`, `outbox scheduler`, `import CSV`, `system resilience`, `API guardrails`). Alineado con el PR gate mas tests completos; artefacto `full-junit.xml`.
- PR gate unificado: `.github/workflows/nextgen-pr-gate.yml`
  - Un solo job: `actionlint` → `pip-audit -r requirements-dev.txt` → `bandit` sobre `apps/api/app` → Docker Compose → mismos smoke que PR smoke (`test_auth_contract`, `test_outbox_contract`, `test_system_resilience_contract`, `test_api_guardrails_contract`), JUnit + Job Summary + artifact `pr-gate-junit.xml`.
- Release readiness manual: `.github/workflows/nextgen-release-readiness.yml`
  - Ejecuta gate manual pre-release (actionlint + seguridad + smoke, opcional full contracts con `run_full_contracts=true`, u opcional solo contrato de import con `run_import_contract=true` si no activas el full).
  - Cuando elegir smoke vs import vs full: `docs/GITHUB_RELEASE_GUARDRAILS.md` (seccion **Release readiness manual**).
- Borrador de notas de release: `.github/workflows/nextgen-release-notes.yml`
  - Genera `release-draft.md` desde `docs/RELEASE_TEMPLATE.md` + changelog Git (artifact + Job Summary).
- Promoción de release: `.github/workflows/nextgen-release-promote.yml`
  - Promueve un draft existente a release publicada con controles explícitos (`latest`/`prerelease`).
- Verificación post-release: `.github/workflows/nextgen-post-release-verify.yml`
  - Valida `health/live/ready` y headers de build (`x-api-version`, `x-deploy-id`, `x-git-sha`, etc.) en entorno real.
  - Input `fail_on_latency_breach` (por defecto `true`): desactiva solo el fallo por promedio agregado vs umbral (útil para diagnóstico en staging).
- Vigilancia post-release: `.github/workflows/nextgen-post-release-watch.yml`
  - Repite las mismas comprobaciones durante una ventana de tiempo (intervalo configurable).
  - Mismo input `fail_on_latency_breach` que la verificación puntual.
- Vigilancia programada de staging: `.github/workflows/nextgen-post-release-watch-scheduled.yml`
  - Ejecuta chequeos periódicos automáticos usando `NEXTGEN_POST_RELEASE_BASE_URL` como secret.
  - Latencia opcional vía `NEXTGEN_POST_RELEASE_MAX_TOTAL_TIME_SECONDS` (secret) y overrides por endpoint (`..._HEALTH_SECONDS`, `..._LIVE_SECONDS`, `..._READY_SECONDS`).
  - Secret opcional `NEXTGEN_POST_RELEASE_FAIL_ON_LATENCY_BREACH` (`false` = no fallar por guardrail agregado en ejecuciones por cron).
- Si fallan tests, los workflows que levantan Compose suelen adjuntar artifact con logs Docker (p. ej. PR gate, smoke PR) para diagnóstico rápido.
- Varios workflows publican `junit.xml` como artifact y resumen en Job Summary.
- Carga nocturna: `.github/workflows/nextgen-nightly-load.yml` (k6 + reporte artifact).

## Runbooks

- Outbox: `docs/OUTBOX_RUNBOOK.md`
- Escalado horizontal: `docs/HORIZONTAL_SCALING_RUNBOOK.md`
- Autoscaling: `docs/AUTOSCALING_POLICY.md`
- Capacity plan: `docs/CAPACITY_PLAN.md`
- SLO targets: `docs/SLO_TARGETS.md`
- Multi-región: `docs/MULTI_REGION_ROLLOUT.md`
- Go-live internet: `docs/GO_LIVE_CHECKLIST.md`
- Plantilla de release: `docs/RELEASE_TEMPLATE.md`
- Ejecución 14 días: `docs/EXECUTION_PLAN_14_DAYS.md`
- Migración por tenant: `docs/TENANT_MIGRATION_GUIDE.md`
- Respuesta a incidentes: `docs/INCIDENT_RESPONSE_RUNBOOK.md`
- Guía de retry para clientes API: `docs/API_CLIENT_RETRY_GUIDE.md`
- Guardrails de release en GitHub: `docs/GITHUB_RELEASE_GUARDRAILS.md` (branch protection, post-release, **inputs de release readiness**, tabla de **timeouts** por workflow).

## Nota

Este modulo no reemplaza automaticamente la app actual.
Se usa para migracion gradual por modulos con feature flags.
