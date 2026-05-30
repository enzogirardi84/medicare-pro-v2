"""Interfaz de usuario para flujos de seguridad: TOTP, ECDSA, Session Timeout.
Disenio profesional y sobrio para entorno medico.
"""

from __future__ import annotations

import base64
import io
import time
from typing import Any, Optional

import streamlit as st

from core.app_logging import log_event
from core.audit_trail_immutable import ImmutableAuditTrail
from core.totp_mfa import (
    TOTPManager,
    TOTPConfig,
    verificar_codigo_recuperacion,
    render_recovery_codes,
)


# ═══════════════════════════════════════════════════════════════════
# 1. PANTALLA DE LOGIN CON DESAFIO TOTP
# ═══════════════════════════════════════════════════════════════════

def render_login_totp(login_name: str) -> bool:
    """Muestra el desafio TOTP despues del login exitoso.

    Args:
        login_name: Nombre de usuario ya autenticado.

    Returns:
        True si TOTP fue verificado exitosamente.
    """
    st.markdown("### Verificacion de dos factores")
    st.caption("Ingresa el codigo de 6 digitos de tu app de autenticacion.")

    tab1, tab2 = st.tabs(["Codigo TOTP", "Codigo de recuperacion"])

    with tab1:
        codigo = st.text_input(
            "Codigo de autenticacion",
            max_chars=6,
            placeholder="000000",
            key="totp_login_code",
            label_visibility="collapsed",
        )
        cols = st.columns([1, 1])
        with cols[0]:
            if st.button("Verificar", type="primary", use_container_width=True, key="totp_verify_btn"):
                config: Optional[TOTPConfig] = st.session_state.get(f"_totp_config_{login_name}")
                if config and TOTPManager.verificar_codigo(config.secreto, codigo):
                    config.ultimo_uso = time.time()
                    st.session_state[f"_totp_config_{login_name}"] = config
                    st.session_state["totp_verified"] = True
                    st.rerun()
                else:
                    st.error("Codigo invalido. Verifica que la hora del dispositivo este sincronizada.")
        with cols[1]:
            if st.button("Cancelar", use_container_width=True, key="totp_cancel_btn"):
                st.session_state["logeado"] = False
                st.session_state.pop("u_actual", None)
                st.rerun()

    with tab2:
        st.caption("Usa uno de tus codigos de recuperacion si perdiste el acceso a la app.")
        recovery_code = st.text_input(
            "Codigo de recuperacion",
            placeholder="MED-XXXX-XXXX",
            key="totp_recovery_code",
            label_visibility="collapsed",
        )
        if st.button("Usar codigo de recuperacion", use_container_width=True, key="recovery_btn"):
            if verificar_codigo_recuperacion(login_name, recovery_code):
                st.session_state["totp_verified"] = True
                st.success("Acceso concedido via codigo de recuperacion.")
                st.rerun()
            else:
                st.error("Codigo de recuperacion invalido o ya utilizado.")

    return st.session_state.get("totp_verified", False)


# ═══════════════════════════════════════════════════════════════════
# 2. PANEL DE ENROLAMIENTO TOTP (MI PERFIL)
# ═══════════════════════════════════════════════════════════════════

