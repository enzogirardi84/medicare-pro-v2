import time

import streamlit as st

from core.app_logging import log_event
from core.clinicas_control import login_bloqueado_por_clinica, sincronizar_clinicas_desde_datos
from core.database import (
    cargar_datos,
    completar_claves_db_session,
    guardar_datos,
    login_usa_monolito_legacy,
    modo_shard_activo,
    sesion_usa_monolito_legacy,
    tenant_key_normalizado,
    vaciar_datos_app_en_sesion,
)
from core.auth_security import (
    limpiar_fallos_login,
    puede_intentar_login,
    registrar_fallo_login,
    texto_ayuda_proteccion,
)
from core.password_crypto import (
    aplicar_hash_tras_login_ok,
    bcrypt_rounds_config,
    establecer_password_nuevo,
    mensaje_password_no_cumple_politica,
    password_min_length,
    password_usuario_coincide,
)
from core.session_auth_cleanup import limpiar_estado_sesion_login_efimero
from core.email_2fa import (
    SESSION_KEY,
    iniciar_desafio_login,
    limpiar_desafio_email_2fa,
    login_email_2fa_enabled,
    reenviar_codigo_login,
    requiere_2fa_correo,
    smtp_config_ok,
    texto_ayuda_email_2fa_config,
    usuario_email_2fa_valido,
    verificar_codigo_ingresado,
)
from core.utils import (
    DEFAULT_ADMIN_USER,
    ahora,
    asegurar_usuarios_base,
    logins_clave_default_superadmin,
    normalizar_usuario_sistema,
)

SESSION_TIMEOUT_MINUTES = 90
_DEBOUNCE_GUARDAR_LOGS_CLINICA_SEC = 60.0

# Mensajes genéricos ante fallo (no distinguir usuario inexistente vs contraseña incorrecta).
MSG_LOGIN_CREDENCIALES_FALLIDAS = (
    "No pudimos validar el acceso. Revisá usuario, contraseña y empresa "
    "(en modo multiclínica). Si olvidaste la clave, usá «Olvidé mi contraseña»."
)
MSG_RECOVER_DATOS_INVALIDOS = (
    "No pudimos validar los datos. Revisá usuario, empresa y PIN, e intentá de nuevo."
)

_SESSION_LOGIN_FLASH = "_mc_auth_login_flash"
_SESSION_RECOVER_FLASH = "_mc_auth_recover_flash"


def _auth_set_flash(key: str, kind: str, message: str) -> None:
    st.session_state[key] = (kind, message)


def _auth_pop_flash(key: str) -> None:
    item = st.session_state.pop(key, None)
    if not item:
        return
    kind, message = item
    if kind == "warning":
        st.warning(message)
    elif kind == "error":
        st.error(message)
    elif kind == "info":
        st.info(message)
    elif kind == "success":
        st.success(message)


def _auth_strip_modulo_query_param() -> None:
    """Quita ?modulo= de la URL en la pantalla de login (marcadores viejos). Compatible con Streamlit sin query_params."""
    if st.session_state.get("logeado"):
        return
    qp = getattr(st, "query_params", None)
    if qp is None:
        return
    try:
        raw = qp.get("modulo")
        if raw is None:
            return
        if isinstance(raw, list):
            effective = "".join(str(x) for x in raw).strip()
        else:
            effective = str(raw).strip()
        if not effective:
            return
        qp.pop("modulo", None)
    except Exception:
        pass


def _cargar_db_login(empresa_login: str, u_limpio: str):
    """En modo shard: admin y allowlist cargan monolito legacy; el resto solo su clínica."""
    st.session_state.pop("_db_monolito_sesion", None)
    if not modo_shard_activo():
        d = cargar_datos(force=True)
        return (d, None) if d is not None else (None, "No se pudieron cargar los datos.")
    if login_usa_monolito_legacy(u_limpio):
        st.session_state["_db_monolito_sesion"] = True
        d = cargar_datos(force=True, monolito_legacy=True)
        return (d, None) if d is not None else (None, "No se pudo cargar la base global (monolito).")
    tk = tenant_key_normalizado(empresa_login)
    if not tk:
        return None, "En modo multiclínica debés ingresar **Empresa / Clínica** (como está dada de alta)."
    d = cargar_datos(force=True, tenant_key=tk)
    if d is None:
        return None, "No hay datos para esa clínica. Verificá el nombre o contactá a soporte."
    return d, None


