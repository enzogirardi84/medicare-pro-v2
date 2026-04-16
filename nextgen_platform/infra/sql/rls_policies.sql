-- RLS base para entorno PostgreSQL/Supabase.
-- Requiere que la API setee:
--   SET app.tenant_id = '<uuid-tenant>';
--   SET app.user_role = '<role>';
-- En Supabase puede mapearse con claims JWT.

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE visits ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_users ON users;
CREATE POLICY tenant_isolation_users
ON users
USING (tenant_id::text = current_setting('app.tenant_id', true));

DROP POLICY IF EXISTS tenant_isolation_patients ON patients;
CREATE POLICY tenant_isolation_patients
ON patients
USING (tenant_id::text = current_setting('app.tenant_id', true));

DROP POLICY IF EXISTS tenant_isolation_visits ON visits;
CREATE POLICY tenant_isolation_visits
ON visits
USING (tenant_id::text = current_setting('app.tenant_id', true));

DROP POLICY IF EXISTS tenant_isolation_audit_logs ON audit_logs;
CREATE POLICY tenant_isolation_audit_logs
ON audit_logs
USING (tenant_id::text = current_setting('app.tenant_id', true));

DROP POLICY IF EXISTS audit_read_roles ON audit_logs;
CREATE POLICY audit_read_roles
ON audit_logs
FOR SELECT
USING (current_setting('app.user_role', true) IN ('admin', 'auditor'));
