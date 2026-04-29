"""Módulo APS / Dispensario para MediCare Enterprise PRO.

Ventana general de Atención Primaria de la Salud:
- Panel diario con métricas
- Ficha APS del paciente
- Historial APS unificado
- Nueva atención
- Farmacia e insumos
- Trabajo Social
- Epidemiología
- Visitas domiciliarias
- Reportes
"""

from datetime import date, datetime

import streamlit as st

from core.database import guardar_json_db
from core.view_helpers import aviso_sin_paciente
from core.utils import puede_accion


def _get_paciente_id_visual(paciente_sel):
    """Devuelve un ID limpio para guardar en la base de datos."""
    return str(paciente_sel or "").strip()


def _header_paciente(paciente_sel, user):
    """Muestra la cabecera del paciente seleccionado."""
    from core.utils import mapa_detalles_pacientes

    detalles = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})
    dni = detalles.get("dni", "S/D")
    empresa = detalles.get("empresa", "S/D")
    estado = detalles.get("estado", "Activo")

    with st.container(border=True):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Paciente", paciente_sel or "-")
        col2.metric("DNI", dni)
        col3.metric("Empresa / Barrio", empresa)
        col4.metric("Estado", estado)


def _metricas_aps_del_dia():
    """Métricas rápidas basadas en datos de hoy en session_state."""
    hoy_iso = date.today().isoformat()

    atenciones = st.session_state.get("atenciones_aps_db", [])
    entregas = st.session_state.get("entregas_aps_db", [])
    epi = st.session_state.get("epidemiologia_aps_db", [])
    visitas = st.session_state.get("visitas_domiciliarias_aps_db", [])

    pacientes_hoy = set()
    medicacion_hoy = 0
    alertas_epi = 0
    visitas_pend = 0

    for a in atenciones:
        if str(a.get("fecha_atencion", ""))[:10] == hoy_iso:
            pacientes_hoy.add(a.get("paciente_id"))

    for e in entregas:
        if str(e.get("fecha_entrega", ""))[:10] == hoy_iso:
            medicacion_hoy += 1

    for ep in epi:
        if ep.get("estado") in ("Pendiente", "En seguimiento"):
            alertas_epi += 1
        if ep.get("requiere_visita") and ep.get("estado") == "Pendiente":
            visitas_pend += 1

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Pacientes atendidos hoy", len(pacientes_hoy))
    col2.metric("Medicación entregada hoy", medicacion_hoy)
    col3.metric("Alertas epidemiológicas", alertas_epi)
    col4.metric("Visitas domic. pendientes", visitas_pend)


