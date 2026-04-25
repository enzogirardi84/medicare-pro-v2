from __future__ import annotations

import copy
import hashlib
import time
from contextlib import nullcontext
from typing import Any, Optional

import streamlit as st

from core.app_logging import log_event
from core.db_serialize import dumps_db_sorted, loads_db_payload, loads_json_any
from core.norm_empresa import norm_empresa_key
from core._database_local import (
    LOCAL_DB_PATH,
    _cargar_local,
    _cargar_local_tenant,
    _guardar_local,
    _guardar_local_tenant,
    _tenant_local_fs_key,
)
from core._database_supabase import (
    PAYLOAD_ALERTA_BYTES,
    _cargar_supabase_monolito,
    _cargar_supabase_tenant,
    _fijar_cache_y_hash,
    _payload_muy_grande,
    _supabase_execute_with_retry,
    _upsert_supabase_monolito,
    _upsert_supabase_tenant,
    init_supabase,
    supabase,
)


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
    if s in logins_monolito_allowlist():
        return True
    try:
        from core.utils import EMERGENCY_SUPERADMIN_LOGINS

        return s in EMERGENCY_SUPERADMIN_LOGINS
    except Exception:
        return False


def tenant_key_normalizado(empresa: str) -> str:
    return norm_empresa_key(empresa) or ""




def sesion_usa_monolito_legacy() -> bool:
    return bool(st.session_state.get("_db_monolito_sesion"))


# Colecciones que deben ser dict en sesión (el resto, list).
_DB_KEYS_DICT = frozenset(
    {"usuarios_db", "detalles_pacientes_db", "plantillas_whatsapp_db", "clinicas_db"}
)


def _normalizar_blob_datos(data: Any) -> dict | None:
    """
    Supabase / backup local pueden devolver None, dict, o en casos raros string JSON.
    Cualquier otro tipo (lista vacía como raíz, número) se trata como inválido para no tumbar la app.
    Retorna dict normalizado o None si no es válido.
    """
    if data is None:
        return None
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        s = data.strip()
        if not s:
            return None
        try:
            parsed = loads_json_any(s)
        except Exception:
            log_event("db", "blob_datos_json_invalido")
            return None
        if isinstance(parsed, dict):
            return parsed
        log_event("db", f"blob_datos_raiz_no_dict:{type(parsed).__name__}")
        return None
    log_event("db", f"blob_datos_tipo_inesperado:{type(data).__name__}")
    return None


def _coleccion_db_tipo_valido(key: str, value: Any) -> bool:
    if key in _DB_KEYS_DICT:
        return isinstance(value, dict)
    return isinstance(value, list)


def _estructura_vacia_por_clave() -> dict[str, dict | list]:
    """Plantilla de estructuras vacías por clave de base de datos."""
    return {
        "usuarios_db": {},
        "pacientes_db": [],
        "detalles_pacientes_db": {},
        "turnos_db": [],
        "logs_db": [],
        "fotos_heridas_db": [],
        "agenda_db": [],
        "nomenclador_db": [],
        "firmas_tactiles_db": [],
        "reportes_diarios_db": [],
        "estudios_db": [],
        "profesionales_red_db": [],
        "solicitudes_servicios_db": [],
        "plantillas_whatsapp_db": {},
        "clinicas_db": {},
        # Datos clinicos criticos
        "evoluciones_db": [],
        "vitales_db": [],
        "indicaciones_db": [],
        "cuidados_enfermeria_db": [],
        "inventario_db": [],
        "facturacion_db": [],
        "administracion_med_db": [],
        "auditoria_legal_db": [],
        # Claves adicionales de modulos
        "consumos_db": [],
        "checkin_db": [],
        "balance_db": [],
        "consentimientos_db": [],
        "pediatria_db": [],
        "escalas_clinicas_db": [],
        "emergencias_db": [],
        "diagnosticos_db": [],
    }


def _coleccion_fresca_como(default: Any) -> Any:
    """Plantilla solo usa dict/list vacíos; evita deepcopy en el camino caliente."""
    if isinstance(default, dict):
        return {}
    if isinstance(default, list):
        return []
    return copy.deepcopy(default)


