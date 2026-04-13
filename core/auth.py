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
from core.password_reset_email import (
    crear_token_restablecimiento,
    enviar_correo_confirmacion_cambio_password,
    enviar_correo_restablecimiento,
    extraer_token_restablecimiento_desde_texto,
    verificar_token_restablecimiento,
)
from core.utils import (
    DEFAULT_ADMIN_USER,
    ahora,
    asegurar_usuarios_base,
    logins_clave_default_superadmin,
    normalizar_usuario_sistema,
    obtener_email_usuario,
)

SESSION_TIMEOUT_MINUTES = 90
_DEBOUNCE_GUARDAR_LOGS_CLINICA_SEC = 60.0

# Mensajes genéricos ante fallo (no distinguir usuario inexistente vs contraseña incorrecta).
MSG_LOGIN_CREDENCIALES_FALLIDAS = (
    "No pudimos validar el acceso. Revisá **usuario** y **contraseña** "
    "(no el PIN de 4 dígitos ni el DNI, salvo que esa sea la clave que te asignaron). "
    "En **multiclínica**, el nombre de **Empresa / Clínica** debe coincidir con Mi equipo. "
    "Si olvidaste la clave, usá «Olvidé mi contraseña» (correo con enlace seguro si está configurado SMTP)."
)
MSG_RECOVER_DATOS_INVALIDOS = (
    "No pudimos validar los datos. Revisá usuario y empresa tal como figuran en Mi equipo e intentá de nuevo."
)
_SESSION_LOGIN_FLASH = "_mc_auth_login_flash"
_SESSION_RECOVER_FLASH = "_mc_auth_recover_flash"


def _auth_set_flash(key: str, kind: str, message: str) -> None:
    return None


def _auth_pop_flash(key: str) -> None:
    return None


def _obtener_pwreset_desde_query() -> str:
    qp = getattr(st, "query_params", None)
    if qp is None:
        return ""
    try:
        raw = qp.get("pwreset")
        if raw is None:
            return ""
        if isinstance(raw, list):
            s = str(raw[0] or "").strip()
        else:
            s = str(raw).strip()
        return extraer_token_restablecimiento_desde_texto(s) if s else ""
    except Exception:
        return ""


