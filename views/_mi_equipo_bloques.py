"""Bloques UI reutilizables de Mi Equipo. Extraído de views/mi_equipo.py."""
import re
from html import escape

import streamlit as st

from core.database import guardar_datos
from core.email_2fa import login_email_2fa_enabled, smtp_config_ok, usuario_email_2fa_valido
from core.input_validation import email_formato_aceptable
from core.password_crypto import (
    bcrypt_rounds_config,
    establecer_password_nuevo,
    mensaje_password_no_cumple_politica,
)
from core.utils import (
    actor_puede_modificar_usuario_equipo,
    bloqueo_autoservicio_suspension_baja,
    inferir_perfil_profesional,
    normalizar_usuario_sistema,
    obtener_email_usuario,
    obtener_pin_usuario,
    puede_eliminar_cuenta_equipo,
    puede_suspender_reactivar_usuario_mi_equipo,
    registrar_auditoria_legal,
)
from core.alert_toasts import queue_toast


def _widget_key_equipo(login: str, parte: str) -> str:
    """Claves estables para widgets Streamlit (login puede tener espacios)."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(login or "").strip()).strip("_") or "user"
    return f"eq_{parte}_{slug}"


def _validar_alta_usuario_equipo(u_id, u_pw, u_dni, u_pin, u_email) -> str | None:
    """Validación del formulario de alta. Devuelve mensaje de error o None si puede continuar."""
    if not u_id or not u_pw or not u_dni:
        return "Todos los campos obligatorios deben completarse."
    if u_pin.strip() and (len(u_pin.strip()) != 4 or not u_pin.strip().isdigit()):
        return "Si cargas PIN, debe tener exactamente 4 digitos numericos."
    if (pw_err := mensaje_password_no_cumple_politica(u_pw.strip())):
        return pw_err
    if u_email.strip() and not email_formato_aceptable(u_email.strip()):
        return "El formato del correo electrónico no es válido."
    if u_id.strip().lower() in st.session_state.get("usuarios_db", {}):
        return "El usuario ya existe. Elija otro login."
    return None


def _render_pings_seguridad_usuario(d: dict, *, puede_ver_pin: bool = False) -> None:
    """Estado de clave, PIN (recuperación) y correo/2FA."""
    ph = str(d.get("pass_hash") or "").strip()
    pw = str(d.get("pass") or "").strip()
    tiene_clave = bool(ph or pw)
    pin = str(d.get("pin") or "").strip()
    pin_ok = len(pin) == 4 and pin.isdigit()

    st.caption(
        "**Clave de acceso:** "
        + ("asignada" if tiene_clave else "sin clave (alta o pedí clave a coordinación)")
    )

    if puede_ver_pin:
        if pin_ok:
            st.markdown(
                "<div class='mc-mi-equipo-pin-ok' role='status'>"
                "<span class='mc-mi-equipo-pin-label'>PIN recuperación</span> "
                f"<code class='mc-mi-equipo-pin-code'>{escape(pin)}</code>"
                "<span class='mc-mi-equipo-pin-hint'> Opcional (procesos internos). La clave nueva la asigna coordinación desde Mi equipo.</span>"
                "</div>",
                unsafe_allow_html=True,
            )
        elif not pin:
            st.markdown(
                "<div class='mc-mi-equipo-pin-warn' role='alert'>"
                "<strong>Sin PIN.</strong> Opcional. El correo en ficha puede usarse para avisos o 2FA si hay SMTP; "
                "la clave la define coordinación.</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div class='mc-mi-equipo-pin-warn' role='alert'>"
                "<strong>PIN inválido:</strong> deben ser exactamente 4 dígitos numéricos.</div>",
                unsafe_allow_html=True,
            )
    else:
        if pin_ok:
            st.caption(
                "**PIN:** configurado (oculto). Un **SuperAdmin** o **Coordinador** con permiso de gestión ve el valor aquí."
            )
        else:
            st.caption("**PIN:** sin definir o inválido.")

    if login_email_2fa_enabled() and smtp_config_ok():
        if usuario_email_2fa_valido(d):
            st.caption("**2FA correo:** listo (código al iniciar sesión).")
        else:
            em = str(d.get("email") or "").strip()
            if em:
                st.caption("**2FA correo:** correo cargado pero formato no válido para envío.")
            else:
                st.caption("**2FA correo:** sin correo — ingreso solo con contraseña hasta cargar email.")
    else:
        em_ok = bool(str(d.get("email") or "").strip()) and email_formato_aceptable(
            str(d.get("email") or "").strip()
        )
        if em_ok:
            st.caption("**Correo:** OK (verificación por correo desactivada en el servidor).")
        elif str(d.get("email") or "").strip():
            st.caption("**Correo:** formato no válido.")
        else:
            st.caption("**Correo:** sin cargar.")


def _mi_equipo_bloque_principal(
    u: str,
    d: dict,
    *,
    user: dict,
    rol: str,
    mi_empresa: str,
    ok_gestionar: bool,
    puede_editar_mail_equipo: bool,
    motivo_sin_gestion: str,
    omitir_titulo: bool,
) -> None:
    if not omitir_titulo:
        st.markdown(f"**{d.get('nombre', 'Sin nombre')}**")
    d_norm = normalizar_usuario_sistema(dict(d))
    perfil_usuario = d_norm.get("perfil_profesional", "") or inferir_perfil_profesional(d_norm) or "Sin perfil"
    email_actual = obtener_email_usuario(d_norm)
    pin_actual = obtener_pin_usuario(d_norm)
    st.caption(
        f"Empresa: {d.get('empresa', 'S/D')} · Login: {u} · Rol: {d.get('rol', 'S/D')} · "
        f"Perfil: {perfil_usuario}"
    )
    st.caption(f"Título: {d.get('titulo', 'S/D')} · DNI: {d.get('dni', 'S/D')}")
    _render_pings_seguridad_usuario(d, puede_ver_pin=ok_gestionar)
    if ok_gestionar:
        with st.expander("Coordinación: nueva contraseña y/o PIN", expanded=False):
            st.caption(
                "Podés **asignar una clave nueva** desde acá o **definir/cambiar el PIN** de 4 dígitos (opcional, respaldo interno). "
                "Sin correo de recuperación: el usuario puede usar **Nueva contraseña con PIN** en el login si tiene PIN cargado; "
                "si no, la clave nueva la asignás desde acá."
            )
            ch_pin = st.text_input(
                "PIN de recuperación (4 dígitos, opcional)",
                max_chars=4,
                key=_widget_key_equipo(u, "ch_pin"),
                placeholder="Ej. 4821",
            )
            ch_pw = st.text_input(
                "Nueva contraseña (opcional si solo actualizás PIN)",
                type="password",
                key=_widget_key_equipo(u, "ch_pw"),
            )
            ch_pw2 = st.text_input(
                "Repetir contraseña",
                type="password",
                key=_widget_key_equipo(u, "ch_pw2"),
            )
            if st.button("Guardar", key=_widget_key_equipo(u, "ch_btn"), width='stretch'):
                pin_l = str(ch_pin).strip()
                pw_l = str(ch_pw).strip()
                pw2_l = str(ch_pw2).strip()
                if pin_l and (len(pin_l) != 4 or not pin_l.isdigit()):
                    st.error("El PIN debe ser exactamente 4 dígitos numéricos.")
                elif not pw_l and not pin_l:
                    st.error("Completá una nueva contraseña o un PIN para guardar.")
                elif pw_l and pw_l != pw2_l:
                    st.error("Las contraseñas no coinciden.")
                elif pw_l:
                    msg_pw = mensaje_password_no_cumple_politica(ch_pw)
                    if msg_pw:
                        st.error(msg_pw)
                    else:
                        if pin_l:
                            st.session_state["usuarios_db"][u]["pin"] = pin_l
                        establecer_password_nuevo(
                            st.session_state["usuarios_db"][u],
                            pw_l,
                            rounds=bcrypt_rounds_config(),
                        )
                        registrar_auditoria_legal(
                            "Equipo", "GLOBAL", "Cambio de contraseña por coordinacion",
                            user.get("nombre", "Sistema"), user.get("matricula", ""),
                            f"Nueva clave asignada a {u}" + ("; PIN actualizado." if pin_l else "."),
                            referencia=u,
                        )
                        guardar_datos(spinner=True)
                        queue_toast("Contraseña actualizada.")
                        st.rerun()
                else:
                    st.session_state["usuarios_db"][u]["pin"] = pin_l
                    registrar_auditoria_legal(
                        "Equipo", "GLOBAL", "Actualizacion PIN por coordinacion",
                        user.get("nombre", "Sistema"), user.get("matricula", ""),
                        f"PIN de recuperacion actualizado para {u}.",
                        referencia=u,
                    )
                    guardar_datos(spinner=True)
                    queue_toast("PIN actualizado.")
                    st.rerun()
    if puede_editar_mail_equipo and ok_gestionar:
        with st.expander("Recuperacion y credenciales", expanded=False):
            ne = st.text_input("Correo electrónico", value=email_actual, key=f"emp_mail_new_{u}")
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
                            "Equipo", "GLOBAL", "Actualizacion acceso usuario",
                            user.get("nombre", "Sistema"), user.get("matricula", ""),
                            f"Se actualizo acceso del usuario {u}. Correo: {'si' if ne_l else 'no'} | PIN: {'si' if np_l else 'no'} | Clave: {'si' if nueva_pass.strip() else 'sin cambios'}.",
                            referencia=u,
                        )
                        guardar_datos(spinner=True)
                        st.rerun()
    elif puede_editar_mail_equipo and not ok_gestionar:
        st.caption(motivo_sin_gestion)


def _mi_equipo_bloque_suspender(
    u: str,
    d: dict,
    *,
    user: dict,
    rol: str,
    mi_empresa: str,
    mostrar_ui_suspender: bool,
    ok_gestionar: bool,
    tiene_rol_bajas: bool,
) -> None:
    if mostrar_ui_suspender:
        if d.get("estado", "Activo") == "Activo":
            if st.button("Suspender", key=f"susp_{u}", width='stretch'):
                if not puede_suspender_reactivar_usuario_mi_equipo(rol):
                    st.error("Tu rol no puede suspender usuarios (solo SuperAdmin o Coordinador de la misma clinica).")
                else:
                    blk, msg_blk = bloqueo_autoservicio_suspension_baja(user.get("usuario_login"), u, rol)
                    if blk:
                        st.error(msg_blk)
                    else:
                        ok_m, msg_m = actor_puede_modificar_usuario_equipo(rol, mi_empresa, d)
                        if not ok_m:
                            st.error(msg_m)
                        else:
                            st.session_state["usuarios_db"][u]["estado"] = "Bloqueado"
                            registrar_auditoria_legal(
                                "Equipo", "GLOBAL", "Suspension de usuario",
                                user.get("nombre", "Sistema"), user.get("matricula", ""),
                                f"Se suspendio el usuario {u}.", referencia=u,
                            )
                            guardar_datos(spinner=True)
                            st.rerun()
        else:
            if st.button("Reactivar", key=f"reac_{u}", width='stretch'):
                if not puede_suspender_reactivar_usuario_mi_equipo(rol):
                    st.error("Tu rol no puede reactivar usuarios (solo SuperAdmin o Coordinador de la misma clinica).")
                else:
                    blk, msg_blk = bloqueo_autoservicio_suspension_baja(user.get("usuario_login"), u, rol)
                    if blk:
                        st.error(msg_blk)
                    else:
                        ok_m, msg_m = actor_puede_modificar_usuario_equipo(rol, mi_empresa, d)
                        if not ok_m:
                            st.error(msg_m)
                        else:
                            st.session_state["usuarios_db"][u]["estado"] = "Activo"
                            registrar_auditoria_legal(
                                "Equipo", "GLOBAL", "Reactivacion de usuario",
                                user.get("nombre", "Sistema"), user.get("matricula", ""),
                                f"Se reactivo el usuario {u}.", referencia=u,
                            )
                            guardar_datos(spinner=True)
                            st.rerun()
    elif tiene_rol_bajas and not ok_gestionar:
        st.caption("—")
    elif not tiene_rol_bajas:
        pass
    else:
        st.caption("—")


def _mi_equipo_bloque_eliminar(
    u: str,
    d: dict,
    *,
    user: dict,
    rol: str,
    mi_empresa: str,
    mostrar_ui_eliminar: bool,
    ok_gestionar: bool,
    puede_eliminar: bool,
) -> None:
    if mostrar_ui_eliminar:
        seguro = st.checkbox("Confirmar baja", key=f"chk_del_{u}")
        st.caption("La eliminación es permanente y quita el usuario del sistema.")
        if st.button("Eliminar", key=f"del_{u}", width='stretch', disabled=not seguro):
            if not puede_eliminar_cuenta_equipo(rol):
                st.error("Tu rol no puede eliminar usuarios (solo SuperAdmin o Coordinador de la misma clinica).")
            else:
                blk, msg_blk = bloqueo_autoservicio_suspension_baja(user.get("usuario_login"), u, rol)
                if blk:
                    st.error(msg_blk)
                else:
                    ok_m, msg_m = actor_puede_modificar_usuario_equipo(rol, mi_empresa, d)
                    if not ok_m:
                        st.error(msg_m)
                    else:
                        registrar_auditoria_legal(
                            "Equipo", "GLOBAL", "Eliminacion de usuario",
                            user.get("nombre", "Sistema"), user.get("matricula", ""),
                            f"Se elimino el usuario {u}.", referencia=u,
                        )
                        del st.session_state["usuarios_db"][u]
                        guardar_datos(spinner=True)
                        st.toast(f"Usuario {u} eliminado.")
                        st.rerun()
    elif puede_eliminar and not ok_gestionar:
        st.caption("—")
    elif not puede_eliminar:
        pass