def completar_claves_db_session() -> None:
    """Rellena colecciones faltantes y corrige tipos inválidos (shards viejos o JSON parcial por tenant)."""
    plantilla = _estructura_vacia_por_clave()
    for k, default in plantilla.items():
        if k not in st.session_state:
            st.session_state[k] = _coleccion_fresca_como(default)
            continue
        if not _coleccion_db_tipo_valido(k, st.session_state[k]):
            st.session_state[k] = _coleccion_fresca_como(default)
            
        # NOTA: No se borran datos clinicos de la sesion.
        # La limpieza de RAM selectiva fue desactivada porque borraba
        # evoluciones_db, vitales_db, etc. antes de guardar, causando perdida de datos.


def _registrar_estado_guardado(estado: str, detalle: str = "", guardado_nube: bool = False, guardado_local: bool = False) -> None:
    st.session_state["_ultimo_guardado_estado"] = estado
    st.session_state["_ultimo_guardado_detalle"] = str(detalle or "").strip()
    st.session_state["_ultimo_guardado_ts"] = time.time()
    st.session_state["_ultimo_guardado_nube"] = bool(guardado_nube)
    st.session_state["_ultimo_guardado_local"] = bool(guardado_local)


def obtener_estado_guardado() -> dict[str, Any]:
    """Retorna el estado del último guardado como dict."""
    return {
        "estado": st.session_state.get("_ultimo_guardado_estado", ""),
        "detalle": st.session_state.get("_ultimo_guardado_detalle", ""),
        "timestamp": st.session_state.get("_ultimo_guardado_ts"),
        "guardado_nube": bool(st.session_state.get("_ultimo_guardado_nube", False)),
        "guardado_local": bool(st.session_state.get("_ultimo_guardado_local", False)),
    }


def procesar_guardado_pendiente() -> bool:
    """
    Flush silencioso para guardados agrupados por ráfaga.
    Se llama en cada rerun de la app ya logueada.
    """
    if not st.session_state.get("_guardar_datos_pendiente"):
        return False
    try:
        from core.feature_flags import GUARDAR_DATOS_MIN_INTERVALO_SEGUNDOS

        min_intervalo = float(GUARDAR_DATOS_MIN_INTERVALO_SEGUNDOS or 0)
    except Exception:
        min_intervalo = 0.0
    if min_intervalo <= 0:
        return False

    ultimo = float(st.session_state.get("_guardar_datos_ultimo_intento_ts", 0.0) or 0.0)
    if ultimo > 0 and (time.monotonic() - ultimo) < min_intervalo:
        return False
    st.session_state["_guardar_datos_pendiente"] = False
    try:
        guardar_datos(spinner=False, force=True)
    except Exception as e:
        log_event("db", f"procesar_guardado_pendiente_error:{type(e).__name__}")
    return True


def _db_keys():
    return [
        "usuarios_db",
        "pacientes_db",
        "detalles_pacientes_db",
        "turnos_db",
        "logs_db",
        "fotos_heridas_db",
        "agenda_db",
        "nomenclador_db",
        "firmas_tactiles_db",
        "reportes_diarios_db",
        "estudios_db",
        "profesionales_red_db",
        "solicitudes_servicios_db",
        "plantillas_whatsapp_db",
        "clinicas_db",
        # Datos clinicos criticos - deben guardarse en Supabase
        "evoluciones_db",
        "vitales_db",
        "indicaciones_db",
        "cuidados_enfermeria_db",
        "inventario_db",
        "facturacion_db",
        "administracion_med_db",
        "auditoria_legal_db",
        # Claves adicionales de modulos
        "consumos_db",
        "checkin_db",
        "balance_db",
        "consentimientos_db",
        "pediatria_db",
        "escalas_clinicas_db",
        "emergencias_db",
        "diagnosticos_db",
    ]


def get_cache_size_estimate() -> int:
    """Estima el tamaño de cache en numero de claves relevantes."""
    keys = 0
    for k in st.session_state.keys():
        if k.startswith("_db_cache") or k.startswith("_mc_cache_"):
            keys += 1
    return keys


def should_cleanup_cache() -> bool:
    """Determina si hay que limpiar caches grandes basandose en la cantidad de entradas."""
    return get_cache_size_estimate() > 50


