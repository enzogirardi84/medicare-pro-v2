import base64
import hashlib
import hmac
import json
import re
import secrets
import unicodedata
import urllib.request
from datetime import datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path

import pytz
import streamlit as st
from PIL import Image, ImageOps

# Zona horaria fija para Argentina
ARG_TZ = pytz.timezone("America/Argentina/Buenos_Aires")
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
SESSION_KEY_MODO_LIVIANO = "modo_celular_viejo"
PASSWORD_HASH_PREFIX = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 390000
MAX_RAW_IMAGE_UPLOAD_MB = 20
ROLES_BYPASS_PERMISOS = frozenset({"superadmin", "admin", "coordinador"})
# Solo estos roles omiten el filtro por empresa en listados (multiclínica real).
ROLES_GLOBAL_DATOS_MULTICLINICA = frozenset({"superadmin", "admin"})
# Eliminar / suspender usuario: lista estricta sin bypass global (Admin legacy no hereda suspender).
ACCIONES_PERMISO_ESTRICTO_SIN_GLOBAL = frozenset({"equipo_eliminar_usuario", "equipo_cambiar_estado"})
# Alta y edicion de mail: SuperAdmin/Admin global o Coordinador en lista.
ACCIONES_PERMISO_ESTRICTO_LISTA_O_GLOBAL = frozenset({"equipo_crear_usuario", "equipo_editar_email_usuario"})
LEGACY_ROLE_TO_PROFILE = {
    "medico": "Medico",
    "enfermeria": "Enfermeria",
    "operativo": "Operativo",
    "auditoria": "Administrativo",
}


DEFAULT_ADMIN_USER = {
    "pass": None,  # Removed hardcoded password - use SUPERADMIN_EMERGENCY_PASSWORD from secrets
    "rol": "SuperAdmin",
    "nombre": "Enzo Girardi",
    "empresa": "SISTEMAS E.G.",
    "matricula": "M.P 21947",
    "dni": "37108100",
    "titulo": "Director de Sistemas",
    "perfil_profesional": "Direccion",
    "estado": "Activo",
    "pin": "1234",
}


def obtener_emergency_password() -> str | None:
    """
    Obtiene la contraseña de emergencia desde secrets.toml (SUPERADMIN_EMERGENCY_PASSWORD).
    Retorna None si no está configurada, deshabilitando el login de emergencia.
    """
    try:
        pwd = st.secrets.get("SUPERADMIN_EMERGENCY_PASSWORD", None)
        if pwd and str(pwd).strip():
            return str(pwd).strip()
    except Exception:
        pass
    return None

# Logins que pueden usar la SUPERADMIN_EMERGENCY_PASSWORD desde secrets si el hash en base no coincide (recuperación).
EMERGENCY_SUPERADMIN_LOGINS = frozenset({"admin", "enzogirardi"})


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


ACTION_ROLE_RULES = {
    "recetas_prescribir": ["Medico"],
    "recetas_cargar_papel": ["Operativo", "Enfermeria", "Medico"],
    "recetas_registrar_dosis": ["Operativo", "Enfermeria", "Medico"],
    "recetas_cambiar_estado": ["Medico"],
    "pdf_exportar_historia": ["Operativo", "Enfermeria", "Medico", "Auditoria"],
    "pdf_exportar_excel": ["Operativo", "Auditoria"],
    "pdf_exportar_respaldo": ["Operativo", "Enfermeria", "Medico", "Auditoria"],
    "pdf_guardar_consentimiento": ["Operativo", "Enfermeria", "Medico"],
    "pdf_descargar_consentimiento": ["Operativo", "Enfermeria", "Medico", "Auditoria"],
    "evolucion_registrar": ["Operativo", "Enfermeria", "Medico"],
    "evolucion_borrar": ["Medico"],
    "estudios_registrar": ["Operativo", "Enfermeria", "Medico"],
    "estudios_borrar": ["Medico"],
    "equipo_crear_usuario": ["Coordinador"],
    "equipo_cambiar_estado": ["SuperAdmin"],
    "equipo_editar_email_usuario": ["Coordinador"],
    "equipo_eliminar_usuario": ["SuperAdmin", "Coordinador"],
}

MODULO_ALIAS = {
    "Visitas": "Visitas y Agenda",
    "Red": "Red de Profesionales",
    "Emergencias": "Emergencias y Ambulancia",
    "Escalas": "Escalas Clinicas",
    "Cierre": "Cierre Diario",
    "Equipo": "Mi Equipo",
    "Asistencia": "Asistencia en Vivo",
    "RRHH": "RRHH y Fichajes",
    "Legal": "Auditoria Legal",
}

PERMISOS_MODULOS = {
    # Perfil asistencial (Medico, Enfermeria, Operativo): menu acotado a lo clinico.
    "operativo_clinico": [
        "Visitas",
        "Admision",
        "Clinica",
        "Pediatria",
        "Evolucion",
        "Estudios",
        "Materiales",
        "Recetas",
        "Balance",
        "Emergencias",
        "Escalas",
        "Historial",
        "PDF",
        "Telemedicina",
        "Cierre",
    ],
    # Perfil de gestion (Administrativo, Coordinacion, Direccion en ficha): backoffice + equipo.
    "operativo_gestion": [
        "Dashboard",
        "Admision",
        "Materiales",
        "Balance",
        "Inventario",
        "Caja",
        "Red",
        "Historial",
        "PDF",
        "Equipo",
        "Asistencia",
        "RRHH",
        "Legal",
    ],
    # Auditoria: mismo alcance de modulos que la antigua columna administrativa.
    "auditoria": [
        "Dashboard",
        "Admision",
        "Materiales",
        "Balance",
        "Inventario",
        "Caja",
        "Red",
        "Historial",
        "PDF",
        "Equipo",
        "Asistencia",
        "RRHH",
        "Legal",
    ],
}


def _texto_normalizado(valor):
    """
    Minúsculas + strip + NFKC y sin marcas diacríticas (NFD), para que
    «Enfermería» y «enfermeria» resuelvan igual en roles, perfiles y menú.
    """
    t = unicodedata.normalize("NFKC", str(valor or "").strip()).lower()
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def empresas_clinica_coinciden(empresa_a, empresa_b) -> bool:
    """Misma clínica aunque difieran tildes o espacios raros (NFKC + sin diacríticos)."""
    return _texto_normalizado(empresa_a) == _texto_normalizado(empresa_b)


def _password_normalizado(password):
    return str(password or "").strip()