def _cargar_db_recover(rec_emp: str, u_limpio: str):
    st.session_state.pop("_db_monolito_sesion", None)
    if modo_shard_activo():
        if login_usa_monolito_legacy(u_limpio):
            st.session_state["_db_monolito_sesion"] = True
            d = cargar_datos(force=True, monolito_legacy=True)
            if d is None:
                return None, "No se pudo cargar la base global (monolito)."
            return d, None
        tk = tenant_key_normalizado(rec_emp)
        if not tk:
            return None, "Indicá la empresa asignada."
        d = cargar_datos(force=True, tenant_key=tk)
        if d is None:
            return None, "No hay datos para esa clínica."
        return d, None
    d = cargar_datos(force=True)
    if d is None:
        return None, "No se pudieron cargar los datos."
    return d, None


def _persistir_logs_tras_rechazo_clinica():
    """Primer rechazo en la sesion guarda enseguida; los siguientes, como maximo cada ~60s."""
    if not st.session_state.get("_login_clinica_rechazo_guardado_once"):
        st.session_state["_login_clinica_rechazo_guardado_once"] = True
        guardar_datos()
        return
    ahora_ts = time.time()
    clave = "_debounce_guardar_logs_clinica_ts"
    ultimo = float(st.session_state.get(clave, 0) or 0)
    if ahora_ts - ultimo < _DEBOUNCE_GUARDAR_LOGS_CLINICA_SEC:
        return
    st.session_state[clave] = ahora_ts
    guardar_datos()


def _completar_login_exitoso(user_data: dict, u_limpio: str, accion_log: str, evento_log: str):
    limpiar_desafio_email_2fa()
    limpiar_fallos_login(u_limpio)
    sesion = dict(user_data)
    login_key = str(sesion.get("usuario_login") or u_limpio or "").strip().lower()
    sesion = normalizar_usuario_sistema(sesion)
    sesion["usuario_login"] = login_key or u_limpio.strip().lower()
    st.session_state["u_actual"] = sesion
    st.session_state["logeado"] = True
    st.session_state.setdefault("logs_db", [])
    st.session_state["logs_db"].append(
        {
            "F": ahora().strftime("%d/%m/%Y"),
            "H": ahora().strftime("%H:%M"),
            "U": user_data["nombre"],
            "E": user_data["empresa"],
            "A": accion_log,
        }
    )
    log_event("auth", evento_log)
    guardar_datos()
    st.rerun()


def _render_bloque_verificacion_email_2fa() -> bool:
    """Si hay desafío activo, muestra UI y devuelve True (el caller debe st.stop())."""
    from core.email_2fa import desafio_email_2fa_activo

    fb = st.session_state.pop("_mc_2fa_resend_toast", None)
    if fb:
        if fb[0] == "ok":
            st.success(fb[1])
        else:
            st.error(fb[1])

    p = st.session_state.get(SESSION_KEY)
    if not p:
        return False
    if not desafio_email_2fa_activo():
        limpiar_desafio_email_2fa()
        st.warning("La verificación por correo venció. Volvé a iniciar sesión.")
        return False

    st.subheader("Verificación por correo")
    st.caption(f"Código enviado a **{p.get('destino_mascarado', 'tu correo')}**.")
    with st.form("form_email_2fa"):
        cod = st.text_input("Código de 6 dígitos", max_chars=6, placeholder="000000")
        if st.form_submit_button("Confirmar acceso", use_container_width=True):
            ok, err = verificar_codigo_ingresado(cod)
            if ok:
                uk = p.get("usuario_key")
                u_limpio = str(p.get("u_limpio") or "")
                limpiar_desafio_email_2fa()
                user_data = dict(st.session_state["usuarios_db"][uk])
                user_data["usuario_login"] = uk
                _completar_login_exitoso(user_data, u_limpio, "Login", "login_ok")
            else:
                st.error(err)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Reenviar código", use_container_width=True):
            ok_r, err_r = reenviar_codigo_login()
            st.session_state["_mc_2fa_resend_toast"] = (
                ("ok", "Nuevo código enviado.") if ok_r else ("err", err_r)
            )
            st.rerun()
    with c2:
        if st.button("Cancelar", use_container_width=True):
            limpiar_desafio_email_2fa()
            st.rerun()
    return True