def limpiar_cache_app() -> int:
    """Limpia caches grandes para liberar memoria (L1 y L2). Retorna total limpiadas."""
    total = 0
    # Limpiar cache principal
    for k in ("_db_cache", "_db_cache_hash", "_db_cache_ts"):
        if st.session_state.pop(k, None) is not None:
            total += 1
    # Limpiar caches por prefijo
    prefixes = ("_mc_cache_pac_", "_mc_cache_alertas_", "_mc_cache_cons_", "_mc_cache_vit_")
    for key in list(st.session_state.keys()):
        if any(key.startswith(p) for p in prefixes):
            st.session_state.pop(key, None)
            total += 1
    # Clear any general historial/pdf caches si existen
    for key in list(st.session_state.keys()):
        if key.startswith("historial_") or key.startswith("_pdf_"):
            st.session_state.pop(key, None)
            total += 1
    import gc
    gc.collect()
    return total


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

def cargar_datos(force: bool = False, tenant_key: str | None = None, monolito_legacy: bool = False) -> dict | None:
    """
    Modo clásico: un único JSON (id=1 / local_data). La app no precarga este JSON al arranque: se llama desde login/recuperación.
    Modo shard (USE_TENANT_SHARDS en secrets): una fila por tenant_key; carga bajo demanda por tenant o monolito legacy.
    - tenant_key: empresa normalizada (minúsculas) para cargar solo esa clínica.
    - monolito_legacy: fuerza fila id=1 (usuario admin de emergencia y operación global legacy).
    """
    # LIMPIEZA: si hay demasiadas claves de cache, limpiar
    if should_cleanup_cache():
        if "_db_cache" in st.session_state:
            # Si hay cache activo y piden FORCAR, guardar ANTES de borrar
            # (lógica existente de guardar_datos si hay cambios...)
            pass
        limpiar_cache_app()
    
    t0 = time.monotonic()
    ok = True
    cache_key = "_db_cache"
    shard = modo_shard_activo()
    try:
        # --- OPTIMIZACIÓN STATELESS ---
        # Si el dual-write está activo, significa que ya estamos 100% en PostgreSQL.
        # No necesitamos descargar el JSON gigante de Supabase, solo devolvemos una estructura vacía.
        try:
            from core.feature_flags import ENABLE_NEXTGEN_API_DUAL_WRITE
            if ENABLE_NEXTGEN_API_DUAL_WRITE:
                u_actual = st.session_state.get("u_actual")
                estructura = _estructura_vacia_por_clave()

                # En pantalla de login todavía no hay u_actual. Si devolvemos una
                # estructura vacía y luego se llama guardar_datos() al autenticar,
                # el monolito remoto queda pisado con listas vacías.
                if not isinstance(u_actual, dict):
                    try:
                        if supabase is not None:
                            datos_remotos_completos = _normalizar_blob_datos(_cargar_supabase_monolito())
                            if isinstance(datos_remotos_completos, dict):
                                estructura = datos_remotos_completos
                    except Exception as e:
                        log_event("db", f"error_cargar_monolito_prelogin:{e}")
                    if estructura == _estructura_vacia_por_clave():
                        try:
                            datos_locales_completos = _normalizar_blob_datos(_cargar_local())
                            if isinstance(datos_locales_completos, dict):
                                estructura = datos_locales_completos
                        except Exception as e:
                            log_event("db", f"error_cargar_local_prelogin:{e}")

                def _usuarios_validos(blob):
                    if not isinstance(blob, dict):
                        return {}
                    usuarios = blob.get("usuarios_db")
                    return usuarios if isinstance(usuarios, dict) else {}

                # 1. Usuarios: local primero, y si el servidor no tiene copia, caemos al monolito remoto.
                try:
                    if LOCAL_DB_PATH.exists():
                        usuarios_locales = _usuarios_validos(loads_json_any(LOCAL_DB_PATH.read_bytes()))
                        if usuarios_locales:
                            estructura["usuarios_db"] = usuarios_locales
                except Exception as e:
                    log_event("db", f"error_cargar_usuarios_locales:{e}")

                if not estructura["usuarios_db"] and supabase is not None:
                    try:
                        datos_remotos = _normalizar_blob_datos(_cargar_supabase_monolito())
                        usuarios_remotos = _usuarios_validos(datos_remotos)
                        if usuarios_remotos:
                            estructura["usuarios_db"] = usuarios_remotos
                    except Exception as e:
                        log_event("db", f"error_cargar_usuarios_remotos:{e}")

                from core.utils import DEFAULT_ADMIN_USER

                if "admin" not in estructura["usuarios_db"]:
                    estructura["usuarios_db"]["admin"] = DEFAULT_ADMIN_USER.copy()

                st.session_state["_modo_offline"] = False

                # 2. Pacientes: en roles globales traemos todas las clinicas; el resto sigue filtrado por empresa.
                from core.db_sql import get_pacientes_by_empresa, get_pacientes_globales, nombre_paciente_sql
                from core.nextgen_sync import _obtener_uuid_empresa

                if isinstance(u_actual, dict):
                    rol_actual = str(u_actual.get("rol", "") or "").strip().lower()
                    empresa_actual = str(u_actual.get("empresa", "") or "").strip()
                    empresa_map = {}
                    pacs_sql = []

                    try:
                        if rol_actual in {"superadmin", "admin"} and supabase is not None:
                            empresas_res = _supabase_execute_with_retry(
                                "get_empresas_dualwrite",
                                lambda: supabase.table("empresas").select("id,nombre").execute(),
                            )
                            empresa_map = {
                                str(item.get("id")): str(item.get("nombre", "") or "").strip()
                                for item in (empresas_res.data or [])
                                if isinstance(item, dict)
                            }
                            pacs_sql = get_pacientes_globales(limit=1000)
                        elif empresa_actual:
                            empresa_uuid = _obtener_uuid_empresa(empresa_actual)
                            if empresa_uuid:
                                pacs_sql = get_pacientes_by_empresa(empresa_uuid, incluir_altas=True)
                    except Exception as e:
                        log_event("db", f"error_cargar_pacientes_sql:{e}")
                        pacs_sql = []

                    for p in pacs_sql:
                        nombre = nombre_paciente_sql(p)
                        dni = str(p.get("dni", "") or "").strip()
                        paciente_id_visual = f"{nombre} - {dni}" if dni else nombre

                        if paciente_id_visual not in estructura["pacientes_db"]:
                            estructura["pacientes_db"].append(paciente_id_visual)

                        empresa_paciente = empresa_map.get(str(p.get("empresa_id") or ""), empresa_actual)
                        estructura["detalles_pacientes_db"][paciente_id_visual] = {
                            "dni": dni,
                            "fnac": str(p.get("fecha_nacimiento", "") or "").strip(),
                            "sexo": str(p.get("sexo", "") or "").strip(),
                            "estado": p.get("estado", "Activo"),
                            "obra_social": p.get("obra_social", ""),
                            "empresa": empresa_paciente,
                            "telefono": p.get("telefono", ""),
                            "direccion": p.get("direccion", ""),
                            "alergias": p.get("alergias", ""),
                            "patologias": p.get("patologias", ""),
                        }
                
                # Fijar el cache para evitar guardados innecesarios
                # Le pasamos la estructura completa para que calcule el hash base
                _fijar_cache_y_hash(estructura)
                
                # También marcamos que no hay guardado pendiente
                st.session_state["_guardar_datos_pendiente"] = False
                
                return estructura
        except Exception as _exc:
            from core.app_logging import log_event
            log_event("db_guardar", f"fallo_guardado_{source}:{type(_exc).__name__}:{_exc}")
        # ------------------------------

        if shard and not monolito_legacy and not tenant_key:
            if not force and cache_key in st.session_state:
                _cts = float(st.session_state.get("_db_cache_ts", 0))
                try:
                    from core.feature_flags import DB_CACHE_TTL_SEGUNDOS
                    _ttl = float(DB_CACHE_TTL_SEGUNDOS or 90)
                except Exception:
                    _ttl = 90.0
                if (time.monotonic() - _cts) < _ttl:
                    cached = st.session_state[cache_key]
                    try:
                        pb, _ = dumps_db_sorted(cached)
                        return loads_db_payload(pb)
                    except Exception:
                        return copy.deepcopy(cached)
            return None

        if not force and cache_key in st.session_state:
            # TTL: si el cache tiene menos de DB_CACHE_TTL_SEGUNDOS, usarlo directo
            _cache_ts = float(st.session_state.get("_db_cache_ts", 0))
            _cache_age = time.monotonic() - _cache_ts
            try:
                from core.feature_flags import DB_CACHE_TTL_SEGUNDOS
                ttl = float(DB_CACHE_TTL_SEGUNDOS or 90)
            except Exception:
                ttl = 90.0
            if _cache_age < ttl:
                # Fast path: orjson round-trip es ~3x mas rapido que deepcopy en dicts grandes
                cached = st.session_state[cache_key]
                try:
                    pb, _ = dumps_db_sorted(cached)
                    return loads_db_payload(pb)
                except Exception:
                    return copy.deepcopy(cached)

        tk = tenant_key_normalizado(tenant_key) if tenant_key else ""

        if supabase is None:
            st.session_state["_modo_offline"] = True
            if shard and tk and not monolito_legacy:
                data_local = _normalizar_blob_datos(_cargar_local_tenant(tk))
            else:
                data_local = _normalizar_blob_datos(_cargar_local())
            if data_local:
                pb = _fijar_cache_y_hash(data_local)
                if pb and _payload_muy_grande(pb):
                    log_event("db", f"payload_grande_local:{len(pb)}")
            return copy.deepcopy(data_local) if data_local else None

        try:
            if shard and tk and not monolito_legacy:
                data = _normalizar_blob_datos(_cargar_supabase_tenant(tk))
            else:
                data = _normalizar_blob_datos(_cargar_supabase_monolito())

            if data is not None:
                pb = _fijar_cache_y_hash(data)
                st.session_state["_modo_offline"] = False
                if pb and _payload_muy_grande(pb):
                    log_event("db", f"payload_grande_nube:{len(pb)}")
                return copy.deepcopy(data)

            # Conexión OK pero sin fila en nube (tenant nuevo / vacío): reutilizar backup local si existe.
            data_local = None
            if shard and tk and not monolito_legacy:
                data_local = _normalizar_blob_datos(_cargar_local_tenant(tk))
            if data_local is None:
                data_local = _normalizar_blob_datos(_cargar_local())
            if data_local:
                _fijar_cache_y_hash(data_local)
                st.session_state["_modo_offline"] = True
                return copy.deepcopy(data_local)
        except Exception as e:
            log_event("db", f"supabase_unavailable:{type(e).__name__}:{e!s}")
            data_local = None
            if shard and tk and not monolito_legacy:
                data_local = _normalizar_blob_datos(_cargar_local_tenant(tk))
            if data_local is None:
                data_local = _normalizar_blob_datos(_cargar_local())
            if data_local:
                _fijar_cache_y_hash(data_local)
            st.session_state["_modo_offline"] = True
            if not st.session_state.get("_aviso_offline_mostrado"):
                st.warning(
                    "Modo local: no pudimos conectar con la nube en este momento. "
                    "Si hay copia en este equipo, seguimos trabajando con ella."
                )
                with st.expander("Detalle tecnico (soporte)", expanded=False):
                    st.caption("El mensaje completo quedó registrado en los logs del servidor (si están activos).")
                    st.code(type(e).__name__, language="text")
                st.session_state["_aviso_offline_mostrado"] = True
            ok = False
            return copy.deepcopy(data_local) if data_local else None
        return None
    finally:
        try:
            from core.perf_metrics import record_perf

            record_perf("db.cargar_datos", (time.monotonic() - t0) * 1000.0, ok=ok)
        except Exception as _exc:
            from core.app_logging import log_event
            log_event("db_cargar", f"fallo_record_perf:{type(_exc).__name__}:{_exc}")