def inferir_perfil_profesional(data):
    if not isinstance(data, dict):
        return ""

    perfil_cargado = str(data.get("perfil_profesional", "") or "").strip()
    if perfil_cargado:
        return perfil_cargado

    rol_normalizado = _texto_normalizado(data.get("rol", ""))
    titulo_normalizado = _texto_normalizado(data.get("titulo", ""))

    if rol_normalizado in LEGACY_ROLE_TO_PROFILE:
        return LEGACY_ROLE_TO_PROFILE[rol_normalizado]
    if rol_normalizado == "coordinador":
        return "Coordinacion"
    if rol_normalizado in {"superadmin", "admin"}:
        return "Direccion"
    if rol_normalizado == "administrativo":
        return "Administrativo"
    if "medic" in titulo_normalizado:
        return "Medico"
    if "enfermer" in titulo_normalizado:
        return "Enfermeria"
    if any(
        clave in titulo_normalizado
        for clave in (
            "kinesi",
            "fono",
            "nutri",
            "psico",
            "acompan",
            "terapeut",
            "trabajador",
            "social",
            "cuidad",
            "auxiliar",
        )
    ):
        return "Operativo"
    if any(clave in titulo_normalizado for clave in ("admin", "recep", "factur", "secretar")):
        return "Administrativo"
    if "coord" in titulo_normalizado:
        return "Coordinacion"
    if any(clave in titulo_normalizado for clave in ("director", "direccion", "geren")):
        return "Direccion"
    return ""


def obtener_password_usuario(data):
    if not isinstance(data, dict):
        return ""
    for clave in ("pass", "password", "clave", "contrasena", "contraseña"):
        valor = str(data.get(clave, "") or "").strip()
        if valor:
            return valor
    return ""


def obtener_pin_usuario(data):
    if not isinstance(data, dict):
        return ""
    for clave in ("pin", "ping", "codigo_pin", "codigo"):
        valor = str(data.get(clave, "") or "").strip()
        if valor:
            return valor
    return ""


def obtener_email_usuario(data):
    if not isinstance(data, dict):
        return ""
    for clave in ("email", "mail", "correo", "correo_verificacion", "correo_recuperacion"):
        valor = str(data.get(clave, "") or "").strip().lower()
        if valor:
            return valor
    return ""


def normalizar_usuario_sistema(data):
    if not isinstance(data, dict):
        return {}

    usuario = dict(data)
    perfil = inferir_perfil_profesional(usuario)
    rol_normalizado = _texto_normalizado(usuario.get("rol", ""))
    perfil_normalizado = _texto_normalizado(perfil)

    if rol_normalizado in {"superadmin", "admin"}:
        usuario["rol"] = "SuperAdmin"
    elif rol_normalizado == "coordinador":
        usuario["rol"] = "Coordinador"
    elif rol_normalizado == "medico":
        usuario["rol"] = "Medico"
    elif rol_normalizado == "enfermeria":
        usuario["rol"] = "Enfermeria"
    elif rol_normalizado == "operativo":
        usuario["rol"] = "Operativo"
    elif rol_normalizado == "auditoria":
        usuario["rol"] = "Auditoria"
    elif rol_normalizado in {"administrativo", "administrador"}:
        if perfil_normalizado == "medico":
            usuario["rol"] = "Medico"
        elif perfil_normalizado == "enfermeria":
            usuario["rol"] = "Enfermeria"
        else:
            usuario["rol"] = "Operativo"
    elif not str(usuario.get("rol", "") or "").strip():
        usuario["rol"] = "Operativo"

    usuario["pass"] = obtener_password_usuario(usuario)
    pin_actual = obtener_pin_usuario(usuario)
    if pin_actual:
        usuario["pin"] = pin_actual
    else:
        usuario.setdefault("pin", "")
    usuario["email"] = obtener_email_usuario(usuario)

    for campo in ("nombre", "empresa", "matricula", "dni", "titulo", "estado"):
        if campo in usuario:
            usuario[campo] = str(usuario.get(campo, "") or "").strip()

    if not usuario.get("estado"):
        usuario["estado"] = "Activo"

    if perfil:
        usuario["perfil_profesional"] = perfil
    return usuario


def _modulo_canonico(nombre_modulo):
    nombre = str(nombre_modulo or "").strip()
    return MODULO_ALIAS.get(nombre, nombre)


def clave_menu_usuario(rol_actual, usuario_actual=None):
    rol_normalizado = _texto_normalizado(rol_actual or (usuario_actual or {}).get("rol"))
    if rol_normalizado in {"superadmin", "admin", "coordinador"}:
        return rol_normalizado
    if rol_normalizado == "auditoria":
        return "auditoria"
    if rol_normalizado in {"medico", "enfermeria"}:
        return "operativo_clinico"
    if rol_normalizado in {"operativo", "administrativo"}:
        perfil_normalizado = _texto_normalizado((usuario_actual or {}).get("perfil_profesional"))
        if not perfil_normalizado and isinstance(usuario_actual, dict):
            perfil_normalizado = _texto_normalizado(inferir_perfil_profesional(usuario_actual))
        if perfil_normalizado in {"operativo", "medico", "enfermeria"}:
            return "operativo_clinico"
        return "operativo_gestion"

    return rol_normalizado


def _roles_usuario_para_filtrado(data):
    roles = set()
    rol_normalizado = _texto_normalizado(data.get("rol", ""))
    titulo_normalizado = _texto_normalizado(data.get("titulo", ""))
    perfil_normalizado = _texto_normalizado(data.get("perfil_profesional", ""))
    perfil_inferido = _texto_normalizado(inferir_perfil_profesional(data))

    for valor in {rol_normalizado, perfil_normalizado, perfil_inferido}:
        if valor:
            roles.add(valor)

    if rol_normalizado in {"superadmin", "admin"}:
        roles.update({"superadmin", "admin"})
    if rol_normalizado == "coordinador":
        roles.add("coordinador")

    if perfil_inferido == "medico" or "medic" in titulo_normalizado:
        roles.update({"medico", "operativo"})
    if perfil_inferido == "enfermeria" or "enfermer" in titulo_normalizado:
        roles.update({"enfermeria", "operativo"})
    if perfil_inferido == "operativo" or any(
        clave in titulo_normalizado
        for clave in (
            "kinesi",
            "fono",
            "nutri",
            "psico",
            "acompan",
            "terapeut",
            "trabajador",
            "social",
            "cuidad",
            "auxiliar",
        )
    ):
        roles.add("operativo")
    if perfil_inferido == "administrativo" or any(
        clave in titulo_normalizado for clave in ("admin", "recep", "factur", "secretar")
    ):
        roles.add("administrativo")

    return roles


