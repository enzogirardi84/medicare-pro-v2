"""Funciones de permisos, roles y acceso por módulo.

Extraído de core/utils.py.
"""
import unicodedata

from core.norm_empresa import norm_empresa_key

ROLES_BYPASS_PERMISOS = frozenset({"superadmin", "admin", "coordinador"})
ROLES_GLOBAL_DATOS_MULTICLINICA = frozenset({"superadmin", "admin"})
ACCIONES_PERMISO_ESTRICTO_SIN_GLOBAL = frozenset({"equipo_eliminar_usuario", "equipo_cambiar_estado"})
ACCIONES_PERMISO_ESTRICTO_LISTA_O_GLOBAL = frozenset({"equipo_crear_usuario", "equipo_editar_email_usuario"})
ROLES_PUEDEN_ELIMINAR_USUARIO_MI_EQUIPO = frozenset({"superadmin", "coordinador"})
ROLES_PUEDEN_SUSPENDER_REACTIVAR_MI_EQUIPO = frozenset({"superadmin", "coordinador"})
ROLES_ACTOR_GESTION_BAJA_USUARIO_MI_EQUIPO = frozenset({"superadmin", "admin", "coordinador"})
ROLES_PROHIBIDOS_ACCIONES_BAJA_MI_EQUIPO = frozenset({"operativo", "medico", "enfermeria", "auditoria"})

LEGACY_ROLE_TO_PROFILE = {
    "medico": "Medico",
    "enfermeria": "Enfermeria",
    "operativo": "Operativo",
    "auditoria": "Administrativo",
}

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
    "APS": "APS / Dispensario",
}

PERMISOS_MODULOS = {
    "operativo_clinico": [
        "Visitas", "Admision", "Clinica", "Pediatria", "Evolucion", "Estudios",
        "Materiales", "Recetas", "Balance", "Emergencias", "Escalas", "Historial",
        "PDF", "Telemedicina", "Cierre", "APS / Dispensario",
    ],
    "operativo_gestion": [
        "Dashboard", "Admision", "Materiales", "Balance", "Inventario", "Caja",
        "Red", "Historial", "PDF", "Equipo", "Asistencia", "RRHH", "Legal",
        "APS / Dispensario",
    ],
    "auditoria": [
        "Dashboard", "Admision", "Materiales", "Balance", "Inventario", "Caja",
        "Red", "Historial", "PDF", "Equipo", "Asistencia", "RRHH", "Legal",
        "APS / Dispensario",
    ],
}


def _texto_normalizado(valor):
    t = unicodedata.normalize("NFKC", str(valor or "").strip()).lower()
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def empresas_clinica_coinciden(empresa_a, empresa_b) -> bool:
    return _texto_normalizado(empresa_a) == _texto_normalizado(empresa_b)


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
    if any(c in titulo_normalizado for c in ("kinesi", "fono", "nutri", "psico", "acompan", "terapeut", "trabajador", "social", "cuidad", "auxiliar")):
        return "Operativo"
    if any(c in titulo_normalizado for c in ("admin", "recep", "factur", "secretar")):
        return "Administrativo"
    if "coord" in titulo_normalizado:
        return "Coordinacion"
    if any(c in titulo_normalizado for c in ("director", "direccion", "geren")):
        return "Direccion"
    return ""


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
    if perfil_inferido == "operativo" or any(c in titulo_normalizado for c in ("kinesi", "fono", "nutri", "psico", "acompan", "terapeut", "trabajador", "social", "cuidad", "auxiliar")):
        roles.add("operativo")
    if perfil_inferido == "administrativo" or any(c in titulo_normalizado for c in ("admin", "recep", "factur", "secretar")):
        roles.add("administrativo")
    return roles


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


def tiene_permiso(rol_actual, roles_permitidos=None):
    rol_normalizado = str(rol_actual or "").strip().lower()
    if rol_normalizado in ROLES_BYPASS_PERMISOS:
        return True
    if not roles_permitidos:
        return True
    roles_normalizados = {str(rol).strip().lower() for rol in roles_permitidos if rol}
    return rol_normalizado in roles_normalizados


def _permiso_estricto_lista_roles(rol_actual, roles_permitidos):
    rol_normalizado = str(rol_actual or "").strip().lower()
    if not roles_permitidos:
        return False
    return rol_normalizado in {str(r).strip().lower() for r in roles_permitidos if r}


def _permiso_estricto_lista_o_global(rol_actual, roles_permitidos):
    r = str(rol_actual or "").strip().lower()
    if r in ROLES_GLOBAL_DATOS_MULTICLINICA:
        return True
    return _permiso_estricto_lista_roles(rol_actual, roles_permitidos)


def puede_eliminar_cuenta_equipo(rol_actual) -> bool:
    r = _texto_normalizado(rol_actual)
    if r in ROLES_PROHIBIDOS_ACCIONES_BAJA_MI_EQUIPO:
        return False
    return r in ROLES_PUEDEN_ELIMINAR_USUARIO_MI_EQUIPO


def puede_suspender_reactivar_usuario_mi_equipo(rol_actual) -> bool:
    r = _texto_normalizado(rol_actual)
    if r in ROLES_PROHIBIDOS_ACCIONES_BAJA_MI_EQUIPO:
        return False
    return r in ROLES_PUEDEN_SUSPENDER_REACTIVAR_MI_EQUIPO


