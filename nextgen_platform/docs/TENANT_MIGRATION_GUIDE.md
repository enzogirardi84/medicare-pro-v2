# Tenant-by-Tenant Migration Guide

## Objetivo

Migrar clíncias/tenants de forma gradual del sistema actual al nuevo (`nextgen_platform`) minimizando riesgo.

## Estrategia

1. Pilot tenant (bajo riesgo).
2. Cohortes pequeñas de tenants.
3. Monitoreo y validación por cohorte.
4. Escalado progresivo hasta cobertura total.

## Etapas por tenant

### Etapa A - Preparación

- Validar usuarios/roles y datos base.
- Definir fecha/hora de corte para ese tenant.
- Confirmar rollback plan.

### Etapa B - Migración de datos

- Exportar datos del tenant del sistema legado.
- Transformar al esquema nuevo.
- Importar en entorno objetivo (staging primero, luego prod).
- Verificar integridad (conteos, muestras aleatorias, campos críticos).

### Etapa C - Activación controlada

- Habilitar tenant en el sistema nuevo (feature flag).
- Mantener observación reforzada (latencia, errores, import/outbox).
- Confirmar operación con usuario referente del tenant.

### Etapa D - Estabilización

- Monitorear 24-72h.
- Resolver incidentes menores.
- Confirmar cierre de migración de tenant.

## Criterios de rollback por tenant

- Error rate > umbral acordado por período sostenido.
- Inconsistencias de datos críticas no resueltas.
- Fallas operativas que bloqueen atención clínica.

## Checklist por tenant

- [ ] Backup previo confirmado.
- [ ] Conteo de pacientes consistente.
- [ ] Conteo de visitas consistente.
- [ ] Usuarios y permisos validados.
- [ ] Pruebas UAT del tenant aprobadas.
- [ ] Monitoreo post-cambio estable.
