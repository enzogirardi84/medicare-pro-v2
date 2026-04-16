-- Base de estrategia de particionado para tablas de alto volumen.
-- Nota: este script es guía inicial y debe aplicarse con plan de migración.

-- Ejemplo para audit_logs por mes:
-- CREATE TABLE audit_logs_partitioned (
--   LIKE audit_logs INCLUDING ALL
-- ) PARTITION BY RANGE (created_at);
--
-- CREATE TABLE audit_logs_2026_04 PARTITION OF audit_logs_partitioned
-- FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

-- Ejemplo para visits por mes:
-- CREATE TABLE visits_partitioned (
--   LIKE visits INCLUDING ALL
-- ) PARTITION BY RANGE (created_at);
--
-- CREATE TABLE visits_2026_04 PARTITION OF visits_partitioned
-- FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

-- Recomendaciones:
-- 1) Mantener índices por partición en (tenant_id, created_at) y (tenant_id, patient_id).
-- 2) Crear job mensual automático de nuevas particiones.
-- 3) Definir retención/archivo para particiones antiguas.
