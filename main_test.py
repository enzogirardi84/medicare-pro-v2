"""TEST - Entry point minimo para diagnosticar pantalla azul"""
import streamlit as st

st.set_page_config(page_title="Medicare TEST", layout="wide")

st.title("MEDICARE PRO - MODO DIAGNOSTICO")
st.success("Si ves este mensaje, la app base funciona correctamente.")

st.info("""
Este es un entry point minimo para verificar que Streamlit y 
las dependencias basicas funcionan.
""")

with st.expander("Verificaciones", expanded=True):
    import sys
    st.write(f"Python: {sys.version}")
    
    try:
        from core.app_bootstrap import insert_repo_root_on_path
        st.success("core.app_bootstrap: OK")
    except Exception as e:
        st.error(f"core.app_bootstrap: {e}")
    
    try:
        from core.app_logging import configurar_logging_basico
        configurar_logging_basico()
        st.success("core.app_logging: OK")
    except Exception as e:
        st.error(f"core.app_logging: {e}")
    
    try:
        from core.database import supabase
        st.success(f"Supabase: {'CONECTADO' if supabase else 'No configurado'}")
    except Exception as e:
        st.error(f"Supabase: {e}")
    
    try:
        import pandas as pd
        st.success(f"pandas: {pd.__version__}")
    except Exception as e:
        st.error(f"pandas: {e}")

st.button("Click para probar", width='stretch')
st.caption("2026 Medicare Pro - Test Mode")
