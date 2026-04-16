# Release Template (NextGen)

Usar esta plantilla en cada release para estandarizar decision de salida, evidencia tecnica y rollback.

## 1) Metadata de release

- Version:
- Fecha/hora (UTC):
- Entorno objetivo (`staging`/`production`):
- Responsable release:
- Incident commander de guardia:
- PR(s) / Issue(s):
- `deploy_id` esperado:
- `git_sha` esperado:

## 2) Alcance del cambio

- Resumen funcional (1-3 puntos):
- Componentes impactados (API/workers/infra/monitoring):
- Riesgo estimado (`bajo`/`medio`/`alto`) y por que:
- Cambios de configuracion/secrets:

## 3) Evidencia CI/CD obligatoria

- [ ] `nextgen-pr-gate / gate` verde.
- [ ] `github-actions-lint / actionlint` verde.
- [ ] `nextgen-security / security-scan` verde.
- [ ] `nextgen-release-readiness` verde.
- [ ] `nextgen-release-readiness` con `run_full_contracts=true` (release formal), o `run_import_contract=true` si el full no aplica pero debe validarse import/worker.
- Links a runs/artifacts:
  - PR gate:
  - Security:
  - Release readiness:

## 4) Verificacion pre-deploy

- [ ] Preflight local rapido:
  - `powershell -ExecutionPolicy Bypass -File scripts/preflight_check.ps1 -Mode quick`
- [ ] Preflight local completo:
  - `powershell -ExecutionPolicy Bypass -File scripts/preflight_check.ps1 -Mode full -StrictGit`
- [ ] Checklist go-live validado (`docs/GO_LIVE_CHECKLIST.md`).
- [ ] (Opcional) Contratos locales contra API levantada: `scripts/run_integration_contracts.ps1 -Quick` (paridad con PR gate) o suite completa sin `-Quick`; ver `docs/GO_LIVE_COMMANDS.md`.

## 5) Plan de despliegue

- Ventana de deploy:
- Estrategia (`rolling`/`blue-green`/`canary`):
- Pasos exactos:
  1.
  2.
  3.

## 6) Criterios de exito post-deploy (15-30 min)

- [ ] `/health`, `/live`, `/ready` OK.
- [ ] `API Deployed Version` coincide.
- [ ] `API Deploy ID` coincide.
- [ ] `API Git SHA` coincide.
- [ ] Sin alertas criticas nuevas.
- [ ] Error ratio y p99 dentro de umbral operativo.

## 7) Monitoreo reforzado (24-72h)

- [ ] Seguimiento de `API Regional 5xx Ratio`.
- [ ] Seguimiento de `API Regional Latency vs Global (p99)`.
- [ ] Seguimiento de `API Regional Capacity Share`.
- [ ] Seguimiento de `API Build Info Staleness by Node`.
- [ ] Seguimiento de `API Region Heartbeat Staleness (All Nodes)`.

## 8) Rollback plan

- Condiciones de rollback inmediato:
  - p99 sostenido fuera de objetivo.
  - incremento 5xx por encima de umbral.
  - alerta zonal (`ApiBuildInfoRegionHeartbeatMissing`) persistente.
- Comando/procedimiento de rollback:
- Responsable de ejecutar rollback:
- Tiempo maximo de decision:

## 9) Aprobaciones

- Aprobacion tecnica:
- Aprobacion operativa:
- Aprobacion producto/negocio (si aplica):
- Estado final (`aprobado`/`bloqueado`):

## 10) Resultado y lecciones

- Resultado del release:
- Incidentes durante release:
- Acciones preventivas/postmortem:
