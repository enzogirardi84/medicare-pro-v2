from core.alert_toasts import queue_toast
import re
from html import escape

import streamlit as st

from core.anticolapso import anticolapso_activo
from core.clinicas_control import sincronizar_clinicas_desde_datos
from core.database import guardar_datos
from core.input_validation import email_formato_aceptable
from core.password_crypto import (
    bcrypt_rounds_config,
    establecer_password_nuevo,
    mensaje_password_no_cumple_politica,
    password_min_length,
)
from core.utils import (
    actor_puede_modificar_usuario_equipo,
    bloqueo_autoservicio_suspension_baja,
    filtrar_registros_empresa,
    inferir_perfil_profesional,
    mi_equipo_mostrar_ui_eliminar,
    mi_equipo_mostrar_ui_suspender,
    modo_celular_viejo_activo,
    normalizar_usuario_sistema,
    obtener_email_usuario,
    obtener_pin_usuario,
    puede_accion,
    puede_eliminar_cuenta_equipo,
    puede_suspender_reactivar_usuario_mi_equipo,
    registrar_auditoria_legal,
    seleccionar_limite_registros,
)
from core.view_helpers import bloque_mc_grid_tarjetas, lista_plegable
from views._mi_equipo_bloques import (
    _widget_key_equipo,
    _validar_alta_usuario_equipo,
    _render_pings_seguridad_usuario,
    _mi_equipo_bloque_principal,
    _mi_equipo_bloque_suspender,
    _mi_equipo_bloque_eliminar,
)



