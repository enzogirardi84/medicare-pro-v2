import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.utils import ahora, mostrar_dataframe_con_scroll, seleccionar_limite_registros


TIPOS_PERFIL = [
    "Enfermeria",
    "Medicina",
    "Kinesiologia",
    "Psicologia",
    "Nutricion",
    "Fonoaudiologia",
    "Terapia ocupacional",
    "Farmacia",
    "Administrativo",
    "Coordinacion",
    "Ambulancia y traslados",
    "Acompanante terapeutico",
    "Cuidador/a domiciliario/a",
    "Institucion / Empresa de salud",
    "Otro",
]

SERVICIOS_POR_TIPO = {
    "Enfermeria": [
        "Inyectables",
        "Curaciones",
        "Control de signos vitales",
        "Internacion domiciliaria",
        "Postoperatorios",
        "Control diabetologico",
        "Sondas y ostomias",
        "Cuidados paliativos",
        "Nebulizaciones y oxigenoterapia",
        "Higiene y confort",
    ],
    "Medicina": [
        "Consulta clinica",
        "Seguimiento domiciliario",
        "Prescripciones y recetas",
        "Certificados",
        "Cuidados paliativos",
        "Control de patologias cronicas",
        "Teleconsulta",
    ],
    "Kinesiologia": [
        "Rehabilitacion motora",
        "Kinesiologia respiratoria",
        "Postoperatorios",
        "Neurorehabilitacion",
        "Traumatologia",
    ],
    "Psicologia": [
        "Atencion psicologica",
        "Acompanamiento familiar",
        "Psicologia domiciliaria",
        "Teleconsulta",
    ],
    "Nutricion": [
        "Plan nutricional",
        "Control domiciliario",
        "Educacion alimentaria",
        "Soporte enteral",
    ],
    "Fonoaudiologia": [
        "Rehabilitacion del habla",
        "Deglucion",
        "Seguimiento neurologico",
    ],
    "Terapia ocupacional": [
        "Rehabilitacion funcional",
        "Adaptacion domiciliaria",
        "Estimulo cognitivo",
    ],
    "Farmacia": [
        "Armado de medicacion",
        "Control de stock",
        "Dispensa y seguimiento",
    ],
    "Administrativo": [
        "Admision de pacientes",
        "Facturacion",
        "Autorizaciones",
        "Gestion documental",
    ],
    "Coordinacion": [
        "Coordinacion de equipos",
        "Derivaciones",
        "Auditoria",
        "Gestion operativa",
    ],
    "Ambulancia y traslados": [
        "Traslado programado",
        "Traslado asistencial",
        "Cobertura de eventos",
        "Emergencias",
    ],
    "Acompanante terapeutico": [
        "Acompanamiento terapeutico",
        "Acompanamiento nocturno",
        "Seguimiento conductual",
    ],
    "Cuidador/a domiciliario/a": [
        "Compania y cuidado",
        "Higiene y confort",
        "Acompanamiento nocturno",
        "Movilizacion",
    ],
    "Institucion / Empresa de salud": [
        "Internacion domiciliaria",
        "Emergencias y ambulancias",
        "Servicios administrativos",
        "Prestadores tercerizados",
        "Cobertura integral",
    ],
    "Otro": [
        "Prestacion personalizada",
        "Guardias",
        "Consulta",
    ],
}


def _servicios_catalogo():
    servicios = []
    for lista in SERVICIOS_POR_TIPO.values():
        servicios.extend(lista)
    return sorted(set(servicios))


def _servicios_sugeridos(tipo):
    return SERVICIOS_POR_TIPO.get(tipo, SERVICIOS_POR_TIPO["Otro"])


def _obtener_profesional_actual(user, mi_empresa):
    nombre = user.get("nombre", "")
    registros = st.session_state.get("profesionales_red_db", [])
    for reg in registros:
        if reg.get("nombre") == nombre and reg.get("empresa") == mi_empresa:
            return reg
    return None


