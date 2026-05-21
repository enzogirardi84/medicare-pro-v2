"""Panel central de funciones IA - Resumen, búsqueda, codificación, población."""

from __future__ import annotations

import streamlit as st

from core.ai_assistant import (
    is_llm_enabled,
    get_risk_predictor,
    get_anomaly_detector,
    get_priority_classifier,
)
from core.view_helpers import aviso_sin_paciente


def render_ai_features_panel(paciente_sel, mi_empresa, user, rol):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    llm_ok = is_llm_enabled()

    st.markdown("""
        <div class="mc-hero">
            <h2 class="mc-hero-title">🤖 Asistente IA</h2>
            <p class="mc-hero-text">Resumen clínico, codificación, búsqueda inteligente y análisis de población.</p>
        </div>
    """, unsafe_allow_html=True)

    if not llm_ok:
        st.warning("IA no configurada. Activá un proveedor en Ajustes → Configuración de IA para usar estas funciones.")

    tab_res, tab_cod, tab_bus, tab_pob, tab_clin = st.tabs([
        "📋 Resumen Clínico", "🏷️ Codificación CIE-10",
        "🔍 Búsqueda", "📊 Análisis de Población", "🩺 Riesgo y Anomalías",
    ])

    with tab_res:
        render_resumen(paciente_sel, llm_ok)

    with tab_cod:
        render_codificacion(llm_ok)

    with tab_bus:
        render_busqueda(paciente_sel, llm_ok)

    with tab_pob:
        render_poblacion(mi_empresa, llm_ok)

    with tab_clin:
        render_clinico(paciente_sel)


def render_resumen(paciente_sel, llm_ok):
    st.subheader("Resumen Clínico para Entrega / Derivación")
    st.caption("Genera un resumen estructurado del paciente ideal para cambio de turno, derivación o referencia.")

    if st.button("📄 Generar resumen con IA", use_container_width=True, type="primary", key="ai_summary_btn"):
        if not llm_ok:
            st.warning("IA no configurada.")
            return
        with st.spinner("Generando resumen clínico..."):
            from core.ai_features import generate_patient_summary
            resultado = generate_patient_summary(paciente_sel)
        if resultado:
            st.session_state["_ai_summary_result"] = resultado
            st.rerun()

    if st.session_state.get("_ai_summary_result"):
        st.markdown("---")
        st.info(st.session_state["_ai_summary_result"])
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("🗑️ Limpiar", use_container_width=True, key="ai_summary_clear"):
                st.session_state.pop("_ai_summary_result", None)
                st.rerun()
        with col_s2:
            txt = st.session_state["_ai_summary_result"]
            st.download_button("📥 Descargar .txt", data=txt, file_name=f"resumen_{paciente_sel[:20]}.txt",
                               use_container_width=True, key="ai_summary_dl")

    if st.button("📋 Reporte de evolución (30 días)", use_container_width=True, key="ai_report_btn"):
        if not llm_ok:
            st.warning("IA no configurada.")
            return
        with st.spinner("Generando reporte..."):
            from core.ai_features import generate_report_ai
            resultado = generate_report_ai(paciente_sel, 30)
        if resultado:
            st.session_state["_ai_report_result"] = resultado
            st.rerun()

    if st.session_state.get("_ai_report_result"):
        st.info(st.session_state["_ai_report_result"])
        if st.button("Limpiar reporte", key="ai_report_clear", use_container_width=True):
            st.session_state.pop("_ai_report_result", None)
            st.rerun()


def render_codificacion(llm_ok):
    st.subheader("Asistente de Codificación CIE-10")
    st.caption("Ingresá una descripción clínica y la IA sugerirá códigos de diagnóstico.")

    desc = st.text_area("Descripción clínica", placeholder="Ej: Paciente presenta fiebre alta, tos productiva y dolor pleurítico desde hace 3 días",
                        height=100, key="ai_icd_input")
    if st.button("🏷️ Sugerir códigos CIE-10", use_container_width=True, type="primary", key="ai_icd_btn"):
        if not llm_ok:
            st.warning("IA no configurada.")
        elif not desc.strip():
            st.warning("Ingresá una descripción clínica.")
        else:
            with st.spinner("Consultando IA..."):
                from core.ai_features import suggest_icd_codes
                resultado = suggest_icd_codes(desc)
            if resultado:
                st.session_state["_ai_icd_result"] = resultado
                st.rerun()

    if st.session_state.get("_ai_icd_result"):
        st.markdown("---")
        st.info(st.session_state["_ai_icd_result"])
        if st.button("Limpiar", key="ai_icd_clear", use_container_width=True):
            st.session_state.pop("_ai_icd_result", None)
            st.rerun()

    st.divider()
    st.subheader("Diagnósticos Diferenciales")
    st.caption("Basado en síntomas y evolución del paciente actual.")
    if st.button("🩺 Sugerir diagnósticos diferenciales", use_container_width=True, key="ai_diff_btn"):
        if not llm_ok:
            st.warning("IA no configurada.")
        else:
            with st.spinner("Analizando paciente..."):
                from core.ai_features import suggest_differential_ai
                resultado = suggest_differential_ai(st.session_state.get("_paciente_sel", ""))
            if resultado:
                st.session_state["_ai_diff_result"] = resultado
                st.rerun()

    if st.session_state.get("_ai_diff_result"):
        st.info(st.session_state["_ai_diff_result"])
        if st.button("Limpiar", key="ai_diff_clear", use_container_width=True):
            st.session_state.pop("_ai_diff_result", None)
            st.rerun()


