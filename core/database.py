import copy
import hashlib
import json
import time
from pathlib import Path

import streamlit as st

from core.app_logging import log_event
from core.clinicas_control import norm_empresa_key

try:
    from supabase import create_client
except ImportError:
    create_client = None

LOCAL_DB_PATH = Path(__file__).resolve().parent.parent / ".streamlit" / "local_data.json"
LOCAL_DB_DIR = Path(__file__).resolve().parent.parent / ".streamlit" / "data_store"
LOCAL_TENANTS_DIR = LOCAL_DB_DIR / "tenants"

# Aviso si el JSON serializado supera esto (no corta el guardado; solo log + toast ocasional)
PAYLOAD_ALERTA_BYTES = 9 * 1024 * 1024


def modo_shard_activo() -> bool:
    try:
        v = st.secrets.get("USE_TENANT_SHARDS", False)
        if isinstance(v, bool):
            return v
        return str(v).strip().lower() in ("1", "true", "yes", "si", "on")
    except Exception:
        return False


def logins_monolito_allowlist() -> set[str]:
    """
    Logins (normalizados a minúsculas) que en modo shard cargan el monolito id=1 en lugar de un tenant.
    Secret MONOLITO_LOGIN_ALLOWLIST: lista TOML, o string separado por comas / punto y coma.
    El usuario 'admin' siempre usa monolito aunque no esté en la lista.
    """
    try:
        raw = st.secrets.get("MONOLITO_LOGIN_ALLOWLIST", None)
    except Exception:
        return set()
    if raw is None or raw == "":
        return set()
    if isinstance(raw, (list, tuple)):
        return {str(x).strip().lower() for x in raw if str(x).strip()}
    s = str(raw).replace(";", ",")
    return {x.strip().lower() for x in s.split(",") if x.strip()}


def login_usa_monolito_legacy(login_normalizado: str) -> bool:
    """True si este login debe usar la base global (monolito) con USE_TENANT_SHARDS activo."""
    s = str(login_normalizado or "").strip().lower()
    if not s:
        return False
    if s == "admin":
        return True
    return s in logins_monolito_allowlist()


def tenant_key_normalizado(empresa: str) -> str:
    return norm_empresa_key(empresa) or ""


def sesion_usa_monolito_legacy() -> bool:
    return bool(st.session_state.get("_db_monolito_sesion"))


def _estructura_vacia_por_clave():
    return {
        "usuarios_db": {},
        "pacientes_db": [],
        "detalles_pacientes_db": {},
        "vitales_db": [],
        "indicaciones_db": [],
        "turnos_db": [],
        "evoluciones_db": [],
        "facturacion_db": [],
        "logs_db": [],
        "balance_db": [],
        "pediatria_db": [],
        "fotos_heridas_db": [],
        "agenda_db": [],
        "checkin_db": [],
        "inventario_db": [],
        "consumos_db": [],
        "nomenclador_db": [],
        "firmas_tactiles_db": [],
        "reportes_diarios_db": [],
        "estudios_db": [],
        "administracion_med_db": [],
        "consentimientos_db": [],
        "emergencias_db": [],
        "cuidados_enfermeria_db": [],
        "escalas_clinicas_db": [],
        "auditoria_legal_db": [],
        "profesionales_red_db": [],
        "solicitudes_servicios_db": [],
        "plantillas_whatsapp_db": {},
        "clinicas_db": {},
    }


def completar_claves_db_session():
    """Rellena colecciones faltantes (shards viejos o migraciones parciales)."""
    plantilla = _estructura_vacia_por_clave()
    for k, default in plantilla.items():
        if k not in st.session_state:
            st.session_state[k] = copy.deepcopy(default)


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
        "plantillas_whatsapp_db",
        "clinicas_db",
    ]


def vaciar_datos_app_en_sesion() -> None:
    """Elimina datos clínicos en memoria (cerrar sesión en equipo compartido). El próximo login vuelve a cargar."""
    for k in _db_keys():
        st.session_state.pop(k, None)
    for k in (
        "_db_cache",
        "_db_cache_hash",
        "_modo_offline",
        "_aviso_offline_mostrado",
        "_ultimo_toast_guardado",
        "_db_monolito_sesion",
        "_mc_app_alerta_fetch",
        "_mc_app_alerta_ts",
        "_mc_app_alerta_emp",
    ):
        st.session_state.pop(k, None)


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


