"""Migrar @st.cache_data a cache manual en funciones SQL getter."""
import re, time, sys

def migrate_clinico():
    path = r"c:\programa de salud optimizado\core\_db_sql_clinico.py"
    src = open(path, encoding="utf-8", errors="replace").read()

    functions = [
        ("get_evoluciones_by_paciente", 90, "f'_sql_clin_evol_{{paciente_id}}_{{limit}}'", "List[Dict[str, Any]]", "[]"),
        ("get_indicaciones_activas", 90, "f'_sql_clin_ind_{{paciente_id}}'", "List[Dict[str, Any]]", "[]"),
        ("get_estudios_by_paciente", 90, "f'_sql_clin_est_{{paciente_id}}'", "List[Dict[str, Any]]", "[]"),
        ("get_signos_vitales", 90, "f'_sql_clin_vit_{{paciente_id}}_{{limit}}'", "List[Dict[str, Any]]", "[]"),
        ("get_cuidados_enfermeria", 90, "f'_sql_clin_cuid_{{paciente_id}}'", "List[Dict[str, Any]]", "[]"),
        ("get_consentimientos_by_paciente", 90, "f'_sql_clin_cons_{{paciente_id}}'", "List[Dict[str, Any]]", "[]"),
        ("get_pediatria_by_paciente", 90, "f'_sql_clin_ped_{{paciente_id}}'", "List[Dict[str, Any]]", "[]"),
        ("get_escalas_by_paciente", 90, "f'_sql_clin_esc_{{paciente_id}}'", "List[Dict[str, Any]]", "[]"),
    ]

    for fname, ttl, cache_expr, ret_type, empty in functions:
        # Find decorator + function definition
        pat = rf'@st\.cache_data\(ttl={ttl}, show_spinner=False\)\n(def {fname}\([^)]*\)\s*->\s*{re.escape(ret_type)}:\s*\n)(\s+""".*?"""\s*\n)?(\s+if not _ok\(\):\s*\n\s+return {re.escape(empty)}\s*\n)(\s+try:\s*\n\s+response = _supabase_execute_with_retry\(\s*\n\s+"([^"]+)",\s*\n\s+lambda: supabase\.table\("([^"]+)"\)\.select\("([^"]*)"\)(.*?),\s*\n\s+\)\s*\n)(\s+return response\.data if response and response\.data else {re.escape(empty)}\s*\n)(\s+except Exception as e:\s*\n\s+log_event\("db_sql", f"error_([^"]+):\{type\(e\)\.\__name__\}\"\)\s*\n\s+return {re.escape(empty)}\s*\n)'
        m = re.search(pat, src, re.DOTALL)
        if not m:
            print(f"SKIP {fname}: pattern no match")
            continue
        # Build replacement
        cache_key_str = cache_expr.replace("{{", "{").replace("}}", "}")
        # Extract args from signature for cache key interpolation
        sig = m.group(1)
        # Simple approach: just insert cache check after docstring, before if not _ok
        # But we need to handle variable args. Let's use f-string with known params.
        # For simplicity, use the cache_key_str directly but interpolate known params.
        
        # We'll construct the new function body manually
        start = m.start()
        end = m.end()
        
        # Extract lambda body
        table_name = m.group(7)
        select_cols = m.group(8)
        lambda_tail = m.group(9).strip()
        op_name = m.group(6)
        error_key = m.group(11)
        
        new_body = f'''    """Cache manual a prueba de fallos."""
    cache_key = {cache_key_str}
    cached = st.session_state.get(cache_key)
    if cached and time.monotonic() - cached["ts"] < {ttl}:
        return cached["data"]
    if not _ok():
        return {empty}
    try:
        response = _supabase_execute_with_retry(
            "{op_name}",
            lambda: supabase.table("{table_name}").select("{select_cols}"){lambda_tail}.execute(),
        )
        data = response.data if response and response.data else {empty}
        st.session_state[cache_key] = {{"data": data, "ts": time.monotonic()}}
        return data
    except Exception as e:
        log_event("db_sql", f"error_{error_key}:{{type(e).__name__}}")
        return {empty}
'''
        # Replace decorator+body
        decorator = m.group(0).split("def ")[0]
        src = src[:start] + f"def {fname}{sig.split('def '+fname)[1].split(':')[0]}:\n" + new_body + src[end:]
        print(f"MIGRATED {fname}")

    open(path, "w", encoding="utf-8").write(src)

if __name__ == "__main__":
    migrate_clinico()
    print("Done.")
