from __future__ import annotations

import secrets
import time

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
    limpiar_fallos_login,
    texto_ayuda_proteccion,
)
from core.password_crypto import (
    bcrypt_rounds_config,
    establecer_password_nuevo,
    mensaje_password_no_cumple_politica,
    password_usuario_coincide,
    texto_ayuda_politica_password_breve,
    aplicar_hash_tras_login_ok,
)
from core.session_auth_cleanup import limpiar_estado_sesion_login_efimero
from core.email_2fa import (
    iniciar_desafio_login,
    login_email_2fa_enabled,
    requiere_2fa_correo,
    smtp_config_ok,
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
    _auth_loader_markup,
    _auth_strip_pwreset_query_param as _auth_strip_pwreset_query_param_impl,
    _auth_strip_modulo_query_param,
    _buscar_usuario_por_login,
    _pin_coincide_tiempo_constante,
    _cargar_db_login,
    _persistir_logs_tras_rechazo_clinica,
    _completar_login_exitoso,
    _render_bloque_verificacion_email_2fa,
)

def _session_timeout_minutes() -> int:
    """Timeout de sesión configurable para jornada clínica.

    Por defecto queda en 8 horas para evitar cierres prematuros durante guardias.
    Si se define SESSION_TIMEOUT_MINUTES en secrets, se respeta entre 15 min y 12 h.
    """
    try:
        raw = st.secrets.get("SESSION_TIMEOUT_MINUTES", 480)
    except Exception:
        raw = 480
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 480
    return max(15, min(720, value))


SESSION_TIMEOUT_MINUTES = _session_timeout_minutes()

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
MSG_LOGIN_USUARIOS_NO_DISPONIBLES = (
    "No se cargó la lista de usuarios de Mi equipo. Revisá conexión con la nube, configuración de Supabase "
    "o el nombre de Empresa / Clínica. Si el problema sigue, contactá a soporte."
)


def _db_login_tiene_usuarios(db_data: dict | None) -> bool:
    if not isinstance(db_data, dict):
        return False
    usuarios = db_data.get("usuarios_db")
    return isinstance(usuarios, dict) and any(isinstance(u, dict) for u in usuarios.values())


def _intentar_login_emergencia(u_limpio: str, p_plain: str, loader_ph) -> bool:
    emergency_pwd = obtener_emergency_password()
    if u_limpio not in logins_clave_default_superadmin() or not emergency_pwd:
        return False
    if not secrets.compare_digest(p_plain, emergency_pwd):
        return False
    limpiar_fallos_login(u_limpio)
    user_data = DEFAULT_ADMIN_USER.copy()
    user_data["usuario_login"] = u_limpio
    aplicar_hash_tras_login_ok(user_data, p_plain, rounds=bcrypt_rounds_config())
    if not isinstance(st.session_state.get("usuarios_db"), dict):
        st.session_state["usuarios_db"] = {}
    st.session_state["usuarios_db"][u_limpio] = user_data
    if loader_ph is not None:
        loader_ph.empty()
    _completar_login_exitoso(user_data, u_limpio, "Login emergencia superadmin", "login_ok_admin_emergencia")
    return True  # _completar_login_exitoso hace st.rerun(), esto no se alcanza normalmente

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
        log_event("auth", f"query_params_error")
        return False
    _auth_strip_pwreset_query_param()
    st.session_state.pop("mc_pwreset_token", None)
    st.session_state.pop("mc_auth_mode_radio", None)
    return True