def _payload_muy_grande(serializado: str) -> bool:
    return len(serializado.encode("utf-8")) >= PAYLOAD_ALERTA_BYTES


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


def _cargar_local_tenant(tenant_key: str):
    try:
        p = LOCAL_TENANTS_DIR / f"{tenant_key}.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def _guardar_local_tenant(tenant_key: str, data: dict) -> bool:
    try:
        LOCAL_TENANTS_DIR.mkdir(parents=True, exist_ok=True)
        path = LOCAL_TENANTS_DIR / f"{tenant_key}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return True
    except Exception:
        return False


def _cargar_supabase_monolito():
    response = supabase.table("medicare_db").select("datos").eq("id", 1).execute()
    if response.data:
        return response.data[0]["datos"]
    return None


def _cargar_supabase_tenant(tenant_key: str):
    r = (
        supabase.table("medicare_db")
        .select("datos")
        .eq("tenant_key", tenant_key)
        .limit(1)
        .execute()
    )
    if r.data and len(r.data) > 0:
        return r.data[0].get("datos")
    return None


def _upsert_supabase_monolito(data: dict):
    tbl = supabase.table("medicare_db")
    try:
        tbl.upsert({"id": 1, "datos": data}, on_conflict="id").execute()
    except TypeError:
        tbl.upsert({"id": 1, "datos": data}).execute()


def _upsert_supabase_tenant(tenant_key: str, data: dict):
    tbl = supabase.table("medicare_db")
    try:
        tbl.upsert({"tenant_key": tenant_key, "datos": data}, on_conflict="tenant_key").execute()
    except TypeError:
        tbl.upsert({"tenant_key": tenant_key, "datos": data}).execute()


def cargar_datos(force=False, tenant_key=None, monolito_legacy: bool = False):
    """
    Modo clásico: un único JSON (id=1 / local_data). La app no precarga este JSON al arranque: se llama desde login/recuperación.
    Modo shard (USE_TENANT_SHARDS en secrets): una fila por tenant_key; carga bajo demanda por tenant o monolito legacy.
    - tenant_key: empresa normalizada (minúsculas) para cargar solo esa clínica.
    - monolito_legacy: fuerza fila id=1 (usuario admin de emergencia y operación global legacy).
    """
    cache_key = "_db_cache"
    shard = modo_shard_activo()

    if shard and not monolito_legacy and not tenant_key:
        if not force and cache_key in st.session_state:
            return copy.deepcopy(st.session_state[cache_key])
        return None

    if not force and cache_key in st.session_state:
        return copy.deepcopy(st.session_state[cache_key])

    tk = tenant_key_normalizado(tenant_key) if tenant_key else ""

    if supabase is None:
        st.session_state["_modo_offline"] = True
        if shard and tk and not monolito_legacy:
            data_local = _cargar_local_tenant(tk)
        else:
            data_local = _cargar_local()
        if data_local:
            st.session_state[cache_key] = copy.deepcopy(data_local)
            payload_serializado = json.dumps(data_local, sort_keys=True, default=str, ensure_ascii=False)
            st.session_state["_db_cache_hash"] = hashlib.md5(payload_serializado.encode("utf-8")).hexdigest()
            if _payload_muy_grande(payload_serializado):
                log_event("db", f"payload_grande_local:{len(payload_serializado)}")
        return copy.deepcopy(data_local) if data_local else None

    try:
        if shard and tk and not monolito_legacy:
            data = _cargar_supabase_tenant(tk)
        else:
            data = _cargar_supabase_monolito()

        if data is not None:
            st.session_state[cache_key] = copy.deepcopy(data)
            payload_serializado = json.dumps(data, sort_keys=True, default=str, ensure_ascii=False)
            st.session_state["_db_cache_hash"] = hashlib.md5(payload_serializado.encode("utf-8")).hexdigest()
            st.session_state["_modo_offline"] = False
            if _payload_muy_grande(payload_serializado):
                log_event("db", f"payload_grande_nube:{len(payload_serializado)}")
            return copy.deepcopy(data)

        # Conexión OK pero sin fila en nube (tenant nuevo / vacío): reutilizar backup local si existe.
        data_local = None
        if shard and tk and not monolito_legacy:
            data_local = _cargar_local_tenant(tk)
        if data_local is None:
            data_local = _cargar_local()
        if data_local:
            st.session_state[cache_key] = copy.deepcopy(data_local)
            payload_serializado = json.dumps(data_local, sort_keys=True, default=str, ensure_ascii=False)
            st.session_state["_db_cache_hash"] = hashlib.md5(payload_serializado.encode("utf-8")).hexdigest()
            st.session_state["_modo_offline"] = True
            return copy.deepcopy(data_local)
    except Exception as e:
        log_event("db", f"supabase_unavailable:{type(e).__name__}")
        data_local = None
        if shard and tk and not monolito_legacy:
            data_local = _cargar_local_tenant(tk)
        if data_local is None:
            data_local = _cargar_local()
        if data_local:
            st.session_state[cache_key] = copy.deepcopy(data_local)
            payload_serializado = json.dumps(data_local, sort_keys=True, default=str, ensure_ascii=False)
            st.session_state["_db_cache_hash"] = hashlib.md5(payload_serializado.encode("utf-8")).hexdigest()
        st.session_state["_modo_offline"] = True
        if not st.session_state.get("_aviso_offline_mostrado"):
            st.warning(
                "Modo local activo: no se pudo conectar a la nube. "
                f"Detalle técnico: {type(e).__name__}. Los datos locales se siguen usando si existen."
            )
            st.session_state["_aviso_offline_mostrado"] = True
        return copy.deepcopy(data_local) if data_local else None
    return None


