import copy
import hashlib
import json
import time
from pathlib import Path

import streamlit as st

try:
    from supabase import create_client
except ImportError:
    create_client = None

LOCAL_DB_PATH = Path(__file__).resolve().parent.parent / ".streamlit" / "local_data.json"
LOCAL_DB_DIR = Path(__file__).resolve().parent.parent / ".streamlit" / "data_store"


def _registrar_estado_guardado(estado, detalle="", guardado_nube=False, guardado_local=False):
    st.session_state["_ultimo_guardado_estado"] = estado
    st.session_state["_ultimo_guardado_detalle"] = str(detalle or "").strip()
    st.session_state["_ultimo_guardado_ts"] = time.time()
    st.session_state["_ultimo_guardado_nube"] = bool(guardado_nube)
    st.session_state["_ultimo_guardado_local"] = bool(guardado_local)


def obtener_estado_guardado():
    return {
        "estado": st.session_state.get("_ultimo_guardado_estado", ""),
        "detalle": st.session_state.get("_ultimo_guardado_detalle", ""),
        "timestamp": st.session_state.get("_ultimo_guardado_ts"),
        "guardado_nube": bool(st.session_state.get("_ultimo_guardado_nube", False)),
        "guardado_local": bool(st.session_state.get("_ultimo_guardado_local", False)),
    }


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
        "profesionales_red_db",
        "solicitudes_servicios_db",
    ]


@st.cache_resource
def init_supabase():
    if create_client is None:
        return None
    try:
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")
    except Exception:
        return None
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
        _registrar_estado_guardado("sin_cambios", "No habia cambios pendientes.", guardado_nube=supabase is not None, guardado_local=True)
        return

    guardado_nube = False
    error_nube = ""
    if supabase is not None:
        try:
            supabase.table("medicare_db").upsert({"id": 1, "datos": data}).execute()
            guardado_nube = True
            st.session_state["_modo_offline"] = False
        except Exception as e:
            error_nube = str(e)
            st.session_state["_modo_offline"] = True
            if not st.session_state.get("_aviso_offline_mostrado"):
                st.warning(f"No se pudo subir a la nube. Se guardara localmente ({e}).")
                st.session_state["_aviso_offline_mostrado"] = True

    guardado_local = _guardar_local(data)
    st.session_state["_db_cache"] = copy.deepcopy(data)
    st.session_state["_db_cache_hash"] = payload_hash

    if guardado_nube:
        _registrar_estado_guardado("nube", "Guardado sincronizado en la nube.", guardado_nube=True, guardado_local=guardado_local)
    elif guardado_local:
        detalle = "Guardado local activo."
        if error_nube:
            detalle = f"Guardado local por falta de nube: {error_nube}"
        _registrar_estado_guardado("local", detalle, guardado_nube=False, guardado_local=True)
    else:
        detalle = "No se pudo guardar ni en la nube ni en este equipo."
        if error_nube:
            detalle = f"{detalle} Error nube: {error_nube}"
        _registrar_estado_guardado("error", detalle, guardado_nube=False, guardado_local=False)

    ultimo_toast = st.session_state.get("_ultimo_toast_guardado")
    ahora_ts = time.time()
    if ultimo_toast is None or ahora_ts - ultimo_toast > 8:
        if guardado_nube:
            st.toast("Guardado exitosamente en la nube")
        elif guardado_local:
            st.toast("Guardado localmente")
        else:
            st.error("No se pudo guardar la informacion. Verifica conexion y permisos de escritura.")
        st.session_state["_ultimo_toast_guardado"] = ahora_ts

    return {
        "guardado_nube": guardado_nube,
        "guardado_local": guardado_local,
        "error_nube": error_nube,
    }
