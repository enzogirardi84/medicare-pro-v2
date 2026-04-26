import streamlit as st

from core.app_logging import log_event
from core.clinicas_control import login_bloqueado_por_clinica, sincronizar_clinicas_desde_datos
from core.database import (
    completar_claves_db_session,
    guardar_datos,
    modo_shard_activo,
    sesion_usa_monolito_legacy,
    vaciar_datos_app_en_sesion,
)
from core.auth_security import (
    puede_intentar_login,
    registrar_fallo_login,
    texto_ayuda_proteccion,
)
from core.password_crypto import (
    bcrypt_rounds_config,
    establecer_password_nuevo,
    mensaje_password_no_cumple_politica,
    password_usuario_coincide,
    texto_ayuda_politica_password_breve,
)
from core.session_auth_cleanup import limpiar_estado_sesion_login_efimero
from core.email_2fa import (
    SESSION_KEY,
    iniciar_desafio_login,
    login_email_2fa_enabled,
    mascarar_email_privado,
    requiere_2fa_correo,
    smtp_config_ok,
    texto_ayuda_email_2fa_config,
    usuario_email_2fa_valido,
)
from core.utils import (
    DEFAULT_ADMIN_USER,
    ahora,
    asegurar_usuarios_base,
    logins_clave_default_superadmin,
    normalizar_usuario_sistema,
    obtener_emergency_password,
    obtener_pin_usuario,
)
from core._auth_helpers import (
    _auth_set_flash,
    _auth_pop_flash,
    _auth_loader_markup,
    _auth_strip_pwreset_url_si_hay_param as _auth_strip_pwreset_url_si_hay_param_impl,
    _auth_strip_pwreset_query_param as _auth_strip_pwreset_query_param_impl,
    _auth_strip_modulo_query_param,
    _buscar_usuario_por_login,
    _pin_coincide_tiempo_constante,
    _cargar_db_login,
    _persistir_logs_tras_rechazo_clinica,
    _completar_login_exitoso,
    _render_bloque_verificacion_email_2fa,
)

SESSION_TIMEOUT_MINUTES = 90

MSG_LOGIN_CREDENCIALES_FALLIDAS = (
    "No pudimos validar el acceso. Revisá **usuario** y **contraseña** "
    "(no el PIN de 4 dígitos ni el DNI, salvo que esa sea la clave que te asignaron). "
    "En **multiclínica**, el nombre de **Empresa / Clínica** debe coincidir con Mi equipo. "
    "Si olvidaste la clave y tenés **PIN** de recuperación, usá **Nueva contraseña con PIN**; si no, pedila a **coordinación**."
)
MSG_PIN_RESET_FALLIDO = (
    "No pudimos cambiar la contraseña. Revisá **usuario**, **PIN** de 4 dígitos y, en multiclínica, **empresa** "
    "como en Mi equipo."
)


def _auth_strip_pwreset_query_param() -> None:
    qp = getattr(st, "query_params", None)
    if qp is None:
        return
    try:
        qp.pop("pwreset", None)
    except Exception:
        _auth_strip_pwreset_query_param_impl()


def _auth_strip_pwreset_url_si_hay_param() -> bool:
    """
    Wrapper local para que tests y login usen el `st` del modulo `core.auth`.
    """
    qp = getattr(st, "query_params", None)
    if qp is None:
        return False
    try:
        if qp.get("pwreset") is None:
            return False
    except Exception:
        return False
    _auth_strip_pwreset_query_param()
    st.session_state.pop("mc_pwreset_token", None)
    st.session_state.pop("mc_auth_mode_radio", None)
    return True


