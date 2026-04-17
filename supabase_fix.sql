-- ==========================================
-- CREAR TABLAS MEDICARE PRO - VERSION CORREGIDA
-- ==========================================

-- 1. TABLA EMPRESAS
DROP TABLE IF EXISTS visitas CASCADE;
DROP TABLE IF EXISTS recetas CASCADE;
DROP TABLE IF EXISTS evoluciones CASCADE;
DROP TABLE IF EXISTS signos_vitales CASCADE;
DROP TABLE IF EXISTS pacientes CASCADE;
DROP TABLE IF EXISTS usuarios CASCADE;
DROP TABLE IF EXISTS empresas CASCADE;

CREATE TABLE empresas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(255) NOT NULL,
    cuit VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. TABLA USUARIOS
CREATE TABLE usuarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID REFERENCES empresas(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    nombre VARCHAR(255) NOT NULL,
    rol VARCHAR(50) DEFAULT 'medico',
    matricula VARCHAR(50),
    telefono VARCHAR(50),
    estado VARCHAR(20) DEFAULT 'Activo',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. TABLA PACIENTES
CREATE TABLE pacientes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID REFERENCES empresas(id) ON DELETE CASCADE,
    dni VARCHAR(20) NOT NULL,
    nombre VARCHAR(255) NOT NULL,
    apellido VARCHAR(255),
    fecha_nacimiento DATE,
    sexo VARCHAR(10),
    obra_social VARCHAR(255),
    numero_afiliado VARCHAR(100),
    telefono VARCHAR(50),
    direccion TEXT,
    alergias TEXT,
    antecedentes TEXT,
    estado VARCHAR(20) DEFAULT 'Activo',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(dni)
);

-- 4. TABLA SIGNOS VITALES
CREATE TABLE signos_vitales (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID REFERENCES pacientes(id) ON DELETE CASCADE,
    usuario_id UUID REFERENCES usuarios(id),
    fecha_registro TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    tension_arterial VARCHAR(20),
    frecuencia_cardiaca INTEGER,
    frecuencia_respiratoria INTEGER,
    temperatura DECIMAL(4,2),
    saturacion_oxigeno INTEGER,
    glucemia VARCHAR(20),
    observaciones TEXT
);

-- 5. TABLA EVOLUCIONES
CREATE TABLE evoluciones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID REFERENCES pacientes(id) ON DELETE CASCADE,
    usuario_id UUID REFERENCES usuarios(id),
    fecha_evolucion TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    evolucion TEXT NOT NULL,
    indicaciones TEXT
);

-- 6. TABLA RECETAS
CREATE TABLE recetas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID REFERENCES pacientes(id) ON DELETE CASCADE,
    usuario_id UUID REFERENCES usuarios(id),
    fecha_receta TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    medicamentos TEXT,
    indicaciones TEXT
);

-- 7. TABLA VISITAS
CREATE TABLE visitas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID REFERENCES pacientes(id) ON DELETE CASCADE,
    usuario_id UUID REFERENCES usuarios(id),
    fecha_visita TIMESTAMP WITH TIME ZONE,
    motivo TEXT,
    estado VARCHAR(20) DEFAULT 'Programada'
);

-- 8. INDICES
CREATE INDEX idx_pacientes_dni ON pacientes(dni);
CREATE INDEX idx_vitales_paciente ON signos_vitales(paciente_id);
CREATE INDEX idx_evoluciones_paciente ON evoluciones(paciente_id);
CREATE INDEX idx_recetas_paciente ON recetas(paciente_id);
CREATE INDEX idx_visitas_paciente ON visitas(paciente_id);

-- 9. DESACTIVAR RLS
ALTER TABLE empresas DISABLE ROW LEVEL SECURITY;
ALTER TABLE usuarios DISABLE ROW LEVEL SECURITY;
ALTER TABLE pacientes DISABLE ROW LEVEL SECURITY;
ALTER TABLE signos_vitales DISABLE ROW LEVEL SECURITY;
ALTER TABLE evoluciones DISABLE ROW LEVEL SECURITY;
ALTER TABLE recetas DISABLE ROW LEVEL SECURITY;
ALTER TABLE visitas DISABLE ROW LEVEL SECURITY;
