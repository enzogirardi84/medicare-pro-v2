import copy
import hashlib
import json
import time
from pathlib import Path

import streamlit as st
from supabase import Client, create_client

LOCAL_DB_PATH = Path(__file__).resolve().parent.parent / ".streamlit" / "local_data.json"
LOCAL_DB_DIR = Path(__file__).resolve().parent.parent / ".streamlit" / "data_store"


def _db_keys():
    return [
        "usuarios_db",
        "pacientes_db",
        "detalles_pacientes_db",
        "vitales_db",
        "indicaciones_db",
        "turnos_db",
        "evoluciones_db",
        "facturacion_db",
        "logs_db",
        "balance_db",
        "pediatria_db",
        "fotos_heridas_db",
        "agenda_db",
        "checkin_db",
        "inventario_db",
        "consumos_db",
        "nomenclador_db",
        "firmas_tactiles_db",
        "reportes_diarios_db",
        "estudios_db",
        "administracion_med_db",
        "consentimientos_db",
        "emergencias_db",
        "cuidados_enfermeria_db",
        "escalas_clinicas_db",
        "auditoria_legal_db",
    ]


@st.cache_resource
def init_supabase():
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")
    if not url or "tu-proyecto-aqui" in url or not key:
        return None
    return create_client(url, key)


supabase = init_supabase()


def _guardar_local(data):
    try:
        LOCAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_DB_DIR.mkdir(parents=True, exist_ok=True)
        manifest = {
            "version": 2,
            "keys": sorted(list(data.keys())),
            "updated_at": time.time(),
        }
        for key, value in data.items():
            (LOCAL_DB_DIR / f"{key}.json").write_text(
                json.dumps(value, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        (LOCAL_DB_DIR / "_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # Compatibilidad hacia atras por si alguna herramienta externa sigue leyendo el archivo unico.
        LOCAL_DB_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return True
    except Exception:
        return False


def _cargar_local():
    try:
        manifest_path = LOCAL_DB_DIR / "_manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            data = {}
            for key in manifest.get("keys", []):
                shard_path = LOCAL_DB_DIR / f"{key}.json"
                if shard_path.exists():
                    data[key] = json.loads(shard_path.read_text(encoding="utf-8"))
            if data:
                return data
        if LOCAL_DB_PATH.exists():
            return json.loads(LOCAL_DB_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def cargar_datos(force=False):
    cache_key = "_db_cache"
    if not force and cache_key in st.session_state:
        return copy.deepcopy(st.session_state[cache_key])

    if supabase is None:
        data_local = _cargar_local()
        if data_local:
            st.session_state[cache_key] = copy.deepcopy(data_local)
            payload_serializado = json.dumps(data_local, sort_keys=True, default=str, ensure_ascii=False)
            st.session_state["_db_cache_hash"] = hashlib.md5(payload_serializado.encode("utf-8")).hexdigest()
        st.session_state["_modo_offline"] = True
        return copy.deepcopy(data_local) if data_local else None

    try:
        response = supabase.table("medicare_db").select("datos").eq("id", 1).execute()
        if response.data:
            data = response.data[0]["datos"]
            st.session_state[cache_key] = copy.deepcopy(data)
            payload_serializado = json.dumps(data, sort_keys=True, default=str, ensure_ascii=False)
            st.session_state["_db_cache_hash"] = hashlib.md5(payload_serializado.encode("utf-8")).hexdigest()
            st.session_state["_modo_offline"] = False
            return copy.deepcopy(data)
    except Exception as e:
        data_local = _cargar_local()
        if data_local:
            st.session_state[cache_key] = copy.deepcopy(data_local)
            payload_serializado = json.dumps(data_local, sort_keys=True, default=str, ensure_ascii=False)
            st.session_state["_db_cache_hash"] = hashlib.md5(payload_serializado.encode("utf-8")).hexdigest()
        st.session_state["_modo_offline"] = True
        if not st.session_state.get("_aviso_offline_mostrado"):
            st.warning(f"Modo local activo: no se pudo conectar a la nube ({e}).")
            st.session_state["_aviso_offline_mostrado"] = True
        return copy.deepcopy(data_local) if data_local else None
    return None


def guardar_datos():
    claves = _db_keys()
    data = {k: st.session_state[k] for k in claves if k in st.session_state}
    payload_serializado = json.dumps(data, sort_keys=True, default=str, ensure_ascii=False)
    payload_hash = hashlib.md5(payload_serializado.encode("utf-8")).hexdigest()

    if st.session_state.get("_db_cache_hash") == payload_hash:
        return

    guardado_nube = False
    if supabase is not None:
        try:
            supabase.table("medicare_db").upsert({"id": 1, "datos": data}).execute()
            guardado_nube = True
            st.session_state["_modo_offline"] = False
        except Exception as e:
            st.session_state["_modo_offline"] = True
            if not st.session_state.get("_aviso_offline_mostrado"):
                st.warning(f"No se pudo subir a la nube. Se guardara localmente ({e}).")
                st.session_state["_aviso_offline_mostrado"] = True

    guardado_local = _guardar_local(data)
    st.session_state["_db_cache"] = copy.deepcopy(data)
    st.session_state["_db_cache_hash"] = payload_hash

    ultimo_toast = st.session_state.get("_ultimo_toast_guardado")
    ahora_ts = time.time()
    if ultimo_toast is None or ahora_ts - ultimo_toast > 8:
        if guardado_nube:
            st.toast("Guardado exitosamente en la nube")
        elif guardado_local:
            st.toast("Guardado localmente")
        st.session_state["_ultimo_toast_guardado"] = ahora_ts
