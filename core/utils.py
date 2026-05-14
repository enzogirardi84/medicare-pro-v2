from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import unicodedata
from datetime import datetime
from pathlib import Path

import pytz
import streamlit as st

from core.norm_empresa import norm_empresa_key
from core.password_crypto import (
    aplicar_hash_tras_login_ok as _aplicar_hash,
    parece_hash_bcrypt as _parece_hash,
    verificar_password as _verificar_password,
)


def password_requiere_migracion(pass_plain: str | None) -> bool:
    s = str(pass_plain or "").strip()
    return bool(s) and not _parece_hash(s)


def actualizar_password_usuario(user_dict: dict, pass_plain: str) -> None:
    try:
        _aplicar_hash(user_dict, pass_plain)
    except Exception as _exc:
        from core.app_logging import log_event
        log_event("utils", f"fallo_actualizar_password:{type(_exc).__name__}")


def _password_bytes(password: str) -> bytes:
    return _password_normalizado(password).encode("utf-8")


def _parsear_hash_pbkdf2(valor: str) -> tuple[int, str, str] | None:
    texto = str(valor or "").strip()
    if not texto.startswith(f"{PASSWORD_HASH_PREFIX}$"):
        return None
    partes = texto.split("$", 3)
    if len(partes) != 4:
        return None
    _, iteraciones_txt, salt, digest = partes
    try:
        iteraciones = int(iteraciones_txt)
    except Exception:
        return None
    if iteraciones <= 0 or not salt or not digest:
        return None
    return iteraciones, salt, digest


def generar_hash_password(password: str, *, salt: str | None = None, iteraciones: int | None = None) -> str:
    """
    Compatibilidad legacy para imports viejos/tests.

    Genera un hash PBKDF2-SHA256 autocontenido:
    `pbkdf2_sha256$iteraciones$salt$hex_digest`
    """
    salt_final = str(salt or secrets.token_hex(16)).strip()
    iter_final = int(iteraciones or PASSWORD_HASH_ITERATIONS)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        _password_bytes(password),
        salt_final.encode("utf-8"),
        iter_final,
    ).hex()
    return f"{PASSWORD_HASH_PREFIX}${iter_final}${salt_final}${digest}"


def validar_password_guardado(almacenado: str, password_ingresado: str) -> bool:
    """
    Compatibilidad legacy para imports viejos/tests.

    Acepta:
    - PBKDF2 legacy generado por `generar_hash_password`
    - bcrypt / texto plano mediante la verificación actual del sistema
    """
    parsed = _parsear_hash_pbkdf2(almacenado)
    if parsed is not None:
        iteraciones, salt, digest_guardado = parsed
        digest_actual = hashlib.pbkdf2_hmac(
            "sha256",
            _password_bytes(password_ingresado),
            salt.encode("utf-8"),
            iteraciones,
        ).hex()
        return hmac.compare_digest(digest_guardado, digest_actual)
    return _verificar_password(password_ingresado, almacenado)

ARG_TZ = pytz.timezone("America/Argentina/Buenos_Aires")
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
SESSION_KEY_MODO_LIVIANO = "modo_celular_viejo"
PASSWORD_HASH_PREFIX = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 390000

