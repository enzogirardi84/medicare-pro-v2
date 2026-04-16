# Integration tests

Pruebas de API + DB + Redis + permisos.

## Ejecucion local (Windows)

1. Instalar dependencias:
   - `pip install -r requirements-dev.txt`
2. Definir URL base:
   - `set NEXTGEN_BASE_URL=http://localhost:8000`
3. Ejecutar contratos principales:
   - `python -m pytest tests/integration/test_auth_contract.py tests/integration/test_outbox_contract.py tests/integration/test_outbox_scheduler_contract.py tests/integration/test_import_csv_contract.py tests/integration/test_system_resilience_contract.py -q`
   - `test_import_csv_contract` incluye `POST /import-jobs/{id}/retry` con `reason` y `retry-failed` masivo.

## Runner rapido (PowerShell)

- Contratos completos: `powershell -ExecutionPolicy Bypass -File scripts/run_integration_contracts.ps1 -BaseUrl http://localhost:8000`
- Solo smoke tipo PR gate (cuatro tests, sin scheduler ni import): agregar `-Quick`

## Smoke suite (rapido pre-deploy)

- Core: cuatro tests alineados con `nextgen-smoke-pr` (incluye `test_api_guardrails_contract`). `powershell -ExecutionPolicy Bypass -File scripts/run_smoke_suite.ps1 -BaseUrl http://localhost:8000`
- Extendido (scheduler + import, como contratos completos): agregar `-Extended`.