def tiene_permiso(rol_actual, roles_permitidos=None):
    rol_normalizado = str(rol_actual or "").strip().lower()
    if rol_normalizado in ROLES_BYPASS_PERMISOS:
        return True
    if not roles_permitidos:
        return True
    roles_normalizados = {str(rol).strip().lower() for rol in roles_permitidos if rol}
    return rol_normalizado in roles_normalizados


def _permiso_estricto_lista_roles(rol_actual, roles_permitidos):
    """Sin bypass: solo coincide si el rol está en la lista explícita."""
    rol_normalizado = str(rol_actual or "").strip().lower()
    if not roles_permitidos:
        return False
    roles_normalizados = {str(rol).strip().lower() for rol in roles_permitidos if rol}
    return rol_normalizado in roles_normalizados


def _permiso_estricto_lista_o_global(rol_actual, roles_permitidos):
    """SuperAdmin/Admin global, o rol incluido en la lista (p. ej. Coordinador)."""
    r = str(rol_actual or "").strip().lower()
    if r in ROLES_GLOBAL_DATOS_MULTICLINICA:
        return True
    return _permiso_estricto_lista_roles(rol_actual, roles_permitidos)


# Lista cerrada: ni Operativo asistencial ni "Admin" legacy (solo SuperAdmin y Coordinador).
ROLES_PUEDEN_ELIMINAR_USUARIO_MI_EQUIPO = frozenset({"superadmin", "coordinador"})
# Suspender/reactivar usuario en Mi equipo: misma lista blanca que eliminar.
ROLES_PUEDEN_SUSPENDER_REACTIVAR_MI_EQUIPO = frozenset({"superadmin", "coordinador"})
# Quien puede intentar suspender/eliminar otro usuario (reglas de fila aparte en la misma funcion).
ROLES_ACTOR_GESTION_BAJA_USUARIO_MI_EQUIPO = frozenset({"superadmin", "admin", "coordinador"})
# Denegacion explicita ademas de la lista blanca (defensa ante datos o sesiones inconsistentes).
ROLES_PROHIBIDOS_ACCIONES_BAJA_MI_EQUIPO = frozenset({"operativo", "medico", "enfermeria", "auditoria"})


def puede_eliminar_cuenta_equipo(rol_actual) -> bool:
    """Solo SuperAdmin y Coordinador. Operativo, Medico y demas: False (lista blanca, sin ambiguedad con 'Admin')."""
    r = _texto_normalizado(rol_actual)
    if r in ROLES_PROHIBIDOS_ACCIONES_BAJA_MI_EQUIPO:
        return False
    return r in ROLES_PUEDEN_ELIMINAR_USUARIO_MI_EQUIPO


def puede_suspender_reactivar_usuario_mi_equipo(rol_actual) -> bool:
    """Solo SuperAdmin y Coordinador. Operativo y demas: sin botones de suspension."""
    r = _texto_normalizado(rol_actual)
    if r in ROLES_PROHIBIDOS_ACCIONES_BAJA_MI_EQUIPO:
        return False
    return r in ROLES_PUEDEN_SUSPENDER_REACTIVAR_MI_EQUIPO


def mi_equipo_actor_es_superadmin(usuario_actual) -> bool:
    """Equivale a usuario_actual.rol == 'SuperAdmin' (tras NFKC / normalizacion de sesion)."""
    return _texto_normalizado((usuario_actual or {}).get("rol")) == "superadmin"


def mi_equipo_coordinador_puede_eliminar_objetivo(usuario_actual, usuario_objetivo, empresa_actor) -> bool:
    """
    Coordinador valido: misma clinica que el objetivo y el objetivo no es cuenta global (SuperAdmin/Admin).
    """
    if _texto_normalizado((usuario_actual or {}).get("rol")) != "coordinador":
        return False
    if not isinstance(usuario_objetivo, dict):
        return False
    emp_a = _texto_normalizado(empresa_actor)
    emp_t = _texto_normalizado(usuario_objetivo.get("empresa"))
    if emp_t != emp_a:
        return False
    rol_obj = _texto_normalizado(usuario_objetivo.get("rol"))
    return rol_obj not in {"superadmin", "admin"}


def mi_equipo_mostrar_ui_suspender(usuario_actual, ok_gestionar_fila: bool) -> bool:
    """Suspender/reactivar: misma regla de negocio que eliminar, con fila habilitada."""
    return bool(ok_gestionar_fila) and puede_suspender_reactivar_usuario_mi_equipo(
        (usuario_actual or {}).get("rol")
    )


def mi_equipo_mostrar_ui_eliminar(usuario_actual, usuario_objetivo, empresa_actor, ok_gestionar_fila: bool) -> bool:
    """
    Eliminar: solo si la fila ya cumple reglas de empresa/cuenta global y el rol puede dar de baja.
    """
    return bool(ok_gestionar_fila) and puede_eliminar_cuenta_equipo((usuario_actual or {}).get("rol"))


def puede_accion(rol_actual, accion, roles_extra=None):
    roles_base = list(ACTION_ROLE_RULES.get(accion, []))
    if roles_extra:
        roles_base.extend(roles_extra)
    if accion in ACCIONES_PERMISO_ESTRICTO_SIN_GLOBAL:
        return _permiso_estricto_lista_roles(rol_actual, roles_base)
    if accion in ACCIONES_PERMISO_ESTRICTO_LISTA_O_GLOBAL:
        return _permiso_estricto_lista_o_global(rol_actual, roles_base)
    return tiene_permiso(rol_actual, roles_base)


def rol_ve_datos_todas_las_clinicas(rol_actual) -> bool:
    return str(rol_actual or "").strip().lower() in ROLES_GLOBAL_DATOS_MULTICLINICA


def actor_puede_modificar_usuario_equipo(rol_actor, empresa_actor, data_usuario_objetivo):
    """
    - SuperAdmin/Admin global: suspender/eliminar según reglas de cuenta global (solo SuperAdmin toca otra global).
    - Coordinador: suspender/eliminar solo usuarios de su empresa, nunca cuentas globales.
    - Cualquier otro rol (Operativo, Medico, variantes de texto, etc.): no suspender ni eliminar desde Mi equipo.
    """
    r = _texto_normalizado(rol_actor)
    if not isinstance(data_usuario_objetivo, dict):
        return False, "Datos de usuario invalidos."
    if r not in ROLES_ACTOR_GESTION_BAJA_USUARIO_MI_EQUIPO:
        return (
            False,
            "Tu rol no puede suspender ni eliminar usuarios en Mi equipo. Solo **SuperAdmin** o **Coordinador** de la misma clinica pueden hacerlo, segun reglas.",
        )
    rol_t = _texto_normalizado(data_usuario_objetivo.get("rol"))
    cuenta_global = rol_t in {"superadmin", "admin"}

    if r in ROLES_GLOBAL_DATOS_MULTICLINICA:
        if cuenta_global and r != "superadmin":
            return (
                False,
                "Solo un usuario **SuperAdmin** puede dar de baja o suspender otra cuenta SuperAdmin o Admin global.",
            )
        return True, ""

    emp_a = str(empresa_actor or "").strip().lower()
    emp_t = str(data_usuario_objetivo.get("empresa") or "").strip().lower()
    if emp_t != emp_a:
        return False, "Solo podes gestionar usuarios de tu clinica."
    if cuenta_global:
        return False, "Las cuentas de nivel global solo las gestiona un administrador del sistema."
    return True, ""


