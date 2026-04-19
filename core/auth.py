import secrets
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
    password_usuario_coincide,
    texto_ayuda_politica_password_breve,
)
from core.session_auth_cleanup import limpiar_estado_sesion_login_efimero
from core.email_2fa import (
    SESSION_KEY,
    iniciar_desafio_login,
    limpiar_desafio_email_2fa,
    login_email_2fa_enabled,
    mascarar_email_privado,
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
    obtener_emergency_password,
    obtener_pin_usuario,
)

SESSION_TIMEOUT_MINUTES = 90
_DEBOUNCE_GUARDAR_LOGS_CLINICA_SEC = 60.0

# Mensajes genéricos ante fallo (no distinguir usuario inexistente vs contraseña incorrecta).
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
_SESSION_LOGIN_FLASH = "_mc_auth_login_flash"


def _auth_set_flash(key: str, kind: str, message: str) -> None:
    return None


def _auth_pop_flash(key: str) -> None:
    return None


def _auth_strip_pwreset_url_si_hay_param() -> bool:
    """
    Sin recuperación por correo en esta instalación: si la URL trae ?pwreset=, se elimina el parámetro
    y se devuelve True para mostrar un aviso único en la pantalla de login.
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


def _auth_strip_pwreset_query_param() -> None:
    qp = getattr(st, "query_params", None)
    if qp is None:
        return
    try:
        qp.pop("pwreset", None)
    except Exception:
        pass


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


def _buscar_usuario_por_login(login_texto: str):
    login_normalizado = str(login_texto or "").strip().lower()
    if not login_normalizado:
        return None
    for key_db in st.session_state.get("usuarios_db", {}).keys():
        if str(key_db or "").strip().lower() == login_normalizado:
            return key_db
    return None


def _pin_coincide_tiempo_constante(user_data: dict, pin_raw: str) -> bool:
    pin = str(pin_raw or "").strip()
    if len(pin) != 4 or not pin.isdigit():
        return False
    alm = str(obtener_pin_usuario(user_data) or "").strip()
    if not alm:
        return False
    try:
        return secrets.compare_digest(pin, alm)
    except Exception:
        return False


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
    st.session_state["_mc_login_transition"] = True
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
    if not st.session_state["logeado"] and _render_bloque_verificacion_email_2fa():
        st.stop()

    if not st.session_state["logeado"]:
        _auth_strip_modulo_query_param()
        if _auth_strip_pwreset_url_si_hay_param():
            st.session_state["_mc_pwreset_url_aviso_once"] = True
        _, col, _ = st.columns([0.9, 1.35, 0.9])
        with col:
            st.markdown(
                "<div style='text-align:center;margin-bottom:0.35rem'>"
                "<span style='font-size:0.72rem;font-weight:800;letter-spacing:0.18em;text-transform:uppercase;"
                "color:#2dd4bf'>Plataforma clínica</span></div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<h2 style='text-align:center;margin:0 0 0.15rem;font-size:1.55rem;font-weight:800;"
                "letter-spacing:-0.03em;background:linear-gradient(120deg,#5eead4,#60a5fa,#a5b4fc);"
                "-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent'>"
                "MediCare Enterprise PRO</h2>"
                "<p style='text-align:center;margin:0 0 1rem;font-size:0.88rem;color:#94a3b8'>V9.12 · Acceso institucional</p>",
                unsafe_allow_html=True,
            )
            st.caption(
                "Ingresá con el usuario (login) y contraseña que te asignó tu clínica. "
                "Si la clínica fue suspendida por abono o decisión administrativa, el acceso queda bloqueado hasta la reactivación: "
                "contactá a MediCare o a tu coordinador."
            )
            with st.expander("Problemas para ingresar o fallas del sistema", expanded=False):
                st.markdown(
                    "- Confirmá **usuario**, **contraseña** y, en multiclínica, **empresa** exacta como en Mi equipo.\n"
                    "- Varios intentos fallidos pueden activar **bloqueo temporal**: esperá unos minutos o pedí ayuda a coordinación.\n"
                    "- Pantalla en blanco o *No se pudo cargar el modulo*: probá **F5**; si vuelve, abrí el expander "
                    "**Detalle tecnico** en la app y enviá captura a soporte.\n"
                    "- Si no hay conexión, la app puede usar **modo local** con datos ya descargados; revisá WiFi o datos móviles."
                )
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
                    "Ingresá con **usuario** y **contraseña**. La contraseña no es el DNI salvo que tu clínica te haya "
                    "configurado la cuenta así."
                )
            else:
                st.caption(
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
                    submit = st.form_submit_button("Ingresar al sistema", use_container_width=True)
                else:
                    submit = st.form_submit_button("Guardar nueva contraseña", use_container_width=True)
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
                            _loader_ph.markdown("""
<style>
.mc-auth-overlay{position:fixed;top:0;left:0;width:100vw;height:100vh;
background:rgba(3,6,15,0.82);backdrop-filter:blur(14px);
-webkit-backdrop-filter:blur(14px);display:flex;flex-direction:column;
justify-content:center;align-items:center;z-index:9999999;gap:20px;}
.mc-auth-spinner{width:46px;height:46px;border:3px solid rgba(255,255,255,0.08);
border-left-color:#14b8a6;border-top-color:#60a5fa;border-radius:50%;
animation:mc-auth-spin 0.9s linear infinite;}
.mc-auth-title{color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
font-size:18px;font-weight:600;letter-spacing:0.3px;margin:0;}
.mc-auth-sub{color:#94a3b8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
font-size:13px;font-weight:400;letter-spacing:0.4px;margin:0;
animation:mc-auth-pulse 1.6s ease-in-out infinite;}
@keyframes mc-auth-spin{to{transform:rotate(360deg);}}
@keyframes mc-auth-pulse{0%,100%{opacity:1;}50%{opacity:0.5;}}
</style>
<div class="mc-auth-overlay">
  <div class="mc-auth-spinner"></div>
  <p class="mc-auth-title">MediCare Enterprise PRO</p>
  <p class="mc-auth-sub">Autenticando...</p>
</div>
""", unsafe_allow_html=True)
                            db_f, err_db = _cargar_db_login(empresa_login, u_limpio_pre)
                            _loader_ph.markdown("""
<style>.mc-auth-sub{animation:none !important;}</style>
<div class="mc-auth-overlay">
  <div class="mc-auth-spinner"></div>
  <p class="mc-auth-title">MediCare Enterprise PRO</p>
  <p class="mc-auth-sub">Verificando acceso...</p>
</div>
""", unsafe_allow_html=True)
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
                st.warning(f"Tu sesion se cerro automaticamente por inactividad ({SESSION_TIMEOUT_MINUTES} minutos).")
                st.rerun()
            else:
                st.session_state["ultima_actividad"] = ahora()