def render_login():
    if "logeado" not in st.session_state:
        st.session_state["logeado"] = False
    # Evita pantalla en blanco si quedó logeado=True sin usuario (sesión vieja o estado corrupto).
    if st.session_state["logeado"] and not st.session_state.get("u_actual"):
        st.session_state["logeado"] = False
    if not st.session_state["logeado"] and _render_bloque_verificacion_email_2fa():
        st.stop()

    if not st.session_state["logeado"]:
        from core.ui_liviano import headers_sugieren_equipo_liviano

        es_movil = headers_sugieren_equipo_liviano() or st.session_state.get("mc_liviano_modo") == "on"
        _auth_strip_modulo_query_param()
        if _auth_strip_pwreset_url_si_hay_param():
            st.session_state["_mc_pwreset_url_aviso_once"] = True
        st.markdown(
            """
            <style>
            @media (max-width: 767px) {
                .block-container {
                    padding-top: 0.35rem !important;
                }
                [data-testid="stRadio"] {
                    margin: 0.1rem 0 0.2rem !important;
                }
                [data-testid="stRadio"] [role="radiogroup"] {
                    gap: 0.45rem 0.6rem !important;
                }
                div[data-testid="stExpander"] {
                    margin-bottom: 0.35rem !important;
                }
                div[data-testid="stForm"] {
                    padding: 0.72rem 0.78rem !important;
                    margin: 0.18rem 0 0.38rem !important;
                    border-radius: 16px !important;
                }
                div[data-testid="stForm"] [data-testid="stVerticalBlock"] {
                    gap: 0.24rem !important;
                }
                div[data-testid="stForm"] [data-testid="stElementContainer"] {
                    margin-bottom: 0.18rem !important;
                }
                div[data-testid="stForm"] label {
                    margin: 0 0 0.14rem 0 !important;
                    padding-bottom: 0 !important;
                    line-height: 1.15 !important;
                }
                div[data-testid="stForm"] input {
                    min-height: 38px !important;
                }
                div[data-testid="stForm"] [data-testid="stTextInput"],
                div[data-testid="stForm"] [data-testid="stNumberInput"] {
                    margin: 0 !important;
                }
                div[data-testid="stForm"] [data-testid="stFormSubmitButton"] {
                    margin-top: 0.32rem !important;
                }
                div[data-testid="stForm"] button[type="submit"] {
                    min-height: 40px !important;
                }
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        if es_movil:
            col = st.container()
        else:
            _, col, _ = st.columns([1, 1.5, 1])
        with col:
            with st.container(border=True):
                st.markdown("<div style='text-align:center'>### 🔐 Acceso a MediCare</div>", unsafe_allow_html=True)
                st.caption("V9.12 · Acceso institucional")
            intro_login = (
                "Ingresá con el usuario y la contraseña asignados por tu clínica."
                if es_movil
                else
                "Ingresá con el usuario (login) y contraseña que te asignó tu clínica. "
                "Si la clínica fue suspendida por abono o decisión administrativa, el acceso queda bloqueado hasta la reactivación: "
                "contactá a MediCare o a tu coordinador."
            )
            st.caption(intro_login)
            with st.expander("Problemas para ingresar o fallas del sistema", expanded=False):
                st.markdown(
                    "- Confirmá **usuario**, **contraseña** y, en multiclínica, **empresa** exacta como en Mi equipo.\n"
                    "- Varios intentos fallidos pueden activar **bloqueo temporal**: esperá unos minutos o pedí ayuda a coordinación.\n"
                    "- Pantalla en blanco o *No se pudo cargar el modulo*: probá **F5**; si vuelve, abrí el expander "
                    "**Detalle tecnico** en la app y enviá captura a soporte.\n"
                    "- Si no hay conexión, la app puede usar **modo local** con datos ya descargados; revisá WiFi o datos móviles."
                )
            _aviso_exp = st.session_state.pop("_aviso_sesion_expirada", None)
            if _aviso_exp:
                st.warning(_aviso_exp)
            if st.session_state.pop("_mc_pwreset_url_aviso_once", False):
                st.info(
                    "Detectamos un enlace de restablecimiento de contraseña en la URL. "
                    "En esta instalación **no** se usa recuperación por correo. "
                    "Si tenés **PIN** en Mi equipo, probá **Nueva contraseña con PIN**; si no, pedí clave a **coordinación**."
                )
            _sec_tip = texto_ayuda_proteccion()
            if _sec_tip:
                st.caption(_sec_tip)
            modo_auth = st.radio(
                "Acceso",
                ["login", "pin_new"],
                horizontal=True,
                label_visibility="collapsed",
                format_func=lambda m: "Iniciar sesión" if m == "login" else "Nueva contraseña con PIN",
                key="mc_auth_mode_radio",
            )
            if modo_auth == "login":
                st.caption(
                    "Ingresá con **usuario** y **contraseña**."
                    if es_movil
                    else
                    "Ingresá con **usuario** y **contraseña**. La contraseña no es el DNI salvo que tu clínica te haya "
                    "configurado la cuenta así."
                )
            else:
                st.caption(
                    "Usá tu **PIN de 4 dígitos** para definir una clave nueva."
                    if es_movil
                    else
                    "Si **coordinación** te cargó un **PIN de 4 dígitos** en Mi equipo, podés definir una **clave nueva** "
                    "sin correo. Sin PIN, pedí la clave a coordinación."
                )
                st.caption(texto_ayuda_politica_password_breve())
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
                if modo_auth == "login":
                    p = st.text_input(
                        "Contraseña",
                        type="password",
                        help="Clave de acceso asignada o definida por tu clínica; no el PIN de 4 dígitos ni el DNI, salvo que esa sea tu clave.",
                    )
                else:
                    pin_rec = st.text_input(
                        "PIN de recuperación (4 dígitos)",
                        type="password",
                        max_chars=4,
                        help="El mismo PIN que figura en Mi equipo para tu usuario.",
                    )
                    p1 = st.text_input("Nueva contraseña", type="password")
                    p2 = st.text_input("Repetir nueva contraseña", type="password")
                if modo_auth == "login":
                    submit = st.form_submit_button("Ingresar al sistema")
                else:
                    submit = st.form_submit_button("Guardar nueva contraseña")
                if submit and modo_auth == "pin_new":
                    if not u.strip():
                        st.warning("Ingresá tu usuario (login).")
                        st.stop()
                    pin_rec_s = str(pin_rec or "").strip()
                    p1s = str(p1 or "").strip()
                    p2s = str(p2 or "").strip()
                    if not pin_rec_s or not p1s or not p2s:
                        st.warning("Completá usuario, PIN y la nueva contraseña en ambos campos.")
                        st.stop()
                    if p1s != p2s:
                        st.error("Las contraseñas nuevas no coinciden.")
                        st.stop()
                    u_limpio_pre = u.strip().lower()
                    ok_lock, lock_msg = puede_intentar_login(u_limpio_pre)
                    if not ok_lock:
                        st.error(lock_msg)
                        st.stop()
                    db_f, err_db = _cargar_db_login(empresa_login, u_limpio_pre)
                    if err_db:
                        st.error(err_db)
                        st.stop()
                    if db_f is None:
                        st.error("No se pudieron cargar los datos.")
                        st.stop()
                    for k, v in db_f.items():
                        st.session_state[k] = v
                    completar_claves_db_session()
                    asegurar_usuarios_base(solo_normalizar=modo_shard_activo())
                    sincronizar_clinicas_desde_datos(st.session_state)
                    u_limpio = u.strip().lower()
                    usuario_encontrado = _buscar_usuario_por_login(u_limpio)
                    if not usuario_encontrado:
                        registrar_fallo_login(u_limpio)
                        st.error(MSG_PIN_RESET_FALLIDO)
                        st.stop()
                    user_data = normalizar_usuario_sistema(
                        dict(st.session_state["usuarios_db"][usuario_encontrado])
                    )
                    user_data["usuario_login"] = usuario_encontrado
                    st.session_state["usuarios_db"][usuario_encontrado] = user_data
                    emp_l = str(empresa_login or "").strip().lower()
                    empresa_coincide = str(user_data.get("empresa", "")).strip().lower() == emp_l
                    if modo_shard_activo() and sesion_usa_monolito_legacy():
                        empresa_ok = (not str(empresa_login or "").strip()) or empresa_coincide
                    else:
                        empresa_ok = empresa_coincide
                    if not empresa_ok:
                        registrar_fallo_login(u_limpio)
                        st.error(MSG_PIN_RESET_FALLIDO)
                        st.stop()
                    if user_data.get("estado", "Activo") == "Bloqueado":
                        registrar_fallo_login(u_limpio)
                        st.error(
                            "Tu usuario está **bloqueado**. Contactá al coordinador para reactivar el acceso antes de cambiar la clave."
                        )
                        st.stop()
                    if login_bloqueado_por_clinica(user_data):
                        registrar_fallo_login(u_limpio)
                        st.error(
                            "La clínica asignada a tu usuario está suspendida. No se puede cambiar la contraseña hasta la reactivación."
                        )
                        st.stop()
                    if not str(obtener_pin_usuario(user_data) or "").strip():
                        st.error(
                            "Tu cuenta **no tiene PIN de recuperación** en Mi equipo. Pedí una clave nueva a coordinación."
                        )
                        st.stop()
                    if not _pin_coincide_tiempo_constante(user_data, pin_rec_s):
                        registrar_fallo_login(u_limpio)
                        st.error(MSG_PIN_RESET_FALLIDO)
                        st.stop()
                    msg_pw = mensaje_password_no_cumple_politica(p1s)
                    if msg_pw:
                        st.error(msg_pw)
                        st.stop()
                    with st.spinner("Guardando tu nueva contraseña…"):
                        limpiar_fallos_login(u_limpio)
                        establecer_password_nuevo(
                            st.session_state["usuarios_db"][usuario_encontrado],
                            p1s,
                            rounds=bcrypt_rounds_config(),
                        )
                        guardar_datos()
                        log_event("auth", "password_reset_via_pin_ok")
                    st.success(
                        "Listo. Ya podés **iniciar sesión** con tu usuario y la contraseña nueva (elegí **Iniciar sesión** arriba)."
                    )
                    st.stop()
                if submit and modo_auth == "login":
                    if not u.strip() or not p.strip():
                        st.warning("Ingresá usuario y contraseña.")
                        st.stop()
                    else:
                        u_limpio_pre = u.strip().lower()
                        ok_lock, lock_msg = puede_intentar_login(u_limpio_pre)
                        if not ok_lock:
                            st.error(lock_msg)
                        else:
                            _loader_ph = st.empty()
                            _loader_ph.markdown(_auth_loader_markup("Autenticando..."), unsafe_allow_html=True)
                            db_f, err_db = _cargar_db_login(empresa_login, u_limpio_pre)
                            _loader_ph.markdown(_auth_loader_markup("Verificando acceso..."), unsafe_allow_html=True)
                            if err_db:
                                _loader_ph.empty()
                                st.error(err_db)
                            elif db_f is None:
                                _loader_ph.empty()
                                st.error("No se pudieron cargar los datos.")
                            else:
                                for k, v in db_f.items():
                                    st.session_state[k] = v
                                completar_claves_db_session()
                                asegurar_usuarios_base(solo_normalizar=modo_shard_activo())
                                sincronizar_clinicas_desde_datos(st.session_state)
                                u_limpio = u.strip().lower()
                                usuario_encontrado = _buscar_usuario_por_login(u_limpio)

                                if usuario_encontrado:
                                    user_data = normalizar_usuario_sistema(
                                        dict(st.session_state["usuarios_db"][usuario_encontrado])
                                    )
                                    user_data["usuario_login"] = usuario_encontrado
                                    st.session_state["usuarios_db"][usuario_encontrado] = user_data
                                    ok_pw, migrar_hash = password_usuario_coincide(user_data, p.strip())
                                    if user_data.get("estado", "Activo") == "Bloqueado":
                                        _loader_ph.empty()
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
                                            _loader_ph.empty()
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
                                                _loader_ph.empty()
                                                st.error(err_send)
                                            else:
                                                # 2FA por correo solo si el usuario tiene email válido (requiere_2fa_correo).
                                                # Sin email en ficha el ingreso es con contraseña para no bloquear cuentas históricas.
                                                if (
                                                    login_email_2fa_enabled()
                                                    and smtp_config_ok()
                                                    and not usuario_email_2fa_valido(user_data)
                                                ):
                                                    log_event(
                                                        "auth",
                                                        "login_ok_2fa_omitido_sin_email_en_ficha",
                                                    )
                                                _loader_ph.empty()
                                                _completar_login_exitoso(
                                                    user_data,
                                                    u_limpio,
                                                    "Login",
                                                    "login_ok",
                                                )
                                    else:
                                        # Verificar login de emergencia con contraseña desde secrets
                                        emergency_pwd = obtener_emergency_password()
                                        if u_limpio in logins_clave_default_superadmin() and emergency_pwd and p.strip() == emergency_pwd:
                                            limpiar_fallos_login(u_limpio)
                                            user_data = DEFAULT_ADMIN_USER.copy()
                                            user_data["usuario_login"] = "admin"
                                            aplicar_hash_tras_login_ok(user_data, p.strip(), rounds=bcrypt_rounds_config())
                                            st.session_state["usuarios_db"]["admin"] = user_data
                                            _loader_ph.empty()
                                            _completar_login_exitoso(
                                                user_data,
                                                "admin",
                                                "Login emergencia superadmin",
                                                "login_ok_admin_emergencia",
                                            )
                                        else:
                                            _loader_ph.empty()
                                            registrar_fallo_login(u_limpio)
                                            st.error(MSG_LOGIN_CREDENCIALES_FALLIDAS)
                                else:
                                    # Verificar login de emergencia con contraseña desde secrets
                                    emergency_pwd = obtener_emergency_password()
                                    if u_limpio in logins_clave_default_superadmin() and emergency_pwd and p.strip() == emergency_pwd:
                                        limpiar_fallos_login(u_limpio)
                                        user_data = DEFAULT_ADMIN_USER.copy()
                                        user_data["usuario_login"] = "admin"
                                        aplicar_hash_tras_login_ok(user_data, p.strip(), rounds=bcrypt_rounds_config())
                                        st.session_state["usuarios_db"]["admin"] = user_data
                                        _loader_ph.empty()
                                        _completar_login_exitoso(
                                            user_data,
                                            "admin",
                                            "Login emergencia superadmin",
                                            "login_ok_admin_emergencia",
                                        )
                                    else:
                                        _loader_ph.empty()
                                        registrar_fallo_login(u_limpio)
                                        st.error(MSG_LOGIN_CREDENCIALES_FALLIDAS)
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
            "Coordinadores y operativos (incluye personal de gestion) no pueden usar la app hasta la reactivacion. "
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
                st.session_state["_aviso_sesion_expirada"] = f"Tu sesion se cerro automaticamente por inactividad ({SESSION_TIMEOUT_MINUTES} minutos)."
                # Guard: evitar tormenta de reruns en móviles con red lenta
                _ult_rerun_exp = st.session_state.get("_ult_rerun_expiracion_ts", 0)
                if (ahora().timestamp() - _ult_rerun_exp) > 5:
                    st.session_state["_ult_rerun_expiracion_ts"] = ahora().timestamp()
                    st.rerun()
            else:
                st.session_state["ultima_actividad"] = ahora()


# ── Funciones públicas para tests ───────────────────────────────

def _verify_password(plain: str, stored_hash: str) -> bool:
    """Wrapper para compatibilidad con mocks de tests."""
    from core.password_crypto import verificar_password
    return verificar_password(plain, stored_hash)


def _pin_coincide(provided: str, stored: str) -> bool:
    """Compara PIN en tiempo constante."""
    import secrets
    return secrets.compare_digest(str(provided or ""), str(stored or ""))


def registrar_auditoria(accion: str, usuario: str, detalles: dict = None):
    """Stub para auditoría; usado en tests con patch."""
    pass


def verificar_login(session_state, username: str, password: str, pin: str = None, empresa: str = None) -> bool:
    """Verifica credenciales y establece sesión si son válidas."""
    usuarios = session_state.get("usuarios_db", {})
    user = usuarios.get(username)
    if not user:
        return False
    if not user.get("activo", True):
        return False
    if empresa and user.get("empresa") != empresa:
        return False
    if not _verify_password(password, user.get("password_hash", "")):
        return False
    if pin is not None and not _pin_coincide(pin, user.get("pin", "")):
        return False
    session_state["logeado"] = True
    session_state["u_actual"] = user
    registrar_auditoria("login", username)
    return True


def crear_sesion(session_state, usuario: dict):
    """Crea una sesión de usuario en session_state."""
    session_state["logeado"] = True
    session_state["u_actual"] = usuario


def cerrar_sesion(session_state):
    """Cierra la sesión actual."""
    session_state["logeado"] = False
    session_state["u_actual"] = None
    session_state.pop("_last_activity", None)


def verificar_timeout_sesion(session_state, timeout_minutes: int = 30) -> bool:
    """Retorna True si la sesión expiró por inactividad."""
    import time
    last = session_state.get("_last_activity")
    if last is None:
        return False
    return (time.time() - last) / 60.0 > timeout_minutes
