# Plan de migracion (sin romper produccion)

## Fase 0 - Preparacion
- Definir esquema nuevo y contratos API.
- Baseline de performance actual.

## Fase 1 - Fundacion
- API base + auth + tenants + pacientes.
- DB nueva en paralelo.

## Fase 2 - Dual write
- Guardar en legado y nuevo temporalmente.
- Reconciliacion de datos.

## Fase 3 - Read switch
- Lectura principal desde nuevo sistema.
- Fallback controlado.

## Fase 4 - Decomisionado
- Retirar caminos legados por modulo.