from core.utils_roles import (  # noqa: E402
    ACTION_ROLE_RULES,
    ACCIONES_PERMISO_ESTRICTO_LISTA_O_GLOBAL,
    ACCIONES_PERMISO_ESTRICTO_SIN_GLOBAL,
    LEGACY_ROLE_TO_PROFILE,
    MODULO_ALIAS,
    PERMISOS_MODULOS,
    ROLES_BYPASS_PERMISOS,
    ROLES_GLOBAL_DATOS_MULTICLINICA,
    actor_puede_modificar_usuario_equipo,
    bloqueo_autoservicio_suspension_baja,
    clave_menu_usuario,
    compactar_etiqueta_paciente,
    descripcion_acceso_rol,
    empresas_clinica_coinciden,
    es_control_total,
    filtrar_registros_empresa,
    inferir_perfil_profesional,
    mi_equipo_actor_es_superadmin,
    mi_equipo_coordinador_puede_eliminar_objetivo,
    mi_equipo_mostrar_ui_eliminar,
    mi_equipo_mostrar_ui_suspender,
    normalizar_usuario_sistema,
    obtener_modulos_permitidos,
    puede_accion,
    puede_eliminar_cuenta_equipo,
    puede_suspender_reactivar_usuario_mi_equipo,
    rol_ve_datos_todas_las_clinicas,
    tiene_permiso,
    _texto_normalizado,
    _roles_usuario_para_filtrado,
    _modulo_canonico,
)
from core.utils_pacientes import (  # noqa: E402
    asegurar_detalles_pacientes_en_sesion,
    estado_pacientes_sql,
    limpiar_estado_ui_paciente,
    mapa_detalles_pacientes,
    obtener_alertas_clinicas,
    obtener_pacientes_visibles,
    obtener_profesionales_visibles,
    registrar_estado_pacientes_sql,
    set_paciente_actual,
)
from core.utils_fechas import (  # noqa: E402
    ahora,
    calcular_estado_agenda,
    calcular_velocidad_ml_h,
    extraer_frecuencia_desde_indicacion,
    format_horarios_receta,
    generar_plan_escalonado_ml_h,
    horarios_programados_desde_frecuencia,
    normalizar_hora_texto,
    obtener_horarios_receta,
    parse_agenda_datetime,
    parse_fecha_hora,
    parse_horarios_programados,
)
from core.utils_ui import (  # noqa: E402
    cargar_json_asset,
    cargar_texto_asset,
    firma_a_base64,
    limite_archivo_mb,
    modo_celular_viejo_activo,
    mostrar_dataframe_con_scroll,
    obtener_config_firma,
    obtener_direccion_real,
    optimizar_imagen_bytes,
    preparar_imagen_clinica_bytes,
    seleccionar_limite_registros,
    validar_archivo_bytes,
    valor_por_modo_liviano,
)
MAX_RAW_IMAGE_UPLOAD_MB = 20


def decodificar_base64_seguro(valor: str) -> bytes:
    import base64
    try:
        return base64.b64decode(valor) if valor else b""
    except Exception:
        return b""


DEFAULT_ADMIN_USER = {
    "pass": None,  # Removed hardcoded password - use SUPERADMIN_EMERGENCY_PASSWORD from secrets
    "rol": "SuperAdmin",
    "nombre": "Enzo Girardi",
    "empresa": "SISTEMAS E.G.",
    "matricula": "M.P 21947",
    "dni": "37108100",
    "titulo": "Director de Sistemas",
    "perfil_profesional": "Direccion",
}


def validar_dni(dni: str) -> tuple[bool, str]:
    """
    Valida un DNI argentino.
    Retorna (valido, mensaje_error).
    """
    if not dni:
        return False, "El DNI es obligatorio"
    dni_limpio = str(dni).strip().replace(".", "").replace("-", "").replace(" ", "")
    if not dni_limpio.isdigit():
        return False, "El DNI debe contener solo números"
    if len(dni_limpio) < 7 or len(dni_limpio) > 8:
        return False, "El DNI debe tener entre 7 y 8 dígitos"
    if dni_limpio == "00000000" or dni_limpio == "0000000":
        return False, "DNI inválido"
    return True, ""


def validar_email(email: str) -> tuple[bool, str]:
    """
    Valida un email.
    Retorna (valido, mensaje_error).
    """
    if not email:
        return False, "El email es obligatorio"
    email = str(email).strip()
    patron = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(patron, email):
        return False, "Formato de email inválido"
    return True, ""


def validar_telefono(telefono: str) -> tuple[bool, str]:
    """
    Valida un teléfono argentino.
    Retorna (valido, mensaje_error).
    """
    if not telefono:
        return True, ""  # Telefono opcional
    tel_limpio = str(telefono).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not tel_limpio.isdigit():
        return False, "El teléfono debe contener solo números"
    if len(tel_limpio) < 8 or len(tel_limpio) > 15:
        return False, "El teléfono debe tener entre 8 y 15 dígitos"
    return True, ""


def validar_texto_obligatorio(texto: str, nombre_campo: str, min_len: int = 2) -> tuple[bool, str]:
    """
    Valida un campo de texto obligatorio.
    Retorna (valido, mensaje_error).
    """
    if not texto or not str(texto).strip():
        return False, f"{nombre_campo} es obligatorio"
    if len(str(texto).strip()) < min_len:
        return False, f"{nombre_campo} debe tener al menos {min_len} caracteres"
    return True, ""


def obtener_emergency_password() -> str | None:
    """
    Obtiene la contraseña de emergencia desde secrets.toml (SUPERADMIN_EMERGENCY_PASSWORD).
    Retorna None si no está configurada, deshabilitando el login de emergencia.
    """
    try:
        pwd = st.secrets.get("SUPERADMIN_EMERGENCY_PASSWORD", None)
        if pwd and str(pwd).strip():
            return str(pwd).strip()
    except Exception as _exc:
        from core.app_logging import log_event
        log_event("utils", f"fallo_secrets_emergency_password:{type(_exc).__name__}")
    return None