def guardar_datos(*, spinner: Optional[bool] = None, force: bool = False):
    """
    Anticolapso: un fallo inesperado no debe dejar la app sin mensaje claro.

    spinner: None = usar `GUARDAR_DATOS_SPINNER_DEFAULT` en feature_flags; False = sin spinner; True = forzar.
    """
    from core.feature_flags import GUARDAR_DATOS_MIN_INTERVALO_SEGUNDOS, GUARDAR_DATOS_SPINNER_DEFAULT, GUARDAR_DATOS_FORZAR_SIN_SPINNER

    spinner_original = GUARDAR_DATOS_SPINNER_DEFAULT if spinner is None else spinner
    mostrar = spinner_original
    if mostrar and GUARDAR_DATOS_FORZAR_SIN_SPINNER:
        mostrar = False
    # Guardados no forzados: evita ráfagas de upserts cuando hay muchos eventos seguidos.
    # Si el caller pidió spinner=True (guardado crítico), se ejecuta siempre sin throttle.
    if not force and not spinner_original:
        try:
            min_intervalo = float(GUARDAR_DATOS_MIN_INTERVALO_SEGUNDOS or 0)
        except Exception:
            min_intervalo = 0.0
        if min_intervalo > 0:
            ahora_ts = time.monotonic()
            ultimo_ts = float(st.session_state.get("_guardar_datos_ultimo_intento_ts", 0.0) or 0.0)
            if ultimo_ts > 0 and (ahora_ts - ultimo_ts) < min_intervalo:
                st.session_state["_guardar_datos_pendiente"] = True
                _registrar_estado_guardado(
                    "pendiente",
                    "Guardado en cola por rafaga; se sincroniza automaticamente en segundos.",
                    guardado_nube=supabase is not None,
                    guardado_local=True,
                )
                return
            st.session_state["_guardar_datos_ultimo_intento_ts"] = ahora_ts
    ctx = st.spinner("Guardando cambios...") if mostrar else nullcontext()
    try:
        with ctx:
            _guardar_datos_ejecutar()
    except Exception as e:
        log_event("db", f"guardar_datos_fatal:{type(e).__name__}:{e!s}")
        st.error(
            "Error inesperado al guardar. Los datos en pantalla no se vaciaron: reintenta guardar, "
            "revisa la conexion y, si sigue igual, recarga la pagina y copia el detalle tecnico para soporte."
        )
        with st.expander("Detalle tecnico (soporte)", expanded=False):
            st.caption("El detalle completo quedó en los logs del servidor.")
            st.code(type(e).__name__, language="text")


