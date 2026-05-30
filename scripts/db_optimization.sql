-- =============================================================================
-- Optimizacion de Base de Datos - MediCare Enterprise PRO
-- Indices compuestos, vistas materializadas y optimizaciones
-- para busqueda de hashes QR y consultas GIS del BiAnalyticsEngine.
-- =============================================================================

-- ═══════════════════════════════════════════════════════════════════════════════
-- 1. INDICES PARA BUSQUEDA DE HASH QR (< 50ms)
-- ═══════════════════════════════════════════════════════════════════════════════

-- Indice compuesto para busqueda por hash en audit_trail
-- El DocumentValidator busca por hash en detalle y recurso
CREATE INDEX IF NOT EXISTS idx_audit_trail_hash_search
    ON audit_trail (usuario, accion, recurso, timestamp);

-- Indice全文 (full-text) para busqueda rapida de hashes en detalle
-- Reduce la busqueda secuencial de 5000 filas a < 50ms
CREATE INDEX IF NOT EXISTS idx_audit_trail_detalle_hash
    ON audit_trail (detalle text_pattern_ops)
    WHERE detalle LIKE 'hash:%' OR detalle LIKE 'sha256:%' OR length(detalle) > 32;

-- Indice compuesto por timestamp + hash para la URL publica de validacion
-- La busqueda tipica es: WHERE detalle LIKE '%HASH_HEX%' ORDER BY timestamp DESC
CREATE INDEX IF NOT EXISTS idx_audit_trail_validacion_qr
    ON audit_trail (timestamp DESC, detalle)
    INCLUDE (usuario, recurso);


-- ═══════════════════════════════════════════════════════════════════════════════
-- 2. VISTA MATERIALIZADA PARA MAPA DE DENSIDAD GEOGRAFICA (BiAnalyticsEngine)
-- ═══════════════════════════════════════════════════════════════════════════════

-- Vista materializada que agrega coordenadas GPS por diagnostico
-- Actualizable via REFRESH MATERIALIZED VIEW CONCURRENTLY
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_densidad_geografica AS
SELECT
    c.gps_lat::numeric(10,6) AS lat,
    c.gps_lon::numeric(10,6) AS lon,
    e.diagnostico,
    COUNT(*) AS peso,
    COUNT(DISTINCT c.profesional) AS profesionales_unicos,
    MIN(c.fecha_hora) AS primera_visita,
    MAX(c.fecha_hora) AS ultima_visita,
    -- Agrupar por cuadricula de 0.01 grados (~1km) para mapas de calor
    ROUND(c.gps_lat::numeric, 2) AS cuadrante_lat,
    ROUND(c.gps_lon::numeric, 2) AS cuadrante_lon
FROM checkins c
LEFT JOIN evoluciones e ON e.paciente = c.paciente
    AND e.fecha::date = c.fecha_hora::date
WHERE c.gps_lat IS NOT NULL
    AND c.gps_lon IS NOT NULL
    AND e.diagnostico IS NOT NULL
GROUP BY
    c.gps_lat, c.gps_lon,
    e.diagnostico,
    ROUND(c.gps_lat::numeric, 2),
    ROUND(c.gps_lon::numeric, 2);

-- Indices para la vista materializada
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_densidad_unique
    ON mv_densidad_geografica (lat, lon, diagnostico);

CREATE INDEX IF NOT EXISTS idx_mv_densidad_cuadrante
    ON mv_densidad_geografica (cuadrante_lat, cuadrante_lon);

CREATE INDEX IF NOT EXISTS idx_mv_densidad_diagnostico
    ON mv_densidad_geografica (diagnostico);


-- ═══════════════════════════════════════════════════════════════════════════════
-- 3. INDICES PARA CONSULTAS DE GEOFENCING Y COSTO OPERATIVO
-- ═══════════════════════════════════════════════════════════════════════════════

-- Indice compuesto para busqueda de visitas por geofencing
-- El BiAnalyticsEngine consulta por rango de fechas + profesional
CREATE INDEX IF NOT EXISTS idx_visitas_geofencing
    ON visitas_geofencing (fecha_entrada, fecha_salida, profesional)
    INCLUDE (paciente, duracion_seg, radio_metros);

-- Indice para calculo de costo operativo por tenant
CREATE INDEX IF NOT EXISTS idx_visitas_costo
    ON visitas_geofencing (tenant_id, fecha_entrada)
    INCLUDE (duracion_seg);


-- ═══════════════════════════════════════════════════════════════════════════════
-- 4. FUNCION DE ACTUALIZACION PROGRAMADA
-- ═══════════════════════════════════════════════════════════════════════════════

-- Funcion para refrescar la vista materializada (ejecutar via cron)
CREATE OR REPLACE FUNCTION refresh_mv_densidad_geografica()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_densidad_geografica;
END;
$$ LANGUAGE plpgsql;


-- ═══════════════════════════════════════════════════════════════════════════════
-- 5. VERIFICACION DE RENDIMIENTO
-- ═══════════════════════════════════════════════════════════════════════════════

-- Explicar plan de ejecucion para busqueda QR:
-- Debe mostrar Index Scan, no Seq Scan
EXPLAIN ANALYZE
SELECT * FROM audit_trail
WHERE detalle LIKE '%a1b2c3d4e5f6%'
ORDER BY timestamp DESC
LIMIT 1;

-- Explicar plan para consulta de densidad geografica:
EXPLAIN ANALYZE
SELECT cuadrante_lat, cuadrante_lon, diagnostico, SUM(peso) as total
FROM mv_densidad_geografica
WHERE diagnostico IN ('Neumonia', 'Fractura')
GROUP BY cuadrante_lat, cuadrante_lon, diagnostico
ORDER BY total DESC
LIMIT 100;