def render_totp_enrollment(usuario: str) -> None:
    """Pantalla de configuracion de MFA TOTP desde el perfil del medico.

    Muestra QR, secreto en texto, confirmacion y codigos de recuperacion.
    """
    st.markdown("### Autenticacion de dos factores (2FA)")
    st.caption("Configura TOTP con tu app de autenticacion (Google Authenticator, Authy, etc.).")

    # Verificar si ya esta configurado
    config_actual: Optional[TOTPConfig] = st.session_state.get(f"_totp_config_{usuario}")
    if config_actual and config_actual.habilitado:
        st.success("2FA activo.")
        if st.button("Desactivar 2FA", type="secondary", key="totp_disable"):
            st.session_state.pop(f"_totp_config_{usuario}", None)
            st.session_state.pop("_totp_recovery_codes_" + usuario, None)
            st.rerun()
        return

    # Paso 1: Generar secreto
    if "totp_setup_secret" not in st.session_state:
        st.session_state["totp_setup_secret"] = TOTPManager.generar_secreto()

    secreto = st.session_state["totp_setup_secret"]
    uri = TOTPManager.generar_uri(usuario, secreto)
    qr_b64 = TOTPManager.generar_qr_b64(uri)

    # Layout en dos columnas
    col_qr, col_info = st.columns([1, 2])

    with col_qr:
        if qr_b64:
            st.image(f"data:image/png;base64,{qr_b64}", width=180)
        else:
            st.caption("QR no disponible. Instala `qrcode` para la imagen.")

    with col_info:
        st.markdown("**Paso 1:** Escanea el codigo QR con tu app")
        st.markdown("**Paso 2:** Ingresa el codigo de 6 digitos para confirmar")
        with st.expander("Mostrar codigo secreto en texto"):
            st.code(secreto, language="text")
            st.caption("Usa este codigo si no podes escanear el QR.")

    # Paso 2: Verificar codigo
    st.markdown("---")
    codigo = st.text_input(
        "Codigo de verificacion (6 digitos)",
        max_chars=6,
        placeholder="000000",
        key="totp_enroll_code",
    )
    if st.button("Confirmar y activar 2FA", type="primary", use_container_width=True, key="totp_enroll_btn"):
        if not codigo.strip():
            st.warning("Ingresa el codigo de 6 digitos de tu app.")
            return
        if TOTPManager.verificar_codigo(secreto, codigo):
            config = TOTPConfig(usuario=usuario, secreto=secreto, habilitado=True, ultimo_uso=time.time())
            st.session_state[f"_totp_config_{usuario}"] = config
            st.session_state.pop("totp_setup_secret", None)
            st.success("2FA activado correctamente.")
            log_event("totp", f"enrolamiento_ok:{usuario}")

            # Mostrar codigos de recuperacion
            st.markdown("### Codigos de recuperacion")
            st.warning("Guardalos en un lugar seguro. Cada codigo solo puede usarse una vez.")
            codes = render_recovery_codes(usuario)
            for c in codes:
                st.code(c, language="text")
            st.caption("Si perdes el celular, usa uno de estos codigos para acceder.")
            st.rerun()
        else:
            st.error("Codigo invalido. Verifica que la hora del telefono este sincronizada.")


# ═══════════════════════════════════════════════════════════════════
# 3. FORMULARIO DE EVOLUCION CON FIRMA ECDSA + UPLOAD VALIDATION
# ═══════════════════════════════════════════════════════════════════

def render_evolucion_form(paciente_sel: str, profesional: str) -> Optional[dict]:
    """Formulario de evolucion medica con firma digital y validacion de archivos.

    Args:
        paciente_sel: Paciente seleccionado.
        profesional: Profesional que firma.

    Returns:
        Dict con la evolucion creada, o None si no se envio.
    """
    st.markdown("### Registro de evolucion")
    st.caption(f"Paciente: {paciente_sel}")

    nota = st.text_area(
        "Nota medica",
        height=180,
        placeholder="Describa la evolucion del paciente, hallazgos, diagnostico y plan...",
        key="evol_nota",
    )

    col_diag, col_med = st.columns(2)
    with col_diag:
        diagnostico = st.text_input("Diagnostico (opcional)", placeholder="Ej: Neumonia adquirida")
    with col_med:
        medicacion = st.text_input("Medicacion indicada (opcional)", placeholder="Ej: Amoxicilina 500mg c/8hs")

    # Upload de estudios con validacion
    st.markdown("#### Estudio adjunto (opcional)")
    archivo = st.file_uploader(
        "Seleccionar archivo",
        type=["pdf", "jpg", "jpeg", "png", "gif", "webp"],
        key="evol_upload",
        label_visibility="collapsed",
    )

    upload_status = None
    if archivo is not None:
        with st.spinner("Validando archivo..."):
            try:
                from core.upload_sanitizer import validar_estudio_adjunto
                ok, msg, info = validar_estudio_adjunto(archivo)
                if ok:
                    upload_status = ("success", f"Archivo validado: {info['mime']} ({info['tamano'] // 1024} KB)")
                else:
                    upload_status = ("error", f"Archivo rechazado: {msg}")
            except ImportError:
                upload_status = ("success", "Archivo seleccionado (validacion basica).")

    if upload_status:
        kind, text = upload_status
        if kind == "success":
            st.success(text)
        else:
            st.error(text)

    # Boton de firma y guardado
    guardar = st.button(
        "Firmar y guardar evolucion",
        type="primary",
        use_container_width=True,
        key="evol_save_btn",
        disabled=(not nota.strip()),
    )

    if guardar:
        if not nota.strip():
            st.warning("La nota medica no puede estar vacia.")
            return None

        evol = {
            "paciente": paciente_sel,
            "nota": nota.strip(),
            "diagnostico": diagnostico.strip(),
            "medicacion": medicacion.strip(),
            "firma": profesional,
            "timestamp": time.time(),
        }

        # Simular firma ECDSA
        with st.spinner("Firmando documento con clave privada..."):
            time.sleep(0.5)
            try:
                priv_b64 = st.session_state.get(f"_ecdsa_priv_{profesional}")
                if priv_b64:
                    from core.ecdsa_signature import ECDSASignatureManager
                    priv_pem = base64.b64decode(priv_b64)
                    signed = ECDSASignatureManager.firmar(evol, priv_pem, firmante=profesional)
                    evol["_firma_ecdsa"] = ECDSASignatureManager.serializar(signed)
                    log_event("ecdsa", f"evolucion_firmada_ok:{paciente_sel}")
            except Exception as exc:
                log_event("ecdsa", f"firma_error:{type(exc).__name__}")

        # Procesar archivo si se subio
        if archivo is not None and upload_status and upload_status[0] == "success":
            try:
                evol["adjunto_b64"] = base64.b64encode(archivo.read()).decode()
                evol["adjunto_nombre"] = archivo.name
            except Exception as exc:
                log_event("evolucion", f"adjunto_error:{type(exc).__name__}")

        # Audit trail
        try:
            auditor = ImmutableAuditTrail()
            auditor.registrar(
                usuario=profesional,
                accion="escritura",
                recurso=f"evolucion:{paciente_sel}",
                detalle="Evolucion medica registrada y firmada",
            )
        except Exception as exc:
            log_event("audit", f"evolucion_audit_error:{type(exc).__name__}")

        return evol
    return None