def render_mi_equipo(mi_empresa, rol, user=None):
    # Siempre el rol canonico desde la sesion (evita desalineacion argumento vs u_actual y sesiones previas al login normalizado).
    raw_u = st.session_state.get("u_actual")
    if isinstance(raw_u, dict):
        canon = normalizar_usuario_sistema(dict(raw_u))
        merged = dict(raw_u)
        _cambio = False
        for _k in ("rol", "perfil_profesional"):
            if _k in canon and canon.get(_k) != raw_u.get(_k):
                merged[_k] = canon[_k]
                _cambio = True
        if _cambio:
            st.session_state["u_actual"] = merged
        user = st.session_state["u_actual"]
        rol = user.get("rol") or rol
    else:
        user = dict(user or {})
        user = normalizar_usuario_sistema(user)
        rol = user.get("rol") or rol

    rol_normalizado = str(rol or "").strip().lower()
    emp_e = escape(str(mi_empresa or ""))
    st.markdown(
        f"""
        <div class="mc-hero">
            <h2 class="mc-hero-title">Mi equipo y usuarios</h2>
            <p class="mc-hero-text">Alta de logins, roles, matriculas y perfiles para {emp_e}. Las acciones sensibles quedan sujetas a permisos y auditoria legal.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Usuarios</span>
                <span class="mc-chip">Roles</span>
                <span class="mc-chip">Matricula</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ("Alta", "Login, clave, correo y PIN opcional para nuevos accesos."),
            ("Control", "Busqueda y gestion por rol: SuperAdmin o Coordinador en su clinica, segun reglas."),
            ("Rol vs perfil", "Rol = permisos en el sistema; perfil = agenda y filtros asistenciales."),
        ]
    )
    st.caption(
        "El listado de abajo muestra solo usuarios de **tu clinica** (salvo administradores globales). "
        "El login **admin** de emergencia no aparece en la grilla."
    )
    puede_crear = puede_accion(rol, "equipo_crear_usuario")
    puede_editar_mail_equipo = puede_accion(rol, "equipo_editar_email_usuario")
    # Capacidad por rol (para leyendas); los botones usan mi_equipo_mostrar_ui_* fila a fila.
    puede_suspender = puede_suspender_reactivar_usuario_mi_equipo(rol)
    puede_eliminar = puede_eliminar_cuenta_equipo(rol)
    tiene_rol_bajas = puede_suspender or puede_eliminar

    if puede_crear:
        with st.expander("Habilitar nuevo usuario al equipo", expanded=False):
            st.caption(
                "Login, contraseña y DNI son obligatorios. PIN y correo opcionales según política de la clínica."
            )
            # clear_on_submit=False: si falla la validación (p. ej. contraseña corta), los datos siguen cargados;
            # al guardar OK hacemos st.rerun() y el formulario vuelve vacío.
            with st.form("equipo_alta_usuario", clear_on_submit=False):
                st.markdown("##### Datos del nuevo acceso")
                col_id, col_pw, col_pin = st.columns([2, 2, 1])
                u_id = col_id.text_input("Usuario (Login)", placeholder="ej: maria.lopez")
                with col_pw:
                    u_pw = st.text_input("Clave de acceso", type="password")
                    st.caption(f"Mínimo {password_min_length()} caracteres (configurable en secrets).")
                u_pin = col_pin.text_input("PIN opcional", max_chars=4, placeholder="1234")

                u_nm = st.text_input("Nombre Completo del Profesional")
                col_dni, col_mt = st.columns(2)
                u_dni = col_dni.text_input("DNI del Profesional")
                u_mt = col_mt.text_input("Matricula / Matricula Profesional")

                u_ti = st.selectbox(
                    "Titulo / Cargo",
                    [
                        "Medico/a",
                        "Lic. en Enfermeria",
                        "Enfermero/a",
                        "Kinesiologo/a",
                        "Fonoaudiologo/a",
                        "Nutricionista",
                        "Psicologo/a",
                        "Acompanante Terapeutico",
                        "Trabajador/a Social",
                        "Administrativo/a",
                        "Otro",
                    ],
                )
                u_pf = st.selectbox(
                    "Perfil profesional / area del equipo",
                    [
                        "Medico",
                        "Enfermeria",
                        "Operativo",
                        "Administrativo",
                        "Coordinacion",
                        "Direccion",
                    ],
                )

                u_emp = st.text_input("Asignar a Clinica / Empresa", value=mi_empresa) if rol_normalizado == "superadmin" else mi_empresa
                u_rl = st.selectbox(
                    "Rol en el sistema",
                    (
                        ["Operativo", "Coordinador", "SuperAdmin"]
                        if rol_normalizado == "superadmin"
                        else ["Operativo", "Coordinador"]
                    ),
                )
                st.caption("El rol define accesos del sistema. El perfil profesional se usa para agenda, equipo y filtros asistenciales.")
                st.caption(
                    "Ingreso con login + contraseña. **Clave nueva:** la asigna coordinación desde Mi equipo. "
                    "El correo en ficha puede usarse para 2FA si hay SMTP. PIN opcional interno."
                )
                u_email = st.text_input(
                    "Correo electrónico",
                    placeholder="profesional@clinica.com",
                )

                if st.form_submit_button("Habilitar Acceso", use_container_width=True, type="primary"):
                    err_alta = _validar_alta_usuario_equipo(u_id, u_pw, u_dni, u_pin, u_email)
                    if err_alta:
                        st.error(err_alta)
                    else:
                        uid = u_id.strip().lower()
                        st.session_state["usuarios_db"][uid] = {
                            "nombre": u_nm.strip(),
                            "rol": u_rl,
                            "titulo": u_ti,
                            "perfil_profesional": u_pf,
                            "empresa": u_emp.strip() if isinstance(u_emp, str) else mi_empresa,
                            "matricula": u_mt.strip(),
                            "dni": u_dni.strip(),
                            "estado": "Activo",
                            "pin": u_pin.strip(),
                        }
                        establecer_password_nuevo(
                            st.session_state["usuarios_db"][uid],
                            u_pw.strip(),
                            rounds=bcrypt_rounds_config(),
                        )
                        if u_email.strip():
                            st.session_state["usuarios_db"][uid]["email"] = u_email.strip().lower()
                        registrar_auditoria_legal(
                            "Equipo",
                            "GLOBAL",
                            "Alta de usuario",
                            user.get("nombre", "Sistema"),
                            user.get("matricula", ""),
                            f"Se creo el usuario {u_id.strip().lower()} con rol {u_rl} para {u_emp.strip() if isinstance(u_emp, str) else mi_empresa}.",
                            referencia=u_id.strip().lower(),
                        )
                        sincronizar_clinicas_desde_datos(st.session_state)
                        guardar_datos(spinner=True)
                        queue_toast(f"Usuario {u_id} habilitado correctamente.")
                        st.rerun()
    else:
        st.info("La gestion de altas de usuarios queda reservada a coordinacion y administracion total.")

    st.divider()

    st.subheader("Control de Accesos")
    with st.expander("Ayuda: PIN, coordinación y bajas", expanded=False):
        st.markdown(
            "**PIN y clave:** quien puede gestionar ve el PIN en un recuadro compacto y el expander "
            "**Coordinación: nueva contraseña y/o PIN**. La contraseña la cambia coordinación desde acá "
            "(no hay recuperación automática por correo en el login).\n\n"
            "**Suspender / Eliminar:** solo **SuperAdmin** o **Coordinador** de la clínica (según reglas). "
            "Otros roles no ven esas acciones en la grilla."
        )
    compacto_equipo = modo_celular_viejo_activo(st.session_state) or anticolapso_activo()
    if compacto_equipo:
        st.caption(
            "Vista compacta (Versión Lite automática en móvil o equipo limitado): fichas apiladas y lista más baja."
        )
    buscar_usuario = st.text_input("Buscar usuario por nombre, login o DNI...", "")

    usuarios_base = []
    
    # 1. Intentar leer desde PostgreSQL (Hybrid Read)
    try:
        from core.db_sql import check_supabase_connection
        from core.database import supabase
        from core.nextgen_sync import _obtener_uuid_empresa
        
        if check_supabase_connection():
            empresa_uuid = _obtener_uuid_empresa(mi_empresa)
            if empresa_uuid:
                res = supabase.table("usuarios").select("*").eq("empresa_id", empresa_uuid).execute()
                if res.data:
                    for u_sql in res.data:
                        fila = {
                            "_login": u_sql["nombre"],
                            "nombre": u_sql["nombre"],
                            "rol": u_sql["rol"],
                            "empresa": mi_empresa,
                            "matricula": u_sql.get("matricula", ""),
                            "dni": u_sql.get("dni", ""),
                            "titulo": u_sql.get("titulo", ""),
                            "estado": u_sql.get("estado", "Activo"),
                            "email": u_sql.get("email", ""),
                            "pass": u_sql.get("password_hash", "")
                        }
                        usuarios_base.append(fila)
    except Exception as e:
        from core.app_logging import log_event
        log_event("error_leer_usuarios_sql", str(e))

    # 2. Fallback a JSON si SQL falla o esta vacio
    if not usuarios_base:
        for login, datos in st.session_state["usuarios_db"].items():
            fila = dict(datos)
            fila["_login"] = login
            usuarios_base.append(fila)

    usuarios_filtrados = {
        fila["_login"]: {k: v for k, v in fila.items() if k != "_login"}
        for fila in filtrar_registros_empresa(usuarios_base, mi_empresa, rol)
        if (
            not buscar_usuario
            or buscar_usuario.lower() in fila["_login"].lower()
            or buscar_usuario.lower() in fila.get("nombre", "").lower()
            or buscar_usuario.lower() in str(fila.get("dni", "")).lower()
        )
    }

    if not usuarios_filtrados:
        st.warning(
            "No hay usuarios que coincidan con la busqueda o con el filtro de clinica. Limpiá el texto o verifica que el equipo este dado de alta."
        )
        return

    st.caption(f"Mostrando {len(usuarios_filtrados)} usuarios")
    usuarios_ordenados = [(u, d) for u, d in usuarios_filtrados.items() if u != "admin"]
    limite = seleccionar_limite_registros(
        "Usuarios a mostrar",
        len(usuarios_ordenados),
        key="equipo_limite_usuarios",
        default=20,
        opciones=(10, 20, 30, 50, 100, 200),
    )
    altura_lista_equipo = 400 if compacto_equipo else 520
    with lista_plegable(
        "Listado del equipo (fichas y permisos)",
        count=min(limite, len(usuarios_ordenados)),
        expanded=False,
        height=altura_lista_equipo,
    ):
        mostro_usuario = False
        for u, d in usuarios_ordenados[:limite]:
            mostro_usuario = True
            estado_txt = "Activo" if d.get("estado", "Activo") == "Activo" else "Bloqueado"
            ok_gestionar, motivo_sin_gestion = actor_puede_modificar_usuario_equipo(rol, mi_empresa, d)
            mostrar_ui_suspender = mi_equipo_mostrar_ui_suspender(user, ok_gestionar)
            mostrar_ui_eliminar = mi_equipo_mostrar_ui_eliminar(user, d, mi_empresa, ok_gestionar)
            with st.container(border=True):
                if compacto_equipo:
                    h1, h2 = st.columns([2, 1])
                    with h1:
                        st.markdown(f"**{d.get('nombre', 'Sin nombre')}**")
                    with h2:
                        st.caption(f"Estado\n**{estado_txt}**")
                    _mi_equipo_bloque_principal(
                        u,
                        d,
                        user=user,
                        rol=rol,
                        mi_empresa=mi_empresa,
                        ok_gestionar=ok_gestionar,
                        puede_editar_mail_equipo=puede_editar_mail_equipo,
                        motivo_sin_gestion=motivo_sin_gestion,
                        omitir_titulo=True,
                    )
                    st.divider()
                    _mi_equipo_bloque_suspender(
                        u,
                        d,
                        user=user,
                        rol=rol,
                        mi_empresa=mi_empresa,
                        mostrar_ui_suspender=mostrar_ui_suspender,
                        ok_gestionar=ok_gestionar,
                        tiene_rol_bajas=tiene_rol_bajas,
                    )
                    _mi_equipo_bloque_eliminar(
                        u,
                        d,
                        user=user,
                        rol=rol,
                        mi_empresa=mi_empresa,
                        mostrar_ui_eliminar=mostrar_ui_eliminar,
                        ok_gestionar=ok_gestionar,
                        puede_eliminar=puede_eliminar,
                    )
                else:
                    col1, col2, col3, col4 = st.columns([3.6, 0.45, 1.05, 1.05])
                    with col1:
                        _mi_equipo_bloque_principal(
                            u,
                            d,
                            user=user,
                            rol=rol,
                            mi_empresa=mi_empresa,
                            ok_gestionar=ok_gestionar,
                            puede_editar_mail_equipo=puede_editar_mail_equipo,
                            motivo_sin_gestion=motivo_sin_gestion,
                            omitir_titulo=False,
                        )
                    with col2:
                        st.markdown(f"**{estado_txt}**")
                    with col3:
                        _mi_equipo_bloque_suspender(
                            u,
                            d,
                            user=user,
                            rol=rol,
                            mi_empresa=mi_empresa,
                            mostrar_ui_suspender=mostrar_ui_suspender,
                            ok_gestionar=ok_gestionar,
                            tiene_rol_bajas=tiene_rol_bajas,
                        )
                    with col4:
                        _mi_equipo_bloque_eliminar(
                            u,
                            d,
                            user=user,
                            rol=rol,
                            mi_empresa=mi_empresa,
                            mostrar_ui_eliminar=mostrar_ui_eliminar,
                            ok_gestionar=ok_gestionar,
                            puede_eliminar=puede_eliminar,
                        )
        if not mostro_usuario:
            st.warning(
                "No hay usuarios para mostrar en este rango (solo queda **admin** o el limite oculta filas). Aumenta **Usuarios a mostrar** o da de alta personal con el formulario de arriba."
            )
