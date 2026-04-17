import json

def recuperar_desde_local():
    try:
        with open(".streamlit/local_data.json", "r", encoding="utf-8") as f:
            datos = json.load(f)
            
        usuarios = datos.get("usuarios_db", {})
        print(f"Se encontraron {len(usuarios)} usuarios en local_data.json")
        
        with open("usuarios_recuperados.json", "w", encoding="utf-8") as f:
            json.dump(usuarios, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    recuperar_desde_local()