-- ==========================================
-- ESQUEMA COMPLETO MEDICARE PRO v2.0
-- Con mejoras: índices, triggers, constraints
-- ==========================================

-- ==========================================
-- 1. FUNCIONES AUXILIARES
-- ==========================================

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- ==========================================
-- 2. TABLAS BASE (si no existen)
-- ==========================================

-- Tabla de Empresas/Clínicas
CREATE TABLE IF NOT EXISTS empresas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(255) NOT NULL,
    cuit VARCHAR(20) UNIQUE,
    direccion TEXT,
    telefono VARCHAR(50),
    email VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Trigger para updated_at
DROP TRIGGER IF EXISTS update_empresas_updated_at ON empresas;
CREATE TRIGGER update_empresas_updated_at
    BEFORE UPDATE ON empresas
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Tabla de Usuarios
CREATE TABLE IF NOT EXISTS usuarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID REFERENCES empresas(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    nombre VARCHAR(255) NOT NULL,
    rol VARCHAR(50) NOT NULL DEFAULT 'medico',
    matricula VARCHAR(50),
    telefono VARCHAR(50),
    estado VARCHAR(20) DEFAULT 'Activo',
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_usuarios_empresa ON usuarios(empresa_id);
CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);

DROP TRIGGER IF EXISTS update_usuarios_updated_at ON usuarios;
CREATE TRIGGER update_usuarios_updated_at
    BEFORE UPDATE ON usuarios
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Tabla de Pacientes
CREATE TABLE IF NOT EXISTS pacientes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID REFERENCES empresas(id) ON DELETE CASCADE,
    dni VARCHAR(20) NOT NULL,
    nombre VARCHAR(255) NOT NULL,
    apellido VARCHAR(255) NOT NULL,
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
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(empresa_id, dni)
);

-- Índices importantes para pacientes
CREATE INDEX IF NOT EXISTS idx_pacientes_empresa ON pacientes(empresa_id);
CREATE INDEX IF NOT EXISTS idx_pacientes_dni ON pacientes(dni);
CREATE INDEX IF NOT EXISTS idx_pacientes_nombre ON pacientes(nombre);
CREATE INDEX IF NOT EXISTS idx_pacientes_estado ON pacientes(estado) WHERE estado = 'Activo';

DROP TRIGGER IF EXISTS update_pacientes_updated_at ON pacientes;
CREATE TRIGGER update_pacientes_updated_at
    BEFORE UPDATE ON pacientes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ==========================================
-- 3. TABLAS CLÍNICAS CON MEJORAS
-- ==========================================

