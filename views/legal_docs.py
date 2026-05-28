from __future__ import annotations

import streamlit as st
from datetime import datetime

from core.app_logging import log_event
from core.view_helpers import bloque_mc_grid_tarjetas
from core.utils import ahora


_LEY_26529 = """
**Ley 26.529 - Derechos del Paciente, Historia Clinica y Consentimiento Informado**
Sancionada: 2009-11-19

**Articulos clave:**
- **Art. 2:** Derechos del paciente (trato digno, respeto, intimidad, confidencialidad)
- **Art. 5:** Consentimiento informado (escrito, verbal ante testigos)
- **Art. 6:** Excepciones al consentimiento informado (riesgo vital, urgencia)
- **Art. 7:** Revocabilidad del consentimiento
- **Art. 12:** Historia Clinica (obligatoria, cronologica, legible, foliada)

**Implementacion en el sistema:**
- Modulo de consentimientos informados con firma digital
- Historia Clinica Integral exportable en PDF
- Registro de revocacion de consentimientos
- Trazabilidad de accesos a historia clinica
"""

_LEY_25326 = """
**Ley 25.326 - Proteccion de los Datos Personales (Habeas Data)**
Sancionada: 2000-10-04

**Articulos clave:**
- **Art. 2:** Definicion de datos personales y datos sensibles
- **Art. 7:** Datos sensibles (salud) — prohibido su tratamiento salvo consentimiento
- **Art. 8:** Datos relacionados con salud — pueden ser tratados por profesionales de la salud
- **Art. 14:** Derecho de acceso, rectificacion y supresion
- **Art. 15:** Derecho a la actualizacion de datos

**Implementacion en el sistema:**
- Consentimiento explicito para tratamiento de datos de salud
- Boton de "Derecho al olvido" (borrado de datos personales)
- Acceso controlado por roles (RBAC)
- Encriptacion de datos sensibles (PHI)
"""

_LEY_25506 = """
**Ley 25.506 - Firma Digital**
Sancionada: 2001-11-14

**Articulos clave:**
- **Art. 2:** Definicion de firma digital y firma electronica
- **Art. 3:** Efectos juridicos (misma validez que firma manuscrita)
- **Art. 5:** Presuncion de autoría (salvo prueba en contrario)
- **Art. 6:** Requisitos de validez (certificado digital, dispositivo seguro)
- **Art. 8:** Infraestructura de Clave Publica (PKI)
- **Art. 17:** Datos firmados digitalmente se consideran originales

**Implementacion en el sistema:**
- RSA 2048/4096 para firma de documentos
- SHA-256 para hashing de contenido
- Verificacion de integridad de documentos
- Certificado de firma exportable
"""

_LEY_27553 = """
**Ley 27.553 - Recetas Electronicas**
Sancionada: 2020-08-26

**Articulos clave:**
- **Art. 1:** Reconocimiento de la receta electronica en todo el pais
- **Art. 2:** Requisitos (firma digital del profesional, identificacion del paciente)
- **Art. 3:** Dispensacion por farmacia contra presentacion de receta electronica

**Implementacion en el sistema:**
- Prescripcion electronica de medicamentos
- Firma digital del medico en cada receta
- Historial de recetas del paciente
- Alertas de interaccion y duplicacion
"""

_LEY_27706 = """
**Ley 27.706 - Programa Federal de Historias Clinicas Electronicas**
Sancionada: 2022-11-09

**Articulos clave:**
- **Art. 1:** Creacion del Programa Federal de Historia Clinica Electronica
- **Art. 3:** Estandares de interoperabilidad
- **Art. 5:** Confidencialidad y seguridad de la informacion
- **Art. 9:** Consentimiento del paciente para compartir HCE entre jurisdicciones

**Implementacion en el sistema:**
- Estandares FHIR para intercambio de datos clinicos
- Historia Clinica Electronica portable
- Consentimiento para comparticion de datos
"""

_LEY_CODIGO_CIVIL = """
**Codigo Civil y Comercial de la Nacion - Art. 288**
Sancionado: 2014-10-01

**Articulo clave:**
- **Art. 288:** Firma digital en instrumentos particulares (firma digital = firma manuscrita)

**Implementacion en el sistema:**
- Los documentos firmados digitalmente tienen plena validez juridica
- Se almacena el hash y la firma para verificacion posterior
"""


def _render_ley(texto, idx):
    partes = texto.strip().split("\n", 1)
    titulo = partes[0].strip("**")
    cuerpo = partes[1] if len(partes) > 1 else ""
    with st.expander(f"{titulo}", expanded=False):
        st.markdown(cuerpo)