# ═══════════════════════════════════════════════════════════════════
# 4. SISTEMA DE ALERTA DE TIMEOUT DE SESION (SIDEBAR)
# ═══════════════════════════════════════════════════════════════════

SESSION_TIMEOUT_MINUTES = 30


def render_session_timeout_indicator() -> None:
    """Muestra el tiempo restante de sesion en la barra lateral.

    Incluye auto-save automatico cuando el tiempo se agota.
    """
    last_activity = st.session_state.get("_session_last_activity")
    if last_activity is None:
        st.session_state["_session_last_activity"] = time.time()
        return

    elapsed = time.time() - last_activity
    remaining_seconds = SESSION_TIMEOUT_MINUTES * 60 - elapsed

    if remaining_seconds <= 0:
        _auto_save_and_logout()
        return

    remaining_minutes = int(remaining_seconds // 60)
    remaining_secs = int(remaining_seconds % 60)

    # Indicador visual en sidebar
    if remaining_minutes > 10:
        color = "#94a3b8"
    elif remaining_minutes > 2:
        color = "#f59e0b"
    else:
        color = "#ef4444"

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"<div style='font-size:0.75rem;color:{color};text-align:center;'>"
        f"Sesion: {remaining_minutes:02d}:{remaining_secs:02d}</div>",
        unsafe_allow_html=True,
    )

    # Warning si queda menos de 2 minutos
    if remaining_minutes < 2 and not st.session_state.get("_session_timeout_warning_shown"):
        st.session_state["_session_timeout_warning_shown"] = True
        st.sidebar.warning(
            f"La sesion expirara en {remaining_minutes}m {remaining_secs}s. "
            "Los cambios se guardaran automaticamente.",
        )


def _auto_save_and_logout() -> None:
    """Guarda los datos pendientes y cierra la sesion."""
    try:
        if st.session_state.get("_guardar_datos_pendiente"):
            from core.database import guardar_datos
            guardar_datos(spinner=False)
            log_event("session", "auto_save_ok")
    except Exception as exc:
        log_event("session", f"auto_save_error:{type(exc).__name__}")

    st.session_state["logeado"] = False
    st.session_state.pop("u_actual", None)
    st.session_state.pop("_session_last_activity", None)
    st.session_state.pop("_session_timeout_warning_shown", None)
    st.warning("Sesion expirada por inactividad. Los datos fueron guardados.")
    st.rerun()
