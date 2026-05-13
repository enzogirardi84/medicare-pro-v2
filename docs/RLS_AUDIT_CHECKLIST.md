# Auditoria RLS Supabase

Objetivo: confirmar tabla por tabla que los datos clinicos, administrativos y de facturacion no quedan expuestos por consultas anonimas o roles equivocados.

## Ejecutar

1. Abrir Supabase SQL Editor del proyecto productivo.
2. Ejecutar `supabase/rls_audit_report.sql`.
3. Guardar evidencia del resultado antes y despues de cada cambio de politicas.
4. Ninguna tabla critica debe quedar con `rls_enabled = false`.
5. Toda tabla critica con RLS activo debe tener politicas explicitas por `empresa_id`, rol o contexto de usuario.

## Tablas Criticas

- `usuarios`, `empresas`
- `pacientes`, `visitas`, `evoluciones`, `recetas`, `signos_vitales`
- `caja`, `auditoria_legal`
- `billing_clientes`, `billing_presupuestos`, `billing_prefacturas`, `billing_cobros`, `billing_facturas_arca`

## Criterio De Aprobacion

- RLS activo en todas las tablas con datos personales, clinicos o financieros.
- Politicas separadas para lectura, alta, edicion y borrado cuando aplique.
- Acceso de auditoria limitado a lectura y exportacion controlada.
- Acceso financiero limitado a roles de coordinacion/operacion autorizados.
- `service_role` reservado para procesos del servidor y tareas administrativas auditadas.

## Evidencia Minima

- Fecha y responsable de la auditoria.
- Resultado del bloque 1 del SQL.
- Resultado del bloque 3 sin filas para tablas criticas.
- Cambios aplicados y ticket/commit asociado.
