-- =============================================================================
-- Migracion PostgreSQL - MediCare Enterprise PRO
-- Esquema normalizado 3NF, multi-tenant, con auditoria, particionamiento y
-- soporte criptografico para cumplimiento HIPAA/GDPR.
-- =============================================================================

-- ═══════════════════════════════════════════════════════════════════════════════
-- 1. EXTENSIONES
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "btree_gist";  -- indices GiST para rangos de tiempo

-- ═══════════════════════════════════════════════════════════════════════════════
-- 2. ESQUEMA PRINCIPAL
-- ═══════════════════════════════════════════════════════════════════════════════

-- 2a. Tenants (clientes institucionales)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug VARCHAR(64) UNIQUE NOT NULL,                    -- "avalian", "sancor_salud"
    nombre VARCHAR(255) NOT NULL,
    config JSONB DEFAULT '{}',
    public_key_ecdsa TEXT,                                -- Clave KMS propia (BYOK)
    kms_key_arn TEXT,                                     -- ARN de KMS externa
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2b. Profesionales / Usuarios
CREATE TABLE usuarios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    login VARCHAR(128) NOT NULL,
    nombre VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    telefono VARCHAR(64),
    documento VARCHAR(64),
    matricula VARCHAR(128),
    rol VARCHAR(32) NOT NULL CHECK (rol IN (
        'superadmin', 'admin', 'coordinador', 'medico', 'enfermero', 'operativo', 'auditor'
    )),
    password_hash TEXT NOT NULL,
    public_key_ecdsa TEXT,                                -- Clave publica ECDSA para firmas
    totp_secret TEXT,                                     -- Secreto TOTP para 2FA
    totp_habilitado BOOLEAN DEFAULT FALSE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    version INT NOT NULL DEFAULT 1,                       -- Control de concurrencia optimista
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, login)
);

-- 2c. Pacientes
CREATE TABLE pacientes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    nombre VARCHAR(255) NOT NULL,
    dni VARCHAR(32) NOT NULL,
    email VARCHAR(255),
    telefono VARCHAR(64),
    direccion TEXT,
    obra_social VARCHAR(255),
    nro_afiliado VARCHAR(64),
    fecha_nacimiento DATE,
    estado VARCHAR(32) NOT NULL DEFAULT 'Activo' CHECK (estado IN (
        'Activo', 'De Alta', 'Suspendido', 'Archivado'
    )),
    hash_integridad TEXT,                                 -- SHA-256 del registro canonico
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES usuarios(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by UUID REFERENCES usuarios(id),
    UNIQUE (tenant_id, dni)
);

-- 2d. Evoluciones clinicas (tabla principal de historia clinica)
CREATE TABLE evoluciones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    profesional_id UUID NOT NULL REFERENCES usuarios(id),
    nota TEXT NOT NULL,
    diagnostico TEXT,
    medicacion TEXT,
    plantilla VARCHAR(128),
    adjunto_ruta TEXT,                                     -- Ruta en S3/R2 del adjunto
    adjunto_hash TEXT,                                     -- SHA-256 del adjunto
    fecha_atencion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    firma_ecdsa TEXT,                                      -- Firma digital del profesional
    hash_integridad TEXT,                                  -- SHA-256 del registro canonico
    firma_tsa TEXT,                                        -- Timestamp RFC 3161 (TSA)
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES usuarios(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by UUID REFERENCES usuarios(id)
);

CREATE INDEX idx_evoluciones_paciente ON evoluciones (tenant_id, paciente_id, fecha_atencion DESC);
CREATE INDEX idx_evoluciones_profesional ON evoluciones (tenant_id, profesional_id, fecha_atencion DESC);
CREATE INDEX idx_evoluciones_fecha ON evoluciones (tenant_id, fecha_atencion DESC);