def bloqueo_autoservicio_suspension_baja(login_actor, login_objetivo, rol_actor):
    """True si no debe ejecutarse suspender/eliminar (misma cuenta, sin rol global)."""
    r = _texto_normalizado(rol_actor)
    if r in ROLES_GLOBAL_DATOS_MULTICLINICA:
        return False, ""
    la = str(login_actor or "").strip().lower()
    lo = str(login_objetivo or "").strip().lower()
    if la and lo and la == lo:
        return True, "No podes suspender ni eliminar tu propio usuario desde esta pantalla."
    return False, ""


def modo_celular_viejo_activo(session_state=None):
    """
    Versión Lite (datos compactos en Python): automático por UA/cabeceras en sesión real.
    Si se pasa un dict ajeno a st.session_state (p. ej. tests), se usa la clave legada `modo_celular_viejo`.
    """
    state = session_state if session_state is not None else st.session_state
    try:
        if state is not st.session_state:
            return bool(state.get(SESSION_KEY_MODO_LIVIANO, False))
        from core.ui_liviano import datos_compactos_por_cliente_sugerido

        return datos_compactos_por_cliente_sugerido()
    except Exception:
        try:
            return bool(state.get(SESSION_KEY_MODO_LIVIANO, False))
        except Exception:
            return False


def valor_por_modo_liviano(valor_normal, valor_liviano, session_state=None):
    return valor_liviano if modo_celular_viejo_activo(session_state) else valor_normal


def password_hash_formato_valido(valor):
    return str(valor or "").startswith(f"{PASSWORD_HASH_PREFIX}$")


def generar_hash_password(password, salt=None, iterations=PASSWORD_HASH_ITERATIONS):
    password_limpio = _password_normalizado(password)
    salt_hex = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password_limpio.encode("utf-8"),
        salt_hex.encode("utf-8"),
        int(iterations),
    ).hex()
    return f"{PASSWORD_HASH_PREFIX}${int(iterations)}${salt_hex}${digest}"


def validar_password_guardado(valor_guardado, password_ingresado):
    password_limpio = _password_normalizado(password_ingresado)
    if not password_limpio:
        return False

    stored = str(valor_guardado or "")
    if password_hash_formato_valido(stored):
        try:
            _, iterations_str, salt_hex, expected = stored.split("$", 3)
            calculado = hashlib.pbkdf2_hmac(
                "sha256",
                password_limpio.encode("utf-8"),
                salt_hex.encode("utf-8"),
                int(iterations_str),
            ).hex()
            return hmac.compare_digest(calculado, expected)
        except Exception:
            return False
    return stored.strip() == password_limpio


def actualizar_password_usuario(usuario_data, password_plano):
    if isinstance(usuario_data, dict):
        usuario_data["pass"] = generar_hash_password(password_plano)


def password_requiere_migracion(valor_guardado):
    valor = str(valor_guardado or "").strip()
    return bool(valor) and not password_hash_formato_valido(valor)


def decodificar_base64_seguro(raw):
    if not raw:
        return b""
    try:
        return base64.b64decode(raw)
    except Exception:
        return b""


def es_control_total(rol_actual, usuario_actual=None):
    """
    Multiclínica / altas / ciertos paneles: coordinacion y gestion.
    Operativo con perfil asistencial (Medico, Enfermeria, Operativo) queda fuera.
    """
    if usuario_actual is None:
        try:
            usuario_actual = st.session_state.get("u_actual")
        except Exception:
            usuario_actual = None
    r = str(rol_actual or "").strip().lower()
    if r in {"superadmin", "admin", "coordinador"}:
        return True
    if r == "administrativo":
        return True
    if r == "operativo":
        if not isinstance(usuario_actual, dict):
            return False
        p = _texto_normalizado((usuario_actual or {}).get("perfil_profesional"))
        if not p:
            p = _texto_normalizado(inferir_perfil_profesional(usuario_actual))
        if p in {"medico", "enfermeria", "operativo"}:
            return False
        return True
    return False


def descripcion_acceso_rol(rol_actual, usuario_actual=None):
    rol_normalizado = str(rol_actual or "").strip().lower()
    if rol_normalizado in {"superadmin", "admin"}:
        return "Acceso de gestion, control y trazabilidad completa."
    if rol_normalizado == "coordinador":
        return "Acceso total a la operacion, horarios, auditoria y control del equipo."
    if rol_normalizado == "administrativo":
        return "Acceso de gestion y operacion (rol historico; se muestra como Operativo en el sistema)."
    if rol_normalizado == "operativo":
        if es_control_total(rol_actual, usuario_actual):
            return "Acceso de gestion, facturacion, equipo y operacion de la clinica."
        return "Acceso asistencial: registro clinico del paciente y modulos segun tu perfil profesional."
    descripciones = {
        "medico": "Acceso clinico ampliado: prescripcion, evolucion y decisiones terapeuticas.",
        "enfermeria": "Acceso asistencial: registro clinico, indicaciones y seguimiento diario del paciente.",
        "auditoria": "Acceso de control, revision y trazabilidad legal.",
    }
    return descripciones.get(rol_normalizado, "Acceso configurado segun el rol asignado.")


def obtener_modulos_permitidos(rol_actual, todos_los_modulos=None, usuario_actual=None):
    from core.view_roles import modulos_menu_para_rol

    menu_base = (
        list(todos_los_modulos)
        if todos_los_modulos is not None
        else modulos_menu_para_rol(rol_actual)
    )
    if usuario_actual is not None:
        clave_menu = clave_menu_usuario(rol_actual, usuario_actual)
        if clave_menu in {"superadmin", "admin", "coordinador"}:
            return menu_base
        modulos_autorizados = {_modulo_canonico(m) for m in PERMISOS_MODULOS.get(clave_menu, [])}
        return [modulo for modulo in menu_base if modulo in modulos_autorizados]
    if todos_los_modulos is not None:
        allow = set(todos_los_modulos)
        return [m for m in modulos_menu_para_rol(rol_actual) if m in allow]
    return menu_base


