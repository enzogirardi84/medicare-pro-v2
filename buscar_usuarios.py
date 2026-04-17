import json

def buscar_usuarios_local():
    try:
        with open(".streamlit/local_data.json", "r", encoding="utf-8") as f:
            datos = json.load(f)
            
        usuarios = datos.get("usuarios_db", {})
        print(f"Usuarios en local_data.json: {list(usuarios.keys())}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    buscar_usuarios_local()