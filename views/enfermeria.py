from core.alert_toasts import queue_toast
from html import escape

import streamlit as st

# Lazy import pandas - solo cargar cuando se necesite mostrar dataframe
_pandas = None
def get_pandas():
    global _pandas
    if _pandas is None:
        import pandas as pd
        _pandas = pd
    return _pandas

from core.database import guardar_datos
from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio, bloque_mc_grid_tarjetas, lista_plegable
from core.utils import (
    ahora,
    mapa_detalles_pacientes,
    mostrar_dataframe_con_scroll,
    registrar_auditoria_legal,
    seleccionar_limite_registros,
)
from core.db_sql import get_cuidados_enfermeria, insert_cuidado_enfermeria
from core.nextgen_sync import _obtener_uuid_empresa, _obtener_uuid_paciente
from core.app_logging import log_event


TIPOS_CUIDADO = [
    "Control general",
    "Curacion simple",
    "Curacion avanzada",
    "Administracion de medicacion",
    "Control de sonda / cateter",
    "Higiene y confort",
    "Control respiratorio",
    "Plan de movilizacion",
    "Prevencion de UPP",
    "Incidente / evento adverso",
]


def _resolver_uuid_paciente_sql(paciente_sel, empresa):
    partes = str(paciente_sel or "").rsplit(" - ", 1)
    dni = partes[1].strip() if len(partes) == 2 else ""
    empresa_id = _obtener_uuid_empresa(empresa) if empresa else None
    return _obtener_uuid_paciente(dni, empresa_id) if dni and empresa_id else None


