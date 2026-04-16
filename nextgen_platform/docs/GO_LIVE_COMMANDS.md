# Go-Live Commands (Reference)

## Local/Staging checks

```bash
docker compose -f infra/docker/docker-compose.yml up --build -d
```

```bash
python -m pytest tests/integration/test_auth_contract.py tests/integration/test_outbox_contract.py tests/integration/test_outbox_scheduler_contract.py tests/integration/test_import_csv_contract.py tests/integration/test_system_resilience_contract.py tests/integration/test_api_guardrails_contract.py -q
```

PowerShell (mismo suite completo o modo rapido alineado con PR gate):

- `powershell -ExecutionPolicy Bypass -File scripts/run_integration_contracts.ps1 -BaseUrl http://localhost:8000`
- `powershell -ExecutionPolicy Bypass -File scripts/run_integration_contracts.ps1 -BaseUrl http://localhost:8000 -Quick`

Smoke local (paridad con `nextgen-smoke-pr`: cuatro tests incl. guardrails):

- `powershell -ExecutionPolicy Bypass -File scripts/run_smoke_suite.ps1 -BaseUrl http://localhost:8000` — equivalente a `run_integration_contracts.ps1 -Quick` (mismos archivos pytest).
- Suite ampliada (scheduler + import): agregar `-Extended` a `run_smoke_suite.ps1`.

## CI / GitHub (timeouts e incidentes)

- Tabla de `timeout-minutes` por workflow: `docs/GITHUB_RELEASE_GUARDRAILS.md` (seccion **Timeouts de jobs**).
- Workflow cancelado o timeout sin fallo claro en tests: `docs/INCIDENT_RESPONSE_RUNBOOK.md` (sintoma **GitHub Actions** en diagnostico rapido).

## Release readiness (GitHub manual gate)

Workflow:

```bash
nextgen-release-readiness
```

Opcional para release formal:

- ejecutar con input `run_full_contracts=true` (incluye import CSV, scheduler outbox y el resto de contratos).
- alternativa si no quieres el suite completo pero si validar imports + workers: `run_import_contract=true` (se ignora si ya activaste `run_full_contracts=true`).
- Matriz de decision (smoke vs import vs full): `docs/GITHUB_RELEASE_GUARDRAILS.md` (seccion **Release readiness manual**).

## Borrador de notas de release (GitHub)

Workflow manual:

```bash
nextgen-release-notes
```

Inputs:

- `version`: etiqueta (ej. `1.2.0`).
- `compare_from`: ref opcional (`v1.1.0` o commit) para rango `ref..HEAD`; vacio = ultimos commits filtrados por rutas.
- `create_github_release`: si `true`, crea/actualiza un GitHub Release en modo draft con el markdown generado.
- `prerelease`: marca el draft como prerelease cuando `create_github_release=true`.

Local (desde la raiz del repo):

```bash
python nextgen_platform/scripts/generate_release_draft.py --version 1.2.0 --out release-draft.md
python nextgen_platform/scripts/generate_release_draft.py --version 1.2.0 --compare-from v1.1.0 --out release-draft.md
```

## Publicar release (promote draft)

Workflow manual:

```bash
nextgen-release-promote
```

Inputs:

- `version`: tag a promover.
- `mark_as_latest`: marca como latest.
- `prerelease`: mantiene release como prerelease.

## Verificacion post-release

Workflow manual:

```bash
nextgen-post-release-verify
```

Inputs:

- `base_url`: URL base del entorno desplegado.
- `expected_version` (opcional): valida `x-api-version`.
- `expected_deploy_id` (opcional): valida `x-deploy-id`.
- `expected_git_sha` (opcional): valida `x-git-sha`.
- `rounds`: cantidad de rondas (recomendado `3`).
- `sleep_seconds`: espera entre rondas (recomendado `300` = 5 min).
- `retry_attempts`: reintentos por endpoint (recomendado `2` para reducir fallos transitorios).
- `retry_sleep_seconds`: espera entre reintentos (recomendado `2`).
- `max_total_time_seconds` (opcional): falla si `curl` `time_total` supera este valor (ej. `2.0`).
- `max_total_time_health_seconds`, `max_total_time_live_seconds`, `max_total_time_ready_seconds` (opcionales): umbral específico por endpoint; tienen prioridad sobre el global.
- `fail_on_latency_breach` (opcional, por defecto `true`): si es `false`, el workflow no falla por el guardrail de **promedio** agregado (tabla con semáforos); los chequeos HTTP y los umbrales por request del script siguen aplicando. Si aun asi hay endpoints por encima del umbral agregado, el Job Summary incluye una seccion **Aggregate latency guardrail (non-blocking)** con aviso explicito.

