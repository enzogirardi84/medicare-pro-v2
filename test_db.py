import streamlit as st
from supabase import create_client

def test_connection():
    try:
        # 1. Intentar leer del archivo secrets.toml
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        
        print(f"✅ Secretos encontrados. Conectando a: {url}")
        
        # 2. Intentar crear el cliente
        supabase = create_client(url, key)
        
        # 3. Intentar una consulta mínima (traer un solo log o usuario)
        # Cambia 'usuarios_db' por el nombre de una tabla que sepas que existe
        response = supabase.table("usuarios_db").select("*").limit(1).execute()
        
        print("🚀 ¡CONEXIÓN EXITOSA!")
        print(f"Dato recuperado: {response.data}")
        
    except Exception as e:
        print("❌ ERROR DE CONEXIÓN:")
        print(str(e))

if __name__ == "__main__":
    test_connection()