def _render_plan_cuidados_enfermeria_legacy(
    paciente_sel,
    mi_empresa,
    user,
    registros,
    registros_ordenados,
    detalles,
    ultimo_registro,
):
    """Formulario e historial estructurado (UPP, caídas, incidentes). Opcional si la institución ya usa solo Evolución."""
    bloque_mc_grid_tarjetas(
        [
            ("Registro", "Curaciones, riesgos y observaciones por turno."),
            ("Plan actual", "Resumen de prioridad y ultimo plan de cuidados."),
            ("Historial", "Filtra por turno o tipo de cuidado."),
        ]
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Registros", len(registros))
    m2.metric("Curaciones", sum(1 for x in registros if "Curacion" in x.get("tipo_cuidado", "")))
    m3.metric("Incidentes", sum(1 for x in registros if x.get("incidente")))
    m4.metric("Último registro", ultimo_registro)

    st.caption(
        "Elegí **Nuevo registro** para cargar el turno, **Plan actual** para el resumen vigente o **Historial** para filtrar. "
        "Para notas clínicas y **fotos de heridas** usá **Evolución** en el menú."
    )

    st.markdown(
        f"""
        <div class="mc-callout">
            <strong>Paciente activo:</strong> {escape(str(paciente_sel))}<br>
            <strong>Obra social:</strong> {escape(str(detalles.get('obra_social', 'S/D')))}<br>
            <strong>Alergias:</strong> {escape(str(detalles.get('alergias', 'Sin datos')))}<br>
            <strong>Patologías:</strong> {escape(str(detalles.get('patologias', 'Sin datos')))}
        </div>
        """,
        unsafe_allow_html=True,
    )

    vista = st.radio(
        "Vista enfermería",
        ["Nuevo registro", "Plan actual", "Historial"],
        horizontal=False,
        label_visibility="collapsed",
        key="enf_vista",
    )

    if vista == "Nuevo registro":
        with st.container(border=True):
            st.markdown("### Nuevo registro de enfermería")
            c1, c2, c3 = st.columns(3)
            tipo_cuidado = c1.selectbox("Tipo de cuidado", TIPOS_CUIDADO, key="enf_tipo")
            turno = c2.selectbox("Turno", ["Mañana", "Tarde", "Noche", "Guardia"], key="enf_turno")
            prioridad = c3.selectbox("Prioridad", ["Baja", "Moderada", "Alta"], key="enf_prioridad")

            d1, d2, d3 = st.columns(3)
            riesgo_caidas = d1.selectbox("Riesgo de caídas", ["Bajo", "Moderado", "Alto"], key="enf_riesgo_caidas")
            riesgo_upp = d2.selectbox("Riesgo UPP", ["Bajo", "Moderado", "Alto"], key="enf_riesgo_upp")
            dolor = d3.selectbox("Dolor referido", [str(x) for x in range(11)], index=0, key="enf_dolor")

            if tipo_cuidado in {"Curacion simple", "Curacion avanzada", "Prevencion de UPP"}:
                st.markdown("#### Detalle de curación y piel")
                h1, h2, h3 = st.columns(3)
                zona = h1.text_input("Zona / lesión", placeholder="Sacra, talón, pierna, abdomen", key="enf_zona")
                aspecto = h2.selectbox(
                    "Aspecto",
                    ["Limpia", "Exudado leve", "Exudado moderado", "Infectada", "Granulación"],
                    key="enf_aspecto",
                )
                dolor_curacion = h3.selectbox(
                    "Dolor en curación", ["Sin dolor", "Leve", "Moderado", "Severo"], key="enf_dolor_curacion"
                )
            else:
                zona = ""
                aspecto = ""
                dolor_curacion = ""

            objetivo = st.text_input(
                "Objetivo del cuidado",
                placeholder="Ej: mantener herida limpia y seca / vigilar saturación / prevenir caídas",
                key="enf_objetivo",
            )
            intervencion = st.text_area("Intervención realizada", height=110, key="enf_intervencion")
            respuesta = st.text_area("Respuesta del paciente", height=90, key="enf_respuesta")
            observaciones = st.text_area("Observaciones de enfermería", height=90, key="enf_observaciones")
            incidente = st.checkbox("Hubo incidente o evento adverso", key="enf_incidente")
            detalle_incidente = st.text_area("Detalle del incidente", height=80, key="enf_det_inc") if incidente else ""

            if st.button("Guardar registro de enfermería", use_container_width=True, type="primary", key="enf_guardar"):
                if not intervencion.strip():
                    st.error("Debés registrar la intervención realizada.")
                else:
                    fecha_str = ahora().strftime("%d/%m/%Y %H:%M:%S")
                    
                    # 1. Guardar en SQL (Dual-Write)
                    try:
                        paciente_uuid = _resolver_uuid_paciente_sql(paciente_sel, mi_empresa)
                        if paciente_uuid:
                            datos_sql = {
                                "paciente_id": paciente_uuid,
                                "fecha_registro": ahora().isoformat(),
                                "tipo_cuidado": tipo_cuidado,
                                "descripcion": f"Turno: {turno} | Prioridad: {prioridad} | Riesgo Caídas: {riesgo_caidas} | Riesgo UPP: {riesgo_upp} | Dolor: {dolor}\nObjetivo: {objetivo.strip()}\nIntervención: {intervencion.strip()}\nRespuesta: {respuesta.strip()}\nObs: {observaciones.strip()}",
                                "realizado": True
                            }
                            insert_cuidado_enfermeria(datos_sql)
                            log_event("enfermeria_sql_insert", f"Paciente: {paciente_uuid}")
                    except Exception as e:
                        log_event("error_enfermeria_sql", str(e))
                        st.error(f"Error al guardar en SQL: {e}")

                    # 2. Guardar en JSON (Legacy)
                    nuevo = {
                        "paciente": paciente_sel,
                        "fecha": fecha_str,
                        "tipo_cuidado": tipo_cuidado,
                        "turno": turno,
                        "prioridad": prioridad,
                        "riesgo_caidas": riesgo_caidas,
                        "riesgo_upp": riesgo_upp,
                        "dolor": dolor,
                        "objetivo": objetivo.strip(),
                        "intervencion": intervencion.strip(),
                        "respuesta": respuesta.strip(),
                        "observaciones": observaciones.strip(),
                        "incidente": incidente,
                        "detalle_incidente": detalle_incidente.strip(),
                        "zona": zona.strip(),
                        "aspecto": aspecto,
                        "dolor_curacion": dolor_curacion,
                        "profesional": user.get("nombre", ""),
                        "matricula": user.get("matricula", ""),
                    }
                    if "cuidados_enfermeria_db" not in st.session_state:
                        st.session_state["cuidados_enfermeria_db"] = []
                    st.session_state["cuidados_enfermeria_db"].append(nuevo)
                    
                    registrar_auditoria_legal(
                        "Enfermeria",
                        paciente_sel,
                        "Registro de cuidado",
                        user.get("nombre", ""),
                        user.get("matricula", ""),
                        f"{tipo_cuidado} | Turno: {turno} | Prioridad: {prioridad}",
                    )
                    guardar_datos()
                    queue_toast("Registro de enfermería guardado.")
                    st.rerun()

    elif vista == "Plan actual":
        st.markdown("### Resumen operativo del cuidado")
        if not registros_ordenados:
            bloque_estado_vacio(
                "Sin plan de enfermería",
                "Todavía no hay registros de enfermería para este paciente.",
                sugerencia="En la pestaña Registro cargá el primer plan o control.",
            )
            return

        ultimo = registros_ordenados[0]
        c1, c2, c3 = st.columns(3)
        c1.info(f"Prioridad actual: {ultimo.get('prioridad', 'S/D')}")
        c2.info(f"Riesgo de caídas: {ultimo.get('riesgo_caidas', 'S/D')}")
        c3.info(f"Riesgo UPP: {ultimo.get('riesgo_upp', 'S/D')}")

        with st.container(border=True):
            st.markdown("#### Último plan registrado")
            st.write(f"**Tipo de cuidado:** {ultimo.get('tipo_cuidado', 'S/D')}")
            st.write(f"**Objetivo:** {ultimo.get('objetivo', 'Sin objetivo consignado')}")
            st.write(f"**Intervención:** {ultimo.get('intervencion', 'S/D')}")
            st.write(f"**Respuesta:** {ultimo.get('respuesta', 'S/D')}")
            st.write(f"**Observaciones:** {ultimo.get('observaciones', 'S/D')}")
            if ultimo.get("zona"):
                st.write(f"**Zona / lesión:** {ultimo.get('zona')}")
            if ultimo.get("aspecto"):
                st.write(f"**Aspecto:** {ultimo.get('aspecto')}")
            if ultimo.get("incidente"):
                st.error(f"Incidente informado: {ultimo.get('detalle_incidente', 'Sin detalle')}")

        pendientes = [x for x in registros_ordenados if x.get("prioridad") == "Alta"][:8]
        if pendientes:
            with lista_plegable("Registros de mayor prioridad", count=len(pendientes), expanded=False, height=300):
                for reg in pendientes:
                    with st.container(border=True):
                        st.markdown(f"**{reg.get('fecha', '')}** | {reg.get('tipo_cuidado', '')}")
                        st.caption(
                            f"Turno: {reg.get('turno', 'S/D')} | Profesional: {reg.get('profesional', 'S/D')} | Riesgo UPP: {reg.get('riesgo_upp', 'S/D')}"
                        )
                        st.write(reg.get("intervencion", ""))

    else:
        st.markdown("### Historial de cuidados")
        if not registros_ordenados:
            bloque_estado_vacio(
                "Sin historial de enfermería",
                "No hay registros previos para listar.",
                sugerencia="Usá la pestaña Registro para cargar cuidados y observaciones.",
            )
            return

        col_f1, col_f2 = st.columns(2)
        turno_filtro = col_f1.selectbox("Filtrar por turno", ["Todos", "Mañana", "Tarde", "Noche", "Guardia"], key="enf_hist_turno")
        tipo_filtro = col_f2.selectbox("Filtrar por tipo", ["Todos"] + TIPOS_CUIDADO, key="enf_hist_tipo")

        registros_filtrados = registros_ordenados
        if turno_filtro != "Todos":
            registros_filtrados = [x for x in registros_filtrados if x.get("turno") == turno_filtro]
        if tipo_filtro != "Todos":
            registros_filtrados = [x for x in registros_filtrados if x.get("tipo_cuidado") == tipo_filtro]

        if not registros_filtrados:
            bloque_estado_vacio(
                "Sin resultados con este filtro",
                "No hay registros que coincidan con turno o tipo elegidos.",
                sugerencia="Probá «Todos» en los filtros o ampliá el historial.",
            )
            return

        limite = seleccionar_limite_registros(
            "Registros a mostrar",
            len(registros_filtrados),
            key="enfermeria_limite_historial",
            default=30,
            opciones=(10, 20, 30, 50, 100, 200, 500),
        )
        resumen_df = pd.DataFrame(registros_filtrados[:limite]).drop(columns=["paciente", "empresa"], errors="ignore")
        with lista_plegable("Historial de cuidados (tabla)", count=len(resumen_df), expanded=False, height=440):
            mostrar_dataframe_con_scroll(resumen_df, height=380)


def render_enfermeria(paciente_sel, mi_empresa, user, *, compact=False):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    # 1. Intentar leer desde PostgreSQL (Hybrid Read)
    registros = []
    try:
        paciente_uuid = _resolver_uuid_paciente_sql(paciente_sel, mi_empresa)
        if paciente_uuid:
            # Traer los ultimos 30 dias para no sobrecargar la vista
            fecha_inicio = (pd.Timestamp.now() - pd.Timedelta(days=30)).isoformat()
            fecha_fin = (pd.Timestamp.now() + pd.Timedelta(days=1)).isoformat()
            
            cuidados_sql = get_cuidados_enfermeria(paciente_uuid, fecha_inicio, fecha_fin)
            if cuidados_sql:
                for c in cuidados_sql:
                    # Mapear de SQL a formato legacy para la UI
                    dt = pd.to_datetime(c.get("fecha_registro", ""))
                    registros.append({
                        "paciente": paciente_sel,
                        "empresa": mi_empresa,
                        "fecha": dt.strftime("%d/%m/%Y %H:%M:%S") if pd.notnull(dt) else c.get("fecha_registro"),
                        "tipo_cuidado": c.get("tipo_cuidado", ""),
                        "intervencion": c.get("descripcion", ""),
                        "profesional": c.get("usuarios", {}).get("nombre", "Desconocido") if isinstance(c.get("usuarios"), dict) else "Desconocido",
                        # Campos legacy que quizas no esten en SQL pero la UI espera
                        "turno": "S/D",
                        "prioridad": "S/D",
                        "riesgo_caidas": "S/D",
                        "riesgo_upp": "S/D",
                        "dolor": "S/D",
                        "objetivo": "S/D",
                        "respuesta": "S/D",
                        "observaciones": "S/D",
                        "incidente": False,
                        "zona": "",
                        "aspecto": "",
                    })
    except Exception as e:
        log_event("error_leer_cuidados_sql", str(e))

    # 2. Fallback a JSON si SQL falla o esta vacio
    if not registros:
        registros = [x for x in st.session_state.get("cuidados_enfermeria_db", []) if x.get("paciente") == paciente_sel]
        
    detalles = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})
    registros_ordenados = sorted(registros, key=lambda x: x.get("fecha", ""), reverse=True)
    ultimo_registro = registros_ordenados[0]["fecha"] if registros_ordenados else "Sin datos"

    if not compact:
        st.markdown(
            """
            <div class="mc-hero">
                <h2 class="mc-hero-title">Enfermería y documentación clínica</h2>
                <p class="mc-hero-text">El registro narrativo de evolución, cambios del paciente y <strong>fotos de heridas o lesiones</strong> se carga en
                <strong>Evolución</strong>, donde documentan todos los profesionales (médicos, enfermería, operativos). Este menú conserva solo un
                <strong>plan de cuidados estructurado</strong> opcional (riesgo UPP, caídas, incidentes) si su institución lo separa del texto libre.</p>
                <div class="mc-chip-row">
                    <span class="mc-chip">→ Evolución: notas + fotos</span>
                    <span class="mc-chip">Opcional: plan UPP / caídas</span>
                    <span class="mc-chip">Historial PDF sin cambios</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.info(
            "**Usá la pestaña Evolución clínica** para notas, curaciones en texto y **fotografías** "
            "(plantillas Enfermería o Heridas). Acá solo el **plan estructurado** (UPP, caídas, incidentes).",
            icon="📋",
        )

        with st.expander(
            "Plan de cuidados estructurado — opcional (UPP, caídas, incidentes, datos ya cargados en el sistema)",
            expanded=bool(registros),
        ):
            _render_plan_cuidados_enfermeria_legacy(
                paciente_sel,
                mi_empresa,
                user,
                registros,
                registros_ordenados,
                detalles,
                ultimo_registro,
            )
    else:
        st.caption(
            "Plan estructurado opcional: UPP, caídas, incidentes. Las notas y fotos van en la pestaña **Evolución clínica**."
        )
        _render_plan_cuidados_enfermeria_legacy(
            paciente_sel,
            mi_empresa,
            user,
            registros,
            registros_ordenados,
            detalles,
            ultimo_registro,
        )