def render_login():
    if "logeado" not in st.session_state:
        st.session_state["logeado"] = False
    # Evita pantalla en blanco si quedó logeado=True sin usuario (sesión vieja o estado corrupto).
    if st.session_state["logeado"] and not st.session_state.get("u_actual"):
        st.session_state["logeado"] = False

    if not st.session_state["logeado"]:
        _auth_strip_modulo_query_param()
        _, col, _ = st.columns([1, 1.5, 1])
        with col:
            st.markdown("<br><h2 style='text-align:center; color:#3b82f6;'>MediCare Enterprise PRO V9.12</h2>", unsafe_allow_html=True)
            st.caption(
                "Ingresa con el usuario (login) y contrasena que te asigno tu clinica. "
                "Si la clinica fue suspendida por abono o decision administrativa, el sistema bloquea el acceso hasta la reactivacion: contacta a MediCare o a tu coordinador."
            )
            _tip2 = texto_ayuda_email_2fa_config()
            if _tip2:
                st.caption(_tip2)
            if _render_bloque_verificacion_email_2fa():
                st.stop()
            modo_auth = st.radio(
                "Acceso",
                ["Iniciar sesion", "Olvide mi contrasena"],
                horizontal=False,
                label_visibility="collapsed",
            )

            if modo_auth == "Iniciar sesion":
                st.session_state.pop(_SESSION_RECOVER_FLASH, None)
                _sec_tip = texto_ayuda_proteccion()
                if _sec_tip:
                    st.caption(_sec_tip)
                with st.form("login", clear_on_submit=True):
                    if modo_shard_activo():
                        st.caption(
                            "Modo **multiclínica** activo: cada clínica tiene su propia base. "
                            "Ingresá la empresa tal como figura en el sistema. "
                            "Los logins de operación global (p. ej. **admin** o los configurados en `MONOLITO_LOGIN_ALLOWLIST`) "
                            "pueden dejar empresa vacía y usar solo usuario y contraseña."
                        )
                        empresa_login = st.text_input("Empresa / Clínica (opcional para logins monolito)")
                    else:
                        empresa_login = ""
                    u = st.text_input("Usuario")
                    p = st.text_input("Contrasena", type="password")
                    if st.form_submit_button("Ingresar al Sistema", use_container_width=True):
                        if not u.strip() or not p.strip():
                            _auth_set_flash(
                                _SESSION_LOGIN_FLASH,
                                "warning",
                                "Ingresá usuario y contraseña.",
                            )
                        else:
                            u_limpio_pre = u.strip().lower()
                            ok_lock, lock_msg = puede_intentar_login(u_limpio_pre)
                            if not ok_lock:
                                st.error(lock_msg)
                            else:
                                db_f, err_db = _cargar_db_login(empresa_login, u_limpio_pre)
                                if err_db:
                                    st.error(err_db)
                                elif db_f is None:
                                    st.error("No se pudieron cargar los datos.")
                                else:
                                    for k, v in db_f.items():
                                        st.session_state[k] = v
                                    completar_claves_db_session()
                                    asegurar_usuarios_base(solo_normalizar=modo_shard_activo())
                                    sincronizar_clinicas_desde_datos(st.session_state)
                                    u_limpio = u.strip().lower()
                                    usuario_encontrado = None
                                    for key_db in st.session_state["usuarios_db"].keys():
                                        if key_db.strip().lower() == u_limpio:
                                            usuario_encontrado = key_db
                                            break

                                    if usuario_encontrado:
                                        user_data = dict(st.session_state["usuarios_db"][usuario_encontrado])
                                        user_data["usuario_login"] = usuario_encontrado
                                        st.session_state["usuarios_db"][usuario_encontrado]["usuario_login"] = usuario_encontrado
                                        ok_pw, migrar_hash = password_usuario_coincide(user_data, p.strip())
                                        if user_data.get("estado", "Activo") == "Bloqueado":
                                            registrar_fallo_login(u_limpio)
                                            st.error(
                                                "Tu usuario está **bloqueado**. "
                                                "Contactá al coordinador o administrador de tu clínica para reactivar el acceso."
                                            )
                                        elif ok_pw:
                                            if migrar_hash:
                                                aplicar_hash_tras_login_ok(
                                                    st.session_state["usuarios_db"][usuario_encontrado],
                                                    p.strip(),
                                                    rounds=bcrypt_rounds_config(),
                                                )
                                                user_data = dict(st.session_state["usuarios_db"][usuario_encontrado])
                                                user_data["usuario_login"] = usuario_encontrado
                                            if login_bloqueado_por_clinica(user_data):
                                                registrar_fallo_login(u_limpio)
                                                st.session_state.setdefault("logs_db", [])
                                                st.session_state["logs_db"].append(
                                                    {
                                                        "F": ahora().strftime("%d/%m/%Y"),
                                                        "H": ahora().strftime("%H:%M"),
                                                        "U": str(user_data.get("nombre", usuario_encontrado)),
                                                        "E": str(user_data.get("empresa", "")),
                                                        "A": f"Login rechazado (clinica suspendida) login={usuario_encontrado}",
                                                    }
                                                )
                                                _persistir_logs_tras_rechazo_clinica()
                                                st.error(
                                                    "La clinica asignada a tu usuario esta suspendida (abono o decision administrativa). "
                                                    "No podes ingresar hasta la reactivacion. Si sos personal de la clinica, avisa a tu responsable; "
                                                    "la gestion la hace MediCare desde el panel global de clinicas."
                                                )
                                            else:
                                                if requiere_2fa_correo(user_data):
                                                    if migrar_hash:
                                                        guardar_datos()
                                                    ok_send, err_send = iniciar_desafio_login(
                                                        str(user_data.get("email") or "").strip(),
                                                        usuario_encontrado,
                                                        u_limpio,
                                                    )
                                                    if ok_send:
                                                        st.info(
                                                            "Te enviamos un código de 6 dígitos. Revisá tu correo y completá el paso siguiente."
                                                        )
                                                        st.rerun()
                                                    st.error(err_send)
                                                elif login_email_2fa_enabled() and smtp_config_ok() and not usuario_email_2fa_valido(
                                                    user_data
                                                ):
                                                    st.error(
                                                        "La verificación por correo está activa y tu usuario no tiene un email válido. "
                                                        "Pedí a coordinación que cargue tu correo en **Mi equipo**."
                                                    )
                                                else:
                                                    _completar_login_exitoso(
                                                        user_data,
                                                        u_limpio,
                                                        "Login",
                                                        "login_ok",
                                                    )
                                        else:
                                            if u_limpio in logins_clave_default_superadmin() and p.strip() == str(
                                                DEFAULT_ADMIN_USER["pass"]
                                            ).strip():
                                                limpiar_fallos_login(u_limpio)
                                                user_data = DEFAULT_ADMIN_USER.copy()
                                                user_data["usuario_login"] = "admin"
                                                aplicar_hash_tras_login_ok(user_data, p.strip(), rounds=bcrypt_rounds_config())
                                                st.session_state["usuarios_db"]["admin"] = user_data
                                                _completar_login_exitoso(
                                                    user_data,
                                                    "admin",
                                                    "Login emergencia superadmin",
                                                    "login_ok_admin_emergencia",
                                                )
                                            else:
                                                registrar_fallo_login(u_limpio)
                                                st.error(MSG_LOGIN_CREDENCIALES_FALLIDAS)
                                    else:
                                        if u_limpio in logins_clave_default_superadmin() and p.strip() == str(
                                            DEFAULT_ADMIN_USER["pass"]
                                        ).strip():
                                            limpiar_fallos_login(u_limpio)
                                            user_data = DEFAULT_ADMIN_USER.copy()
                                            user_data["usuario_login"] = "admin"
                                            aplicar_hash_tras_login_ok(user_data, p.strip(), rounds=bcrypt_rounds_config())
                                            st.session_state["usuarios_db"]["admin"] = user_data
                                            _completar_login_exitoso(
                                                user_data,
                                                "admin",
                                                "Login emergencia superadmin",
                                                "login_ok_admin_emergencia",
                                            )
                                        else:
                                            registrar_fallo_login(u_limpio)
                                            st.error(MSG_LOGIN_CREDENCIALES_FALLIDAS)
                _auth_pop_flash(_SESSION_LOGIN_FLASH)
            else:
                st.session_state.pop(_SESSION_LOGIN_FLASH, None)
                _rec_tip = texto_ayuda_proteccion()
                if _rec_tip:
                    st.caption(_rec_tip)
                with st.form("recover", clear_on_submit=True):
                    st.info(
                        f"Para crear una nueva contrasena, ingresa tu PIN de 4 digitos. "
                        f"Largo mínimo de clave: {password_min_length()} caracteres."
                    )
                    rec_u = st.text_input("Usuario (Login)")
                    rec_emp = st.text_input("Empresa / Clinica asignada")
                    rec_pin = st.text_input("PIN de Seguridad", type="password", max_chars=4)
                    rec_pass = st.text_input("Nueva Contrasena", type="password")
                    if st.form_submit_button("Cambiar Contrasena", use_container_width=True):
                        if not rec_u.strip():
                            _auth_set_flash(
                                _SESSION_RECOVER_FLASH,
                                "warning",
                                "Ingresá tu usuario (login).",
                            )
                        elif not str(rec_pin).strip() or not str(rec_pass).strip():
                            _auth_set_flash(
                                _SESSION_RECOVER_FLASH,
                                "warning",
                                "Completá PIN de seguridad y nueva contraseña.",
                            )
                        else:
                            u_limpio = rec_u.strip().lower()
                            ok_rec, lock_rec = puede_intentar_login(u_limpio)
                            if not ok_rec:
                                st.error(lock_rec)
                            else:
                                db_f, err_rec = _cargar_db_recover(rec_emp, u_limpio)
                                if err_rec:
                                    st.error(err_rec)
                                elif db_f is None:
                                    st.error("No se pudieron cargar los datos.")
                                else:
                                    for k, v in db_f.items():
                                        st.session_state[k] = v
                                    completar_claves_db_session()
                                    asegurar_usuarios_base(solo_normalizar=modo_shard_activo())
                                    sincronizar_clinicas_desde_datos(st.session_state)
                                    if u_limpio in st.session_state["usuarios_db"]:
                                        user_data = st.session_state["usuarios_db"][u_limpio]
                                        rec_emp_l = rec_emp.strip().lower()
                                        empresa_coincide = user_data["empresa"].strip().lower() == rec_emp_l
                                        if modo_shard_activo() and sesion_usa_monolito_legacy():
                                            empresa_ok = (not rec_emp.strip()) or empresa_coincide
                                        else:
                                            empresa_ok = empresa_coincide
                                        if empresa_ok:
                                            if str(user_data.get("pin", "")) == str(rec_pin).strip() and str(rec_pin).strip() != "":
                                                _msg_pw = mensaje_password_no_cumple_politica(rec_pass)
                                                if not _msg_pw:
                                                    limpiar_fallos_login(u_limpio)
                                                    establecer_password_nuevo(
                                                        st.session_state["usuarios_db"][u_limpio],
                                                        rec_pass,
                                                        rounds=bcrypt_rounds_config(),
                                                    )
                                                    guardar_datos()
                                                    log_event("auth", "password_reset_via_pin_ok")
                                                    st.success("Contrasena actualizada.")
                                                else:
                                                    registrar_fallo_login(u_limpio)
                                                    st.error(_msg_pw)
                                            else:
                                                registrar_fallo_login(u_limpio)
                                                st.error(MSG_RECOVER_DATOS_INVALIDOS)
                                        else:
                                            registrar_fallo_login(u_limpio)
                                            st.error(MSG_RECOVER_DATOS_INVALIDOS)
                                    else:
                                        registrar_fallo_login(u_limpio)
                                        st.error(MSG_RECOVER_DATOS_INVALIDOS)
                _auth_pop_flash(_SESSION_RECOVER_FLASH)
        st.stop()


