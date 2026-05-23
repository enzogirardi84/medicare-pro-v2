-- ============================================================
-- RLS Multi-Tenant: Aislamiento por empresa_id
-- Medicare Enterprise PRO
-- Ejecutar en consola SQL de Supabase (Dashboard > SQL Editor)
-- ============================================================

-- 1. Funcion para setear contexto del tenant
CREATE OR REPLACE FUNCTION public.set_tenant_context(empresa_id text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  PERFORM set_config('app.current_empresa_id', empresa_id, false);
END;
$$;

-- 2. Funcion helper para obtener el tenant actual
CREATE OR REPLACE FUNCTION public.current_tenant_id()
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT current_setting('app.current_empresa_id', true);
$$;

-- ============================================================
-- POLITICAS RLS POR TABLA
-- ============================================================

-- PACIENTES
ALTER TABLE pacientes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_pacientes ON pacientes;
CREATE POLICY tenant_isolation_pacientes ON pacientes
  FOR ALL
  USING (empresa_id = current_tenant_id() OR current_tenant_id() IS NULL);

-- EVOLUCIONES
ALTER TABLE evoluciones ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_evoluciones ON evoluciones;
CREATE POLICY tenant_isolation_evoluciones ON evoluciones
  FOR ALL
  USING (empresa_id = current_tenant_id() OR current_tenant_id() IS NULL);

-- INDICACIONES / RECETAS
ALTER TABLE indicaciones ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_indicaciones ON indicaciones;
CREATE POLICY tenant_isolation_indicaciones ON indicaciones
  FOR ALL
  USING (empresa_id = current_tenant_id() OR current_tenant_id() IS NULL);

-- SIGNOS VITALES
ALTER TABLE signos_vitales ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_signos_vitales ON signos_vitales;
CREATE POLICY tenant_isolation_signos_vitales ON signos_vitales
  FOR ALL
  USING (empresa_id = current_tenant_id() OR current_tenant_id() IS NULL);

-- ESTUDIOS
ALTER TABLE estudios ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_estudios ON estudios;
CREATE POLICY tenant_isolation_estudios ON estudios
  FOR ALL
  USING (empresa_id = current_tenant_id() OR current_tenant_id() IS NULL);

-- FACTURACION
ALTER TABLE facturacion ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_facturacion ON facturacion;
CREATE POLICY tenant_isolation_facturacion ON facturacion
  FOR ALL
  USING (empresa_id = current_tenant_id() OR current_tenant_id() IS NULL);

-- INVENTARIO
ALTER TABLE inventario ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_inventario ON inventario;
CREATE POLICY tenant_isolation_inventario ON inventario
  FOR ALL
  USING (empresa_id = current_tenant_id() OR current_tenant_id() IS NULL);

-- BALANCE
ALTER TABLE balance ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_balance ON balance;
CREATE POLICY tenant_isolation_balance ON balance
  FOR ALL
  USING (empresa_id = current_tenant_id() OR current_tenant_id() IS NULL);

-- AUDITORIA LEGAL
ALTER TABLE auditoria_legal ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_auditoria ON auditoria_legal;
CREATE POLICY tenant_isolation_auditoria ON auditoria_legal
  FOR ALL
  USING (empresa_id = current_tenant_id() OR current_tenant_id() IS NULL);

-- EMERGENCIAS
ALTER TABLE emergencias ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_emergencias ON emergencias;
CREATE POLICY tenant_isolation_emergencias ON emergencias
  FOR ALL
  USING (empresa_id = current_tenant_id() OR current_tenant_id() IS NULL);

-- TURNOS
ALTER TABLE turnos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_turnos ON turnos;
CREATE POLICY tenant_isolation_turnos ON turnos
  FOR ALL
  USING (empresa_id = current_tenant_id() OR current_tenant_id() IS NULL);

-- CHECKINS
ALTER TABLE checkin_asistencia ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_checkins ON checkin_asistencia;
CREATE POLICY tenant_isolation_checkins ON checkin_asistencia
  FOR ALL
  USING (empresa_id = current_tenant_id() OR current_tenant_id() IS NULL);

-- USUARIOS
ALTER TABLE usuarios ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_usuarios ON usuarios;
CREATE POLICY tenant_isolation_usuarios ON usuarios
  FOR ALL
  USING (empresa_id = current_tenant_id() OR current_tenant_id() IS NULL);

-- ============================================================
-- NOTA: Luego de ejecutar, cada consulta desde Python debe
-- llamar a: SET LOCAL app.current_empresa_id = '<empresa_id>';
-- antes de cualquier operacion CRUD.
-- ============================================================