def _render_login_ui(es_movil: bool, modo_auth: str):
    """Renderiza el formulario de login completo. Retorna (submit, modo_auth, empresa_login, usuario, pass_data, pin_data)."""
    if es_movil:
        col = st.container()
    else:
        _, col, _ = st.columns([1, 1.5, 1])
    with col:
        with st.container(border=True):
            st.markdown("<div style='text-align:center'><h3 style='margin:0;color:#1e293b;'>🔐 Acceso a MediCare</h3></div>", unsafe_allow_html=True)
            st.caption("V9.12 · Acceso institucional")
        intro_login = (
            "Ingresá con el usuario y la contraseña asignados por tu clínica."
            if es_movil else
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
        st.radio("Acceso", ["login", "pin_new"], horizontal=True,
                 label_visibility="collapsed",
                 format_func=lambda m: "Iniciar sesión" if m == "login" else "Nueva contraseña con PIN",
                 key="mc_auth_mode_radio")
        if modo_auth == "login":
            st.caption("Ingresá con **usuario** y **contraseña**." if es_movil else
                       "Ingresá con **usuario** y **contraseña**. La contraseña no es el DNI salvo que tu clínica te haya configurado la cuenta así.")
        else:
            st.caption("Usá tu **PIN de 4 dígitos** para definir una clave nueva." if es_movil else
                       "Si **coordinación** te cargó un **PIN de 4 dígitos** en Mi equipo, podés definir una **clave nueva** sin correo. Sin PIN, pedí la clave a coordinación.")
            st.caption(texto_ayuda_politica_password_breve())
        with st.form("login", clear_on_submit=True):
            empresa_login = st.text_input("Empresa / Clínica (opcional para logins monolito)") if modo_shard_activo() else ""
            u = st.text_input("Usuario")
            pin_data = {}
            if modo_auth == "login":
                p = st.text_input("Contraseña", type="password")
            else:
                pin_data = {"pin": st.text_input("PIN de recuperación (4 dígitos)", type="password", max_chars=4),
                            "p1": st.text_input("Nueva contraseña", type="password"),
                            "p2": st.text_input("Repetir nueva contraseña", type="password")}
                p = ""
            submit = st.form_submit_button("Ingresar al sistema" if modo_auth == "login" else "Guardar nueva contraseña")
            return submit, empresa_login, u.strip(), p, pin_data

def _procesar_pin_reset(empresa_login: str, u: str, pin_data: dict):
    """Maneja el flujo de reset de contraseña por PIN. Retorna True si debe detenerse."""
    if not u:
        st.warning("Ingresá tu usuario (login)."); st.stop(); return True
    pin_s, p1s, p2s = pin_data.get("pin",""), pin_data.get("p1",""), pin_data.get("p2","")
    if not pin_s or not p1s or not p2s:
        st.warning("Completá usuario, PIN y la nueva contraseña en ambos campos."); st.stop(); return True
    if p1s != p2s:
        st.error("Las contraseñas nuevas no coinciden."); st.stop(); return True
    u_limpio = u.strip().lower()
    ok_lock, msg = puede_intentar_login(u_limpio)
    if not ok_lock:
        st.error(msg); st.stop(); return True
    db_f, err_db = _cargar_db_login(empresa_login, u_limpio)
    if err_db:
        st.error(err_db); st.stop(); return True
    if db_f is None:
        st.error("No se pudieron cargar los datos."); st.stop(); return True
    for k, v in db_f.items():
        st.session_state[k] = v
    completar_claves_db_session(); asegurar_usuarios_base(solo_normalizar=modo_shard_activo())
    sincronizar_clinicas_desde_datos(st.session_state)
    usuario_encontrado = _buscar_usuario_por_login(u_limpio)
    if not usuario_encontrado:
        registrar_fallo_login(u_limpio); st.error(MSG_PIN_RESET_FALLIDO); st.stop(); return True
    user_data = normalizar_usuario_sistema(dict(st.session_state["usuarios_db"][usuario_encontrado]))
    user_data["usuario_login"] = usuario_encontrado
    st.session_state["usuarios_db"][usuario_encontrado] = user_data
    if not _validar_empresa_usuario(user_data, empresa_login, MSG_PIN_RESET_FALLIDO):
        return True
    if user_data.get("estado", "Activo") == "Bloqueado":
        registrar_fallo_login(u_limpio); st.error("Tu usuario está **bloqueado**. Contactá al coordinador para reactivar el acceso antes de cambiar la clave."); st.stop(); return True
    if login_bloqueado_por_clinica(user_data):
        registrar_fallo_login(u_limpio); st.error("La clínica asignada a tu usuario está suspendida."); st.stop(); return True
    if not str(obtener_pin_usuario(user_data) or "").strip():
        st.error("Tu cuenta **no tiene PIN de recuperación** en Mi equipo."); st.stop(); return True
    if not _pin_coincide_tiempo_constante(user_data, pin_s):
        registrar_fallo_login(u_limpio); st.error(MSG_PIN_RESET_FALLIDO); st.stop(); return True
    msg_pw = mensaje_password_no_cumple_politica(p1s)
    if msg_pw:
        st.error(msg_pw); st.stop(); return True
    with st.spinner("Guardando tu nueva contraseña…"):
        limpiar_fallos_login(u_limpio)
        establecer_password_nuevo(st.session_state["usuarios_db"][usuario_encontrado], p1s, rounds=bcrypt_rounds_config())
        guardar_datos()
    st.success("Listo. Ya podés **iniciar sesión** con tu usuario y la contraseña nueva.")
    st.stop(); return True

def _procesar_login(empresa_login: str, u: str, p: str):
    """Maneja el flujo de login. No retorna nada — usa st.rerun/st.stop para controlar flujo."""
    if not u or not p:
        st.warning("Ingresá usuario y contraseña."); st.stop(); return
    u_limpio = u.strip().lower()
    ok_lock, msg = puede_intentar_login(u_limpio)
    if not ok_lock:
        st.error(msg); return
    if _intentar_login_emergencia(u_limpio, p, None):
        return
    ph = st.empty()
    ph.markdown(_auth_loader_markup("Autenticando..."), unsafe_allow_html=True)
    db_f, err_db = _cargar_db_login(empresa_login, u_limpio)
    ph.markdown(_auth_loader_markup("Verificando acceso..."), unsafe_allow_html=True)
    if err_db:
        ph.empty(); st.error(err_db); return
    if db_f is None:
        ph.empty(); st.error("No se pudieron cargar los datos."); return
    usuarios_disponibles_en_origen = _db_login_tiene_usuarios(db_f)
    for k, v in db_f.items():
        st.session_state[k] = v
    completar_claves_db_session(); asegurar_usuarios_base(solo_normalizar=modo_shard_activo())
    sincronizar_clinicas_desde_datos(st.session_state)
    usuario_encontrado = _buscar_usuario_por_login(u_limpio)
    if not usuario_encontrado:
        ph.empty()
        if _intentar_login_emergencia(u_limpio, p, ph):
            return
        if not usuarios_disponibles_en_origen:
            log_event("auth", "login_failed:usuarios_db_no_disponible")
            st.error(MSG_LOGIN_USUARIOS_NO_DISPONIBLES); return
        registrar_fallo_login(u_limpio); st.error(MSG_LOGIN_CREDENCIALES_FALLIDAS); return
    user_data = normalizar_usuario_sistema(dict(st.session_state["usuarios_db"][usuario_encontrado]))
    user_data["usuario_login"] = usuario_encontrado
    st.session_state["usuarios_db"][usuario_encontrado] = user_data
    ok_pw, migrar_hash = password_usuario_coincide(user_data, p)
    if user_data.get("estado", "Activo") == "Bloqueado":
        ph.empty(); registrar_fallo_login(u_limpio)
        st.error("Tu usuario está **bloqueado**. Contactá al coordinador o administrador de tu clínica para reactivar el acceso."); return
    if ok_pw:
        if migrar_hash:
            aplicar_hash_tras_login_ok(st.session_state["usuarios_db"][usuario_encontrado], p, rounds=bcrypt_rounds_config())
            user_data = dict(st.session_state["usuarios_db"][usuario_encontrado])
            user_data["usuario_login"] = usuario_encontrado
        if login_bloqueado_por_clinica(user_data):
            registrar_fallo_login(u_limpio); _log_rechazo_clinica(user_data, usuario_encontrado)
            ph.empty()
            st.error("La clinica asignada a tu usuario esta suspendida. No podes ingresar hasta la reactivacion."); return
        if requiere_2fa_correo(user_data):
            if migrar_hash:
                guardar_datos()
            ok_send, err_send = iniciar_desafio_login(str(user_data.get("email") or "").strip(), usuario_encontrado, u_limpio)
            if ok_send:
                st.info("Te enviamos un código de 6 dígitos. Revisá tu correo y completá el paso siguiente.")
                st.rerun()
            ph.empty(); st.error(err_send); return
        if login_email_2fa_enabled() and smtp_config_ok() and not usuario_email_2fa_valido(user_data):
            log_event("auth", "login_ok_2fa_omitido_sin_email_en_ficha")
        ph.empty()
        _completar_login_exitoso(user_data, u_limpio, "Login", "login_ok")
    else:
        ph.empty()
        if _intentar_login_emergencia(u_limpio, p, ph):
            return
        registrar_fallo_login(u_limpio); st.error(MSG_LOGIN_CREDENCIALES_FALLIDAS)

def _validar_empresa_usuario(user_data: dict, empresa_login: str, msg_error: str) -> bool:
    emp_l = str(empresa_login or "").strip().lower()
    coincide = str(user_data.get("empresa", "")).strip().lower() == emp_l
    if modo_shard_activo() and sesion_usa_monolito_legacy():
        ok = (not emp_l) or coincide
    else:
        ok = coincide
    if not ok:
        registrar_fallo_login(str(user_data.get("usuario_login", "")).lower())
        st.error(msg_error); st.stop()
    return ok

def _log_rechazo_clinica(user_data: dict, login_name: str):
    st.session_state.setdefault("logs_db", [])
    st.session_state["logs_db"].append({
        "F": ahora().strftime("%d/%m/%Y"), "H": ahora().strftime("%H:%M"),
        "U": str(user_data.get("nombre", login_name)),
        "E": str(user_data.get("empresa", "")),
        "A": f"Login rechazado (clinica suspendida) login={login_name}",
    })
    _persistir_logs_tras_rechazo_clinica()

def render_login():
    if "logeado" not in st.session_state:
        st.session_state["logeado"] = False
    if st.session_state.get("logeado") and not st.session_state.get("u_actual"):
        st.session_state["logeado"] = False
    if not st.session_state.get("logeado") and _render_bloque_verificacion_email_2fa():
        st.stop(); return
    if not st.session_state.get("logeado"):
        login_name = str(st.session_state.get("u_actual", {}).get("usuario_login", ""))
        if login_name:
            totp_cfg = st.session_state.get(f"_totp_config_{login_name}")
            if totp_cfg and getattr(totp_cfg, "habilitado", False):
                from core.seguridad_ui import render_login_totp
                st.markdown("---")
                if not render_login_totp(login_name):
                    st.stop(); return
    if not st.session_state.get("logeado"):
        from core.ui_liviano import headers_sugieren_equipo_liviano
        es_movil = headers_sugieren_equipo_liviano() or st.session_state.get("mc_liviano_modo") == "on"
        st.markdown('<span class="mc-auth-page-marker"></span>', unsafe_allow_html=True)
        if es_movil:
            st.markdown("""
            <style>
            .stTextInput input { min-height: 48px !important; font-size: 16px !important; }
            .stButton button { min-height: 48px !important; font-size: 16px !important; }
            .stForm { width: 100% !important; }
            .block-container { padding: 0.5rem 0.3rem !important; }
            section.main > div { padding-top: 0 !important; }
            </style>""", unsafe_allow_html=True)
        _auth_strip_modulo_query_param()
        if _auth_strip_pwreset_url_si_hay_param():
            st.session_state["_mc_pwreset_url_aviso_once"] = True
        modo_auth = st.session_state.get("mc_auth_mode_radio", "login")
        submit, empresa_login, u, p, pin_data = _render_login_ui(es_movil, modo_auth)
        if submit:
            if modo_auth == "pin_new":
                _procesar_pin_reset(empresa_login, u, pin_data)
            else:
                _procesar_login(empresa_login, u, p)
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
        _ult_rerun_susp = st.session_state.get("_ult_rerun_suspension_ts", 0)
        if (ahora().timestamp() - _ult_rerun_susp) > 5:
            st.session_state["_ult_rerun_suspension_ts"] = ahora().timestamp()
            st.rerun()


def check_inactividad():
    if st.session_state.get("logeado"):
        last_activity = st.session_state.get("_last_activity")
        if last_activity is None:
            st.session_state["_last_activity"] = time.time()
            st.session_state["ultima_actividad"] = ahora()
        else:
            elapsed = time.time() - last_activity
            remaining = SESSION_TIMEOUT_MINUTES * 60 - elapsed

            if remaining < 300 and remaining > 0 and not st.session_state.get("_timeout_warning_shown"):
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                if mins >= 2:
                    st.warning(f"⏳ Tu sesión expirará en **{mins} min** por inactividad. Hacé clic en «Sigo aquí» para mantenerla activa.")
                else:
                    st.warning(f"⏳⚠️ Tu sesión expirará en **{mins} min {secs}s** — hacé clic YA en «Sigo aquí».")
                if st.button("Sigo aquí", key="keep_alive"):
                    st.session_state["_last_activity"] = time.time()
                    st.session_state["ultima_actividad"] = ahora()
                    st.session_state["_timeout_warning_shown"] = False
                    st.rerun()
                st.session_state["_timeout_warning_shown"] = True

            if elapsed > SESSION_TIMEOUT_MINUTES * 60:
                st.session_state["logeado"] = False
                st.session_state.pop("ultima_actividad", None)
                st.session_state.pop("u_actual", None)
                st.session_state.pop("_mc_onboarding_oculto", None)
                st.session_state.pop("_last_activity", None)
                st.session_state.pop("_timeout_warning_shown", None)
                limpiar_estado_sesion_login_efimero()
                vaciar_datos_app_en_sesion()
                st.session_state["_aviso_sesion_expirada"] = (
                    f"Tu sesión se cerró automáticamente por inactividad ({SESSION_TIMEOUT_MINUTES} minutos)."
                )
                # Guard: evitar tormenta de reruns en móviles con red lenta
                _ult_rerun_exp = st.session_state.get("_ult_rerun_expiracion_ts", 0)
                if (ahora().timestamp() - _ult_rerun_exp) > 5:
                    st.session_state["_ult_rerun_expiracion_ts"] = ahora().timestamp()
                    st.rerun()
            elif not st.session_state.get("_timeout_warning_shown"):
                st.session_state["ultima_actividad"] = ahora()
                st.session_state["_last_activity"] = time.time()


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

