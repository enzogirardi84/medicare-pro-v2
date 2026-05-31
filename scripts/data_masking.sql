-- =============================================================================
-- Data Masking y Desidentificacion para Investigacion Medica (Privacidad)
 -- Oculta PHI en caliente: nombres, DNI, direcciones. Preserva datos clinicos.
-- =============================================================================

-- 1. VISTA DESIDENTIFICADA DE PACIENTES
CREATE OR REPLACE VIEW pacientes_desidentificados AS
SELECT
    id,
    -- Hash truncado del nombre (solo primeros 4 chars del SHA-256)
    LEFT(ENCODE(DIGEST(nombre, 'sha256'), 'hex'), 8) AS nombre_hash,
    -- DNI enmascarado: mostrar solo ultimos 3 digitos
    CONCAT('***', RIGHT(dni, 3)) AS dni_mascarado,
    -- Rango de edad en vez de fecha exacta
    CASE
        WHEN fecha_nacimiento IS NULL THEN 'S/D'
        WHEN AGE(fecha_nacimiento) < INTERVAL '18 years' THEN '0-17'
        WHEN AGE(fecha_nacimiento) < INTERVAL '30 years' THEN '18-29'
        WHEN AGE(fecha_nacimiento) < INTERVAL '50 years' THEN '30-49'
        WHEN AGE(fecha_nacimiento) < INTERVAL '65 years' THEN '50-64'
        ELSE '65+'
    END AS rango_edad,
    -- Obra social (dato no PHI)
    obra_social,
    -- Cuadrante geografico aproximado (0.1 grado ~ 11km)
    ROUND(latitud::NUMERIC, 1) AS cuadrante_lat,
    ROUND(longitud::NUMERIC, 1) AS cuadrante_lon,
    -- Estado clinico
    estado,
    -- Contador de visitas (sin fechas exactas)
    created_at::DATE AS fecha_alta
FROM pacientes;

-- 2. VISTA DESIDENTIFICADA DE EVOLUCIONES
CREATE OR REPLACE VIEW evoluciones_desidentificadas AS
SELECT
    e.id,
    -- Hash del paciente (consistente para joins)
    LEFT(ENCODE(DIGEST(p.nombre, 'sha256'), 'hex'), 8) AS paciente_hash,
    p.dni_mascarado,
    p.rango_edad,
    p.obra_social,
    -- Datos clinicos (NO PHI)
    e.diagnostico,
    e.medicacion,
    LENGTH(e.nota) AS longitud_nota,
    -- Fecha aproximada (solo mes y ano)
    TO_CHAR(e.created_at, 'YYYY-MM') AS mes_atencion,
    -- Edad del paciente al momento de la atencion
    EXTRACT(YEAR FROM AGE(e.created_at, p.fecha_nacimiento))::INT AS edad_atencion,
    -- Geolocalizacion aproximada del profesional (cuadrante)
    ROUND(c.lat::NUMERIC, 1) AS cuadrante_lat,
    ROUND(c.lon::NUMERIC, 1) AS cuadrante_lon,
    -- Tenant (para filtros)
    e.tenant_id
FROM evoluciones e
JOIN pacientes_desidentificados p ON p.id = e.paciente_id
LEFT JOIN LATERAL (
    SELECT ST_X(cg.punto::GEOMETRY) as lat, ST_Y(cg.punto::GEOMETRY) as lon
    FROM checkins_gps cg
    WHERE cg.profesional_id = e.profesional_id
      AND cg.timestamp = e.created_at
    LIMIT 1
) c ON TRUE
WHERE e.tenant_id = current_setting('app.tenant_id')::UUID;

-- 3. VISTA DESIDENTIFICADA DE ADMINISTRACION DE MEDICAMENTOS
CREATE OR REPLACE VIEW medicacion_desidentificada AS
SELECT
    a.id,
    LEFT(ENCODE(DIGEST(p.nombre, 'sha256'), 'hex'), 8) AS paciente_hash,
    p.rango_edad,
    -- Datos clinicos
    a.medicamento,
    a.dosis,
    a.via,
    a.estado,
    -- Periodo
    TO_CHAR(a.fecha_real, 'YYYY-MM') AS mes_administracion,
    EXTRACT(HOUR FROM a.fecha_real) AS hora_administracion,
    a.tenant_id
FROM administracion_med a
JOIN pacientes_desidentificados p ON p.id = a.paciente_id;

-- 4. USO: SELECT * FROM evoluciones_desidentificadas WHERE mes_atencion = '2026-06';