def render_legal_docs(mi_empresa, user):
    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Marco Legal Aplicable</h2>
            <p class="mc-hero-text">Legislacion argentina vigente para la gestion de historias clinicas, consentimientos, firmas digitales y proteccion de datos.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    bloque_mc_grid_tarjetas(
        [
            ("Leyes citadas", "Cada modulo del sistema cita el articulado especifico que le da respaldo legal."),
            ("Debida diligencia", "Cumplimiento de normativa nacional para responsabilidad profesional."),
            ("Trazabilidad", "Cada accion clinica queda registrada con actor, fecha y hora."),
        ]
    )

    tab_leyes, tab_consent, tab_audit, tab_compliance = st.tabs(
        ["Leyes", "Consentimientos", "Auditoria HMAC", "Compliance"]
    )

    with tab_leyes:
        _render_ley(_LEY_26529, 1)
        _render_ley(_LEY_25326, 2)
        _render_ley(_LEY_25506, 3)
        _render_ley(_LEY_27553, 4)
        _render_ley(_LEY_27706, 5)
        _render_ley(_LEY_CODIGO_CIVIL, 6)

        st.divider()
        st.caption(
            "Referencias: InfoLEG (infoleg.gob.ar), Ministerio de Salud de la Nacion. "
            "Actualizado a " + ahora().strftime("%B %Y") + "."
        )

    with tab_consent:
        _render_consent_tab(mi_empresa, user)

    with tab_audit:
        _render_audit_trail_tab(mi_empresa, user)

    with tab_compliance:
        _render_compliance_tab(mi_empresa, user)


def _render_consent_tab(mi_empresa, user):
    import hashlib as _hl
    from datetime import timedelta

    st.markdown("### Consentimientos Informados")
    st.caption("Gestion de consentimientos con respaldo en Ley 26.529 (Art. 5, 6, 7) y Ley 25.326 (Art. 7, 8).")

    from core.consent_manager import get_consent_manager, ConsentType, ConsentStatus

    manager = get_consent_manager()

    consents = list(st.session_state.get("consentimientos_db", [])) or []
    ahora_dt = ahora()
    hoy_str = ahora_dt.strftime("%d/%m/%Y")

    col_estado, col_vigentes = st.columns(2)
    with col_estado:
        st.metric("Total", len(consents))
        revocados = sum(1 for c in consents if c.get("revocado"))
        st.metric("Revocados", revocados)
    with col_vigentes:
        vigentes = sum(1 for c in consents if (c.get("fecha") or "")[:10] >= hoy_str and not c.get("revocado"))
        st.metric("Vigentes", vigentes)
        vencidos = sum(1 for c in consents if (c.get("fecha") or "")[:10] < hoy_str and not c.get("revocado"))
        st.metric("Vencidos", vencidos)

    with st.expander("Verificar integridad de consentimientos", expanded=False):
        if consents and st.button("Verificar cadena de integridad", key="check_consent_chain", use_container_width=True):
            total = len(consents)
            ok = 0
            for c in consents:
                doc_hash = c.get("doc_hash", "")
                firma = c.get("firma_b64", "")
                if doc_hash and firma:
                    expected = _hl.sha256(f"{c.get('paciente', '')}|{c.get('fecha', '')}|{firma[:64]}".encode()).hexdigest()[:16]
                    if expected == doc_hash:
                        ok += 1
            st.write(f"**{ok}/{total}** consentimientos verificados correctamente.")

    if consents:
        st.dataframe(
            [
                {
                    "Paciente": c.get("paciente", ""),
                    "Fecha": str(c.get("fecha", ""))[:10],
                    "Firmante": c.get("firmante", ""),
                    "Vinculo": c.get("vinculo", ""),
                    "Estado": "Revocado" if c.get("revocado") else ("Vencido" if str(c.get("fecha", ""))[:10] < hoy_str else "Vigente"),
                }
                for c in reversed(consents[-50:])
            ],
            width='stretch',
        )

        st.divider()
        st.subheader("Revocar consentimiento")
        st.caption("Ley 26.529 Art. 7: El paciente puede revocar su consentimiento en cualquier momento.")
        cons_pacientes = sorted({c.get("paciente", "") for c in consents if not c.get("revocado")})
        if cons_pacientes:
            rev_pac = st.selectbox("Seleccionar paciente", cons_pacientes, key="rev_cons_pac")
            cons_pac_rev = [c for c in consents if c.get("paciente") == rev_pac and not c.get("revocado")]
            if cons_pac_rev:
                rev_opts = {f"{c(rev_opts = {f"{c.get('fecha') or '')[:10]} - {c.get('firmante', '')}": c for c in cons_pac_rev}
                rev_sel = st.selectbox("Seleccionar consentimiento", list(rev_opts.keys()), key="rev_cons_sel")
                rev_motivo = st.text_area("Motivo de revocacion", placeholder="Describir el motivo...", key="rev_motivo")
                if st.button("Revocar consentimiento", type="primary", key="btn_revoke", use_container_width=True):
                    target = rev_opts[rev_sel]
                    target["revocado"] = True
                    target["fecha_revocacion"] = ahora().strftime("%d/%m/%Y %H:%M")
                    target["motivo_revocacion"] = rev_motivo.strip()
                    target["revocado_por"] = user.get("nombre", "")
                    from core.database import guardar_datos
                    guardar_datos(spinner=True)
                    st.success(f"Consentimiento de {rev_pac} revocado.")
                    st.rerun()

    st.divider()
    st.markdown("**Fundamento legal:**")
    st.info(
        "Ley 26.529 Art. 5: 'El consentimiento debe ser informado, libre y expreso, "
        "constar por escrito y estar firmado por el paciente y el medico.'"
    )
    st.info(
        "Ley 26.529 Art. 7: 'El paciente puede revocar su consentimiento en cualquier momento.'"
    )
    st.info(
        "Ley 25.326 Art. 7: 'Los datos sensibles solo pueden ser recolectados y objeto "
        "de tratamiento cuando existan razones de interes general.'"
    )


