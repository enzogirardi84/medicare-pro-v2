"""Panel de administracion de usuarios."""
from __future__ import annotations

import streamlit as st

from core.app_logging import log_event
from core.database import guardar_datos
from core.password_crypto import establecer_password_nuevo


def render_admin_usuarios():
    user = st.session_state.get("u_actual", {})
    rol = str(user.get("rol", "")).lower()
    if rol not in ("superadmin", "admin"):
        st.error("🔒 Solo administradores pueden gestionar usuarios.")
        return

    st.markdown("## 👥 Administracion de usuarios")
    st.caption("Gestiona los usuarios del sistema")

    usuarios = st.session_state.get("usuarios_db", {})
    if not isinstance(usuarios, dict):
        usuarios = {}

    # ---- MOSTRAR USUARIOS EXISTENTES ----
    st.markdown("### Usuarios registrados")
    opciones_rol = ["superadmin", "admin", "Medico", "Enfermero/a", "Operativo", "Administrativo"]
    for login, datos in sorted(usuarios.items()):
        with st.container(border=True):
            c1, c2 = st.columns(2)
            c1.text_input("Login", value=login, key=f"au_login_{login}", disabled=True)
            nombre_actual = datos.get("nombre", "")
            nombre_nuevo = c2.text_input("Nombre", value=nombre_actual, key=f"au_nombre_{login}")
            rol_actual = str(datos.get("rol", ""))
            rol_nuevo = c1.selectbox(
                "Rol",
                options=opciones_rol,
                index=opciones_rol.index(rol_actual) if rol_actual in opciones_rol else 0,
                key=f"au_rol_{login}",
            )
            empresa_actual = datos.get("empresa", "")
            empresa_nueva = c2.text_input("Empresa", value=empresa_actual, key=f"au_empresa_{login}")

            c_act1, c_act2 = st.columns(2)
            if c_act1.button("🗑️ Eliminar", use_container_width=True, key=f"au_del_{login}"):
                if st.session_state.get(f"_confirm_del_{login}"):
                    del usuarios[login]
                    st.session_state["usuarios_db"] = usuarios
                    guardar_datos(spinner=False)
                    st.success(f"Usuario '{login}' eliminado")
                    log_event("admin_usuarios", f"eliminado:{login}")
                    st.rerun()
                else:
                    st.session_state[f"_confirm_del_{login}"] = True
                    st.warning(f"Confirma la eliminacion de '{login}' haciendo click otra vez en 🗑️")
            # Save button if changes detected
            if nombre_nuevo != nombre_actual or rol_nuevo != rol_actual or empresa_nueva != empresa_actual:
                if c_act2.button("💾 Guardar cambios", use_container_width=True, key=f"au_save_{login}"):
                    datos["nombre"] = nombre_nuevo
                    datos["rol"] = rol_nuevo
                    datos["empresa"] = empresa_nueva
                    st.session_state["usuarios_db"] = usuarios
                    guardar_datos(spinner=False)
                    st.success(f"Cambios guardados para '{login}'")
                    log_event("admin_usuarios", f"editado:{login}:{rol_nuevo}")
                    st.rerun()

    # ---- CREAR NUEVO USUARIO ----
    st.divider()
    st.markdown("### Crear nuevo usuario")
    with st.form("nuevo_usuario_form"):
        nuevo_login = st.text_input("Login *", placeholder="Ej: jperez")
        nuevo_nombre = st.text_input("Nombre completo *", placeholder="Ej: Juan Perez")
        nuevo_password = st.text_input("Contrasena *", type="password", placeholder="Minimo 6 caracteres")
        nuevo_rol = st.selectbox("Rol", options=opciones_rol, index=0)
        nueva_empresa = st.text_input("Empresa / Clinica", placeholder="Ej: Clinica General")
        if st.form_submit_button("➕ Crear usuario", type="primary"):
            errores = []
            if not nuevo_login.strip():
                errores.append("Login requerido")
            if not nuevo_nombre.strip():
                errores.append("Nombre requerido")
            if not nuevo_password.strip() or len(nuevo_password) < 6:
                errores.append("Contrasena debe tener al menos 6 caracteres")
            if nuevo_login.strip() in usuarios:
                errores.append("El login ya existe")
            if errores:
                for e in errores:
                    st.error(e)
            else:
                uid = nuevo_login.strip()
                usuarios[uid] = {
                    "nombre": nuevo_nombre.strip(),
                    "rol": nuevo_rol,
                    "empresa": nueva_empresa.strip() or "Clinica General",
                    "activo": True,
                }
                establecer_password_nuevo(usuarios[uid], nuevo_password.strip())
                for _login in usuarios:
                    _u = usuarios[_login]
                    if "pass_hash" in _u:
                        _u["password_hash"] = _u["pass_hash"]
                st.session_state["usuarios_db"] = usuarios
                with st.spinner("Guardando..."):
                    guardar_datos()
                st.success(f"Usuario '{uid}' creado")
                log_event("admin_usuarios", f"creado:{uid}:{nuevo_rol}")
                st.rerun()

    # ---- RESETEAR CONTRASENA ----
    st.divider()
    st.markdown("### Resetear contrasena de usuario existente")
    _reset_login = st.selectbox("Seleccionar usuario", options=[""] + sorted(usuarios.keys()), key="reset_pwd_user")
    _reset_pwd = st.text_input("Nueva contrasena", type="password", key="reset_pwd_value")
    if st.button("🔑 Cambiar contrasena", use_container_width=True, key="reset_pwd_btn"):
        if _reset_login and _reset_pwd and len(_reset_pwd) >= 6:
            establecer_password_nuevo(usuarios[_reset_login], _reset_pwd)
            for _login in usuarios:
                _u = usuarios[_login]
                if "pass_hash" in _u:
                    _u["password_hash"] = _u["pass_hash"]
            st.session_state["usuarios_db"] = usuarios
            guardar_datos(spinner=False)
            st.success(f"Contrasena de '{_reset_login}' actualizada")
            log_event("admin_usuarios", f"password_reset:{_reset_login}")
        else:
            st.warning("Selecciona un usuario y una contrasena de al menos 6 caracteres")