## Vigilancia post-release (ventana temporal)

Workflow manual:

```bash
nextgen-post-release-watch
```

Inputs:

- `base_url`, mismos headers opcionales que arriba.
- `duration_minutes`: ventana total (recomendado `60`).
- `interval_seconds`: tiempo entre iteraciones (recomendado `600` = 10 min).
- `retry_attempts`: reintentos por endpoint.
- `retry_sleep_seconds`: espera entre reintentos.
- `max_total_time_seconds` (opcional): mismo criterio de latencia que arriba.
- `max_total_time_health_seconds`, `max_total_time_live_seconds`, `max_total_time_ready_seconds` (opcionales): umbral específico por endpoint.
- `fail_on_latency_breach` (opcional, por defecto `true`): igual que en verificación post-release (solo guardrail agregado).

Workflow programado (staging):

```bash
nextgen-post-release-watch-scheduled
```

Requiere secret en GitHub:

- `NEXTGEN_POST_RELEASE_BASE_URL` (URL base de staging).

Opcional:

- `NEXTGEN_POST_RELEASE_MAX_TOTAL_TIME_SECONDS` (umbral de `time_total` por request, ej. `2.0`).
- `NEXTGEN_POST_RELEASE_MAX_TOTAL_TIME_HEALTH_SECONDS` (umbral específico de `/health`).
- `NEXTGEN_POST_RELEASE_MAX_TOTAL_TIME_LIVE_SECONDS` (umbral específico de `/live`).
- `NEXTGEN_POST_RELEASE_MAX_TOTAL_TIME_READY_SECONDS` (umbral específico de `/ready`).
- `NEXTGEN_POST_RELEASE_FAIL_ON_LATENCY_BREACH` (opcional): `false` desactiva solo el fallo por guardrail de **promedio** agregado en ejecuciones por `schedule`; vacío o ausente = aplicar guardrail (comportamiento por defecto).

Script local (Git Bash / Linux), modo rondas:

```bash
export POST_RELEASE_MODE=rounds
export BASE_URL=https://api.example.com
export POST_RELEASE_ROUNDS=3
export POST_RELEASE_SLEEP_SECONDS=300
export POST_RELEASE_RETRY_ATTEMPTS=2
export POST_RELEASE_RETRY_SLEEP_SECONDS=2
export POST_RELEASE_MAX_TOTAL_TIME_SECONDS=2.0
export POST_RELEASE_MAX_TOTAL_TIME_HEALTH_SECONDS=1.0
export POST_RELEASE_MAX_TOTAL_TIME_LIVE_SECONDS=1.0
export POST_RELEASE_MAX_TOTAL_TIME_READY_SECONDS=2.5
bash nextgen_platform/scripts/post_release_http_verify.sh
```

Modo vigilancia por tiempo:

```bash
export POST_RELEASE_MODE=watch
export BASE_URL=https://api.example.com
export POST_RELEASE_WATCH_DURATION_SECONDS=3600
export POST_RELEASE_WATCH_INTERVAL_SECONDS=600
bash nextgen_platform/scripts/post_release_http_verify.sh
```

## Load tests

```bash
k6 run tests/load/k6_smoke.js
k6 run tests/load/k6_api_flow.js
k6 run tests/load/k6_bulk_flow.js
k6 run tests/load/k6_mixed_scale.js
k6 run tests/load/k6_guardrails_resilience.js
```

## Benchmark summary

```powershell
./scripts/run_benchmark.ps1
```

## Chaos test

```powershell
./scripts/chaos_test.ps1
```

## Kubernetes apply (base)

```bash
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/api-deployment.yaml
kubectl apply -f infra/k8s/api-service.yaml
kubectl apply -f infra/k8s/workers-deployments.yaml
kubectl apply -f infra/k8s/hpa.yaml
```

## Health checks

```bash
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/live
curl -fsS http://localhost:8000/ready
```
