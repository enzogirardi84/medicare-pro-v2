# Go-Live Checklist (Internet)

## 1) Seguridad

- [ ] Secrets en gestor seguro (sin claves hardcodeadas).
- [ ] TLS/HTTPS activo (certificados válidos y renovación automática).
- [ ] JWT secret rotado y política de rotación definida.
- [ ] RLS validado en tablas multi-tenant.
- [ ] Reglas de rate limiting activas y verificadas.

## 2) Infraestructura

- [ ] Ambientes separados (`staging` y `production`).
- [ ] Backups automáticos de DB configurados.
- [ ] Restore test ejecutado con éxito en staging.
- [ ] Redis con monitoreo de memoria/latencia.
- [ ] Workers por cola (`imports`, `events`, `reports`) desplegados.

## 3) Observabilidad

- [ ] Prometheus + Grafana operativos.
- [ ] Dashboards activos:
  - [ ] `NextGen Platform Overview`
  - [ ] `NextGen SLO Overview`
  - [ ] `NextGen Outbox Overview`
  - [ ] `NextGen Import Jobs Overview`
- [ ] Alertas críticas probadas (simulación controlada).
- [ ] Runbooks accesibles al equipo.

## 4) Calidad y release

- [ ] Pipeline CI verde (`nextgen-ci`).
- [ ] PR gate verde (`nextgen-pr-gate`: actionlint + security + smoke).
- [ ] Release readiness manual verde (`nextgen-release-readiness`, con `run_full_contracts=true` para release formal; opcional `run_import_contract=true` si no usas full pero necesitas contrato de import CSV).
- [ ] Plantilla de release completada (`docs/RELEASE_TEMPLATE.md`).
- [ ] Borrador generado (`nextgen-release-notes` o `scripts/generate_release_draft.py`) y revisado.
- [ ] Carga nocturna activa (`nextgen-nightly-load`).
- [ ] Test de carga pre-go-live con objetivos SLO.
- [ ] Plan de rollback validado.
- [ ] Comunicación de ventana de despliegue.

## 5) Operación post-go-live

- [ ] Verificación post-release ejecutada (`nextgen-post-release-verify`) sobre URL real (3 rondas, 5 min entre rondas); el workflow falla automáticamente si algún endpoint queda sobre su umbral de latencia.
- [ ] Vigilancia extendida ejecutada si el cambio es de alto riesgo (`nextgen-post-release-watch`, ej. 60 min / 10 min); también falla automáticamente si algún endpoint supera su umbral.
- [ ] Guardia activa primeras 24-72h.
- [ ] Revisión de p95/p99 cada 1-2 horas.
- [ ] Revisión de error budget diario primera semana.
- [ ] Plan de ajustes rápidos (concurrency, réplicas, colas).