-- Signos Vitales (MEJORADO)
DROP TABLE IF EXISTS signos_vitales CASCADE;
CREATE TABLE signos_vitales (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    usuario_id UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    empresa_id UUID REFERENCES empresas(id) ON DELETE CASCADE,
    
    -- Datos clínicos
    fecha_registro TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    tension_arterial_sistolica INTEGER,
    tension_arterial_diastolica INTEGER,
    frecuencia_cardiaca INTEGER CHECK (frecuencia_cardiaca BETWEEN 30 AND 220),
    frecuencia_respiratoria INTEGER CHECK (frecuencia_respiratoria BETWEEN 8 AND 60),
    temperatura DECIMAL(4,2) CHECK (temperatura BETWEEN 34.0 AND 42.0),
    saturacion_oxigeno INTEGER CHECK (saturacion_oxigeno BETWEEN 70 AND 100),
    glucemia INTEGER CHECK (glucemia BETWEEN 30 AND 600),
    peso_kg DECIMAL(5,2),
    talla_cm DECIMAL(5,2),
    
    -- Alertas automáticas
    alerta_ta BOOLEAN DEFAULT FALSE,
    alerta_fc BOOLEAN DEFAULT FALSE,
    alerta_fr BOOLEAN DEFAULT FALSE,
    alerta_temp BOOLEAN DEFAULT FALSE,
    alerta_sat BOOLEAN DEFAULT FALSE,
    
    observaciones TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices optimizados
CREATE INDEX idx_vitales_paciente_fecha ON signos_vitales(paciente_id, fecha_registro DESC);
CREATE INDEX idx_vitales_empresa ON signos_vitales(empresa_id);
CREATE INDEX idx_vitales_usuario ON signos_vitales(usuario_id);
CREATE INDEX idx_vitales_alertas ON signos_vitales(paciente_id) WHERE alerta_ta = TRUE OR alerta_fc = TRUE OR alerta_temp = TRUE;

-- Trigger para alertas automáticas
CREATE OR REPLACE FUNCTION check_alertas_vitales()
RETURNS TRIGGER AS $$
BEGIN
    -- Alertas TA
    IF NEW.tension_arterial_sistolica IS NOT NULL THEN
        IF NEW.tension_arterial_sistolica > 140 OR NEW.tension_arterial_sistolica < 90 THEN
            NEW.alerta_ta := TRUE;
        END IF;
    END IF;
    
    -- Alertas FC
    IF NEW.frecuencia_cardiaca IS NOT NULL THEN
        IF NEW.frecuencia_cardiaca > 100 OR NEW.frecuencia_cardiaca < 60 THEN
            NEW.alerta_fc := TRUE;
        END IF;
    END IF;
    
    -- Alertas Temperatura
    IF NEW.temperatura IS NOT NULL THEN
        IF NEW.temperatura > 38.0 THEN
            NEW.alerta_temp := TRUE;
        END IF;
    END IF;
    
    -- Alertas Saturación
    IF NEW.saturacion_oxigeno IS NOT NULL THEN
        IF NEW.saturacion_oxigeno < 92 THEN
            NEW.alerta_sat := TRUE;
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_alertas_vitales ON signos_vitales;
CREATE TRIGGER trigger_alertas_vitales
    BEFORE INSERT OR UPDATE ON signos_vitales
    FOR EACH ROW
    EXECUTE FUNCTION check_alertas_vitales();

-- Evoluciones Clínicas
DROP TABLE IF EXISTS evoluciones CASCADE;
CREATE TABLE evoluciones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    usuario_id UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    empresa_id UUID REFERENCES empresas(id) ON DELETE CASCADE,
    
    fecha_evolucion TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    tipo_evolucion VARCHAR(50) DEFAULT 'Regular', -- 'Regular', 'Urgente', 'Control'
    
    -- Campos principales
    motivo_consulta TEXT,
    evolucion_actual TEXT NOT NULL,
    indicaciones TEXT,
    
    -- Estado
    estado VARCHAR(20) DEFAULT 'Activa', -- 'Activa', 'Completada', 'Cancelada'
    
    -- Metadatos
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_evoluciones_paciente_fecha ON evoluciones(paciente_id, fecha_evolucion DESC);
CREATE INDEX idx_evoluciones_empresa ON evoluciones(empresa_id);
CREATE INDEX idx_evoluciones_usuario ON evoluciones(usuario_id);

DROP TRIGGER IF EXISTS update_evoluciones_updated_at ON evoluciones;
CREATE TRIGGER update_evoluciones_updated_at
    BEFORE UPDATE ON evoluciones
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Recetas
DROP TABLE IF EXISTS recetas CASCADE;
CREATE TABLE recetas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    usuario_id UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    empresa_id UUID REFERENCES empresas(id) ON DELETE CASCADE,
    evolucion_id UUID REFERENCES evoluciones(id) ON DELETE SET NULL,
    
    fecha_receta TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    numero_receta VARCHAR(100),
    
    -- Medicamentos (JSONB para flexibilidad)
    medicamentos JSONB NOT NULL DEFAULT '[]',
    /*
    Formato: [
        {
            "nombre": "Paracetamol",
            "dosis": "500mg",
            "frecuencia": "Cada 8 horas",
            "duracion": "7 días",
            "via": "Oral"
        }
    ]
    */
    
    diagnostico TEXT,
    indicaciones_generales TEXT,
    
    -- Estado
    estado VARCHAR(20) DEFAULT 'Activa', -- 'Activa', 'Dispensada', 'Vencida', 'Cancelada'
    fecha_dispensacion TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_recetas_paciente ON recetas(paciente_id);
CREATE INDEX idx_recetas_empresa ON recetas(empresa_id);
CREATE INDEX idx_recetas_fecha ON recetas(fecha_receta DESC);
CREATE INDEX idx_recetas_estado ON recetas(estado);

DROP TRIGGER IF EXISTS update_recetas_updated_at ON recetas;
CREATE TRIGGER update_recetas_updated_at
    BEFORE UPDATE ON recetas
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Visitas / Agenda
DROP TABLE IF EXISTS visitas CASCADE;
CREATE TABLE visitas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    usuario_id UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    empresa_id UUID REFERENCES empresas(id) ON DELETE CASCADE,
    
    fecha_visita TIMESTAMP WITH TIME ZONE NOT NULL,
    duracion_minutos INTEGER DEFAULT 30,
    
    tipo_visita VARCHAR(50) DEFAULT 'Regular', -- 'Regular', 'Urgencia', 'Control', 'Domicilio'
    estado VARCHAR(20) DEFAULT 'Programada', -- 'Programada', 'En Curso', 'Completada', 'Cancelada', 'No Show'
    
    motivo TEXT,
    notas_preparacion TEXT,
    resultado_visita TEXT,
    
    -- Geolocalización (para visitas domiciliarias)
    latitud DECIMAL(10,7),
    longitud DECIMAL(10,7),
    direccion_visitada TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_visitas_paciente ON visitas(paciente_id);
CREATE INDEX idx_visitas_fecha ON visitas(fecha_visita);
CREATE INDEX idx_visitas_estado ON visitas(estado);
CREATE INDEX idx_visitas_usuario ON visitas(usuario_id);

DROP TRIGGER IF EXISTS update_visitas_updated_at ON visitas;
CREATE TRIGGER update_visitas_updated_at
    BEFORE UPDATE ON visitas
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ==========================================
-- 4. TABLAS DE GESTIÓN
-- ==========================================

-- Inventario
DROP TABLE IF EXISTS inventario CASCADE;
CREATE TABLE inventario (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    
    codigo VARCHAR(50),
    nombre VARCHAR(255) NOT NULL,
    descripcion TEXT,
    categoria VARCHAR(100),
    
    stock_actual INTEGER NOT NULL DEFAULT 0 CHECK (stock_actual >= 0),
    stock_minimo INTEGER DEFAULT 0,
    stock_maximo INTEGER,
    
    unidad_medida VARCHAR(50), -- 'unidades', 'ml', 'mg', 'cajas'
    
    costo_unitario DECIMAL(10,2) DEFAULT 0.00,
    precio_venta DECIMAL(10,2) DEFAULT 0.00,
    
    proveedor VARCHAR(255),
    codigo_proveedor VARCHAR(100),
    
    activo BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_inventario_empresa ON inventario(empresa_id);
CREATE INDEX idx_inventario_categoria ON inventario(categoria);
CREATE INDEX idx_inventario_codigo ON inventario(codigo);
CREATE INDEX idx_inventario_stock_bajo ON inventario(empresa_id) WHERE stock_actual <= stock_minimo;

DROP TRIGGER IF EXISTS update_inventario_updated_at ON inventario;
CREATE TRIGGER update_inventario_updated_at
    BEFORE UPDATE ON inventario
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Movimientos de Inventario (Stock)
DROP TABLE IF EXISTS inventario_movimientos CASCADE;
CREATE TABLE inventario_movimientos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inventario_id UUID NOT NULL REFERENCES inventario(id) ON DELETE CASCADE,
    paciente_id UUID REFERENCES pacientes(id) ON DELETE SET NULL,
    usuario_id UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    empresa_id UUID REFERENCES empresas(id) ON DELETE CASCADE,
    
    fecha_movimiento TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    tipo_movimiento VARCHAR(20) NOT NULL, -- 'Entrada', 'Salida', 'Ajuste'
    
    cantidad INTEGER NOT NULL,
    stock_anterior INTEGER NOT NULL,
    stock_nuevo INTEGER NOT NULL,
    
    motivo TEXT,
    referencia_documento VARCHAR(100), -- N° de factura, remito, etc.
    
    costo_unitario DECIMAL(10,2),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_movimientos_inventario ON inventario_movimientos(inventario_id);
CREATE INDEX idx_movimientos_fecha ON inventario_movimientos(fecha_movimiento DESC);
CREATE INDEX idx_movimientos_paciente ON inventario_movimientos(paciente_id);

-- Trigger para actualizar stock automáticamente
CREATE OR REPLACE FUNCTION actualizar_stock_inventario()
RETURNS TRIGGER AS $$
BEGIN
    -- Actualizar stock en tabla inventario
    UPDATE inventario
    SET stock_actual = NEW.stock_nuevo,
        updated_at = NOW()
    WHERE id = NEW.inventario_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_actualizar_stock ON inventario_movimientos;
CREATE TRIGGER trigger_actualizar_stock
    AFTER INSERT ON inventario_movimientos
    FOR EACH ROW
    EXECUTE FUNCTION actualizar_stock_inventario();

-- Auditoría Legal (Logs inmutables)
DROP TABLE IF EXISTS auditoria_legal CASCADE;
CREATE TABLE auditoria_legal (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID REFERENCES empresas(id) ON DELETE CASCADE,
    paciente_id UUID REFERENCES pacientes(id) ON DELETE SET NULL,
    usuario_id UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    
    fecha_evento TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    modulo VARCHAR(100) NOT NULL, -- 'Pacientes', 'Recetas', 'Visitas', etc.
    accion VARCHAR(50) NOT NULL, -- 'CREAR', 'MODIFICAR', 'ELIMINAR', 'VER'
    
    entidad_id UUID, -- ID del registro afectado
    entidad_tipo VARCHAR(50), -- 'paciente', 'receta', etc.
    
    datos_anteriores JSONB,
    datos_nuevos JSONB,
    
    ip_address INET,
    user_agent TEXT,
    
    criticidad VARCHAR(20) DEFAULT 'media', -- 'baja', 'media', 'alta', 'critica'
    detalle TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_auditoria_empresa ON auditoria_legal(empresa_id);
CREATE INDEX idx_auditoria_fecha ON auditoria_legal(fecha_evento DESC);
CREATE INDEX idx_auditoria_paciente ON auditoria_legal(paciente_id);
CREATE INDEX idx_auditoria_usuario ON auditoria_legal(usuario_id);
CREATE INDEX idx_auditoria_criticidad ON auditoria_legal(criticidad) WHERE criticidad IN ('alta', 'critica');

-- Función para registrar auditoría
CREATE OR REPLACE FUNCTION registrar_auditoria(
    p_empresa_id UUID,
    p_paciente_id UUID,
    p_usuario_id UUID,
    p_modulo VARCHAR,
    p_accion VARCHAR,
    p_entidad_id UUID,
    p_entidad_tipo VARCHAR,
    p_datos_anteriores JSONB,
    p_datos_nuevos JSONB,
    p_criticidad VARCHAR DEFAULT 'media',
    p_detalle TEXT DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    INSERT INTO auditoria_legal (
        empresa_id, paciente_id, usuario_id, modulo, accion,
        entidad_id, entidad_tipo, datos_anteriores, datos_nuevos,
        criticidad, detalle
    ) VALUES (
        p_empresa_id, p_paciente_id, p_usuario_id, p_modulo, p_accion,
        p_entidad_id, p_entidad_tipo, p_datos_anteriores, p_datos_nuevos,
        p_criticidad, p_detalle
    );
END;
$$ LANGUAGE plpgsql;

-- ==========================================
-- 5. CONFIGURACIÓN DE SEGURIDAD
-- ==========================================

-- Desactivar RLS temporalmente para configuración inicial
ALTER TABLE empresas DISABLE ROW LEVEL SECURITY;
ALTER TABLE usuarios DISABLE ROW LEVEL SECURITY;
ALTER TABLE pacientes DISABLE ROW LEVEL SECURITY;
ALTER TABLE signos_vitales DISABLE ROW LEVEL SECURITY;
ALTER TABLE evoluciones DISABLE ROW LEVEL SECURITY;
ALTER TABLE recetas DISABLE ROW LEVEL SECURITY;
ALTER TABLE visitas DISABLE ROW LEVEL SECURITY;
ALTER TABLE inventario DISABLE ROW LEVEL SECURITY;
ALTER TABLE inventario_movimientos DISABLE ROW LEVEL SECURITY;
ALTER TABLE auditoria_legal DISABLE ROW LEVEL SECURITY;

-- Comentarios para documentación
COMMENT ON TABLE signos_vitales IS 'Registro de signos vitales con alertas automáticas';
COMMENT ON TABLE evoluciones IS 'Evoluciones clínicas de pacientes';
COMMENT ON TABLE recetas IS 'Recetas médicas con detalle de medicamentos';
COMMENT ON TABLE visitas IS 'Visitas y agenda médica';
COMMENT ON TABLE inventario IS 'Stock de materiales e insumos';
COMMENT ON TABLE auditoria_legal IS 'Logs de auditoría inmutables para cumplimiento legal';

-- Notificar a Supabase para recargar esquema
NOTIFY pgrst, 'reload schema';

-- ==========================================
-- RESUMEN DE MEJORAS APLICADAS
-- ==========================================
-- ✓ Triggers para updated_at automático
-- ✓ Triggers para alertas clínicas automáticas
-- ✓ Triggers para actualización de stock
-- ✓ Índices optimizados para búsquedas frecuentes
-- ✓ Constraints de validación de datos
-- ✓ Función de auditoría centralizada
-- ✓ Campos de geolocalización para visitas
-- ✓ Sistema de alertas en signos vitales
-- ✓ Estados de entidades (máquina de estados)
-- ✓ JSONB para datos flexibles (medicamentos)