def _trim_db_list(clave_db: str, max_items: int) -> None:
    """Recorta una lista JSON en session_state a max_items (mantiene los mas recientes)."""
    lst = st.session_state.get(clave_db)
    if isinstance(lst, list) and len(lst) > max_items:
        st.session_state[clave_db] = lst[-max_items:]


def guardar_json_db(clave_db: str, payload: dict, *, spinner: bool = True, max_items: int = 500) -> None:
    """Agrega un registro al array JSON en session_state y persiste.

    Este helper reemplaza el patron repetido en todas las vistas:
        if "xxx_db" not in st.session_state or not isinstance(..., list):
            st.session_state["xxx_db"] = []
        st.session_state["xxx_db"].append(payload)
        guardar_datos(spinner=True)

    Args:
        max_items: Limite maximo de elementos en la lista (recorta los mas antiguos).
                   Usar 500 para datos clinicos, 1000 para operativos.
    """
    if clave_db not in st.session_state or not isinstance(st.session_state[clave_db], list):
        st.session_state[clave_db] = []
    st.session_state[clave_db].append(payload)
    _trim_db_list(clave_db, max_items)
    guardar_datos(spinner=spinner)


def _guardar_datos_ejecutar():
    t0 = time.monotonic()
    ok = True
    try:
        return _guardar_datos_ejecutar_core()
    except Exception:
        ok = False
        raise
    finally:
        try:
            from core.feature_flags import GUARDAR_DATOS_LOG_LENTO_SEGUNDOS

            um = float(GUARDAR_DATOS_LOG_LENTO_SEGUNDOS or 0)
            if um > 0:
                dt = time.monotonic() - t0
                if dt >= um:
                    log_event("db", f"guardar_lento:{dt:.2f}s")
        except Exception as _exc:
            import logging
            logging.getLogger("database").debug(f"fallo_log_lento:{type(_exc).__name__}")
        try:
            from core.perf_metrics import record_perf

            record_perf("db.guardar_datos", (time.monotonic() - t0) * 1000.0, ok=ok)
        except Exception as _exc:
            import logging
            logging.getLogger("database").debug(f"fallo_record_perf:{type(_exc).__name__}")