def render_red_profesionales(mi_empresa, user, rol):
    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Red de profesionales y organizaciones de salud</h2>
            <p class="mc-hero-text">Esta vista sirve para profesionales individuales, equipos interdisciplinarios, administrativos, empresas de salud y prestadores externos. Permite publicar perfiles, servicios y recibir solicitudes segun necesidad, zona y tipo de atencion.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Perfiles profesionales</span>
                <span class="mc-chip">Instituciones y empresas</span>
                <span class="mc-chip">Servicios por especialidad</span>
                <span class="mc-chip">Pedidos de pacientes y familias</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_perfil, tab_busqueda, tab_solicitudes = st.tabs(
        ["Mi Perfil Profesional", "Buscador de Profesionales", "Solicitudes de Pacientes"]
    )

    with tab_perfil:
        actual = _obtener_profesional_actual(user, mi_empresa) or {}
        st.markdown("### Tu ficha publica")
        with st.container(border=True):
            col1, col2 = st.columns(2)
            nombre = col1.text_input("Nombre visible", value=actual.get("nombre", user.get("nombre", "")))
            tipo = col2.selectbox(
                "Tipo de perfil",
                TIPOS_PERFIL,
                index=TIPOS_PERFIL.index(actual.get("tipo", "Enfermeria")) if actual.get("tipo", "Enfermeria") in TIPOS_PERFIL else 0,
            )
            col3, col4 = st.columns(2)
            titulo = col3.text_input(
                "Titulo / cargo",
                value=actual.get("titulo", "Profesional de salud domiciliaria"),
            )
            especialidad = col4.text_input(
                "Especialidad / sector",
                value=actual.get("especialidad", ""),
                placeholder="Ej: Clinica medica, facturacion, cuidados paliativos, admision",
            )
            col5, col6 = st.columns(2)
            matricula = col5.text_input("Matricula o identificacion", value=actual.get("matricula", user.get("matricula", "")))
            zona = col6.text_input("Zona de cobertura", value=actual.get("zona", "Rio Cuarto y alrededores"))
            col7, col8 = st.columns(2)
            organizacion = col7.text_input("Organizacion / empresa", value=actual.get("organizacion", mi_empresa))
            modalidad = col8.selectbox(
                "Modalidad de trabajo",
                ["Independiente", "Prestador externo", "Equipo institucional", "Empresa de salud", "Organizacion mixta"],
                index=["Independiente", "Prestador externo", "Equipo institucional", "Empresa de salud", "Organizacion mixta"].index(actual.get("modalidad", "Equipo institucional"))
                if actual.get("modalidad", "Equipo institucional") in ["Independiente", "Prestador externo", "Equipo institucional", "Empresa de salud", "Organizacion mixta"]
                else 2,
            )
            col9, col10 = st.columns(2)
            whatsapp = col9.text_input("WhatsApp de contacto", value=actual.get("whatsapp", ""))
            disponibilidad = col10.selectbox(
                "Disponibilidad",
                ["Hoy", "24 hs", "Manana", "Tarde", "Noche", "Guardias programadas", "Bajo agenda"],
                index=["Hoy", "24 hs", "Manana", "Tarde", "Noche", "Guardias programadas", "Bajo agenda"].index(actual.get("disponibilidad", "Hoy"))
                if actual.get("disponibilidad", "Hoy") in ["Hoy", "24 hs", "Manana", "Tarde", "Noche", "Guardias programadas", "Bajo agenda"]
                else 0,
            )

            sugeridos = _servicios_sugeridos(tipo)
            servicios = st.multiselect(
                "Servicios que ofreces",
                _servicios_catalogo(),
                default=actual.get("servicios", sugeridos[: min(3, len(sugeridos))]),
                help="Puedes mezclar servicios asistenciales, administrativos o institucionales.",
            )
            descripcion = st.text_area(
                "Descripcion breve",
                value=actual.get(
                    "descripcion",
                    "Perfil orientado a atencion, coordinacion y seguimiento dentro del ecosistema de salud domiciliaria.",
                ),
                height=120,
            )

            if st.button("Guardar perfil profesional", use_container_width=True, type="primary"):
                nuevo = {
                    "nombre": nombre.strip() or user.get("nombre", ""),
                    "tipo": tipo,
                    "titulo": titulo.strip(),
                    "especialidad": especialidad.strip(),
                    "matricula": matricula.strip(),
                    "zona": zona.strip(),
                    "organizacion": organizacion.strip() or mi_empresa,
                    "modalidad": modalidad,
                    "whatsapp": whatsapp.strip(),
                    "disponibilidad": disponibilidad,
                    "servicios": servicios,
                    "descripcion": descripcion.strip(),
                    "empresa": mi_empresa,
                    "actualizado": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                }
                registros = st.session_state.get("profesionales_red_db", [])
                reemplazado = False
                for idx, reg in enumerate(registros):
                    if reg.get("nombre") == user.get("nombre", "") and reg.get("empresa") == mi_empresa:
                        registros[idx] = nuevo
                        reemplazado = True
                        break
                if not reemplazado:
                    registros.append(nuevo)
                st.session_state["profesionales_red_db"] = registros
                guardar_datos()
                st.success("Perfil profesional guardado.")
                st.rerun()

        vista = _obtener_profesional_actual(user, mi_empresa)
        if vista:
            servicios_txt = " | ".join(vista.get("servicios", [])) or "Sin servicios cargados"
            st.markdown("### Vista previa de tu perfil")
            st.markdown(
                f"""
                <div class="mc-card">
                    <h3>{vista.get("nombre", "")}</h3>
                    <p><strong>{vista.get("tipo", "")}</strong> | {vista.get("titulo", "")}</p>
                    <p>Especialidad: {vista.get("especialidad", "S/D")} | Matricula: {vista.get("matricula", "S/D")}</p>
                    <p>Organizacion: {vista.get("organizacion", "S/D")} | Modalidad: {vista.get("modalidad", "S/D")}</p>
                    <p>Zona: {vista.get("zona", "S/D")} | Disponibilidad: {vista.get("disponibilidad", "S/D")}</p>
                    <p>{vista.get("descripcion", "")}</p>
                    <p><strong>Servicios:</strong> {servicios_txt}</p>
                    <p><strong>WhatsApp:</strong> {vista.get("whatsapp", "S/D")}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with tab_busqueda:
        st.markdown("### Profesionales y organizaciones disponibles")
        registros = pd.DataFrame(st.session_state.get("profesionales_red_db", []))
        if registros.empty:
            st.info("Todavia no hay perfiles cargados.")
        else:
            colf1, colf2, colf3 = st.columns(3)
            tipo_filtro = colf1.selectbox("Tipo", ["Todos"] + TIPOS_PERFIL)
            servicio = colf2.selectbox("Servicio", ["Todos"] + _servicios_catalogo())
            zona = colf3.text_input("Zona")
            organizacion_filtro = st.text_input("Organizacion / empresa")

            df = registros.copy()
            if tipo_filtro != "Todos":
                df = df[df["tipo"] == tipo_filtro]
            if servicio != "Todos":
                df = df[df["servicios"].apply(lambda xs: servicio in xs if isinstance(xs, list) else False)]
            if zona.strip():
                df = df[df["zona"].astype(str).str.contains(zona.strip(), case=False, na=False)]
            if organizacion_filtro.strip():
                df = df[df["organizacion"].astype(str).str.contains(organizacion_filtro.strip(), case=False, na=False)]

            if df.empty:
                st.warning("No hay perfiles que coincidan con ese filtro.")
            else:
                limite = seleccionar_limite_registros(
                    "Perfiles a mostrar",
                    len(df),
                    key=f"limite_red_profesionales_{mi_empresa}",
                    default=20,
                    opciones=(5, 10, 20, 30, 50, 100),
                )
                with st.container(height=540):
                    for _, reg in df.head(limite).iterrows():
                        with st.container(border=True):
                            st.markdown(f"**{reg.get('nombre', '')}** | {reg.get('titulo', '')}")
                            st.caption(
                                f"Tipo: {reg.get('tipo', 'S/D')} | Especialidad: {reg.get('especialidad', 'S/D')} | "
                                f"Organizacion: {reg.get('organizacion', 'S/D')}"
                            )
                            st.caption(
                                f"Zona: {reg.get('zona', 'S/D')} | Disponibilidad: {reg.get('disponibilidad', 'S/D')} | "
                                f"Matricula: {reg.get('matricula', 'S/D')}"
                            )
                            st.write(reg.get("descripcion", ""))
                            st.write(f"Servicios: {', '.join(reg.get('servicios', []))}")
                            if reg.get("whatsapp"):
                                telefono = "".join(ch for ch in str(reg.get("whatsapp")) if ch.isdigit() or ch == "+")
                                if telefono:
                                    st.link_button(
                                        "Contactar por WhatsApp",
                                        f"https://wa.me/{telefono.lstrip('+')}",
                                        use_container_width=True,
                                    )

    with tab_solicitudes:
        st.markdown("### Pedidos de pacientes, familias e instituciones")
        with st.container(border=True):
            col1, col2 = st.columns(2)
            nombre_paciente = col1.text_input("Nombre del paciente o solicitante", key="sol_nombre")
            telefono = col2.text_input("Telefono de contacto", key="sol_tel")
            col3, col4, col5 = st.columns(3)
            tipo_requerido = col3.selectbox("Tipo de profesional requerido", TIPOS_PERFIL, key="sol_tipo")
            servicio = col4.selectbox("Servicio solicitado", _servicios_catalogo(), key="sol_serv")
            prioridad = col5.selectbox("Prioridad", ["Programado", "Hoy", "Urgente", "Critico"], key="sol_prio")
            col6, col7 = st.columns(2)
            organizacion = col6.text_input("Organizacion que solicita", key="sol_org", placeholder="Particular, clinica, residencia, obra social")
            zona = col7.text_input("Zona / direccion", key="sol_zona")
            detalle = st.text_area("Detalle de la necesidad", key="sol_detalle", height=120)

            if st.button("Guardar solicitud", use_container_width=True, type="primary"):
                if not nombre_paciente.strip() or not telefono.strip():
                    st.error("Debe completar al menos nombre y telefono.")
                else:
                    st.session_state["solicitudes_servicios_db"].append(
                        {
                            "fecha": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                            "nombre": nombre_paciente.strip(),
                            "telefono": telefono.strip(),
                            "tipo_requerido": tipo_requerido,
                            "servicio": servicio,
                            "prioridad": prioridad,
                            "organizacion": organizacion.strip(),
                            "zona": zona.strip(),
                            "detalle": detalle.strip(),
                            "empresa": mi_empresa,
                            "cargado_por": user.get("nombre", ""),
                            "estado": "Nueva",
                        }
                    )
                    guardar_datos()
                    st.success("Solicitud guardada correctamente.")
                    st.rerun()

        solicitudes = [
            x for x in st.session_state.get("solicitudes_servicios_db", [])
            if x.get("empresa") == mi_empresa or rol == "SuperAdmin"
        ]
        if not solicitudes:
            st.info("Todavia no hay solicitudes cargadas.")
        else:
            df_sol = pd.DataFrame(solicitudes)
            limite = seleccionar_limite_registros(
                "Solicitudes a mostrar",
                len(df_sol),
                key=f"limite_solicitudes_{mi_empresa}",
                default=20,
                opciones=(10, 20, 30, 50, 100, 200),
            )
            mostrar_dataframe_con_scroll(
                df_sol.sort_values(by="fecha", ascending=False).head(limite),
                height=420,
            )
