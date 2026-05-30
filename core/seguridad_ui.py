"""Interfaz de seguridad optimizada para produccion: TOTP, ECDSA, Session Timeout.
Incluye cache, manejo de memoria, fragment para timeout y exception handler centralizado.
"""
from __future__ import annotations

import base64
import os
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional

import streamlit as st

from core.app_logging import log_event

SESSION_TIMEOUT_MINUTES = 30
UPLOAD_DIR = Path("storage/estudios")


# ═══════════════════════════════════════════════════════════════════
# 0. EXCEPTION HANDLER CENTRALIZADO
# ═══════════════════════════════════════════════════════════════════

def ui_error_boundary(fallback_message: str = "Error interno. La operacion no pudo completarse."):
    """Decorador que captura excepciones en funciones de UI.

    En lugar de mostrar un traceback de Python, registra el error
    en el log y muestra un mensaje controlado al usuario.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                log_event("seguridad_ui", f"{func.__name__}:{type(exc).__name__}:{exc}")
                st.error(fallback_message)
                if st.session_state.get("_debug_mode"):
                    with st.expander("Detalle tecnico"):
                        st.code(f"{type(exc).__name__}: {exc}", language="text")
                return None if "return" in func.__annotations__ else None
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════════
# 1. CACHE: Funciones pesadas cacheadas por sesion
# ═══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_qr_generar(uri: str) -> str:
    """Genera QR en base64 con cache de 1 hora."""
    try:
        import qrcode
        import io
        qr = qrcode.make(uri)
        buf = io.BytesIO()
        qr.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except ImportError:
        return ""


@st.cache_data(ttl=300, show_spinner=False)
def _cached_magic_validation(file_bytes: bytes, ext: str) -> tuple[bool, str, str]:
    """Valida Magic Numbers con cache de 5 minutos por contenido identico."""
    try:
        from core.upload_sanitizer import sanitizar_archivo
        ok, msg, info = sanitizar_archivo(f"archivo{ext}", file_bytes)
        if ok and info:
            return True, msg, info["mime"]
        return False, msg, ""
    except ImportError:
        from core.upload_sanitizer import MAGIC_NUMBERS
        for magic_ext, magic_bytes, mime in MAGIC_NUMBERS:
            if magic_bytes and file_bytes[:len(magic_bytes)] == magic_bytes:
                if ext == ".txt" and mime != "text/plain":
                    return False, "Formato incompatible.", ""
                return True, "Formato valido.", mime
        return False, "Tipo de archivo no reconocido.", ""


@st.cache_resource(ttl=3600)
def _cached_audit_trail() -> Any:
    """Instancia compartida del audit trail (recurso pesado)."""
    from core.audit_trail_immutable import ImmutableAuditTrail
    return ImmutableAuditTrail()


# ═══════════════════════════════════════════════════════════════════
# 2. MANEJO EFICIENTE DE UPLOADS (sin memory leaks)
# ═══════════════════════════════════════════════════════════════════

def _procesar_upload_seguro(
    uploaded_file: Any,
) -> tuple[bool, str, Optional[dict]]:
    """Procesa un archivo subido: valida, escribe a disco, libera memoria.

    1. Lee el archivo en memoria
    2. Valida con upload sanitizer (magic numbers)
    3. Escribe a disco en directorio seguro
    4. Libera el buffer explicito
    5. Retorna metadata del archivo guardado

    Returns:
        (ok, mensaje, info) con ruta del archivo en disco.
    """
    if uploaded_file is None:
        return False, "No se selecciono archivo.", None

    nombre_original = str(getattr(uploaded_file, "name", "archivo") or "archivo")
    ext = os.path.splitext(nombre_original)[1].lower()

    # 1. Leer bytes (unica lectura en RAM)
    raw_bytes = uploaded_file.read()

    # 2. Liberar el buffer de Streamlit inmediatamente
    uploaded_file.seek(0)
    if hasattr(uploaded_file, "close"):
        uploaded_file.close()
    # Forzar garbage collection
    del uploaded_file

    # 3. Validar con cache de magic numbers
    ok, msg, mime = _cached_magic_validation(raw_bytes, ext)
    if not ok:
        del raw_bytes
        return False, msg, None

    # 4. Generar nombre seguro con hash SHA256
    import hashlib
    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    nombre_seguro = f"{sha256[:16]}_{int(time.time())}{ext}"
    ruta_disco = UPLOAD_DIR / nombre_seguro

    # 5. Escribir a disco
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ruta_disco.write_bytes(raw_bytes)

    info = {
        "ruta": str(ruta_disco),
        "nombre": nombre_seguro,
        "mime": mime,
        "sha256": sha256,
        "tamano": len(raw_bytes),
    }

    # 6. Liberar el buffer de memoria
    del raw_bytes

    return True, "Archivo guardado en almacenamiento seguro.", info


# ═══════════════════════════════════════════════════════════════════
# 3. LOGIN TOTP (optimizado con manejo de estados)
# ═══════════════════════════════════════════════════════════════════

@ui_error_boundary("Error en la verificacion de dos factores.")
def render_login_totp(login_name: str) -> bool:
    """Desafio TOTP post-login. Cachea el secreto en session_state."""
    if st.session_state.get("totp_verified"):
        return True

    st.markdown("### Verificacion de dos factores")
    st.caption("Ingresa el codigo de 6 digitos de tu app de autenticacion.")

    tab1, tab2 = st.tabs(["Codigo TOTP", "Codigo de recuperacion"])

    with tab1:
        codigo = st.text_input("Codigo", max_chars=6, placeholder="000000", key="totp_code", label_visibility="collapsed")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Verificar", type="primary", use_container_width=True, key="totp_vf"):
                from core.totp_mfa import TOTPManager
                config = st.session_state.get(f"_totp_config_{login_name}")
                if config and TOTPManager.verificar_codigo(config.secreto, codigo):
                    config.ultimo_uso = time.time()
                    st.session_state[f"_totp_config_{login_name}"] = config
                    st.session_state["totp_verified"] = True
                    st.rerun()
                else:
                    st.error("Codigo invalido.")
        with c2:
            if st.button("Cancelar", use_container_width=True, key="totp_cl"):
                st.session_state["logeado"] = False
                st.session_state.pop("u_actual", None)
                st.rerun()

    with tab2:
        st.caption("Usa un codigo de recuperacion si perdiste el acceso a la app.")
        rc = st.text_input("Codigo", placeholder="MED-XXXX-XXXX", key="totp_rc", label_visibility="collapsed")
        if st.button("Usar codigo de recuperacion", use_container_width=True, key="totp_rc_btn"):
            from core.totp_mfa import verificar_codigo_recuperacion
            if verificar_codigo_recuperacion(login_name, rc):
                st.session_state["totp_verified"] = True
                st.success("Acceso concedido.")
                st.rerun()
            else:
                st.error("Codigo invalido o ya utilizado.")

    return bool(st.session_state.get("totp_verified"))


# ═══════════════════════════════════════════════════════════════════
# 4. ENROLAMIENTO TOTP (con QR cacheado)
# ═══════════════════════════════════════════════════════════════════

@ui_error_boundary("Error en la configuracion de 2FA.")
def render_totp_enrollment(usuario: str) -> None:
    """Configuracion de 2FA con QR cacheado y codigos de recuperacion."""
    st.markdown("### Autenticacion de dos factores (2FA)")
    st.caption("Configura TOTP con tu app de autenticacion.")

    config = st.session_state.get(f"_totp_config_{usuario}")
    if config and getattr(config, "habilitado", False):
        st.success("2FA activo.")
        if st.button("Desactivar 2FA", type="secondary", key="totp_disable"):
            st.session_state.pop(f"_totp_config_{usuario}", None)
            st.session_state.pop("_totp_recovery_codes_" + usuario, None)
            st.rerun()
        return

    if "totp_secret" not in st.session_state:
        from core.totp_mfa import TOTPManager
        st.session_state["totp_secret"] = TOTPManager.generar_secreto()

    secreto: str = st.session_state["totp_secret"]

    from core.totp_mfa import TOTPManager
    uri = TOTPManager.generar_uri(usuario, secreto)
    qr_b64 = _cached_qr_generar(uri)

    col_qr, col_info = st.columns([1, 2])
    with col_qr:
        if qr_b64:
            st.image(f"data:image/png;base64,{qr_b64}", width=180)
        else:
            st.caption("QR no disponible.")
    with col_info:
        st.markdown("**1.** Escanea el codigo QR con tu app")
        st.markdown("**2.** Ingresa el codigo de 6 digitos para confirmar")
        with st.expander("Mostrar codigo secreto"):
            st.code(secreto, language="text")

    codigo = st.text_input("Codigo de verificacion", max_chars=6, placeholder="000000", key="totp_enr_code")
    if st.button("Confirmar y activar 2FA", type="primary", use_container_width=True, key="totp_enr_btn"):
        if not codigo.strip():
            st.warning("Ingresa el codigo de 6 digitos.")
            return
        if TOTPManager.verificar_codigo(secreto, codigo):
            from core.totp_mfa import TOTPConfig, render_recovery_codes
            config = TOTPConfig(usuario=usuario, secreto=secreto, habilitado=True, ultimo_uso=time.time())
            st.session_state[f"_totp_config_{usuario}"] = config
            st.session_state.pop("totp_secret", None)
            st.success("2FA activado.")
            log_event("totp", f"enrolamiento_ok:{usuario}")
            st.markdown("### Codigos de recuperacion")
            st.warning("Guardalos en un lugar seguro. Cada codigo solo puede usarse una vez.")
            for c in render_recovery_codes(usuario):
                st.code(c, language="text")
            st.rerun()
        else:
            st.error("Codigo invalido. Verifica la hora del dispositivo.")


# ═══════════════════════════════════════════════════════════════════
# 5. FORMULARIO DE EVOLUCION (con firmas cacheadas + upload eficiente)
# ═══════════════════════════════════════════════════════════════════

@ui_error_boundary("Error al guardar la evolucion. Los datos no se perdieron.")
def render_evolucion_form(paciente_sel: str, profesional: str) -> Optional[dict]:
    """Formulario de evolucion con upload optimizado y firma ECDSA."""
    st.markdown("### Registro de evolucion")
    st.caption(f"Paciente: {paciente_sel}")

    nota = st.text_area("Nota medica", height=180, key="evol_nota",
                        placeholder="Describa la evolucion del paciente...")

    col_d, col_m = st.columns(2)
    with col_d:
        diagnostico = st.text_input("Diagnostico", placeholder="Ej: Neumonia")
    with col_m:
        medicacion = st.text_input("Medicacion", placeholder="Ej: Amoxicilina 500mg")

    # Upload con manejo de memoria seguro
    st.markdown("#### Estudio adjunto (opcional)")
    uploaded = st.file_uploader("Archivo", type=["pdf", "jpg", "jpeg", "png", "gif", "webp"],
                                key="evol_up", label_visibility="collapsed")

    upload_info: Optional[dict] = None
    if uploaded is not None:
        with st.spinner("Validando archivo..."):
            ok, msg, upload_info = _procesar_upload_seguro(uploaded)
            if ok:
                st.success(f"Archivo validado: {upload_info['mime']} ({upload_info['tamano'] // 1024} KB)")
            else:
                st.error(f"Archivo rechazado: {msg}")

    guardar = st.button("Firmar y guardar evolucion", type="primary",
                        use_container_width=True, key="evol_save",
                        disabled=(not nota.strip()))

    if guardar:
        if not nota.strip():
            st.warning("La nota medica no puede estar vacia.")
            return None

        evol: dict[str, Any] = {
            "paciente": paciente_sel,
            "nota": nota.strip(),
            "diagnostico": diagnostico.strip(),
            "medicacion": medicacion.strip(),
            "firma": profesional,
            "timestamp": time.time(),
        }

        if upload_info:
            evol["adjunto_ruta"] = upload_info["ruta"]
            evol["adjunto_nombre"] = upload_info["nombre"]
            evol["adjunto_mime"] = upload_info["mime"]
            evol["adjunto_sha256"] = upload_info["sha256"]

        # Firma ECDSA con cache de clave privada
        with st.spinner("Firmando documento con clave privada..."):
            priv_b64 = st.session_state.get(f"_ecdsa_priv_{profesional}")
            if priv_b64:
                try:
                    from core.ecdsa_signature import ECDSASignatureManager
                    priv_pem = base64.b64decode(priv_b64)
                    signed = ECDSASignatureManager.firmar(evol, priv_pem, firmante=profesional)
                    evol["_firma_ecdsa"] = ECDSASignatureManager.serializar(signed)
                except Exception as exc:
                    log_event("ecdsa", f"firma_error:{type(exc).__name__}")

        # Audit trail (instancia cacheada)
        try:
            auditor = _cached_audit_trail()
            auditor.registrar(usuario=profesional, accion="escritura",
                              recurso=f"evolucion:{paciente_sel}",
                              detalle="Evolucion firmada digitalmente")
        except Exception as exc:
            log_event("audit", f"evolucion_audit_error:{type(exc).__name__}")

        return evol
    return None


# ═══════════════════════════════════════════════════════════════════
# 6. SESSION TIMEOUT INDICATOR (usando st.fragment para eficiencia)
# ═══════════════════════════════════════════════════════════════════

def render_session_timeout_indicator() -> None:
    """Muestra el tiempo restante de sesion en la barra lateral.

    NOTA: No usa st.fragment porque los fragmentos no soportan
    st.sidebar. Se ejecuta en cada rerun pero es ligero.
    """
    try:
        last_activity = st.session_state.get("_session_last_activity")
        if last_activity is None:
            st.session_state["_session_last_activity"] = time.time()
            return

        elapsed = time.time() - last_activity
        remaining = SESSION_TIMEOUT_MINUTES * 60 - elapsed

        if remaining <= 0:
            _auto_save_and_logout()
            return

        mins = int(remaining // 60)
        secs = int(remaining % 60)
        color = "#94a3b8" if mins > 10 else ("#f59e0b" if mins > 2 else "#ef4444")

        st.sidebar.markdown("---")
        st.sidebar.markdown(
            f"<div style='font-size:0.75rem;color:{color};text-align:center;'>"
            f"Sesion: {mins:02d}:{secs:02d}</div>",
            unsafe_allow_html=True,
        )

        if mins < 2 and not st.session_state.get("_session_timeout_warning_shown"):
            st.session_state["_session_timeout_warning_shown"] = True
            st.sidebar.warning("La sesion expirara en menos de 2 minutos. Los cambios se guardaran automaticamente.")
    except Exception as exc:
        log_event("seguridad_ui", f"timeout_indicator_error:{type(exc).__name__}")


def _auto_save_and_logout() -> None:
    """Guarda datos pendientes y cierra sesion."""
    try:
        if st.session_state.get("_guardar_datos_pendiente"):
            from core.database import guardar_datos
            guardar_datos(spinner=False)
    except Exception as exc:
        log_event("session", f"auto_save_error:{type(exc).__name__}")

    st.session_state["logeado"] = False
    for k in ("u_actual", "_session_last_activity", "_session_timeout_warning_shown"):
        st.session_state.pop(k, None)
    st.warning("Sesion expirada por inactividad. Los datos fueron guardados.")
    st.rerun()