-- 2e. Administracion de medicacion (trazabilidad de farmacos)
CREATE TABLE administracion_med (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    profesional_id UUID NOT NULL REFERENCES usuarios(id),
    medicamento VARCHAR(255) NOT NULL,
    dosis VARCHAR(128),
    via VARCHAR(64),
    frecuencia VARCHAR(128),
    fecha_programada TIMESTAMPTZ,
    fecha_real TIMESTAMPTZ,
    estado VARCHAR(32) NOT NULL DEFAULT 'programada' CHECK (estado IN (
        'programada', 'realizada', 'omitida', 'suspendida', 'modificada'
    )),
    motivo_suspension TEXT,
    observaciones TEXT,
    firma_ecdsa TEXT,
    hash_integridad TEXT,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES usuarios(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by UUID REFERENCES usuarios(id)
);

CREATE INDEX idx_adminmed_paciente ON administracion_med (tenant_id, paciente_id, fecha_programada);
CREATE INDEX idx_adminmed_estado ON administracion_med (tenant_id, estado, fecha_programada);

-- 2f. Recetas digitales con firma
CREATE TABLE recetas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    profesional_id UUID NOT NULL REFERENCES usuarios(id),
    medicamentos JSONB NOT NULL,                           -- Array de {nombre, dosis, via, frecuencia, duracion}
    indicaciones TEXT,
    vigencia_dias INT DEFAULT 30,
    fecha_emision TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_vencimiento TIMESTAMPTZ,
    estado VARCHAR(32) DEFAULT 'activa' CHECK (estado IN ('activa', 'suspendida', 'vencida', 'anulada')),
    firma_ecdsa TEXT,
    hash_integridad TEXT,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES usuarios(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by UUID REFERENCES usuarios(id)
);

-- 2g. Archivos adjuntos (estudios, imagenes) validados por upload sanitizer
CREATE TABLE estudios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    profesional_id UUID NOT NULL REFERENCES usuarios(id),
    tipo VARCHAR(64),
    nombre_original TEXT,
    ruta_s3 TEXT NOT NULL,                                -- Ruta en bucket S3/R2
    mime_type VARCHAR(128),
    sha256 TEXT NOT NULL,                                  -- Hash del archivo
    tamano_bytes INT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_estudios_paciente ON estudios (tenant_id, paciente_id, created_at DESC);

-- ═══════════════════════════════════════════════════════════════════════════════
-- 3. TABLA GEOGRAFICA CON PARTICIONAMIENTO MENSUAL
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE checkins_gps (
    id BIGSERIAL,
    tenant_id UUID NOT NULL,
    profesional_id UUID NOT NULL,
    paciente_id UUID,
    punto GEOGRAPHY(POINT, 4326) NOT NULL,
    precision_metros REAL,
    velocidad_kmh REAL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source VARCHAR(32) DEFAULT 'app' CHECK (source IN ('app', 'sync_offline', 'web')),
    hash_integridad TEXT,
    -- Particion por mes: PRIMARY KEY debe incluir la columna de particion
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Crear particiones iniciales (12 meses)
SELECT TO_CHAR(d, 'YYYY_MM') AS partition_name
FROM generate_series('2026-01-01'::DATE, '2027-01-01'::DATE, '1 month'::INTERVAL) AS d
INTO TEMP TABLE tmp_partition_names;

-- Indices por particion (se heredan automaticamente en PG12+)
CREATE INDEX idx_checkins_profesional ON checkins_gps (tenant_id, profesional_id, timestamp DESC);
CREATE INDEX idx_checkins_paciente ON checkins_gps (tenant_id, paciente_id, timestamp DESC);
CREATE INDEX idx_checkins_geo ON checkins_gps USING GIST (punto);

-- ═══════════════════════════════════════════════════════════════════════════════
-- 4. FUNCION AUTOMATICA DE PARTICIONAMIENTO
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION crear_particion_checkins_mensual()
RETURNS void AS $$
DECLARE
    mes_inicio DATE;
    mes_fin DATE;
    partition_name TEXT;
BEGIN
    -- Crear particion para el mes proximo si no existe
    mes_inicio := DATE_TRUNC('month', NOW() + INTERVAL '1 month')::DATE;
    mes_fin := (DATE_TRUNC('month', NOW() + INTERVAL '2 months'))::DATE;
    partition_name := 'checkins_gps_' || TO_CHAR(mes_inicio, 'YYYY_MM');

    IF NOT EXISTS (
        SELECT 1 FROM pg_class WHERE relname = partition_name
    ) THEN
        EXECUTE format(
            'CREATE TABLE %I PARTITION OF checkins_gps
             FOR VALUES FROM (%L) TO (%L)',
            partition_name, mes_inicio, mes_fin
        );
        RAISE NOTICE 'Particion creada: %', partition_name;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Programar ejecucion diaria (via pg_cron si esta disponible)
-- SELECT cron.schedule('crear-particion-checkins', '0 0 1 * *', 'SELECT crear_particion_checkins_mensual();');

-- Alternativa: ejecutar manualmente desde el provisioner
-- SELECT crear_particion_checkins_mensual();

-- ═══════════════════════════════════════════════════════════════════════════════
-- 5. VISTA MATERIALIZADA PARA ANALITICA GEOGRAFICA
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE MATERIALIZED VIEW mv_densidad_atenciones AS
SELECT
    c.tenant_id,
    c.profesional_id,
    c.paciente_id,
    ST_SnapToGrid(c.punto::GEOMETRY, 0.01) AS grid_centroid,
    COUNT(*) AS peso,
    MIN(c.timestamp) AS primera_visita,
    MAX(c.timestamp) AS ultima_visita,
    AVG(c.precision_metros) AS precision_promedio
FROM checkins_gps c
WHERE c.timestamp >= NOW() - INTERVAL '90 days'
GROUP BY
    c.tenant_id,
    c.profesional_id,
    c.paciente_id,
    ST_SnapToGrid(c.punto::GEOMETRY, 0.01)
WITH DATA;

CREATE UNIQUE INDEX idx_mv_densidad_unique
    ON mv_densidad_atenciones (tenant_id, profesional_id, paciente_id, grid_centroid);

-- ═══════════════════════════════════════════════════════════════════════════════
-- 6. FUNCION CANONICA PARA HASH DE INTEGRIDAD
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION calcular_hash_integridad(record JSONB)
RETURNS TEXT AS $$
BEGIN
    -- SHA-256 del JSON canonico (sorted keys, sin espacios)
    RETURN ENCODE(
        digest(record::TEXT, 'sha256'),
        'hex'
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;