def filtrar_registros_empresa(items, mi_empresa, rol_actual, empresa_key="empresa"):
    if rol_ve_datos_todas_las_clinicas(rol_actual):
        return list(items or [])

    filtrados = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        if empresas_clinica_coinciden(item.get(empresa_key, ""), mi_empresa):
            filtrados.append(item)
    return filtrados


def compactar_etiqueta_paciente(nombre, estado):
    nombre = str(nombre or "").strip()
    sufijo = " [ALTA]" if estado == "De Alta" else ""
    limite = 34 if sufijo else 40
    if len(nombre) > limite:
        nombre = f"{nombre[:limite - 3].rstrip()}..."
    return f"{nombre}{sufijo}"


def mapa_detalles_pacientes(session_state) -> dict:
    """Lectura segura del mapa id -> detalle (evita KeyError si la clave falta o no es dict)."""
    m = session_state.get("detalles_pacientes_db")
    return m if isinstance(m, dict) else {}


def asegurar_detalles_pacientes_en_sesion(session_state) -> dict:
    """Garantiza un dict mutable en session_state para altas/ediciones en Admisión y similares."""
    m = session_state.get("detalles_pacientes_db")
    if not isinstance(m, dict):
        m = {}
        session_state["detalles_pacientes_db"] = m
    return m


def obtener_pacientes_visibles(session_state, mi_empresa, rol_actual, incluir_altas=False, busqueda=""):
    busqueda_norm = str(busqueda or "").strip().lower()
    
    # --- SWITCH FINAL: LECTURA DESDE POSTGRESQL ---
    from core.db_sql import get_pacientes_by_empresa
    from core.nextgen_sync import _obtener_uuid_empresa
    
    pacientes_visibles = []
    uso_sql = False
    
    try:
        empresa_id = _obtener_uuid_empresa(mi_empresa)
        if empresa_id:
            # Leemos directamente de la base de datos SQL
            pacs_sql = get_pacientes_by_empresa(empresa_id, busqueda_norm, incluir_altas)
            uso_sql = True
            
            for p in pacs_sql:
                nombre = p.get("nombre_completo", "")
                dni = p.get("dni", "")
                estado = p.get("estado", "Activo")
                obra_social = p.get("obra_social", "")
                
                # El ID visual sigue siendo "Nombre - DNI" para compatibilidad con el resto de la app
                paciente_id_visual = f"{nombre} - {dni}"
                etiqueta = compactar_etiqueta_paciente(paciente_id_visual, estado)
                
                pacientes_visibles.append(
                    (paciente_id_visual, etiqueta, dni, obra_social, estado, mi_empresa)
                )
    except Exception as e:
        print(f"Error en lectura SQL de pacientes: {e}")
        
    if uso_sql:
        pacientes_visibles.sort(key=lambda item: (item[1].lower(), item[0].lower()))
        return pacientes_visibles
    # ----------------------------------------------

    ts = session_state.get("_ultimo_guardado_ts", 0)
    cache_key = f"_mc_cache_pac_vis_{mi_empresa}_{rol_actual}_{incluir_altas}_{busqueda_norm}"
    
    cached = session_state.get(cache_key)
    if cached and cached.get("ts") == ts:
        return cached["data"]

    hay_busqueda = bool(busqueda_norm)
    detalles_db = mapa_detalles_pacientes(session_state)
    pacientes_visibles = []

    for paciente in session_state.get("pacientes_db", []):
        detalles = detalles_db.get(paciente, {})
        if not isinstance(detalles, dict):
            detalles = {}
        if not rol_ve_datos_todas_las_clinicas(rol_actual):
            if not empresas_clinica_coinciden(detalles.get("empresa", ""), mi_empresa):
                continue

        estado = detalles.get("estado", "Activo")
        if estado != "Activo" and not incluir_altas:
            continue

        dni = str(detalles.get("dni", "") or "")
        obra_social = str(detalles.get("obra_social", "") or "")
        empresa = str(detalles.get("empresa", "") or "")
        etiqueta = compactar_etiqueta_paciente(paciente, estado)

        if hay_busqueda:
            searchable = f"{paciente} {etiqueta} {dni} {obra_social} {empresa} {estado}".lower()
            if busqueda_norm not in searchable:
                continue

        pacientes_visibles.append(
            (paciente, etiqueta, dni, obra_social, estado, empresa)
        )

    pacientes_visibles.sort(key=lambda item: (item[1].lower(), item[0].lower()))
    session_state[cache_key] = {"ts": ts, "data": pacientes_visibles}
    return pacientes_visibles


def ahora():
    return datetime.now(ARG_TZ)


def construir_registro_auditoria_legal(
    tipo_evento,
    paciente,
    accion,
    actor,
    matricula="",
    detalle="",
    referencia="",
    extra=None,
    empresa="",
    usuario=None,
    modulo="",
    criticidad="media",
    fecha_evento=None,
):
    extra = dict(extra or {})
    usuario = normalizar_usuario_sistema(usuario or {}) if isinstance(usuario, dict) else {}
    fecha_evento = fecha_evento or ahora()
    actor_nombre = str(actor or usuario.get("nombre") or "Sistema").strip()
    actor_login = str(extra.pop("actor_login", usuario.get("usuario_login", "")) or "").strip().lower()
    actor_rol = str(extra.pop("actor_rol", usuario.get("rol", "")) or "").strip()
    actor_perfil = str(
        extra.pop("actor_perfil", usuario.get("perfil_profesional", inferir_perfil_profesional(usuario)))
        or ""
    ).strip()
    actor_empresa = str(extra.pop("actor_empresa", usuario.get("empresa", "")) or "").strip()
    modulo_registro = str(extra.pop("modulo", modulo or tipo_evento or "General") or "General").strip()
    criticidad_registro = str(extra.pop("criticidad", criticidad or "media") or "media").strip().lower()
    referencia_txt = str(referencia or "").strip()
    detalle_txt = str(detalle or "").strip()
    empresa_txt = str(empresa or "").strip()

    registro = {
        "audit_id": extra.pop(
            "audit_id",
            f"AUD-{fecha_evento.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4).upper()}",
        ),
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
        "detalle": detalle_txt,
        "referencia": referencia_txt,
        "empresa": empresa_txt,
    }

    for clave, valor in extra.items():
        if valor in (None, "", [], {}):
            continue
        registro[clave] = valor

    return registro


