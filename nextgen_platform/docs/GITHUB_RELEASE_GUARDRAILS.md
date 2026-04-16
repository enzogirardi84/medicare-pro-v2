# GitHub Release Guardrails

## Objetivo

Definir una politica operativa minima para que los merges a `main` no degraden seguridad, estabilidad ni contratos API.

Dependabot (`.github/dependabot.yml`) propone actualizaciones de dependencias pip por separado para la app raiz, `nextgen_platform/apps/api`, `nextgen_platform/apps/worker` y `nextgen_platform/requirements-dev.txt`; revisar PRs de Dependabot antes de merge cuando toquen runtime o tests.

## Branch protection recomendada (`main`)

- Require a pull request before merging.
- Require approvals: minimo 1 aprobacion.
- Dismiss stale pull request approvals when new commits are pushed.
- Require conversation resolution before merging.
- Require linear history (opcional, recomendado).
- Do not allow force pushes.
- Do not allow deletions.

## Required status checks

Configurar como obligatorios:

- `nextgen-pr-gate / gate`
- `nextgen-ci / test-nextgen` (en push a `main/master`)
- `github-actions-lint / actionlint`

Contenido efectivo de **`nextgen-pr-gate / gate`** (`.github/workflows/nextgen-pr-gate.yml`), un solo job de merge:

1. `actionlint` sobre workflows y acciones.
2. `pip-audit -r requirements-dev.txt` y `bandit -q -r apps/api/app` (API).
3. Stack Docker Compose + pytest smoke: `test_auth_contract`, `test_outbox_contract`, `test_system_resilience_contract`, `test_api_guardrails_contract` (misma base que `nextgen-smoke-pr`).
4. Publicacion de JUnit (`pr-gate-junit.xml`), Job Summary y logs Docker en fallo.

Contenido efectivo de **`nextgen-ci / test-nextgen`** (`.github/workflows/nextgen-ci.yml`): corre en **push** a `main`/`master` cuando cambia `nextgen_platform/**` (u otros paths listados en el workflow). Orden: `actionlint` sobre `.github`, `pip-audit -r requirements-dev.txt`, `bandit -q -r apps/api/app` (defensa en profundidad en `main`), Docker Compose y los **seis** contratos de integracion: `test_auth_contract`, `test_outbox_contract`, `test_outbox_scheduler_contract`, `test_import_csv_contract`, `test_system_resilience_contract`, `test_api_guardrails_contract`. Salida: `full-junit.xml`, Job Summary y logs Docker en fallo. El workflow `github-actions-lint` sigue siendo util en PRs que solo tocan `.github` sin pasar por `nextgen-ci`/`nextgen_platform`.

Si ya exiges `nextgen-pr-gate`, el workflow `github-actions-lint` puede ser redundante para cambios bajo `nextgen_platform`; se mantiene util para PRs que solo tocan `.github` sin pasar por el gate.

Sugeridos adicionales:

- `nextgen-security / security-scan`
- `nextgen-nightly-load` (no bloqueante para merge diario, si para release formal)

## Disparadores (`paths`) en workflows NextGen

Los workflows `nextgen-pr-gate`, `nextgen-smoke-pr`, `nextgen-security` y `nextgen-ci` usan filtros `nextgen_platform/**` mas `.github/workflows/**` (y `.github/actions/**` donde aplica). Asi, un PR o push que solo toque un YAML de workflow o una accion compuesta vuelve a ejecutar los checks sin depender de listar cada archivo a mano.

## Timeouts de jobs (referencia operativa)

Valores actuales de `timeout-minutes` en `.github/workflows/nextgen-*.yml`. Si un run se corta sin error claro en logs, revisar primero este tope antes de asumir fallo de red o de tests.

| Archivo workflow | Minutos | Uso resumido |
|------------------|--------:|--------------|
| `nextgen-pr-gate.yml` | 40 | PR: lint + seguridad + Compose + smoke |
| `nextgen-ci.yml` | 40 | Push main: lint + seguridad + Compose + contratos completos |
| `nextgen-smoke-pr.yml` | 35 | PR: Compose + smoke (sin pip-audit/bandit en job) |
| `nextgen-security.yml` | 25 | pip-audit + bandit |
| `nextgen-release-readiness.yml` | 60 | Gate manual pre-release |
| `nextgen-nightly-load.yml` | 60 | Cron k6 + stack |
| `nextgen-guardrails-load.yml` | 40 | k6 guardrails (manual) |
| `nextgen-post-release-verify.yml` | 120 | Health rounds + umbrales |
| `nextgen-post-release-watch.yml` | 125 | Ventana larga de vigilancia |
| `nextgen-post-release-watch-scheduled.yml` | 40 | Cron staging |
| `nextgen-release-notes.yml` | 10 | Borrador de notas |
| `nextgen-release-promote.yml` | 10 | Promocionar draft |

