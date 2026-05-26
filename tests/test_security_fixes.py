from core.utils import DEFAULT_ADMIN_USER
from core.guardado_emergencia import _guardar_supabase_signos_vitales, _guardar_supabase_evolucion, _obtener_supabase_signos_vitales


def test_default_admin_no_real_pii():
    assert "Enzo" not in DEFAULT_ADMIN_USER.get("nombre", "")
    assert DEFAULT_ADMIN_USER.get("dni") != "37108100"
    assert "21947" not in DEFAULT_ADMIN_USER.get("matricula", "")


def test_guardado_emergencia_no_create_client():
    import inspect
    for fn in (_guardar_supabase_signos_vitales, _guardar_supabase_evolucion, _obtener_supabase_signos_vitales):
        src = inspect.getsource(fn)
        assert "create_client" not in src, f"{fn.__name__} still uses create_client"
        assert "init_supabase" in src, f"{fn.__name__} should use init_supabase"


def test_error_handling_no_str_e_in_st_error():
    from core.error_handling import safe_operation
    import inspect
    src = inspect.getsource(safe_operation)
    assert "str(e)" not in src.split("st.error")[-1].split("\n")[0] if "st.error" in src else True


def test_db_sql_pacientes_no_str_e_in_log():
    import inspect
    from core import _db_sql_pacientes
    src = inspect.getsource(_db_sql_pacientes)
    lines = src.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "log_event" in stripped and "str(" in stripped:
            assert "str(e)" not in stripped and "str(last_error)" not in stripped, \
                f"Line {i+1}: {stripped} leaks PHI via str() in log_event"
