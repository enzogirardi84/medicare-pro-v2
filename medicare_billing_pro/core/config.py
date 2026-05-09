"""Configuración central: variables de entorno, constantes y paths."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ── Paths ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"

# ── Supabase ───────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# ── App ────────────────────────────────────────────────────
APP_NAME = "Medicare Billing Pro"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Gestión de facturación, cobros y reportes contables para profesionales de la salud."
PAGE_TITLE = "Medicare Billing Pro | Facturación Médica"

# ── Feature flags ──────────────────────────────────────────
ENABLE_EXCEL_EXPORT = True
ENABLE_PDF_EXPORT = True
ITEMS_PER_PAGE_DEFAULT = 50
