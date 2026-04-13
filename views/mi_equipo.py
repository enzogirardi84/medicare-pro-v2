from html import escape

import streamlit as st

from core.clinicas_control import sincronizar_clinicas_desde_datos
from core.database import guardar_datos
from core.input_validation import email_formato_aceptable
from core.password_crypto import (
    bcrypt_rounds_config,
    establecer_password_nuevo,
    mensaje_password_no_cumple_politica,
    password_min_length,
)
from core.view_helpers import bloque_mc_grid_tarjetas
from core.utils import (
    actor_puede_modificar_usuario_equipo,
    bloqueo_autoservicio_suspension_baja,
    filtrar_registros_empresa,
    inferir_perfil_profesional,
    mi_equipo_mostrar_ui_eliminar,
    mi_equipo_mostrar_ui_suspender,
    normalizar_usuario_sistema,
    obtener_email_usuario,
    obtener_password_usuario,
    obtener_pin_usuario,
    puede_accion,
    puede_eliminar_cuenta_equipo,
    puede_suspender_reactivar_usuario_mi_equipo,
    registrar_auditoria_legal,
    seleccionar_limite_registros,
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
            ("Alta", "Login, clave, correo de recuperacion y PIN opcional para nuevos accesos."),
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
        with st.form("equipo", clear_on_submit=True):
            st.markdown("##### Habilitar Nuevo Usuario")
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
                    ["Administrativo", "Coordinador", "SuperAdmin"]
                    if rol_normalizado == "superadmin"
                    else ["Administrativo", "Coordinador"]
                ),
            )
            st.caption("El rol define accesos del sistema. El perfil profesional se usa para agenda, equipo y filtros asistenciales.")
            st.caption("El ingreso normal es con login + contrasena. El correo sirve para recuperar la clave y el PIN queda opcional como respaldo.")
            u_email = st.text_input(
                "Correo de recuperacion",
                placeholder="profesional@clinica.com",
            )

            if st.form_submit_button("Habilitar Acceso", use_container_width=True, type="primary"):
                if not u_id or not u_pw or not u_dni:
                    st.error("Todos los campos obligatorios deben completarse.")
                elif u_pin.strip() and (len(u_pin.strip()) != 4 or not u_pin.strip().isdigit()):
                    st.error("Si cargas PIN, debe tener exactamente 4 digitos numericos.")
                elif (pw_err := mensaje_password_no_cumple_politica(u_pw.strip())):
                    st.error(pw_err)
                elif u_email.strip() and not email_formato_aceptable(u_email.strip()):
                    st.error("El formato del correo electrónico no es válido.")
                elif u_id.strip().lower() in st.session_state["usuarios_db"]:
                    st.error("El usuario ya existe. Elija otro login.")
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
                    guardar_datos()
                    st.success(f"Usuario {u_id} habilitado correctamente.")
                    st.rerun()
    else:
        st.info("La gestion de altas de usuarios queda reservada a coordinacion y administracion total.")

    st.divider()

    st.subheader("Control de Accesos")
    st.caption(
        "**Suspender / Reactivar / Eliminar:** **SuperAdmin** o **Coordinador** en su clinica "
        "(sin cuentas globales). **Administrativo**, **Operativo** y roles clinicos: no ven suspension ni baja en esta grilla."
    )
    buscar_usuario = st.text_input("Buscar usuario por nombre, login o DNI...", "")

    usuarios_base = []
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
    with st.container(height=620, border=True):
        mostro_usuario = False
        for u, d in usuarios_ordenados[:limite]:
            mostro_usuario = True
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns([3.5, 1, 1.2, 1.2])
                estado_color = "Activo" if d.get("estado", "Activo") == "Activo" else "Bloqueado"
                ok_gestionar, motivo_sin_gestion = actor_puede_modificar_usuario_equipo(rol, mi_empresa, d)
                mostrar_ui_suspender = mi_equipo_mostrar_ui_suspender(user, ok_gestionar)
                mostrar_ui_eliminar = mi_equipo_mostrar_ui_eliminar(user, d, mi_empresa, ok_gestionar)

                with col1:
                    d_norm = normalizar_usuario_sistema(dict(d))
                    perfil_usuario = d_norm.get("perfil_profesional", "") or inferir_perfil_profesional(d_norm) or "Sin perfil"
                    email_actual = obtener_email_usuario(d_norm)
                    pin_actual = obtener_pin_usuario(d_norm)
                    clave_configurada = bool(d_norm.get("pass_hash") or obtener_password_usuario(d_norm))
                    st.markdown(f"**{d.get('nombre', 'Sin nombre')}**")
                    st.caption(
                        f"Empresa: {d.get('empresa', 'S/D')} | "
                        f"Login: {u} | Rol sistema: {d.get('rol', 'S/D')} | "
                        f"Perfil: {perfil_usuario} | Titulo: {d.get('titulo', 'S/D')} | DNI: {d.get('dni', 'S/D')}"
                    )
                    st.caption(
                        f"Acceso: login {u} | correo recuperacion: {email_actual or 'Sin correo'} | "
                        f"PIN opcional: {pin_actual or 'No configurado'} | "
                        f"Clave: {'Configurada' if clave_configurada else 'Pendiente'}"
                    )
                    if puede_editar_mail_equipo and ok_gestionar:
                        with st.expander("Recuperacion y credenciales", expanded=False):
                            ne = st.text_input("Correo de recuperacion", value=email_actual, key=f"emp_mail_new_{u}")
                            np = st.text_input("PIN opcional", value=pin_actual, max_chars=4, key=f"emp_pin_{u}")
                            nueva_pass = st.text_input("Nueva contrasena (opcional)", type="password", key=f"emp_pass_{u}")
                            if st.button("Guardar acceso", key=f"btn_access_{u}"):
                                ok_m, msg_m = actor_puede_modificar_usuario_equipo(rol, mi_empresa, d)
                                if not ok_m:
                                    st.error(msg_m)
                                else:
                                    ne_l = ne.strip().lower()
                                    np_l = np.strip()
                                    if ne_l and not email_formato_aceptable(ne_l):
                                        st.error("El formato del correo electronico no es valido.")
                                    elif np_l and (len(np_l) != 4 or not np_l.isdigit()):
                                        st.error("Si cargas PIN, debe tener exactamente 4 digitos numericos.")
                                    elif nueva_pass.strip() and (pw_err := mensaje_password_no_cumple_politica(nueva_pass.strip())):
                                        st.error(pw_err)
                                    else:
                                        st.session_state["usuarios_db"][u]["email"] = ne_l
                                        st.session_state["usuarios_db"][u]["pin"] = np_l
                                        if nueva_pass.strip():
                                            establecer_password_nuevo(
                                                st.session_state["usuarios_db"][u],
                                                nueva_pass.strip(),
                                                rounds=bcrypt_rounds_config(),
                                            )
                                        registrar_auditoria_legal(
                                            "Equipo",
                                            "GLOBAL",
                                            "Actualizacion acceso usuario",
                                            user.get("nombre", "Sistema"),
                                            user.get("matricula", ""),
                                            f"Se actualizo acceso del usuario {u}. Correo: {'si' if ne_l else 'no'} | PIN: {'si' if np_l else 'no'} | Clave: {'si' if nueva_pass.strip() else 'sin cambios'}.",
                                            referencia=u,
                                        )
                                        guardar_datos()
                                        st.rerun()
                    elif puede_editar_mail_equipo and not ok_gestionar:
                        st.caption(motivo_sin_gestion)

                with col2:
                    st.markdown(f"**{estado_color}**")

                with col3:
                    if mostrar_ui_suspender:
                        if d.get("estado", "Activo") == "Activo":
                            if st.button("Suspender", key=f"susp_{u}", use_container_width=True):
                                if not puede_suspender_reactivar_usuario_mi_equipo(rol):
                                    st.error("Tu rol no puede suspender usuarios (solo SuperAdmin o Coordinador de la misma clinica).")
                                else:
                                    blk, msg_blk = bloqueo_autoservicio_suspension_baja(
                                        user.get("usuario_login"), u, rol
                                    )
                                    if blk:
                                        st.error(msg_blk)
                                    else:
                                        ok_m, msg_m = actor_puede_modificar_usuario_equipo(rol, mi_empresa, d)
                                        if not ok_m:
                                            st.error(msg_m)
                                        else:
                                            st.session_state["usuarios_db"][u]["estado"] = "Bloqueado"
                                            registrar_auditoria_legal(
                                                "Equipo",
                                                "GLOBAL",
                                                "Suspension de usuario",
                                                user.get("nombre", "Sistema"),
                                                user.get("matricula", ""),
                                                f"Se suspendio el usuario {u}.",
                                                referencia=u,
                                            )
                                            guardar_datos()
                                            st.rerun()
                        else:
                            if st.button("Reactivar", key=f"reac_{u}", use_container_width=True):
                                if not puede_suspender_reactivar_usuario_mi_equipo(rol):
                                    st.error("Tu rol no puede reactivar usuarios (solo SuperAdmin o Coordinador de la misma clinica).")
                                else:
                                    blk, msg_blk = bloqueo_autoservicio_suspension_baja(
                                        user.get("usuario_login"), u, rol
                                    )
                                    if blk:
                                        st.error(msg_blk)
                                    else:
                                        ok_m, msg_m = actor_puede_modificar_usuario_equipo(rol, mi_empresa, d)
                                        if not ok_m:
                                            st.error(msg_m)
                                        else:
                                            st.session_state["usuarios_db"][u]["estado"] = "Activo"
                                            registrar_auditoria_legal(
                                                "Equipo",
                                                "GLOBAL",
                                                "Reactivacion de usuario",
                                                user.get("nombre", "Sistema"),
                                                user.get("matricula", ""),
                                                f"Se reactivo el usuario {u}.",
                                                referencia=u,
                                            )
                                            guardar_datos()
                                            st.rerun()
                    elif tiene_rol_bajas and not ok_gestionar:
                        st.caption("—")
                    elif not tiene_rol_bajas:
                        pass
                    else:
                        st.caption("—")

                with col4:
                    if mostrar_ui_eliminar:
                        seguro = st.checkbox("Confirmar baja", key=f"chk_del_{u}")
                        st.caption("La eliminación es permanente y quita el usuario del sistema.")
                        if st.button(
                            "Eliminar",
                            key=f"del_{u}",
                            use_container_width=True,
                            disabled=not seguro,
                            type="secondary",
                        ):
                            if not puede_eliminar_cuenta_equipo(rol):
                                st.error("Tu rol no puede eliminar usuarios (solo SuperAdmin o Coordinador de la misma clinica).")
                            else:
                                blk, msg_blk = bloqueo_autoservicio_suspension_baja(
                                    user.get("usuario_login"), u, rol
                                )
                                if blk:
                                    st.error(msg_blk)
                                else:
                                    ok_m, msg_m = actor_puede_modificar_usuario_equipo(rol, mi_empresa, d)
                                    if not ok_m:
                                        st.error(msg_m)
                                    else:
                                        registrar_auditoria_legal(
                                            "Equipo",
                                            "GLOBAL",
                                            "Eliminacion de usuario",
                                            user.get("nombre", "Sistema"),
                                            user.get("matricula", ""),
                                            f"Se elimino el usuario {u}.",
                                            referencia=u,
                                        )
                                        del st.session_state["usuarios_db"][u]
                                        guardar_datos()
                                        st.toast(f"Usuario {u} eliminado.")
                                        st.rerun()
                    elif puede_eliminar and not ok_gestionar:
                        st.caption("—")
                    elif not puede_eliminar:
                        pass

        if not mostro_usuario:
            st.warning(
                "No hay usuarios para mostrar en este rango (solo queda **admin** o el limite oculta filas). Aumenta **Usuarios a mostrar** o da de alta personal con el formulario de arriba."
            )