def _render_audit_trail_tab(mi_empresa, user):
    st.markdown("### Cadena de Auditoria HMAC")
    st.caption("Registro inmutable de acciones con encadenamiento criptografico. Respaldo: Ley 25.506 (Art. 3, 5).")

    entries = list(st.session_state.get("audit_trail", [])) or []
    st.metric("Eventos registrados", len(entries))

    if entries:
        show = st.number_input("Ultimos N eventos", min_value=5, max_value=200, value=20)
        df = [
            {
                "Timestamp": e("Timestamp": e.get("timestamp") or "")[:19] if isinstance(e.get("timestamp", ""), str) else "",
                "Evento": e.get("event_type", ""),
                "Usuario": e.get("user_id", ""),
                "Accion": e.get("action", ""),
                "Recurso": e.get("resource_type", ""),
            }
            for e in reversed(entries[-show:])
        ]
        st.dataframe(df, width='stretch')

        if st.button("Verificar integridad de la cadena", use_container_width=True):
            from core.audit_trail import get_audit_trail
            try:
                trail = get_audit_trail()
                valid = trail.verify_chain()
                if valid:
                    st.success("Cadena de auditoria intacta — no se detectaron modificaciones.")
                else:
                    log_event("legal_docs", "error: cadena de auditoria alterada")
                    st.error("ALERTA: La cadena de auditoria ha sido alterada.")
            except Exception as e:
                st.warning(f"No se pudo verificar la cadena: {e}")
    else:
        st.info("La cadena de auditoria HMAC se activa cuando se registran eventos desde los modulos clinicos.")

    st.divider()
    st.markdown("**Fundamento legal:**")
    st.info(
        "Ley 25.506 Art. 3: 'La firma digital tiene la misma validez que la firma manuscrita "
        "y produce los mismos efectos legales.'"
    )


def _render_compliance_tab(mi_empresa, user):
    st.markdown("### Dashboard de Cumplimiento")
    st.caption("Verificacion automatica contra estandares normativos (HIPAA, GDPR, Ley 25.506, Ley 26.529).")

    if st.button("Ejecutar auditoria de compliance ahora", type="primary", use_container_width=True):
        from core.compliance_monitor import get_compliance_monitor
        try:
            monitor = get_compliance_monitor()
            with st.spinner("Ejecutando controles automaticos..."):
                report = monitor.run_compliance_audit(period_days=30)
            c1, c2 = st.columns(2)
            c1.metric("Estado general", report.overall_status.upper())
            c1.metric("Violaciones totales", report.summary["total_violations"])
            c2.metric("Criticas", report.summary["critical"])
            c2.metric("Altas", report.summary["high"])
            if report.violations:
                with st.expander("Detalle de violaciones", expanded=False):
                    for v in report.violations:
                        sev = v.severity
                        icon = {"critical": "CRIT", "high": "ALT", "medium": "MED", "low": "BAJ"}.get(sev, sev)
                        st.warning(f"[{icon}] {v.standard}: {v.description}")
            else:
                st.success("Sin violaciones detectadas.")
        except Exception as e:
            st.warning(f"No se pudo ejecutar la auditoria: {e}")

    st.divider()
    st.markdown("**Controles implementados:**")
    controls = [
        ("Control de acceso RBAC", "Roles: medico, enfermero, admin, coordinador"),
        ("Encriptacion PHI", "Datos sensibles protegidos con AES-256"),
        ("Audit trail HMAC", "Registro encadenado con verificacion de integridad"),
        ("Consentimientos informados", "Firma digital con hash SHA-256"),
        ("Retencion de datos", "Historias clinicas: 10 anos, Auditoria: 7 anos"),
        ("Backup diario", "Respaldo automatico a Supabase con verificaicon"),
    ]
    for control, desc in controls:
        st.markdown(f"- **{control}:** {desc}")

    st.divider()
    st.markdown("**Fundamento legal:**")
    st.info(
        "Ley 26.529 Art. 12: 'La historia clinica debe ser llevada en forma cronologica, "
        "legible, foliada y firmada por el profesional actuante.'"
    )
    st.info(
        "Ley 25.326 Art. 8: 'Los datos relacionados con la salud solo pueden ser tratados "
        "por profesionales de la salud sujetos a secreto profesional.'"
    )