def guardar_datos():
    """Anticolapso: un fallo inesperado no debe dejar la app sin mensaje claro."""
    try:
        _guardar_datos_ejecutar()
    except Exception as e:
        log_event("db", f"guardar_datos_fatal:{type(e).__name__}")
        st.error(
            "Error inesperado al guardar. Los datos en pantalla no se borraron; "
            "reintentá el guardado o recargá la pagina si el problema continua."
        )


def _guardar_datos_ejecutar():
    claves = _db_keys()
    data = {k: st.session_state[k] for k in claves if k in st.session_state}
    payload_serializado = json.dumps(data, sort_keys=True, default=str, ensure_ascii=False)
    payload_hash = hashlib.md5(payload_serializado.encode("utf-8")).hexdigest()

    if st.session_state.get("_db_cache_hash") == payload_hash:
        _registrar_estado_guardado("sin_cambios", "No habia cambios pendientes.", guardado_nube=supabase is not None, guardado_local=True)
        return

    if _payload_muy_grande(payload_serializado):
        log_event("db", f"guardado_payload_grande:{len(payload_serializado)}")
        if not st.session_state.get("_mc_aviso_payload_grande"):
            st.session_state["_mc_aviso_payload_grande"] = True
            st.warning(
                "El volumen de datos de esta sesión es muy grande. "
                "Conviene activar **USE_TENANT_SHARDS** (una fila por clínica) y migrar datos; "
                "si no, el navegador o Supabase pueden volverse lentos o fallar."
            )

    shard = modo_shard_activo()
    guardado_nube = False
    error_nube = ""
    if supabase is not None:
        try:
            if shard and not sesion_usa_monolito_legacy():
                u = st.session_state.get("u_actual") or {}
                tk = tenant_key_normalizado(str(u.get("empresa", "") or ""))
                if not tk:
                    st.error("No se puede guardar: falta empresa en la sesión (reiniciá sesión).")
                    return
                _upsert_supabase_tenant(tk, data)
            else:
                _upsert_supabase_monolito(data)
            guardado_nube = True
            st.session_state["_modo_offline"] = False
        except Exception as e:
            error_nube = str(e)
            st.session_state["_modo_offline"] = True
            if not st.session_state.get("_aviso_offline_mostrado"):
                st.warning(f"No se pudo subir a la nube. Se guardara localmente ({e}).")
                st.session_state["_aviso_offline_mostrado"] = True

    guardado_local = False
    if shard and not sesion_usa_monolito_legacy():
        u = st.session_state.get("u_actual") or {}
        tk = tenant_key_normalizado(str(u.get("empresa", "") or ""))
        if tk:
            guardado_local = _guardar_local_tenant(tk, data)
    else:
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