def _sincronizar_pwreset_desde_query() -> str:
    token = _obtener_pwreset_desde_query()
    if token and len(token) > 24:
        st.session_state["mc_auth_mode_radio"] = "recover"
        st.session_state["mc_pwreset_token"] = token
        st.session_state["_mc_pwreset_link_detected"] = True
        return token
    return ""


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
    if not st.session_state["logeado"] and _render_bloque_verificacion_email_2fa():
        st.stop()

    if not st.session_state["logeado"]:
        _auth_strip_modulo_query_param()
        _sincronizar_pwreset_desde_query()
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
            modo_auth = st.radio(
                "Acceso",
                ["login", "recover"],
                horizontal=True,
                label_visibility="collapsed",
                format_func=lambda m: "Iniciar sesión" if m == "login" else "Olvidé mi contraseña",
                key="mc_auth_mode_radio",
            )

            if modo_auth == "login":
                st.session_state.pop(_SESSION_RECOVER_FLASH, None)
                _sec_tip = texto_ayuda_proteccion()
                if _sec_tip:
                    st.caption(_sec_tip)
                st.caption(
                    "En este paso usás **usuario + contraseña**. Para una clave nueva usá **Olvidé mi contraseña**: "
                    "te enviamos un **correo** con enlace seguro (requiere SMTP y correo cargado en Mi equipo). "
                    "La contraseña no es el DNI salvo que tu clínica te haya configurado la cuenta así."
                )
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
                    p = st.text_input(
                        "Contraseña",
                        type="password",
                        help="Clave de acceso asignada o definida por tu clínica; no el PIN de 4 dígitos ni el DNI, salvo que esa sea tu clave.",
                    )
                    if st.form_submit_button("Ingresar al sistema", use_container_width=True):
                        if not u.strip() or not p.strip():
                            st.warning("Ingresá usuario y contraseña.")
                            st.stop()
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
                                    usuario_encontrado = _buscar_usuario_por_login(u_limpio)

                                    if usuario_encontrado:
                                        user_data = normalizar_usuario_sistema(
                                            dict(st.session_state["usuarios_db"][usuario_encontrado])
                                        )
                                        user_data["usuario_login"] = usuario_encontrado
                                        st.session_state["usuarios_db"][usuario_encontrado] = user_data
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
            else:
                st.session_state.pop(_SESSION_LOGIN_FLASH, None)
                _rec_tip = texto_ayuda_proteccion()
                if _rec_tip:
                    st.caption(_rec_tip)
                token_precargado = bool(str(st.session_state.get("mc_pwreset_token", "")).strip())

                st.markdown(
                    f"**Recuperación por correo** · Contraseña nueva: mínimo **{password_min_length()}** caracteres. "
                    "Opcional: **PIN** de 4 dígitos en el mismo paso."
                )
                if st.session_state.pop("_mc_pwreset_link_detected", False):
                    st.success(
                        "Detectamos el enlace de recuperación del correo. Ya podés definir la nueva contraseña "
                        "(y el PIN opcional) en el paso 2."
                    )
                if not smtp_config_ok():
                    st.warning(
                        "El envío de correo no está configurado (SMTP en secretos). "
                        "Pedí a quien administra el servidor que defina SMTP_HOST, SMTP_PASSWORD y SMTP_FROM; "
                        "hasta entonces la recuperación automática no puede enviarse."
                    )
                else:
                    st.caption(
                        "Te enviamos un mensaje con enlace seguro y token de respaldo. "
                        "Definí **APP_PUBLIC_URL** en secretos (URL pública de esta app, ej. https://tu-app.streamlit.app) "
                        "para que el botón del correo abra la app directamente."
                    )
                    _2fa_txt = texto_ayuda_email_2fa_config()
                    if _2fa_txt:
                        st.caption(_2fa_txt)

                with st.expander("¿No llega el correo o el enlace venció?", expanded=False):
                    st.markdown(
                        "- Revisá **spam** o **promociones**.\n"
                        "- Tu coordinador debe tener cargado tu correo en **Mi equipo**.\n"
                        "- Enlaces y tokens **caducan**: pedí uno nuevo con **Enviar instrucciones** y usá el último mensaje.\n"
                        "- Si abrís el enlace en otro dispositivo, podés **copiar el token** del correo y pegarlo en el paso 2."
                    )

                st.divider()
                st.markdown("##### 1 · Solicitar correo")
                with st.form("recover_send_email", clear_on_submit=False):
                    rec_u = st.text_input("Usuario (login)")
                    rec_emp = st.text_input("Empresa / clínica asignada")
                    if st.form_submit_button("Enviar instrucciones a mi correo", use_container_width=True):
                        if not rec_u.strip():
                            st.warning("Ingresá tu usuario (login).")
                            st.stop()
                        elif not smtp_config_ok():
                            st.error(
                                "No hay servidor de correo configurado. Contactá al administrador del sistema."
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
                                    usuario_encontrado = _buscar_usuario_por_login(u_limpio)
                                    if not usuario_encontrado:
                                        registrar_fallo_login(u_limpio)
                                        st.error(MSG_RECOVER_DATOS_INVALIDOS)
                                    else:
                                        user_data = normalizar_usuario_sistema(
                                            dict(st.session_state["usuarios_db"][usuario_encontrado])
                                        )
                                        st.session_state["usuarios_db"][usuario_encontrado] = user_data
                                        rec_emp_l = rec_emp.strip().lower()
                                        empresa_coincide = (
                                            str(user_data.get("empresa", "")).strip().lower() == rec_emp_l
                                        )
                                        if modo_shard_activo() and sesion_usa_monolito_legacy():
                                            empresa_ok = (not rec_emp.strip()) or empresa_coincide
                                        else:
                                            empresa_ok = empresa_coincide
                                        if not empresa_ok:
                                            registrar_fallo_login(u_limpio)
                                            st.error(MSG_RECOVER_DATOS_INVALIDOS)
                                        elif user_data.get("estado", "Activo") == "Bloqueado":
                                            registrar_fallo_login(u_limpio)
                                            st.error(
                                                "Tu usuario está bloqueado. Contactá al coordinador para reactivar el acceso."
                                            )
                                        else:
                                            email_actual = obtener_email_usuario(user_data)
                                            if not email_actual or not str(email_actual).strip():
                                                registrar_fallo_login(u_limpio)
                                                st.error(
                                                    "Tu cuenta no tiene correo registrado. "
                                                    "Un coordinador debe cargarlo en **Mi equipo**."
                                                )
                                            else:
                                                token, _exp = crear_token_restablecimiento(
                                                    usuario_encontrado,
                                                    u_limpio,
                                                    str(user_data.get("empresa", "") or ""),
                                                )
                                                nombre_m = str(
                                                    user_data.get("nombre") or usuario_encontrado
                                                )
                                                with st.spinner("Enviando correo…"):
                                                    ok_mail, err_mail = enviar_correo_restablecimiento(
                                                        str(email_actual).strip(),
                                                        nombre_m,
                                                        token,
                                                    )
                                                if ok_mail:
                                                    em_m = mascarar_email_privado(str(email_actual).strip())
                                                    st.success(
                                                        f"Listo. Revisá **{em_m}** (y la carpeta de spam) en los próximos minutos."
                                                    )
                                                else:
                                                    st.error(err_mail or "No se pudo enviar el correo.")

                st.divider()
                st.markdown("##### 2 · Definir nueva contraseña")
                st.caption(texto_ayuda_politica_password_breve())
                if token_precargado:
                    st.caption(
                        "Abriste el enlace del correo. El token ya está cargado: elegí la nueva contraseña "
                        "(y, si querés, un PIN nuevo) y guardá."
                    )
                else:
                    st.caption(
                        "Abrí el enlace del correo o pegá el token aquí, elegí una clave nueva "
                        "(PIN opcional) y guardá."
                    )
                with st.form("recover_set_password", clear_on_submit=True):
                    rec_tok = st.text_input(
                        "Token de recuperación (o pegá el enlace completo y borrá lo demás)",
                        key="mc_pwreset_token",
                    )
                    rec_pass_a = st.text_input("Nueva contraseña", type="password")
                    rec_pass_b = st.text_input("Repetir nueva contraseña", type="password")
                    rec_pin_a = st.text_input(
                        "Nuevo PIN de recuperación (4 dígitos, opcional)",
                        type="password",
                        max_chars=4,
                        help="Si lo completás, debe coincidir con el campo de abajo. Dejalo vacío para no cambiar el PIN.",
                    )
                    rec_pin_b = st.text_input(
                        "Repetir PIN (opcional)",
                        type="password",
                        max_chars=4,
                    )
                    if st.form_submit_button("Guardar nueva contraseña", use_container_width=True):
                        tok_raw = extraer_token_restablecimiento_desde_texto(rec_tok)
                        if not tok_raw:
                            st.warning("Pegá el token del correo o usá el enlace que te enviamos.")
                            st.stop()
                        elif not rec_pass_a.strip() or not rec_pass_b.strip():
                            st.warning("Completá la nueva contraseña en ambos campos.")
                            st.stop()
                        elif rec_pass_a.strip() != rec_pass_b.strip():
                            st.error("Las contraseñas no coinciden.")
                        else:
                            pin_a = str(rec_pin_a or "").strip()
                            pin_b = str(rec_pin_b or "").strip()
                            if pin_a or pin_b:
                                if pin_a != pin_b:
                                    st.error("Los PIN no coinciden.")
                                    st.stop()
                                if len(pin_a) != 4 or not pin_a.isdigit():
                                    st.error("El PIN debe ser exactamente 4 dígitos numéricos.")
                                    st.stop()
                            pin_nuevo = pin_a if pin_a else None
                            ok_t, err_t, info = verificar_token_restablecimiento(tok_raw)
                            if not ok_t or not info:
                                st.error(err_t or "Token inválido.")
                            else:
                                uk = info["uk"]
                                u_limpio = info["u_limpio"]
                                emp_tok = info.get("empresa", "")
                                ok_rec2, lock_rec2 = puede_intentar_login(u_limpio)
                                if not ok_rec2:
                                    st.error(lock_rec2)
                                else:
                                    db_f2, err_rec2 = _cargar_db_recover(emp_tok, u_limpio)
                                    if err_rec2:
                                        st.error(err_rec2)
                                    elif db_f2 is None:
                                        st.error("No se pudieron cargar los datos.")
                                    else:
                                        for k, v in db_f2.items():
                                            st.session_state[k] = v
                                        completar_claves_db_session()
                                        asegurar_usuarios_base(solo_normalizar=modo_shard_activo())
                                        sincronizar_clinicas_desde_datos(st.session_state)
                                        if uk not in st.session_state.get("usuarios_db", {}):
                                            st.error(
                                                "El token ya no coincide con la base actual. Solicitá un correo nuevo."
                                            )
                                        else:
                                            user_data2 = normalizar_usuario_sistema(
                                                dict(st.session_state["usuarios_db"][uk])
                                            )
                                            st.session_state["usuarios_db"][uk] = user_data2
                                            if user_data2.get("estado", "Activo") == "Bloqueado":
                                                st.error(
                                                    "Tu usuario está bloqueado. No se puede cambiar la contraseña hasta reactivar la cuenta."
                                                )
                                            else:
                                                _msg_pw = mensaje_password_no_cumple_politica(rec_pass_a)
                                                if _msg_pw:
                                                    st.error(_msg_pw)
                                                else:
                                                    with st.spinner("Guardando tu acceso…"):
                                                        limpiar_fallos_login(u_limpio)
                                                        establecer_password_nuevo(
                                                            st.session_state["usuarios_db"][uk],
                                                            rec_pass_a.strip(),
                                                            rounds=bcrypt_rounds_config(),
                                                        )
                                                        if pin_nuevo:
                                                            st.session_state["usuarios_db"][uk]["pin"] = pin_nuevo
                                                            log_event("auth", "password_reset_pin_via_email_ok")
                                                        guardar_datos()
                                                        log_event("auth", "password_reset_via_email_token_ok")
                                                        email_confirmacion = obtener_email_usuario(user_data2)
                                                        ok_confirm = False
                                                        if email_confirmacion:
                                                            ok_confirm, _err_confirm = (
                                                                enviar_correo_confirmacion_cambio_password(
                                                                    str(email_confirmacion).strip(),
                                                                    str(user_data2.get("nombre") or uk),
                                                                    pin_actualizado=bool(pin_nuevo),
                                                                )
                                                            )
                                                        _auth_strip_pwreset_query_param()
                                                        st.session_state.pop("mc_pwreset_token", None)
                                                    msg_exito = (
                                                        "Contraseña actualizada. Ya podés iniciar sesión con la clave nueva."
                                                    )
                                                    if pin_nuevo:
                                                        msg_exito += " El PIN de recuperación nuevo también quedó guardado."
                                                    st.success(msg_exito)
                                                    if email_confirmacion and ok_confirm:
                                                        st.info(
                                                            "También te enviamos una confirmación de seguridad a tu correo."
                                                        )
                                                    elif email_confirmacion and not ok_confirm:
                                                        st.caption(
                                                            "Tu clave se guardó bien, pero no pudimos enviar el correo de confirmación. "
                                                            "Si tenés dudas, avisá a coordinación."
                                                        )
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