def mi_equipo_actor_es_superadmin(usuario_actual) -> bool:
    return _texto_normalizado((usuario_actual or {}).get("rol")) == "superadmin"


def mi_equipo_coordinador_puede_eliminar_objetivo(usuario_actual, usuario_objetivo, empresa_actor) -> bool:
    if _texto_normalizado((usuario_actual or {}).get("rol")) != "coordinador":
        return False
    if not isinstance(usuario_objetivo, dict):
        return False
    emp_a = _texto_normalizado(empresa_actor)
    emp_t = _texto_normalizado(usuario_objetivo.get("empresa"))
    if emp_t != emp_a:
        return False
    return _texto_normalizado(usuario_objetivo.get("rol")) not in {"superadmin", "admin"}


def mi_equipo_mostrar_ui_suspender(usuario_actual, ok_gestionar_fila: bool) -> bool:
    return bool(ok_gestionar_fila) and puede_suspender_reactivar_usuario_mi_equipo((usuario_actual or {}).get("rol"))


def mi_equipo_mostrar_ui_eliminar(usuario_actual, usuario_objetivo, empresa_actor, ok_gestionar_fila: bool) -> bool:
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
    r = _texto_normalizado(rol_actor)
    if not isinstance(data_usuario_objetivo, dict):
        return False, "Datos de usuario invalidos."
    if r not in ROLES_ACTOR_GESTION_BAJA_USUARIO_MI_EQUIPO:
        return (False, "Tu rol no puede suspender ni eliminar usuarios en Mi equipo. Solo **SuperAdmin** o **Coordinador** de la misma clinica pueden hacerlo, segun reglas.")
    rol_t = _texto_normalizado(data_usuario_objetivo.get("rol"))
    cuenta_global = rol_t in {"superadmin", "admin"}
    if r in ROLES_GLOBAL_DATOS_MULTICLINICA:
        if cuenta_global and r != "superadmin":
            return (False, "Solo un usuario **SuperAdmin** puede dar de baja o suspender otra cuenta SuperAdmin o Admin global.")
        return True, ""
    emp_a = str(empresa_actor or "").strip().lower()
    emp_t = str(data_usuario_objetivo.get("empresa") or "").strip().lower()
    if emp_t != emp_a:
        return False, "Solo podes gestionar usuarios de tu clinica."
    if cuenta_global:
        return False, "Las cuentas de nivel global solo las gestiona un administrador del sistema."
    return True, ""


def bloqueo_autoservicio_suspension_baja(login_actor, login_objetivo, rol_actor):
    r = _texto_normalizado(rol_actor)
    if r in ROLES_GLOBAL_DATOS_MULTICLINICA:
        return False, ""
    la = str(login_actor or "").strip().lower()
    lo = str(login_objetivo or "").strip().lower()
    if la and lo and la == lo:
        return True, "No podes suspender ni eliminar tu propio usuario desde esta pantalla."
    return False, ""


def es_control_total(rol_actual, usuario_actual=None):
    if usuario_actual is None:
        try:
            import streamlit as st
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
    return {
        "medico": "Acceso clinico ampliado: prescripcion, evolucion y decisiones terapeuticas.",
        "enfermeria": "Acceso asistencial: registro clinico, indicaciones y seguimiento diario del paciente.",
        "auditoria": "Acceso de control, revision y trazabilidad legal.",
    }.get(rol_normalizado, "Acceso configurado segun el rol asignado.")


def obtener_modulos_permitidos(rol_actual, todos_los_modulos=None, usuario_actual=None):
    from core.view_roles import modulos_menu_para_rol
    menu_base = list(todos_los_modulos) if todos_los_modulos is not None else modulos_menu_para_rol(rol_actual)
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
    return [
        item for item in (items or [])
        if isinstance(item, dict) and empresas_clinica_coinciden(item.get(empresa_key, ""), mi_empresa)
    ]


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
    for clave_pwd in ("pass", "password", "clave", "contrasena", "contraseña"):
        valor = str(data.get(clave_pwd, "") or "").strip()
        if valor:
            usuario["pass"] = valor
            break
    else:
        usuario.setdefault("pass", "")
    for clave_pin in ("pin", "ping", "codigo_pin", "codigo"):
        valor_pin = str(data.get(clave_pin, "") or "").strip()
        if valor_pin:
            usuario["pin"] = valor_pin
            break
    else:
        usuario.setdefault("pin", "")
    email_val = ""
    for clave_mail in ("email", "mail", "correo", "correo_verificacion", "correo_recuperacion"):
        email_val = str(data.get(clave_mail, "") or "").strip().lower()
        if email_val:
            break
    usuario["email"] = email_val
    for campo in ("nombre", "empresa", "matricula", "dni", "titulo", "estado"):
        if campo in usuario:
            usuario[campo] = str(usuario.get(campo, "") or "").strip()
    if not usuario.get("estado"):
        usuario["estado"] = "Activo"
    if perfil:
        usuario["perfil_profesional"] = perfil
    return usuario


def compactar_etiqueta_paciente(nombre, estado):
    nombre = str(nombre or "").strip()
    sufijo = " [ALTA]" if estado == "De Alta" else ""
    limite = 34 if sufijo else 40
    if len(nombre) > limite:
        nombre = f"{nombre[:limite - 3].rstrip()}..."
    return f"{nombre}{sufijo}"