def registrar_auditoria_legal(
    tipo_evento,
    paciente,
    accion,
    actor,
    matricula="",
    detalle="",
    referencia="",
    extra=None,
    empresa=None,
    usuario=None,
    modulo="",
    criticidad="media",
):
    extra = dict(extra or {})
    usuario_ctx = usuario if isinstance(usuario, dict) else st.session_state.get("user", {})
    if empresa is None:
        detalles = mapa_detalles_pacientes(st.session_state).get(paciente, {})
        empresa = detalles.get("empresa") or usuario_ctx.get("empresa", "")
        
    # 1. Guardar en PostgreSQL (Dual-Write)
    try:
        from core.db_sql import insert_auditoria
        from core.nextgen_sync import _obtener_uuid_empresa, _obtener_uuid_paciente
        
        empresa_uuid = _obtener_uuid_empresa(empresa)
        paciente_uuid = _obtener_uuid_paciente(paciente) if paciente else None
        
        if empresa_uuid:
            datos_sql = {
                "empresa_id": empresa_uuid,
                "paciente_id": paciente_uuid,
                "fecha_evento": ahora().isoformat(),
                "modulo": modulo or tipo_evento,
                "accion": accion,
                "detalle": detalle,
                "usuario_id": None # Por ahora no tenemos el UUID del usuario en sesion
            }
            insert_auditoria(datos_sql)
    except Exception as e:
        from core.app_logging import log_event
        log_event("error_auditoria_sql", str(e))

    # 2. Guardar en JSON (Legacy)
    st.session_state.setdefault("auditoria_legal_db", [])
    st.session_state["auditoria_legal_db"].append(
        construir_registro_auditoria_legal(
            tipo_evento=tipo_evento,
            paciente=paciente,
            accion=accion,
            actor=actor,
            matricula=matricula,
            detalle=detalle,
            referencia=referencia,
            extra=extra,
            empresa=empresa or "",
            usuario=usuario_ctx,
            modulo=modulo,
            criticidad=criticidad,
        )
    )


def asegurar_usuarios_base(solo_normalizar: bool = False):
    """
    solo_normalizar=True: solo renormaliza usuarios existentes (modo shard / sin inyectar admin de emergencia).
    """
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


def obtener_alertas_clinicas(session_state, paciente_sel):
    if not paciente_sel:
        return []

    detalles = mapa_detalles_pacientes(session_state).get(paciente_sel, {})
    alertas = []

    alergias = str(detalles.get("alergias", "") or "").strip()
    if alergias:
        alertas.append(
            {
                "nivel": "critica",
                "titulo": "Alergias registradas",
                "detalle": alergias,
            }
        )

    patologias = str(detalles.get("patologias", "") or "").strip()
    if patologias:
        alertas.append(
            {
                "nivel": "media",
                "titulo": "Patologias y riesgos",
                "detalle": patologias,
            }
        )

    consentimientos = session_state.get("consentimientos_db", [])
    cons_cache_key = f"_mc_cache_cons_{paciente_sel}"
    cons_cached = session_state.get(cons_cache_key)
    if cons_cached and cons_cached.get("id") == id(consentimientos) and cons_cached.get("len") == len(consentimientos):
        tiene_consentimiento = cons_cached["tiene"]
    else:
        tiene_consentimiento = any(x.get("paciente") == paciente_sel for x in consentimientos)
        session_state[cons_cache_key] = {"id": id(consentimientos), "len": len(consentimientos), "tiene": tiene_consentimiento}

    if not tiene_consentimiento:
        alertas.append(
            {
                "nivel": "alta",
                "titulo": "Consentimiento legal pendiente",
                "detalle": "Todavia no hay un consentimiento domiciliario firmado para este paciente.",
            }
        )

    vitales = session_state.get("vitales_db", [])
    vit_cache_key = f"_mc_cache_vit_ult_{paciente_sel}"
    vit_cached = session_state.get(vit_cache_key)
    if vit_cached and vit_cached.get("id") == id(vitales) and vit_cached.get("len") == len(vitales):
        ultimo_vital = vit_cached["ultimo"]
    else:
        ultimo_vital = None
        for x in reversed(vitales):
            if x.get("paciente") == paciente_sel:
                ultimo_vital = x
                break
        session_state[vit_cache_key] = {"id": id(vitales), "len": len(vitales), "ultimo": ultimo_vital}

    if ultimo_vital:
        sat = _to_float(ultimo_vital.get("Sat"))
        temp = _to_float(ultimo_vital.get("Temp"))
        fc = _to_float(ultimo_vital.get("FC"))
        if sat is not None and sat < 92:
            alertas.append(
                {
                    "nivel": "critica",
                    "titulo": "Desaturacion reciente",
                    "detalle": f"Ultimo SatO2 registrado: {sat:.0f}% | {ultimo_vital.get('fecha', 'S/D')}",
                }
            )
        if temp is not None and temp >= 38:
            alertas.append(
                {
                    "nivel": "alta",
                    "titulo": "Fiebre registrada",
                    "detalle": f"Ultima temperatura: {temp:.1f} C | {ultimo_vital.get('fecha', 'S/D')}",
                }
            )
        if fc is not None and (fc > 110 or fc < 50):
            alertas.append(
                {
                    "nivel": "alta",
                    "titulo": "Frecuencia cardiaca fuera de rango",
                    "detalle": f"Ultima FC: {fc:.0f} lpm | {ultimo_vital.get('fecha', 'S/D')}",
                }
            )

    for indicacion in reversed(session_state.get("indicaciones_db", [])):
        if indicacion.get("paciente") != paciente_sel:
            continue
        estado = str(indicacion.get("estado_receta") or indicacion.get("estado_clinico") or "Activa").strip()
        if estado in {"Suspendida", "Modificada"}:
            fecha_estado = indicacion.get("fecha_estado") or indicacion.get("fecha_suspension") or indicacion.get("fecha", "")
            alertas.append(
                {
                    "nivel": "alta" if estado == "Suspendida" else "media",
                    "titulo": f"Medicacion {estado.lower()}",
                    "detalle": (
                        f"{indicacion.get('med', 'Sin detalle')} | {fecha_estado} | "
                        f"{indicacion.get('profesional_estado', indicacion.get('medico_nombre', 'Sin profesional'))}"
                    ),
                }
            )
            if len(alertas) >= 5:
                break

    return alertas[:5]


def _to_float(value):
    try:
        if value in ("", None):
            return None
        return float(value)
    except Exception:
        return None


@lru_cache(maxsize=8192)
def _parse_fecha_hora_cached(fecha_txt: str):
    formatos = (
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d",
    )
    for formato in formatos:
        try:
            return datetime.strptime(fecha_txt, formato)
        except Exception:
            continue
    return datetime.min