def _guardar_datos_ejecutar_core():
    _trim_logs_db_for_save()

    claves = _db_keys()
    data = {k: st.session_state[k] for k in claves if k in st.session_state}
    payload_bytes, _ = dumps_db_sorted(data)
    payload_hash = hashlib.sha256(payload_bytes).hexdigest()

    if st.session_state.get("_db_cache_hash") == payload_hash:
        st.session_state["_guardar_datos_pendiente"] = False
        _registrar_estado_guardado("sin_cambios", "No habia cambios pendientes.", guardado_nube=supabase is not None, guardado_local=True)
        return

    if _payload_muy_grande(payload_bytes):
        log_event("db", f"guardado_payload_grande:{len(payload_bytes)}")
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
            log_event("db", f"guardar_supabase:{type(e).__name__}:{e!s}")
            error_nube = type(e).__name__
            st.session_state["_modo_offline"] = True
            if not st.session_state.get("_aviso_offline_mostrado"):
                st.warning(
                    "No se pudo sincronizar con la nube. Se intento guardar en este equipo. "
                    "Revisa conexion y configuracion de Supabase si el aviso vuelve a aparecer."
                )
                with st.expander("Detalle del error (soporte)", expanded=False):
                    st.caption("El detalle completo quedó en los logs del servidor.")
                    st.code(error_nube, language="text")
                st.session_state["_aviso_offline_mostrado"] = True

    guardado_local = False
    if shard and not sesion_usa_monolito_legacy():
        u = st.session_state.get("u_actual") or {}
        tk = tenant_key_normalizado(str(u.get("empresa", "") or ""))
        if tk:
            guardado_local = _guardar_local_tenant(tk, data, payload_bytes)
    else:
        guardado_local = _guardar_local(data, payload_bytes)

    st.session_state["_db_cache"] = loads_db_payload(payload_bytes)
    st.session_state["_db_cache_hash"] = payload_hash
    st.session_state["_guardar_datos_pendiente"] = False

    if guardado_nube:
        _registrar_estado_guardado("nube", "Guardado sincronizado en la nube.", guardado_nube=True, guardado_local=guardado_local)
    elif guardado_local:
        detalle = "Guardado local activo."
        if error_nube:
            detalle = f"Guardado local (sin nube). Tipo de error: {error_nube}"
        _registrar_estado_guardado("local", detalle, guardado_nube=False, guardado_local=True)
    else:
        detalle = "No se pudo guardar ni en la nube ni en este equipo."
        if error_nube:
            detalle = f"{detalle} Error nube ({error_nube})."
        _registrar_estado_guardado("error", detalle, guardado_nube=False, guardado_local=False)

    ultimo_toast = st.session_state.get("_ultimo_toast_guardado")
    ahora_ts = time.time()
    if ultimo_toast is None or ahora_ts - ultimo_toast > 8:
        if guardado_nube:
            st.toast("Guardado exitosamente en la nube")
        elif guardado_local:
            st.toast("Guardado localmente")
        else:
            st.error(
                "No se pudo guardar en la nube ni en disco local. "
                "Revisa permisos de escritura, espacio libre y credenciales de Supabase. "
                "No cierres la pestana sin respaldar lo que necesites si el problema continua."
            )
        st.session_state["_ultimo_toast_guardado"] = ahora_ts

    return {
        "guardado_nube": guardado_nube,
        "guardado_local": guardado_local,
        "error_nube": error_nube,
    }


def _trim_logs_db_for_save() -> None:
    try:
        from core.feature_flags import MAX_LOGS_DB_ENTRIES

        max_logs = int(MAX_LOGS_DB_ENTRIES or 0)
    except Exception:
        max_logs = 0
    if max_logs <= 0:
        return
    logs = st.session_state.get("logs_db")
    if not isinstance(logs, list) or len(logs) <= max_logs:
        return
    exceso = len(logs) - max_logs
    st.session_state["logs_db"] = logs[-max_logs:]
    log_event("db", f"logs_db_trim:{exceso}")