# Logins que pueden usar la SUPERADMIN_EMERGENCY_PASSWORD desde secrets si el hash en base no coincide (recuperación).
EMERGENCY_SUPERADMIN_LOGINS = frozenset({"admin"})


def logins_clave_default_superadmin() -> frozenset[str]:
    """
    Usernames normalizados (minúsculas) admitidos para login de emergencia con DEFAULT_ADMIN_USER['pass'].
    Incluye siempre admin y enzogirardi; opcional en secrets: SUPERADMIN_EMERGENCY_LOGINS_EXTRA (lista TOML o CSV).
    """
    s = set(EMERGENCY_SUPERADMIN_LOGINS)
    try:
        raw = st.secrets.get("SUPERADMIN_EMERGENCY_LOGINS_EXTRA", None)
    except Exception:
        return frozenset(s)
    if raw is None:
        return frozenset(s)
    if isinstance(raw, (list, tuple)):
        s.update(str(x).strip().lower() for x in raw if str(x).strip())
    else:
        txt = str(raw).replace(";", ",")
        s.update(x.strip().lower() for x in txt.split(",") if x.strip())
    return frozenset(s)


def _password_normalizado(password: str | None) -> str:
    """Normaliza una contraseña: strip y fallback a vacío."""
    return str(password or "").strip()


def obtener_password_usuario(data: dict | None) -> str:
    """Extrae la contraseña de un dict usuario probando varias claves."""
    if not isinstance(data, dict):
        return ""
    for clave in ("pass", "password", "clave", "contrasena", "contraseña"):
        valor = str(data.get(clave, "") or "").strip()
        if valor:
            return valor
    return ""


def obtener_pin_usuario(data: dict | None) -> str:
    """Extrae el PIN de un dict usuario probando varias claves."""
    if not isinstance(data, dict):
        return ""
    for clave in ("pin", "ping", "codigo_pin", "codigo"):
        valor = str(data.get(clave, "") or "").strip()
        if valor:
            return valor
    return ""


def obtener_email_usuario(data: dict | None) -> str:
    """Extrae el email de un dict usuario probando varias claves."""
    if not isinstance(data, dict):
        return ""
    for clave in ("email", "mail", "correo", "correo_verificacion", "correo_recuperacion"):
        valor = str(data.get(clave, "") or "").strip().lower()
        if valor:
            return valor
    return ""


def construir_registro_auditoria_legal(
    tipo_evento: str,
    paciente: str,
    accion: str,
    actor: str,
    matricula: str = "",
    detalle: str = "",
    referencia: str = "",
    extra: dict | None = None,
    empresa: str = "",
    usuario: dict | None = None,
    modulo: str = "",
    criticidad: str = "media",
    fecha_evento: datetime | None = None,
) -> dict:
    extra = dict(extra or {})
    usuario = normalizar_usuario_sistema(usuario or {}) if isinstance(usuario, dict) else {}
    fecha_evento = fecha_evento or ahora()
    actor_nombre = str(actor or usuario.get("nombre") or "Sistema").strip()
    actor_login = str(extra.pop("actor_login", usuario.get("usuario_login", "")) or "").strip().lower()
    actor_rol = str(extra.pop("actor_rol", usuario.get("rol", "")) or "").strip()
    actor_perfil = str(extra.pop("actor_perfil", usuario.get("perfil_profesional", inferir_perfil_profesional(usuario))) or "").strip()
    actor_empresa = str(extra.pop("actor_empresa", usuario.get("empresa", "")) or "").strip()
    modulo_registro = str(extra.pop("modulo", modulo or tipo_evento or "General") or "General").strip()
    criticidad_registro = str(extra.pop("criticidad", criticidad or "media") or "media").strip().lower()
    registro = {
        "audit_id": extra.pop("audit_id", f"AUD-{fecha_evento.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4).upper()}"),
        "fecha": fecha_evento.strftime("%d/%m/%Y %H:%M:%S"),
        "fecha_iso": fecha_evento.isoformat(timespec="seconds"),
        "tipo_evento": str(tipo_evento or "").strip(),
        "modulo": modulo_registro,
        "criticidad": criticidad_registro,
        "paciente": str(paciente or "").strip(),
        "accion": str(accion or "").strip(),
        "actor": actor_nombre,
        "actor_login": actor_login,
        "actor_rol": actor_rol,
        "actor_perfil": actor_perfil,
        "actor_empresa": actor_empresa,
        "matricula": str(matricula or usuario.get("matricula", "")) or "",
        "detalle": str(detalle or "").strip(),
        "referencia": str(referencia or "").strip(),
        "empresa": str(empresa or "").strip(),
    }
    for clave, valor in extra.items():
        if valor in (None, "", [], {}):
            continue
        registro[clave] = valor
    return registro


