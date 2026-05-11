from __future__ import annotations

import re
from pathlib import Path

import psycopg2

secrets_path = Path(r"c:\programa de salud optimizado\.streamlit\secrets.toml")
sql_path = Path(r"c:\medicare_billing_pro\migracion_supabase.sql")

secrets = secrets_path.read_text(encoding="utf-8")
match = re.search(r'DATABASE_URL\s*=\s*"([^"]+)"', secrets)
if not match:
    raise RuntimeError("DATABASE_URL no encontrado en secrets.toml")

database_url = match.group(1)
sql = sql_path.read_text(encoding="utf-8")

conn = psycopg2.connect(database_url)
conn.autocommit = True
try:
    with conn.cursor() as cur:
        cur.execute(sql)
finally:
    conn.close()

print("MIGRATION_OK")
