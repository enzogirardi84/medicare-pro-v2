# Politica De Backup Y Restauracion

Objetivo: proteger datos clinicos y administrativos con backups cifrados, restaurables y probados.

## Frecuencia

- Backup completo diario de base Supabase/Postgres.
- Retencion minima: 7 diarios, 4 semanales, 12 mensuales.
- Backup adicional antes de migraciones SQL, cambios RLS o despliegues mayores.

## Cifrado

- Todo dump debe cifrarse antes de salir del entorno seguro.
- La clave de cifrado no se versiona en Git y se guarda en gestor de secretos.
- Archivos recomendados: `medicare_YYYYMMDD_HHMM.dump.enc`.

## Restauracion

- Probar restauracion en staging al menos una vez por mes.
- Medir tiempo de restauracion y registrar resultado.
- Validar despues de restaurar:
  - login de usuario de prueba,
  - busqueda de paciente,
  - lectura de historia clinica,
  - modulo Caja,
  - exportacion PDF/Excel,
  - politicas RLS activas.

## Checklist Antes De Produccion

- Backup reciente creado y cifrado.
- Restauracion probada en staging.
- `supabase/rls_audit_report.sql` ejecutado sin hallazgos criticos.
- Secrets productivos rotados si hubo exposicion o cambio de responsable.
- Evidencia guardada fuera del repositorio.

## Responsabilidad

El operador que ejecuta una migracion o despliegue mayor debe confirmar que existe backup valido antes de continuar.