def render_busqueda(paciente_sel, llm_ok):
    st.subheader("Búsqueda Inteligente")
    st.caption("Buscá en lenguaje natural: pacientes, estudios, notas, medicación.")

    query = st.text_input("¿Qué querés buscar?", placeholder="Ej: pacientes con diabetes que no vinieron este mes",
                          key="ai_search_input")
    if st.button("🔍 Buscar con IA", use_container_width=True, type="primary", key="ai_search_btn"):
        if not llm_ok:
            st.warning("IA no configurada.")
        elif not query.strip():
            st.warning("Ingresá una consulta.")
        else:
            with st.spinner("Buscando..."):
                from core.ai_features import smart_search_ai
                resultado = smart_search_ai(query, paciente_sel)
            if resultado:
                st.session_state["_ai_search_result"] = resultado
                st.rerun()

    if st.session_state.get("_ai_search_result"):
        st.info(st.session_state["_ai_search_result"])
        if st.button("Limpiar", key="ai_search_clear", use_container_width=True):
            st.session_state.pop("_ai_search_result", None)
            st.rerun()


def render_poblacion(mi_empresa, llm_ok):
    st.subheader("Análisis de Población")
    st.caption("Consultas sobre tu población de pacientes.")

    query = st.text_input("Consulta sobre la población", placeholder="Ej: ¿Cuántos pacientes tienen hipertensión?",
                          key="ai_pop_input")
    if st.button("📊 Analizar población", use_container_width=True, type="primary", key="ai_pop_btn"):
        if not llm_ok:
            st.warning("IA no configurada.")
        elif not query.strip():
            st.warning("Ingresá una consulta.")
        else:
            with st.spinner("Analizando población..."):
                from core.ai_features import population_analysis_ai
                pacientes = st.session_state.get("detalles_pacientes_db", {})
                pacientes_list = list(pacientes.values()) if isinstance(pacientes, dict) else []
                resultado = population_analysis_ai(query, pacientes_list)
            if resultado:
                st.session_state["_ai_pop_result"] = resultado
                st.rerun()

    if st.session_state.get("_ai_pop_result"):
        st.info(st.session_state["_ai_pop_result"])
        if st.button("Limpiar", key="ai_pop_clear", use_container_width=True):
            st.session_state.pop("_ai_pop_result", None)
            st.rerun()


def render_clinico(paciente_sel):
    st.subheader("Evaluación Clínica (sin IA)")
    st.caption("Herramientas clínicas basadas en reglas que funcionan sin conexión a IA.")

    predictor = get_risk_predictor()
    detector = get_anomaly_detector()
    classifier = get_priority_classifier()

    detalles = st.session_state.get("detalles_pacientes_db", {}).get(paciente_sel, {})
    vitales = [v for v in (st.session_state.get("vitales_db") or []) if v.get("paciente") == paciente_sel]

    col_c1, col_c2, col_c3 = st.columns(3)
    with col_c1:
        st.metric("Riesgo Clínico", "Disponible" if predictor else "N/A")
    with col_c2:
        st.metric("Detector Anomalías", "Disponible" if detector else "N/A")
    with col_c3:
        st.metric("Clasificador Triaje", "Disponible" if classifier else "N/A")

    if vitales:
        st.subheader("Tendencias de Signos Vitales")
        if st.button("📈 Analizar tendencias", use_container_width=True, key="ai_trends_btn"):
            from core.ai_features import check_vital_trends
            resultado = check_vital_trends(paciente_sel)
            if resultado:
                st.session_state["_ai_trends_result"] = resultado
                st.rerun()
            else:
                st.info("Se necesitan al menos 2 registros de signos vitales para analizar tendencias.")

        if st.session_state.get("_ai_trends_result"):
            st.info(st.session_state["_ai_trends_result"])
            if st.button("Limpiar", key="ai_trends_clear", use_container_width=True):
                st.session_state.pop("_ai_trends_result", None)
                st.rerun()

        edad = str(detalles.get("edad", "") or "")
        symptoms = str(detalles.get("patologias", "") or "")
        last_vitals = vitales[-1] if vitales else {}

        st.subheader("Clasificación de Urgencia")
        if st.button("🚑 Clasificar urgencia", use_container_width=True, key="ai_triage_btn"):
            from core.ai_features import classify_urgency
            result = classify_urgency(symptoms, edad, last_vitals)
            st.session_state["_ai_triage_result"] = result

        if st.session_state.get("_ai_triage_result"):
            r = st.session_state["_ai_triage_result"]
            st.info(f"**Prioridad:** {r['priority']}  \n**Tiempo sugerido:** {r['timeframe']}  \n**Razones:** {', '.join(r['reasons'])}")
            if st.button("Cerrar", key="ai_triage_clear", use_container_width=True):
                st.session_state.pop("_ai_triage_result", None)
                st.rerun()