## Regla de merge seguro

Solo mergear cuando:

1. `nextgen-pr-gate` esta verde.
2. No hay vulnerabilidades nuevas criticas/altas.
3. No hay cambios pendientes en runbooks si se tocaron alertas o guardrails.
4. Se actualizo checklist de go-live cuando aplique.

## Preflight local antes de push

Ejecutar desde `nextgen_platform`:

- Modo rapido:
  - `powershell -ExecutionPolicy Bypass -File scripts/preflight_check.ps1 -Mode quick`
- Modo completo:
  - `powershell -ExecutionPolicy Bypass -File scripts/preflight_check.ps1 -Mode full -StrictGit`

## Release readiness manual (`nextgen-release-readiness`)

Workflow disparado a mano antes de publicar o de promover un release. Levanta Docker Compose, ejecuta actionlint, `pip-audit`, `bandit` y contratos de integracion contra la API local.

Elegir un nivel segun riesgo y tiempo:

| Nivel | Inputs | Uso tipico |
|------|--------|------------|
| **Smoke (default)** | (ninguno extra) | Gate rapido: contratos auth + outbox + resilience + guardrails API. |
| **Import CSV** | `run_import_contract=true`, `run_full_contracts=false` | Validar workers Celery + import + retry sin correr el suite completo. Se ignora si ya activaste el full. |
| **Full contracts** | `run_full_contracts=true` | Release formal: incluye scheduler de outbox, import CSV y todos los contratos alineados con `run_integration_contracts.ps1`. |

Recomendacion: release formal con cambios en API, workers o import -> `run_full_contracts=true`. Si solo cambian rutas sin import, puede bastar el smoke; si solo tocas pipeline de import, `run_import_contract=true` puede ser suficiente sin el full.

## Draft de release en GitHub

- Workflow: `nextgen-release-notes`.
- Recomendado para release formal: `create_github_release=true`.
- Mantener el release en `draft` hasta completar validacion operativa.
- Promocion a publicado: `nextgen-release-promote` (solo tras checklist go-live y evidencia CI verde).
- Verificacion posterior obligatoria: `nextgen-post-release-verify` sobre entorno real (recomendado 3 rondas con 5 min entre rondas); falla automaticamente si algun endpoint queda sobre su umbral de latencia.
- Vigilancia extendida opcional: `nextgen-post-release-watch` (ej. 60 min con chequeo cada 10 min); falla automaticamente si algun endpoint supera su umbral.
- Vigilancia periódica de staging: `nextgen-post-release-watch-scheduled` con secret `NEXTGEN_POST_RELEASE_BASE_URL`; tambien falla automaticamente ante endpoints sobre umbral.
- Umbral de latencia opcional en staging: secret `NEXTGEN_POST_RELEASE_MAX_TOTAL_TIME_SECONDS` (segundos, ej. `2.0`).
- Umbrales por endpoint opcionales: `NEXTGEN_POST_RELEASE_MAX_TOTAL_TIME_HEALTH_SECONDS`, `NEXTGEN_POST_RELEASE_MAX_TOTAL_TIME_LIVE_SECONDS`, `NEXTGEN_POST_RELEASE_MAX_TOTAL_TIME_READY_SECONDS`.
- Reintentos por endpoint para mitigar fallos transitorios: `retry_attempts` y `retry_sleep_seconds` en workflows manuales.
- Guardrail agregado de latencia (promedio vs umbral): por defecto el workflow falla si hay endpoint en rojo; en verificación y vigilancia manual se puede desactivar con input `fail_on_latency_breach=false` (solo diagnostico en staging). En `nextgen-post-release-watch-scheduled`, ejecuciones por cron usan el secret opcional `NEXTGEN_POST_RELEASE_FAIL_ON_LATENCY_BREACH` (`false` para no fallar por ese guardrail).
- Implementacion en repo: `scripts/post_release_http_verify.sh` (comprobaciones HTTP y CSV de reporte) y `scripts/post_release_aggregate_latency.sh` (tablas Markdown y guardrail agregado). El preflight local valida que existan.

## Nota operativa

Si el repositorio no tiene permisos de admin para configurar branch protection via UI/API, mantener esta guia como politica manual y validar en cada PR.
