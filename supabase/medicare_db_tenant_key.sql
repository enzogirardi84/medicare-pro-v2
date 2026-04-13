-- Ejecutar una vez en Supabase (SQL editor) antes de activar USE_TENANT_SHARDS.
-- Permite varias filas: legacy id=1 (toda la red) y una fila por clínica (tenant_key).

ALTER TABLE medicare_db ADD COLUMN IF NOT EXISTS tenant_key text;

CREATE UNIQUE INDEX IF NOT EXISTS medicare_db_tenant_key_unique
  ON medicare_db (tenant_key)
  WHERE tenant_key IS NOT NULL;

COMMENT ON COLUMN medicare_db.tenant_key IS 'Clave normalizada de clínica/empresa; NULL = fila legacy monolito (id=1).';

-- En Streamlit secrets, con USE_TENANT_SHARDS = true:
-- MONOLITO_LOGIN_ALLOWLIST = "supervisor,enzo_root"   # o lista TOML: ["a","b"]
-- Esos logins (minúsculas) cargan siempre la fila monolito; "admin" va implícito.