def verificar_clinica_sesion_activa():
    """Cierra sesion si la clinica del usuario quedo suspendida (p. ej. mientras estaba logueado)."""
    if not st.session_state.get("logeado"):
        return
    u = st.session_state.get("u_actual")
    if not u or not isinstance(u, dict):
        return
    sincronizar_clinicas_desde_datos(st.session_state)
    if login_bloqueado_por_clinica(u):
        st.session_state["logeado"] = False
        st.session_state.pop("u_actual", None)
        st.session_state.pop("ultima_actividad", None)
        st.session_state.pop("_mc_onboarding_oculto", None)
        limpiar_estado_sesion_login_efimero()
        vaciar_datos_app_en_sesion()
        st.warning(
            "El acceso de tu clinica fue suspendido mientras tenias sesion abierta. "
            "Coordinadores, operativos y administrativos no pueden usar la app hasta la reactivacion. "
            "Volvete a intentar cuando te confirmen que el servicio fue rehabilitado."
        )
        st.rerun()


def check_inactividad():
    if st.session_state.get("logeado"):
        if "ultima_actividad" not in st.session_state:
            st.session_state["ultima_actividad"] = ahora()
        else:
            minutos_inactivos = (ahora() - st.session_state["ultima_actividad"]).total_seconds() / 60.0
            if minutos_inactivos > SESSION_TIMEOUT_MINUTES:
                st.session_state["logeado"] = False
                st.session_state.pop("ultima_actividad", None)
                st.session_state.pop("u_actual", None)
                st.session_state.pop("_mc_onboarding_oculto", None)
                limpiar_estado_sesion_login_efimero()
                vaciar_datos_app_en_sesion()
                st.warning(f"Tu sesion se cerro automaticamente por inactividad ({SESSION_TIMEOUT_MINUTES} minutos).")
                st.rerun()
            else:
                st.session_state["ultima_actividad"] = ahora()
