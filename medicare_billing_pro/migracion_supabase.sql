-- ============================================================
-- Medicare Billing Pro — Migración de tablas en Supabase
-- Ejecutar en SQL Editor de Supabase
-- ============================================================

-- 1. Clientes Fiscales
CREATE TABLE IF NOT EXISTS billing_clientes (
    id TEXT PRIMARY KEY,
    empresa_id TEXT NOT NULL,
    nombre TEXT NOT NULL,
    dni TEXT NOT NULL,
    email TEXT DEFAULT '',
    telefono TEXT DEFAULT '',
    direccion TEXT DEFAULT '',
    condicion_fiscal TEXT DEFAULT 'Consumidor Final',
    notas TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_billing_clientes_empresa ON billing_clientes(empresa_id);

-- 2. Presupuestos
CREATE TABLE IF NOT EXISTS billing_presupuestos (
    id TEXT PRIMARY KEY,
    empresa_id TEXT NOT NULL,
    numero TEXT NOT NULL,
    cliente_id TEXT,
    cliente_nombre TEXT NOT NULL,
    fecha DATE NOT NULL,
    valido_hasta DATE,
    items JSONB DEFAULT '[]',
    total NUMERIC(12,2) DEFAULT 0,
    estado TEXT DEFAULT 'Borrador',
    notas TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_billing_pres_empresa ON billing_presupuestos(empresa_id);
CREATE INDEX IF NOT EXISTS idx_billing_pres_cliente ON billing_presupuestos(cliente_id);

-- 3. Pre-facturas
CREATE TABLE IF NOT EXISTS billing_prefacturas (
    id TEXT PRIMARY KEY,
    empresa_id TEXT NOT NULL,
    numero TEXT NOT NULL,
    cliente_id TEXT,
    cliente_nombre TEXT NOT NULL,
    cliente_dni TEXT DEFAULT '',
    fecha DATE NOT NULL,
    items JSONB DEFAULT '[]',
    total NUMERIC(12,2) DEFAULT 0,
    estado TEXT DEFAULT 'Pendiente',
    presupuesto_origen TEXT,
    notas TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_billing_fac_empresa ON billing_prefacturas(empresa_id);
CREATE INDEX IF NOT EXISTS idx_billing_fac_cliente ON billing_prefacturas(cliente_id);

-- 4. Cobros
CREATE TABLE IF NOT EXISTS billing_cobros (
    id TEXT PRIMARY KEY,
    empresa_id TEXT NOT NULL,
    cliente_id TEXT,
    cliente_nombre TEXT NOT NULL,
    fecha DATE NOT NULL,
    monto NUMERIC(12,2) NOT NULL,
    metodo_pago TEXT DEFAULT 'Efectivo',
    concepto TEXT DEFAULT '',
    estado TEXT DEFAULT 'Cobrado',
    prefactura_id TEXT,
    notas TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_billing_cob_empresa ON billing_cobros(empresa_id);
CREATE INDEX IF NOT EXISTS idx_billing_cob_cliente ON billing_cobros(cliente_id);
CREATE INDEX IF NOT EXISTS idx_billing_cob_fecha ON billing_cobros(fecha);
CREATE INDEX IF NOT EXISTS idx_billing_cob_prefactura ON billing_cobros(prefactura_id);

-- 5. Configuracion fiscal de empresa
CREATE TABLE IF NOT EXISTS billing_config_fiscal (
    empresa_id TEXT PRIMARY KEY,
    razon_social TEXT DEFAULT '',
    nombre_fantasia TEXT DEFAULT '',
    cuit TEXT DEFAULT '',
    condicion_iva TEXT DEFAULT 'Monotributista',
    domicilio_fiscal TEXT DEFAULT '',
    ingresos_brutos TEXT DEFAULT '',
    inicio_actividades DATE,
    punto_venta INTEGER DEFAULT 1,
    logo_url TEXT DEFAULT '',
    email_facturacion TEXT DEFAULT '',
    telefono_facturacion TEXT DEFAULT '',
    leyenda_factura TEXT DEFAULT '',
    arca_modo TEXT DEFAULT 'homologacion',
    arca_certificado_configurado BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Numeracion formal por empresa, tipo y punto de venta
CREATE TABLE IF NOT EXISTS billing_numeradores (
    id TEXT PRIMARY KEY,
    empresa_id TEXT NOT NULL,
    tipo TEXT NOT NULL,
    punto_venta INTEGER DEFAULT 1,
    prefijo TEXT DEFAULT '',
    ultimo_numero INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (empresa_id, tipo, punto_venta)
);
CREATE INDEX IF NOT EXISTS idx_billing_num_empresa ON billing_numeradores(empresa_id);

-- 7. Facturas ARCA internas
CREATE TABLE IF NOT EXISTS billing_facturas_arca (
    id TEXT PRIMARY KEY,
    empresa_id TEXT NOT NULL,
    numero TEXT NOT NULL,
    punto_venta INTEGER DEFAULT 1,
    tipo_comprobante TEXT DEFAULT 'C',
    concepto_arca TEXT DEFAULT 'Servicios',
    cliente_id TEXT,
    cliente_nombre TEXT NOT NULL,
    cliente_dni TEXT DEFAULT '',
    condicion_iva_receptor TEXT DEFAULT 'Consumidor Final',
    fecha DATE NOT NULL,
    items JSONB DEFAULT '[]',
    neto NUMERIC(12,2) DEFAULT 0,
    iva NUMERIC(12,2) DEFAULT 0,
    total NUMERIC(12,2) DEFAULT 0,
    estado TEXT DEFAULT 'Borrador',
    cae TEXT DEFAULT '',
    cae_vencimiento DATE,
    arca_resultado JSONB DEFAULT '{}',
    prefactura_origen TEXT,
    notas TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_billing_arca_empresa ON billing_facturas_arca(empresa_id);
CREATE INDEX IF NOT EXISTS idx_billing_arca_cliente ON billing_facturas_arca(cliente_id);
CREATE INDEX IF NOT EXISTS idx_billing_arca_fecha ON billing_facturas_arca(fecha);
CREATE INDEX IF NOT EXISTS idx_billing_arca_estado ON billing_facturas_arca(estado);

-- 8. Auditoria operativa
CREATE TABLE IF NOT EXISTS billing_auditoria (
    id TEXT PRIMARY KEY,
    empresa_id TEXT NOT NULL,
    usuario TEXT DEFAULT '',
    accion TEXT NOT NULL,
    entidad TEXT NOT NULL,
    entidad_id TEXT DEFAULT '',
    detalle JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_billing_audit_empresa ON billing_auditoria(empresa_id);
CREATE INDEX IF NOT EXISTS idx_billing_audit_entidad ON billing_auditoria(entidad, entidad_id);

-- 5. Trigger para updated_at automático
CREATE OR REPLACE FUNCTION update_billing_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOR tbl IN
        SELECT unnest(ARRAY['billing_clientes', 'billing_presupuestos', 'billing_prefacturas', 'billing_cobros', 'billing_config_fiscal', 'billing_numeradores', 'billing_facturas_arca'])
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger WHERE tgname = 'trg_' || tbl || '_updated_at'
        ) THEN
            EXECUTE format(
                'CREATE TRIGGER trg_%I_updated_at BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION update_billing_updated_at()',
                tbl, tbl
            );
        END IF;
    END LOOP;
END;
$$;