def registrar_auditoria_legal(
    tipo_evento: str,
    paciente: str,
    accion: str,
    actor: str,
    matricula: str = "",
    detalle: str = "",
    referencia: str = "",
    extra: dict | None = None,
    empresa: str | None = None,
    usuario: dict | None = None,
    modulo: str = "",
    criticidad: str = "media",
) -> None:
    extra = dict(extra or {})
    usuario_ctx = usuario if isinstance(usuario, dict) else st.session_state.get("user", {})
    if empresa is None:
        detalles = mapa_detalles_pacientes(st.session_state).get(paciente, {})
        empresa = detalles.get("empresa") or usuario_ctx.get("empresa", "")
    try:
        from core.db_sql import insert_auditoria
        from core.nextgen_sync import _obtener_uuid_empresa, _obtener_uuid_paciente
        empresa_uuid = _obtener_uuid_empresa(empresa)
        paciente_uuid = None
        if empresa_uuid and paciente:
            paciente_txt = str(paciente or "").strip()
            dni_paciente = paciente_txt.rsplit(" - ", 1)[-1].strip() if " - " in paciente_txt else ""
            if dni_paciente:
                paciente_uuid = _obtener_uuid_paciente(dni_paciente, empresa_uuid)
        if empresa_uuid:
            datos_sql = {
                "empresa_id": empresa_uuid,
                "paciente_id": paciente_uuid,
                "fecha_evento": ahora().isoformat(),
                "modulo": modulo or tipo_evento,
                "accion": accion,
                "detalle": detalle,
                "usuario_id": None,
            }
            insert_auditoria(datos_sql)
    except Exception as e:
        from core.app_logging import log_event
        log_event("error_auditoria_sql", str(e))
    st.session_state.setdefault("auditoria_legal_db", [])
    st.session_state["auditoria_legal_db"].append(
        construir_registro_auditoria_legal(
            tipo_evento=tipo_evento, paciente=paciente, accion=accion, actor=actor,
            matricula=matricula, detalle=detalle, referencia=referencia, extra=extra,
            empresa=empresa or "", usuario=usuario_ctx, modulo=modulo, criticidad=criticidad,
        )
    )
    from core.database import _trim_db_list
    _trim_db_list("auditoria_legal_db", 1000)


def asegurar_usuarios_base(solo_normalizar: bool = False) -> None:
    st.session_state.setdefault("usuarios_db", {})
    if not solo_normalizar:
        if "admin" not in st.session_state["usuarios_db"]:
            st.session_state["usuarios_db"]["admin"] = DEFAULT_ADMIN_USER.copy()
        else:
            combinado = DEFAULT_ADMIN_USER.copy()
            combinado.update(st.session_state["usuarios_db"]["admin"])
            st.session_state["usuarios_db"]["admin"] = combinado
    for login, datos in list(st.session_state["usuarios_db"].items()):
        if not isinstance(datos, dict):
            continue
        usuario_normalizado = normalizar_usuario_sistema(datos)
        usuario_normalizado.setdefault("usuario_login", login)
        if password_requiere_migracion(usuario_normalizado.get("pass")):
            actualizar_password_usuario(usuario_normalizado, usuario_normalizado.get("pass"))
        st.session_state["usuarios_db"][login] = usuario_normalizado


def inicializar_db_state(db: dict | None, precargar_usuario_admin_emergencia: bool = True) -> None:
    if "db_inicializada" not in st.session_state:
        claves_base = {
            "usuarios_db": {"admin": DEFAULT_ADMIN_USER.copy()},
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
        }
        if db is not None:
            for k, v in db.items():
                st.session_state[k] = v
            for k, v in claves_base.items():
                if k not in st.session_state:
                    st.session_state[k] = v
        else:
            for k, v in claves_base.items():
                st.session_state[k] = v
            if not precargar_usuario_admin_emergencia:
                st.session_state["usuarios_db"] = {}
        if precargar_usuario_admin_emergencia:
            asegurar_usuarios_base()
        else:
            asegurar_usuarios_base(solo_normalizar=True)
        try:
            from core.clinicas_control import sincronizar_clinicas_desde_datos

            sincronizar_clinicas_desde_datos(st.session_state)
        except Exception as _exc:
            from core.app_logging import log_event
            log_event("utils", f"fallo_sincronizar_clinicas:{type(_exc).__name__}:{_exc}")
        st.session_state["db_inicializada"] = True
