-- =============================================================================
-- Analisis de Rutas GPS - Optimizacion Geografica (PostGIS)
-- Calcula eficiencia de rutas, desvios inusuales y demoras entre visitas.
-- Requiere PostGIS 3.0+ habilitado en la base de datos.
-- =============================================================================

-- 1. Distancia total recorrida por profesional en el dia de hoy
SELECT
    u.nombre AS profesional,
    ROUND(ST_length(
        ST_MakeLine(array_agg(c.punto::GEOMETRY ORDER BY c.timestamp))
    )::NUMERIC / 1000, 1) AS distancia_km_recorrida,
    COUNT(*) AS checkins_realizados,
    MIN(c.timestamp) AS inicio_jornada,
    MAX(c.timestamp) AS fin_jornada,
    ROUND(EXTRACT(EPOCH FROM MAX(c.timestamp) - MIN(c.timestamp)) / 3600, 1) AS horas_jornada
FROM checkins_gps c
JOIN usuarios u ON u.id = c.profesional_id
WHERE c.timestamp >= CURRENT_DATE
  AND c.timestamp < CURRENT_DATE + INTERVAL '1 day'
GROUP BY u.nombre
ORDER BY distancia_km_recorrida DESC
LIMIT 20;

-- 2. Desvios inusuales: distancia entre check-in consecutivo vs distancia lineal
-- Si la relacion es > 2.0, el profesional se desvio significativamente
WITH checkins_ordenados AS (
    SELECT
        profesional_id,
        timestamp,
        punto,
        LAG(punto) OVER (PARTITION BY profesional_id ORDER BY timestamp) AS punto_anterior,
        LAG(timestamp) OVER (PARTITION BY profesional_id ORDER BY timestamp) AS ts_anterior
    FROM checkins_gps
    WHERE timestamp >= CURRENT_DATE
      AND timestamp < CURRENT_DATE + INTERVAL '1 day'
),
distancias AS (
    SELECT
        profesional_id,
        timestamp,
        ST_Distance(punto, punto_anterior)::NUMERIC / 1000 AS distancia_real_km,
        EXTRACT(EPOCH FROM timestamp - ts_anterior) / 60 AS minutos_entre_visitas
    FROM checkins_ordenados
    WHERE punto_anterior IS NOT NULL
      AND ts_anterior IS NOT NULL
)
SELECT
    u.nombre,
    ROUND(AVG(d.distancia_real_km), 2) AS distancia_promedio_km,
    ROUND(MAX(d.distancia_real_km), 2) AS distancia_maxima_km,
    ROUND(AVG(d.minutos_entre_visitas), 1) AS minutos_promedio_entre_visitas
FROM distancias d
JOIN usuarios u ON u.id = d.profesional_id
GROUP BY u.nombre
HAVING AVG(d.distancia_real_km) > 2.0  -- Desvio inusual
ORDER BY distancia_promedio_km DESC;

-- 3. Demoras excesivas: visitas con mas de 60 minutos entre check-ins consecutivos
-- (posible descanso no registrado, congestion de transito, o perdida de senial)
SELECT
    u.nombre AS profesional,
    c1.timestamp AS checkin_anterior,
    c2.timestamp AS checkin_actual,
    ROUND(EXTRACT(EPOCH FROM (c2.timestamp - c1.timestamp)) / 60, 0) AS demora_minutos,
    ROUND(ST_Distance(c1.punto, c2.punto)::NUMERIC / 1000, 1) AS distancia_km
FROM checkins_gps c1
JOIN checkins_gps c2
    ON c2.profesional_id = c1.profesional_id
    AND c2.timestamp > c1.timestamp
    AND c2.timestamp < c1.timestamp + INTERVAL '3 hours'
JOIN usuarios u ON u.id = c1.profesional_id
WHERE NOT EXISTS (
    SELECT 1 FROM checkins_gps c3
    WHERE c3.profesional_id = c1.profesional_id
      AND c3.timestamp > c1.timestamp
      AND c3.timestamp < c2.timestamp
)
  AND EXTRACT(EPOCH FROM (c2.timestamp - c1.timestamp)) / 60 > 60
  AND c1.timestamp >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY demora_minutos DESC
LIMIT 20;

-- 4. Concentracion geografica: cuadrantes con mayor densidad de atencion
SELECT
    ROUND(ST_X(c.punto::GEOMETRY), 3) AS lon,
    ROUND(ST_Y(c.punto::GEOMETRY), 3) AS lat,
    COUNT(*) AS atenciones,
    COUNT(DISTINCT c.profesional_id) AS profesionales_distintos
FROM checkins_gps c
WHERE c.timestamp >= NOW() - INTERVAL '30 days'
GROUP BY ROUND(ST_X(c.punto::GEOMETRY), 3),
         ROUND(ST_Y(c.punto::GEOMETRY), 3)
ORDER BY atenciones DESC
LIMIT 50;