def _tab_panel_diario(paciente_sel, user):
    st.subheader("Panel Diario APS")
    st.caption("Vista rápida para administración, enfermería y coordinación.")

    atenciones = st.session_state.get("atenciones_aps_db", [])
    entregas = st.session_state.get("entregas_aps_db", [])
    epi = st.session_state.get("epidemiologia_aps_db", [])
    visitas = st.session_state.get("visitas_domiciliarias_aps_db", [])

    hoy_iso = date.today().isoformat()

    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            st.markdown("### Últimas atenciones")
            recientes = [
                a for a in atenciones
                if str(a.get("fecha_atencion", ""))[:10] == hoy_iso
            ][-10:]
            if recientes:
                for a in recientes:
                    st.write(f"• {a.get('paciente_id', '-')} — {a.get('motivo_consulta', '-')}")
            else:
                st.caption("Sin atenciones registradas hoy.")

    with col2:
        with st.container(border=True):
            st.markdown("### Alertas pendientes")
            alertas = [
                ep for ep in epi
                if ep.get("estado") in ("Pendiente", "En seguimiento")
            ]
            if alertas:
                for al in alertas[:5]:
                    nivel = al.get("prioridad", "Media")
                    if nivel in ("Alta", "Urgente"):
                        st.warning(f"{al.get('paciente_id', '-')} — {', '.join(al.get('enfermedades_seguimiento', []))}")
                    else:
                        st.info(f"{al.get('paciente_id', '-')} — {', '.join(al.get('enfermedades_seguimiento', []))}")
            else:
                st.caption("Sin alertas activas.")

    st.divider()

    with st.container(border=True):
        st.markdown("### Visitas domiciliarias")
        pendientes = [
            v for v in visitas
            if v.get("estado", "Pendiente") == "Pendiente"
        ]
        if pendientes:
            st.dataframe(
                [
                    {
                        "Paciente": v.get("paciente_id", "-"),
                        "Motivo": v.get("motivo_visita", "-"),
                        "Prioridad": v.get("prioridad", "Media"),
                        "Barrio": v.get("barrio", "-"),
                    }
                    for v in pendientes
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("Sin visitas domiciliarias pendientes.")


def _tab_ficha_aps(paciente_sel, user, centro_salud_id):
    st.subheader("Ficha APS del Paciente")
    st.caption("Datos generales propios del centro de salud.")

    fichas = st.session_state.get("ficha_aps_db", [])
    paciente_id = _get_paciente_id_visual(paciente_sel)
    ficha_existente = None
    for f in fichas:
        if f.get("paciente_id") == paciente_id and f.get("centro_salud_id") == centro_salud_id:
            ficha_existente = f
            break

    with st.form("form_ficha_aps"):
        col1, col2 = st.columns(2)
        with col1:
            medico_referente = st.text_input(
                "Médico referente",
                value=ficha_existente.get("medico_referente", "") if ficha_existente else "",
            )
            enfermero_referente = st.text_input(
                "Enfermero/a referente",
                value=ficha_existente.get("enfermero_referente", "") if ficha_existente else "",
            )
            promotor_referente = st.text_input(
                "Promotor/a de salud",
                value=ficha_existente.get("promotor_referente", "") if ficha_existente else "",
            )

        with col2:
            riesgo_general = st.selectbox(
                "Riesgo general APS",
                ["Bajo", "Moderado", "Alto", "Crítico"],
                index=(["Bajo", "Moderado", "Alto", "Crítico"].index(ficha_existente.get("riesgo_general", "Bajo")) if ficha_existente else 0),
            )
            programa_asignado = st.multiselect(
                "Programas asignados",
                [
                    "HTA", "Diabetes", "Salud sexual", "Materno infantil",
                    "Leche", "Adulto mayor", "Tuberculosis", "Dengue",
                    "Salud mental", "Trabajo social",
                ],
                default=ficha_existente.get("programa_asignado", []) if ficha_existente else [],
            )
            estado_ficha = st.selectbox(
                "Estado de ficha APS",
                ["Activa", "En seguimiento", "Derivada", "Inactiva"],
                index=(["Activa", "En seguimiento", "Derivada", "Inactiva"].index(ficha_existente.get("estado_ficha", "Activa")) if ficha_existente else 0),
            )

        observaciones_generales = st.text_area(
            "Observaciones generales APS",
            value=ficha_existente.get("observaciones_generales", "") if ficha_existente else "",
            placeholder="Resumen general del paciente dentro del dispensario...",
        )

        guardar = st.form_submit_button("Guardar ficha APS", use_container_width=True)

    if guardar:
        payload = {
            "paciente_id": paciente_id,
            "centro_salud_id": centro_salud_id,
            "medico_referente": medico_referente,
            "enfermero_referente": enfermero_referente,
            "promotor_referente": promotor_referente,
            "riesgo_general": riesgo_general,
            "programa_asignado": programa_asignado,
            "estado_ficha": estado_ficha,
            "observaciones_generales": observaciones_generales,
            "ultima_actualizacion": datetime.now().isoformat(),
        }
        # Actualizar si existe, sino insertar
        if ficha_existente:
            idx = fichas.index(ficha_existente)
            st.session_state["ficha_aps_db"][idx] = payload
        else:
            if "ficha_aps_db" not in st.session_state or not isinstance(st.session_state["ficha_aps_db"], list):
                st.session_state["ficha_aps_db"] = []
            st.session_state["ficha_aps_db"].append(payload)
        guardar_json_db("ficha_aps_db", payload, spinner=True, max_items=500)
        st.success("Ficha APS guardada correctamente.")


def _tab_historial_aps(paciente_sel, user, centro_salud_id):
    st.subheader("Historial APS del Dispensario")
    st.caption("Todos los movimientos del paciente dentro del centro de salud.")

    paciente_id = _get_paciente_id_visual(paciente_sel)

    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_tipo = st.selectbox(
            "Filtrar por tipo",
            [
                "Todos", "Atención APS", "Farmacia", "Trabajo Social",
                "Epidemiología", "Visita domiciliaria", "Ficha APS",
            ],
        )
    with col2:
        fecha_desde = st.date_input("Desde", value=date.today())
    with col3:
        fecha_hasta = st.date_input("Hasta", value=date.today())

    st.divider()

    registros = []

    for a in st.session_state.get("atenciones_aps_db", []):
        if a.get("paciente_id") == paciente_id:
            registros.append({
                "fecha": str(a.get("fecha_atencion", ""))[:16],
                "tipo": "Atención APS",
                "titulo": a.get("motivo_consulta", "-"),
                "detalle": f"PA: {a.get('presion_arterial', 'S/D')} · FC: {a.get('frecuencia_cardiaca', 'S/D')}",
                "registrado_por": a.get("registrado_por", "-"),
            })

    for e in st.session_state.get("entregas_aps_db", []):
        if e.get("paciente_id") == paciente_id:
            registros.append({
                "fecha": str(e.get("fecha_entrega", ""))[:16],
                "tipo": "Farmacia",
                "titulo": e.get("medicamento", "Entrega"),
                "detalle": f"{e.get('cantidad', '-')} {e.get('unidad', '')}",
                "registrado_por": e.get("registrado_por", "-"),
            })

    for s in st.session_state.get("trabajo_social_aps_db", []):
        if s.get("paciente_id") == paciente_id:
            registros.append({
                "fecha": str(s.get("fecha_registro", ""))[:16],
                "tipo": "Trabajo Social",
                "titulo": f"Riesgo: {s.get('riesgo_social', '-')}",
                "detalle": f"Vivienda: {s.get('tipo_vivienda', '-')} · Agua: {s.get('agua_potable', '-')}",
                "registrado_por": s.get("registrado_por", "-"),
            })

    for ep in st.session_state.get("epidemiologia_aps_db", []):
        if ep.get("paciente_id") == paciente_id:
            registros.append({
                "fecha": str(ep.get("fecha_registro", ""))[:16],
                "tipo": "Epidemiología",
                "titulo": ", ".join(ep.get("enfermedades_seguimiento", [])),
                "detalle": f"Prioridad: {ep.get('prioridad', '-')} · Estado: {ep.get('estado', '-')}",
                "registrado_por": ep.get("registrado_por", "-"),
            })

    for v in st.session_state.get("visitas_domiciliarias_aps_db", []):
        if v.get("paciente_id") == paciente_id:
            registros.append({
                "fecha": str(v.get("fecha_visita", ""))[:16],
                "tipo": "Visita domiciliaria",
                "titulo": v.get("motivo_visita", "-"),
                "detalle": v.get("resultado_visita", "-"),
                "registrado_por": v.get("registrado_por", "-"),
            })

    for f in st.session_state.get("ficha_aps_db", []):
        if f.get("paciente_id") == paciente_id:
            registros.append({
                "fecha": str(f.get("ultima_actualizacion", ""))[:16],
                "tipo": "Ficha APS",
                "titulo": f"Riesgo: {f.get('riesgo_general', '-')} · Estado: {f.get('estado_ficha', '-')}",
                "detalle": f"Programas: {', '.join(f.get('programa_asignado', []))}",
                "registrado_por": "-",
            })

    # Filtros
    if filtro_tipo != "Todos":
        registros = [r for r in registros if r["tipo"] == filtro_tipo]

    fd = fecha_desde.isoformat()
    fh = fecha_hasta.isoformat()
    registros = [r for r in registros if fd <= r["fecha"][:10] <= fh]

    registros.sort(key=lambda x: x["fecha"], reverse=True)

    if not registros:
        st.warning("No hay registros para el filtro seleccionado.")
        return

    for item in registros:
        with st.container(border=True):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"**{item['titulo']}**")
                st.caption(f"Tipo: {item['tipo']}")
                st.write(item["detalle"])
                st.caption(f"Registrado por: {item['registrado_por']}")
            with col_b:
                st.write(item["fecha"])


def _tab_nueva_atencion(paciente_sel, user, centro_salud_id):
    st.subheader("Nueva Atención APS")

    paciente_id = _get_paciente_id_visual(paciente_sel)

    with st.form("form_nueva_atencion_aps"):
        motivo = st.selectbox(
            "Motivo de atención",
            [
                "Control general", "Control de presión arterial", "Control de diabetes",
                "Curación", "Vacunación", "Control niño sano", "Control embarazo",
                "Entrega de medicación", "Consulta respiratoria", "Consulta social", "Otro",
            ],
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            presion = st.text_input("Presión arterial", placeholder="120/80")
            frecuencia = st.number_input("Frecuencia cardíaca", min_value=0, max_value=250)
        with col2:
            temperatura = st.number_input("Temperatura", min_value=30.0, max_value=45.0, step=0.1)
            glucemia = st.number_input("Glucemia", min_value=0, max_value=600)
        with col3:
            saturacion = st.number_input("Saturación O2", min_value=0, max_value=100)
            peso = st.number_input("Peso", min_value=0.0, max_value=300.0, step=0.1)

        diagnostico_aps = st.text_input("Diagnóstico / impresión APS")
        conducta = st.text_area("Conducta / indicaciones")
        observaciones = st.text_area("Observaciones de la atención")

        requiere_derivacion = st.checkbox("Requiere derivación")
        destino_derivacion = st.text_input("Destino de derivación", placeholder="Hospital, guardia, especialista...")

        guardar = st.form_submit_button("Guardar atención", use_container_width=True)

    if guardar:
        payload = {
            "paciente_id": paciente_id,
            "centro_salud_id": centro_salud_id,
            "fecha_atencion": datetime.now().isoformat(),
            "motivo_consulta": motivo,
            "presion_arterial": presion,
            "frecuencia_cardiaca": frecuencia,
            "temperatura": temperatura,
            "glucemia": glucemia,
            "saturacion": saturacion,
            "peso": peso,
            "diagnostico_aps": diagnostico_aps,
            "conducta": conducta,
            "observaciones": observaciones,
            "requiere_derivacion": requiere_derivacion,
            "destino_derivacion": destino_derivacion,
            "registrado_por": st.session_state.get("u_actual", {}).get("nombre", "Usuario APS"),
            "created_at": datetime.now().isoformat(),
        }
        guardar_json_db("atenciones_aps_db", payload, spinner=True, max_items=1000)
        st.success("Atención APS guardada correctamente.")


def _tab_farmacia(paciente_sel, user, centro_salud_id):
    st.subheader("Farmacia e Insumos")
    st.caption("Entrega de medicación crónica, leche, anticonceptivos e insumos.")

    paciente_id = _get_paciente_id_visual(paciente_sel)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Medicación crónica")
        medicamento = st.selectbox(
            "Medicamento",
            [
                "Enalapril 10 mg", "Losartán 50 mg", "Amlodipina 5 mg",
                "Metformina 850 mg", "Glibenclamida 5 mg", "Insulina NPH",
                "Salbutamol", "Levotiroxina", "Atorvastatina", "Otro",
            ],
            key="aps_med_select",
        )
        cantidad = st.number_input("Cantidad", min_value=1, value=1, key="aps_med_cant")
        unidad = st.selectbox("Unidad", ["Comprimidos", "Cajas", "Frascos", "Ampollas", "Aerosoles"], key="aps_med_unidad")

    with col2:
        st.markdown("### Programas APS")
        entrega_leche = st.checkbox("Entrega de leche", key="aps_leche")
        cantidad_leche = st.number_input("Cantidad leche", min_value=0, value=0, key="aps_leche_cant")
        entrega_anticonceptivos = st.checkbox("Entrega de anticonceptivos", key="aps_anti")
        tipo_anticonceptivo = st.selectbox(
            "Tipo anticonceptivo",
            [
                "No corresponde", "Preservativos", "Anticonceptivos orales",
                "Inyectable mensual", "Inyectable trimestral", "DIU - derivación", "Implante - derivación",
            ],
            key="aps_anti_tipo",
        )
        insumos = st.multiselect(
            "Insumos entregados",
            [
                "Gasas", "Apósitos", "Guantes", "Jeringas",
                "Alcohol", "Tiras reactivas", "Lancetas", "Material de curación",
            ],
            key="aps_insumos",
        )

    observacion_farmacia = st.text_area("Observación de farmacia", key="aps_farm_obs")

    if st.button("Registrar entrega APS", use_container_width=True, key="aps_btn_farmacia"):
        payload = {
            "paciente_id": paciente_id,
            "centro_salud_id": centro_salud_id,
            "fecha_entrega": datetime.now().isoformat(),
            "tipo_entrega": "farmacia_aps",
            "medicamento": medicamento,
            "cantidad": cantidad,
            "unidad": unidad,
            "entrega_leche": entrega_leche,
            "cantidad_leche": cantidad_leche,
            "entrega_anticonceptivos": entrega_anticonceptivos,
            "tipo_anticonceptivo": tipo_anticonceptivo,
            "insumos_entregados": insumos,
            "observaciones": observacion_farmacia,
            "registrado_por": st.session_state.get("u_actual", {}).get("nombre", "Usuario APS"),
            "created_at": datetime.now().isoformat(),
        }
        guardar_json_db("entregas_aps_db", payload, spinner=True, max_items=1000)
        st.success("Entrega APS registrada correctamente.")


def _tab_trabajo_social(paciente_sel, user, centro_salud_id):
    st.subheader("Trabajo Social APS")

    paciente_id = _get_paciente_id_visual(paciente_sel)

    with st.form("form_trabajo_social_aps"):
        col1, col2 = st.columns(2)
        with col1:
            tipo_vivienda = st.selectbox(
                "Tipo de vivienda",
                ["Material", "Chapa", "Madera", "Mixta", "Rancho", "Situación de calle", "Otra"],
            )
            agua = st.selectbox(
                "Agua potable",
                ["Sí", "No", "Intermitente", "Pozo", "Canilla comunitaria"],
            )
            electricidad = st.selectbox(
                "Electricidad",
                ["Sí", "No", "Conexión precaria"],
            )
        with col2:
            gas = st.selectbox(
                "Gas",
                ["Gas natural", "Garrafa", "Leña / carbón", "No posee"],
            )
            cobertura = st.selectbox(
                "Cobertura social",
                ["Ninguna", "Obra social", "PAMI", "Incluir Salud", "Plan Alimentario", "Asignación", "Otro"],
            )
            riesgo_social = st.selectbox(
                "Riesgo social",
                ["Bajo", "Moderado", "Alto", "Crítico"],
            )

        grupo_familiar = st.number_input("Cantidad de convivientes", min_value=0, max_value=30)
        observaciones = st.text_area("Observaciones sociales")

        guardar = st.form_submit_button("Guardar registro social", use_container_width=True)

    if guardar:
        payload = {
            "paciente_id": paciente_id,
            "centro_salud_id": centro_salud_id,
            "fecha_registro": datetime.now().isoformat(),
            "tipo_vivienda": tipo_vivienda,
            "agua_potable": agua,
            "electricidad": electricidad,
            "gas": gas,
            "grupo_familiar": grupo_familiar,
            "cobertura_social": cobertura,
            "riesgo_social": riesgo_social,
            "observaciones": observaciones,
            "registrado_por": st.session_state.get("u_actual", {}).get("nombre", "Trabajo Social APS"),
            "created_at": datetime.now().isoformat(),
        }
        guardar_json_db("trabajo_social_aps_db", payload, spinner=True, max_items=500)
        st.success("Registro social APS guardado correctamente.")


def _tab_epidemiologia(paciente_sel, user, centro_salud_id):
    st.subheader("Epidemiología APS")

    paciente_id = _get_paciente_id_visual(paciente_sel)

    with st.form("form_epidemiologia_aps"):
        enfermedades = st.multiselect(
            "Enfermedades / eventos de seguimiento",
            [
                "Dengue", "Tuberculosis", "Sífilis", "VIH", "Chagas",
                "Hepatitis", "COVID-19", "Influenza", "ETA",
                "Escabiosis", "Pediculosis", "Desnutrición",
                "Embarazo adolescente", "Violencia familiar", "Otra",
            ],
        )

        col1, col2 = st.columns(2)
        with col1:
            requiere_notificacion = st.checkbox("Requiere notificación obligatoria")
            requiere_visita = st.checkbox("Requiere visita domiciliaria")
        with col2:
            prioridad = st.selectbox("Prioridad", ["Baja", "Media", "Alta", "Urgente"])
            estado = st.selectbox("Estado", ["Pendiente", "En seguimiento", "Resuelto", "Derivado"])

        observaciones = st.text_area("Observaciones para promotor de salud")

        guardar = st.form_submit_button("Guardar epidemiología", use_container_width=True)

    if guardar:
        payload = {
            "paciente_id": paciente_id,
            "centro_salud_id": centro_salud_id,
            "fecha_registro": datetime.now().isoformat(),
            "enfermedades_seguimiento": enfermedades,
            "requiere_notificacion": requiere_notificacion,
            "requiere_visita": requiere_visita,
            "prioridad": prioridad,
            "estado": estado,
            "observaciones_promotor": observaciones,
            "registrado_por": st.session_state.get("u_actual", {}).get("nombre", "Usuario APS"),
            "created_at": datetime.now().isoformat(),
        }
        guardar_json_db("epidemiologia_aps_db", payload, spinner=True, max_items=500)
        st.success("Registro epidemiológico guardado correctamente.")


def _tab_visitas(paciente_sel, user, centro_salud_id):
    st.subheader("Visitas Domiciliarias APS")

    paciente_id = _get_paciente_id_visual(paciente_sel)

    with st.form("form_visita_domiciliaria_aps"):
        motivo = st.selectbox(
            "Motivo de visita",
            [
                "Seguimiento social", "Control epidemiológico", "Control de tratamiento",
                "Paciente ausente a controles", "Embarazo / puerperio",
                "Niño en seguimiento", "Adulto mayor vulnerable", "Otro",
            ],
        )

        domicilio = st.text_input("Domicilio visitado")
        paciente_encontrado = st.checkbox("Paciente encontrado en domicilio")
        resultado = st.text_area("Resultado de la visita")
        requiere_nueva = st.checkbox("Requiere nueva visita")
        prioridad = st.selectbox("Prioridad", ["Baja", "Media", "Alta", "Urgente"])

        guardar = st.form_submit_button("Guardar visita", use_container_width=True)

    if guardar:
        payload = {
            "paciente_id": paciente_id,
            "centro_salud_id": centro_salud_id,
            "fecha_visita": datetime.now().isoformat(),
            "motivo_visita": motivo,
            "domicilio_visitado": domicilio,
            "paciente_encontrado": paciente_encontrado,
            "resultado_visita": resultado,
            "requiere_nueva_visita": requiere_nueva,
            "prioridad": prioridad,
            "estado": "Pendiente" if requiere_nueva else "Completada",
            "registrado_por": st.session_state.get("u_actual", {}).get("nombre", "Promotor APS"),
            "created_at": datetime.now().isoformat(),
        }
        guardar_json_db("visitas_domiciliarias_aps_db", payload, spinner=True, max_items=500)
        st.success("Visita domiciliaria guardada correctamente.")


def _tab_reportes(paciente_sel, user, centro_salud_id):
    st.subheader("Reportes APS")
    st.caption("Indicadores útiles para coordinación, municipio o centro de salud.")

    col1, col2 = st.columns(2)
    with col1:
        fecha_desde = st.date_input("Desde", value=date.today(), key="aps_rep_desde")
        fecha_hasta = st.date_input("Hasta", value=date.today(), key="aps_rep_hasta")
    with col2:
        tipo_reporte = st.selectbox(
            "Tipo de reporte",
            [
                "Atenciones APS", "Entregas de medicación", "Entregas de leche",
                "Casos epidemiológicos", "Pacientes con riesgo social", "Visitas domiciliarias",
            ],
            key="aps_rep_tipo",
        )

    if st.button("Generar reporte", use_container_width=True, key="aps_rep_btn"):
        fd = fecha_desde.isoformat()
        fh = fecha_hasta.isoformat()

        registros = []
        if tipo_reporte == "Atenciones APS":
            registros = [
                a for a in st.session_state.get("atenciones_aps_db", [])
                if fd <= str(a.get("fecha_atencion", ""))[:10] <= fh
            ]
        elif tipo_reporte in ("Entregas de medicación", "Entregas de leche"):
            registros = [
                e for e in st.session_state.get("entregas_aps_db", [])
                if fd <= str(e.get("fecha_entrega", ""))[:10] <= fh
            ]
        elif tipo_reporte == "Casos epidemiológicos":
            registros = [
                ep for ep in st.session_state.get("epidemiologia_aps_db", [])
                if fd <= str(ep.get("fecha_registro", ""))[:10] <= fh
            ]
        elif tipo_reporte == "Pacientes con riesgo social":
            registros = [
                s for s in st.session_state.get("trabajo_social_aps_db", [])
                if fd <= str(s.get("fecha_registro", ""))[:10] <= fh
            ]
        elif tipo_reporte == "Visitas domiciliarias":
            registros = [
                v for v in st.session_state.get("visitas_domiciliarias_aps_db", [])
                if fd <= str(v.get("fecha_visita", ""))[:10] <= fh
            ]

        st.write(f"**{len(registros)}** registros encontrados.")
        if registros:
            st.dataframe(registros, use_container_width=True, hide_index=True)
        else:
            st.info("No hay registros en el período seleccionado.")


def render_dispensario_aps(paciente_sel, mi_empresa, user, rol):
    """Entry point del módulo APS / Dispensario."""

    st.title("🏥 APS / Dispensario")
    st.caption("Atención Primaria de la Salud · Centro de Salud · Dispensario Comunitario")

    centro_salud_id = st.session_state.get("centro_salud_id", "dispensario-demo-001")

    _metricas_aps_del_dia()
    st.divider()

    # Si no hay paciente, mostrar aviso pero permitir acceso a Panel Diario y Reportes
    if not paciente_sel:
        st.info("Seleccioná un paciente desde el sidebar para registrar atenciones, farmacia, trabajo social, epidemiología y visitas.")

    tabs = st.tabs([
        "📊 Panel Diario",
        "👤 Ficha APS",
        "📚 Historial APS",
        "🩺 Nueva Atención",
        "💊 Farmacia",
        "📋 Trabajo Social",
        "🚨 Epidemiología",
        "🏠 Visitas",
        "📈 Reportes",
    ])

    with tabs[0]:
        _tab_panel_diario(paciente_sel, user)

    with tabs[1]:
        if paciente_sel:
            _tab_ficha_aps(paciente_sel, user, centro_salud_id)
        else:
            aviso_sin_paciente()

    with tabs[2]:
        if paciente_sel:
            _tab_historial_aps(paciente_sel, user, centro_salud_id)
        else:
            aviso_sin_paciente()

    with tabs[3]:
        if paciente_sel:
            _tab_nueva_atencion(paciente_sel, user, centro_salud_id)
        else:
            aviso_sin_paciente()

    with tabs[4]:
        if paciente_sel:
            _tab_farmacia(paciente_sel, user, centro_salud_id)
        else:
            aviso_sin_paciente()

    with tabs[5]:
        if paciente_sel:
            _tab_trabajo_social(paciente_sel, user, centro_salud_id)
        else:
            aviso_sin_paciente()

    with tabs[6]:
        if paciente_sel:
            _tab_epidemiologia(paciente_sel, user, centro_salud_id)
        else:
            aviso_sin_paciente()

    with tabs[7]:
        if paciente_sel:
            _tab_visitas(paciente_sel, user, centro_salud_id)
        else:
            aviso_sin_paciente()

    with tabs[8]:
        _tab_reportes(paciente_sel, user, centro_salud_id)
