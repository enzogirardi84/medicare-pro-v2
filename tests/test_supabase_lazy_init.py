from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_database_reintenta_supabase_si_import_inicial_quedo_en_local():
    source = (ROOT / "core" / "database.py").read_text(encoding="utf-8")

    assert "def _ensure_supabase_runtime" in source
    assert "supabase_lazy_init_ok" in source
    assert "_ensure_supabase_runtime()\n\n        if supabase is None:" in source
    assert "_ensure_supabase_runtime()\n    if supabase is not None:" in source
