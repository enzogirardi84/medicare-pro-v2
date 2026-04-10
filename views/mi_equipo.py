import streamlit as st

from core.database import guardar_datos
from core.utils import (
    filtrar_registros_empresa,
    inferir_perfil_profesional,
    puede_accion,
    registrar_auditoria_legal,
    seleccionar_limite_registros,
)


def render_mi_equipo(mi_empresa, rol, user=None):
    user = user or {}
    rol_normalizado = str(rol or "").strip().lower()
    st.subheader(f"Gestion de Personal - {mi_empresa}")
    puede_crear = puede_accion(rol, "equipo_crear_usuario")
    puede_cambiar_estado = puede_accion(rol, "equipo_cambiar_estado")
    puede_eliminar = puede_accion(rol, "equipo_eliminar_usuario")

    if puede_crear:
        with st.form("equipo", clear_on_submit=True):
            st.markdown("##### Habilitar Nuevo Usuario")
            col_id, col_pw, col_pin = st.columns([2, 2, 1])
            u_id = col_id.text_input("Usuario (Login)", placeholder="ej: maria.lopez")
            u_pw = col_pw.text_input("Clave de acceso", type="password")
            u_pin = col_pin.text_input("PIN (4 digitos)", max_chars=4, placeholder="1234")

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

            if st.form_submit_button("Habilitar Acceso", use_container_width=True, type="primary"):
                if not u_id or not u_pw or not u_pin or not u_dni:
                    st.error("Todos los campos obligatorios deben completarse.")
                elif len(u_pin) != 4 or not u_pin.isdigit():
                    st.error("El PIN debe tener exactamente 4 digitos numericos.")
                elif u_id.strip().lower() in st.session_state["usuarios_db"]:
                    st.error("El usuario ya existe. Elija otro login.")
                else:
                    st.session_state["usuarios_db"][u_id.strip().lower()] = {
                        "pass": u_pw.strip(),
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
                    registrar_auditoria_legal(
                        "Equipo",
                        "GLOBAL",
                        "Alta de usuario",
                        user.get("nombre", "Sistema"),
                        user.get("matricula", ""),
                        f"Se creo el usuario {u_id.strip().lower()} con rol {u_rl} para {u_emp.strip() if isinstance(u_emp, str) else mi_empresa}.",
                        referencia=u_id.strip().lower(),
                    )
                    guardar_datos()
                    st.success(f"Usuario {u_id} habilitado correctamente.")
                    st.rerun()
    else:
        st.info("La gestion de altas de usuarios queda reservada a coordinacion y administracion total.")

    st.divider()

    st.subheader("Control de Accesos")
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
        st.info("No se encontraron usuarios con ese criterio.")
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

                with col1:
                    perfil_usuario = d.get("perfil_profesional", "") or inferir_perfil_profesional(d) or "Sin perfil"
                    st.markdown(f"**{d.get('nombre', 'Sin nombre')}**")
                    st.caption(
                        f"Empresa: {d.get('empresa', 'S/D')} | "
                        f"Login: {u} | Rol sistema: {d.get('rol', 'S/D')} | "
                        f"Perfil: {perfil_usuario} | Titulo: {d.get('titulo', 'S/D')} | DNI: {d.get('dni', 'S/D')}"
                    )

                with col2:
                    st.markdown(f"**{estado_color}**")

                if puede_cambiar_estado:
                    with col3:
                        if d.get("estado", "Activo") == "Activo":
                            if st.button("Suspender", key=f"susp_{u}", use_container_width=True):
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

                    with col4:
                        if puede_eliminar:
                            seguro = st.checkbox("Confirmar baja", key=f"chk_del_{u}")
                            if st.button(
                                "Eliminar",
                                key=f"del_{u}",
                                use_container_width=True,
                                disabled=not seguro,
                                type="primary" if seguro else "secondary",
                            ):
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
                        else:
                            st.caption("Solo SuperAdmin")

        if not mostro_usuario:
            st.info("No hay otros usuarios cargados aparte del administrador principal.")