def parse_fecha_hora(fecha_str):
    return _parse_fecha_hora_cached(str(fecha_str or "").strip())


def parse_agenda_datetime(item):
    fecha_hora_programada = str(item.get("fecha_hora_programada", "")).strip()
    if fecha_hora_programada:
        dt_programado = parse_fecha_hora(fecha_hora_programada)
        if dt_programado != datetime.min:
            return dt_programado

    fecha = str(item.get("fecha_programada", "") or item.get("fecha", "")).strip()
    hora = normalizar_hora_texto(item.get("hora", ""), default="00:00")
    combinado = f"{fecha} {hora}"
    return parse_fecha_hora(combinado)


def calcular_estado_agenda(item, now=None):
    now = now or ahora().replace(tzinfo=None)
    estado = str(item.get("estado", "Pendiente")).strip() or "Pendiente"
    if estado in {"Realizada", "Cancelada"}:
        return estado
    dt = parse_agenda_datetime(item)
    if dt == datetime.min:
        return estado
    if dt.date() == now.date() and dt <= now:
        return "En curso"
    if dt < now:
        return "Vencida"
    return "Pendiente"


def normalizar_hora_texto(valor, default="08:00"):
    texto = str(valor or "").strip().lower()
    if not texto:
        return default

    texto = (
        texto.replace(" horas", "")
        .replace(" hora", "")
        .replace("hrs", "")
        .replace("hs.", "")
        .replace("hs", "")
        .replace("h", "")
        .strip()
    )

    match = re.search(r"^(\d{1,2})(?::(\d{1,2}))?$", texto)
    if not match:
        return default

    horas = int(match.group(1))
    minutos = int(match.group(2) or 0)
    if horas > 23 or minutos > 59:
        return default
    return f"{horas:02d}:{minutos:02d}"


def parse_horarios_programados(texto):
    if isinstance(texto, list):
        candidatos = texto
    else:
        candidatos = re.split(r"[,\|;/\n]+", str(texto or ""))

    horarios = []
    for valor in candidatos:
        hora = normalizar_hora_texto(valor, default="")
        if hora:
            horarios.append(hora)

    horarios_unicos = sorted(set(horarios), key=lambda x: (int(x.split(":")[0]), int(x.split(":")[1])))
    return horarios_unicos


def horarios_programados_desde_frecuencia(frecuencia, hora_inicio="08:00"):
    frecuencia = str(frecuencia or "").strip()
    hora_inicio = normalizar_hora_texto(hora_inicio)

    intervalos = {
        "Cada 1 hora": 1,
        "Cada 2 horas": 2,
        "Cada 4 horas": 4,
        "Cada 6 horas": 6,
        "Cada 8 horas": 8,
        "Cada 12 horas": 12,
        "Cada 24 horas": 24,
    }

    if frecuencia == "Dosis unica":
        return [hora_inicio]
    if frecuencia == "Infusion continua":
        return [hora_inicio]
    if frecuencia == "Segun necesidad":
        return []

    intervalo = intervalos.get(frecuencia)
    if not intervalo:
        return []

    hora_base = int(hora_inicio.split(":")[0])
    minuto_base = int(hora_inicio.split(":")[1])
    horas = []
    total = 24 if intervalo < 24 else 1
    for paso in range(total):
        horas.append(f"{(hora_base + (paso * intervalo)) % 24:02d}:{minuto_base:02d}")
        if intervalo == 24:
            break
    return sorted(set(horas), key=lambda x: (int(x.split(":")[0]), int(x.split(":")[1])))


def calcular_velocidad_ml_h(volumen_ml, duracion_horas):
    try:
        volumen = float(volumen_ml)
        horas = float(duracion_horas)
        if volumen <= 0 or horas <= 0:
            return None
        return round(volumen / horas, 2)
    except Exception:
        return None


def generar_plan_escalonado_ml_h(inicio_ml_h, maximo_ml_h, incremento_ml_h=7, hora_inicio="08:00", intervalo_horas=1):
    try:
        inicio = float(inicio_ml_h)
        maximo = float(maximo_ml_h)
        incremento = float(incremento_ml_h)
        intervalo = max(1, int(intervalo_horas))
    except Exception:
        return []

    if inicio <= 0 or maximo <= 0 or incremento <= 0:
        return []

    hora_base = normalizar_hora_texto(hora_inicio)
    base_hora = int(hora_base.split(":")[0])
    base_min = int(hora_base.split(":")[1])

    valores = []
    actual = inicio
    while actual < maximo:
        valores.append(round(actual, 2))
        actual += incremento

    if not valores or valores[-1] != round(maximo, 2):
        valores.append(round(maximo, 2))

    plan = []
    for idx, velocidad in enumerate(valores, start=1):
        hora_paso = (base_hora + ((idx - 1) * intervalo)) % 24
        plan.append(
            {
                "Paso": idx,
                "Hora sugerida": f"{hora_paso:02d}:{base_min:02d}",
                "Velocidad (ml/h)": velocidad,
            }
        )
    return plan


def extraer_frecuencia_desde_indicacion(indicacion):
    texto = str(indicacion or "")
    partes = [parte.strip() for parte in texto.split("|")]
    for parte in partes:
        if parte.startswith("Cada ") or parte == "Dosis unica" or parte == "Segun necesidad":
            return parte
    return ""


def obtener_horarios_receta(registro):
    horarios_guardados = registro.get("horarios_programados", [])
    horarios = parse_horarios_programados(horarios_guardados)
    if horarios:
        return horarios

    frecuencia = registro.get("frecuencia") or extraer_frecuencia_desde_indicacion(registro.get("med", ""))
    hora_inicio = registro.get("hora_inicio", "08:00")
    return horarios_programados_desde_frecuencia(frecuencia, hora_inicio)


def format_horarios_receta(registro):
    horarios = obtener_horarios_receta(registro)
    if not horarios:
        return "A demanda / sin horario fijo"
    return " | ".join(horarios)


def obtener_profesionales_visibles(session_state, mi_empresa, rol_actual, roles_validos=None):
    roles_validos_normalizados = (
        {str(rol).strip().lower() for rol in roles_validos if rol}
        if roles_validos
        else None
    )
    visibles = []
    for username, data in session_state.get("usuarios_db", {}).items():
        if not isinstance(data, dict):
            continue
        data_normalizada = normalizar_usuario_sistema(data)
        roles_usuario = _roles_usuario_para_filtrado(data_normalizada)
        if roles_validos_normalizados and not roles_usuario.intersection(roles_validos_normalizados):
            continue
        if not rol_ve_datos_todas_las_clinicas(rol_actual):
            if not empresas_clinica_coinciden(data_normalizada.get("empresa", ""), mi_empresa):
                continue
        visibles.append(
            {
                "username": username,
                **data_normalizada,
            }
        )

    visibles.sort(key=lambda x: (str(x.get("nombre", "")).lower(), str(x.get("username", "")).lower()))
    return visibles


