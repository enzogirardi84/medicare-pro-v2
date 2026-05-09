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
        SELECT unnest(ARRAY['billing_clientes', 'billing_presupuestos', 'billing_prefacturas', 'billing_cobros'])
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
