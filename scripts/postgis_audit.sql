-- =============================================================================
-- PostGIS Audit Query - MediCare Enterprise PRO
-- Verificacion de salud de la tabla particionada checkins_gps
-- Ejecutar en caliente durante las primeras 24h criticas
-- =============================================================================

-- 1. Filas insertadas en la particion del mes actual
SELECT
    'checkins_gps_actual' AS tabla,
    COUNT(*) AS total_filas,
    MIN(timestamp) AS primera_insercion,
    MAX(timestamp) AS ultima_insercion,
    COUNT(DISTINCT profesional_id) AS profesionales_unicos
FROM checkins_gps
WHERE timestamp >= DATE_TRUNC('month', NOW())
  AND timestamp < DATE_TRUNC('month', NOW()) + INTERVAL '1 month';

-- 2. Tamanos en disco de los indices GIST espaciales
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
    idx_scan AS veces_usado,
    idx_tup_read AS filas_leidas
FROM pg_stat_user_indexes
WHERE indexname LIKE '%checkins%'
ORDER BY pg_relation_size(indexrelid) DESC;

-- 3. Registros sin procesar en la vista materializada
-- Compara la particion actual con la vista
WITH actual AS (
    SELECT COUNT(*) AS total_checkins
    FROM checkins_gps
    WHERE timestamp >= NOW() - INTERVAL '90 days'
),
en_vista AS (
    SELECT COUNT(*) AS total_en_vista
    FROM mv_densidad_atenciones
)
SELECT
    actual.total_checkins,
    en_vista.total_en_vista,
    (actual.total_checkins - COALESCE(en_vista.total_en_vista, 0)) AS diferencia
FROM actual, en_vista;

-- 4. Profesionales con mayor cantidad de check-ins (top 10)
SELECT
    u.nombre AS profesional,
    COUNT(*) AS total_checkins,
    MIN(c.timestamp) AS primer_checkin,
    MAX(c.timestamp) AS ultimo_checkin,
    ROUND(AVG(c.precision_metros)) AS precision_promedio
FROM checkins_gps c
JOIN usuarios u ON u.id = c.profesional_id
WHERE c.timestamp >= NOW() - INTERVAL '7 days'
GROUP BY u.nombre
ORDER BY total_checkins DESC
LIMIT 10;

-- 5. Alertas de rendimiento: indices no usados
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexname NOT LIKE '%pk_%'
ORDER BY pg_relation_size(indexrelid) DESC;