@st.cache_data(show_spinner=False)
@st.cache_data(show_spinner=False)
def cargar_texto_asset(nombre_archivo):
    ruta = ASSETS_DIR / nombre_archivo
    return ruta.read_text(encoding="utf-8")


@st.cache_data(show_spinner=False)
def cargar_json_asset(nombre_archivo):
    ruta = ASSETS_DIR / nombre_archivo
    with ruta.open("r", encoding="utf-8") as archivo:
        return json.load(archivo)


def optimizar_imagen_bytes(image_bytes, max_size=(1280, 1280), quality=75):
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.thumbnail(max_size)
            salida = BytesIO()
            img.save(salida, format="JPEG", optimize=True, quality=quality)
            return salida.getvalue(), "jpg"
    except Exception:
        return image_bytes, None


def _bytes_legibles(cantidad_bytes):
    try:
        cantidad = float(cantidad_bytes or 0)
    except Exception:
        cantidad = 0.0
    if cantidad >= 1024 * 1024:
        return f"{cantidad / (1024 * 1024):.1f} MB"
    if cantidad >= 1024:
        return f"{cantidad / 1024:.0f} KB"
    return f"{int(cantidad)} B"


def limite_archivo_mb(tipo="imagen", session_state=None):
    tipo_normalizado = _texto_normalizado(tipo)
    modo_liviano = modo_celular_viejo_activo(session_state)
    limites = {
        "imagen": 4 if modo_liviano else 8,
        "pdf": 6 if modo_liviano else 12,
        "firma": 2 if modo_liviano else 3,
    }
    return limites.get(tipo_normalizado, 4 if modo_liviano else 8)


def validar_archivo_bytes(file_bytes, tipo="imagen", nombre_archivo="archivo", session_state=None):
    contenido = bytes(file_bytes or b"")
    if not contenido:
        return False, f"No se pudo leer {nombre_archivo}."

    tipo_normalizado = _texto_normalizado(tipo)
    if tipo_normalizado == "imagen":
        max_raw_bytes = MAX_RAW_IMAGE_UPLOAD_MB * 1024 * 1024
        if len(contenido) > max_raw_bytes:
            return (
                False,
                f"{nombre_archivo} pesa {_bytes_legibles(len(contenido))}. Para evitar bloqueos, sube una imagen de hasta {MAX_RAW_IMAGE_UPLOAD_MB} MB.",
            )

    limite_mb = limite_archivo_mb(tipo_normalizado, session_state)
    limite_bytes = limite_mb * 1024 * 1024
    if len(contenido) > limite_bytes and tipo_normalizado != "imagen":
        return (
            False,
            f"{nombre_archivo} pesa {_bytes_legibles(len(contenido))}. El limite para {tipo_normalizado} es {limite_mb} MB.",
        )

    return True, ""


def preparar_imagen_clinica_bytes(
    image_bytes, nombre_archivo="imagen.jpg", max_size=(1280, 1280), quality=75, session_state=None
):
    ok, error = validar_archivo_bytes(image_bytes, tipo="imagen", nombre_archivo=nombre_archivo, session_state=session_state)
    if not ok:
        return {"ok": False, "error": error}

    modo_liviano = modo_celular_viejo_activo(session_state)
    max_size_final = (960, 960) if modo_liviano else max_size
    calidad_final = min(quality, 62) if modo_liviano else quality
    contenido, extension = optimizar_imagen_bytes(image_bytes, max_size=max_size_final, quality=calidad_final)
    ok, error = validar_archivo_bytes(contenido, tipo="imagen", nombre_archivo=nombre_archivo, session_state=session_state)
    if not ok:
        return {"ok": False, "error": error}

    return {
        "ok": True,
        "bytes": contenido,
        "extension": extension or "jpg",
        "mime": "image/jpeg",
        "name": nombre_archivo,
        "tipo_archivo": "imagen",
        "size_bytes": len(contenido),
    }


def obtener_config_firma(key_prefix, default_liviano=True):
    modo_liviano = st.checkbox(
        "Modo firma liviana (recomendado en celulares viejos)",
        value=default_liviano,
        key=f"{key_prefix}_firma_liviana",
    )
    if modo_liviano:
        st.caption("Reduce el tamano del lienzo y las herramientas para que firme mas fluido.")
        return {
            "height": 96,
            "width": 280,
            "stroke_width": 1.8,
            "display_toolbar": False,
        }
    return {
        "height": 140,
        "width": 420,
        "stroke_width": 2.5,
        "display_toolbar": True,
    }


def firma_a_base64(canvas_image_data=None, uploaded_file=None):
    try:
        if uploaded_file is not None:
            firma_bytes, _ = optimizar_imagen_bytes(uploaded_file.getvalue(), max_size=(700, 220), quality=55)
            return base64.b64encode(firma_bytes).decode("utf-8")

        if canvas_image_data is not None:
            img = Image.fromarray(canvas_image_data.astype("uint8"), "RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            bg.thumbnail((700, 220))
            buf = BytesIO()
            bg.save(buf, format="JPEG", optimize=True, quality=55)
            return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        return ""
    return ""


def seleccionar_limite_registros(label, total, key, default=30, opciones=(10, 20, 30, 50, 100, 200, 500)):
    if total <= 0:
        return 0
    if total <= min(opciones):
        st.caption(f"Mostrando {total} registro(s).")
        return total

    opciones_validas = sorted({valor for valor in opciones if valor < total})
    if total not in opciones_validas:
        opciones_validas.append(total)

    valor_default = min(total, default)
    if valor_default not in opciones_validas:
        opciones_validas.append(valor_default)
        opciones_validas = sorted(set(opciones_validas))

    return st.selectbox(label, opciones_validas, index=opciones_validas.index(valor_default), key=key)


def mostrar_dataframe_con_scroll(df, height=420, border=True, hide_index=True):
    with st.container(height=height, border=border):
        st.dataframe(
            df,
            width="stretch",
            hide_index=hide_index,
            height=height - 24,
        )


def obtener_direccion_real(lat, lon):
    from services.nominatim import reverse_geocode_short_label

    return reverse_geocode_short_label(lat, lon)


def inicializar_db_state(db, precargar_usuario_admin_emergencia: bool = True):
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
        except Exception:
            pass
        st.session_state["db_inicializada"] = True
