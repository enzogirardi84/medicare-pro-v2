import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.utils import ahora, mostrar_dataframe_con_scroll, seleccionar_limite_registros


SERVICIOS_BASE = [
    "Inyectables",
    "Curaciones",
    "Control de signos vitales",
    "Internacion domiciliaria",
    "Postoperatorios",
    "Control diabetologico",
    "Pediatria domiciliaria",
    "Cuidados paliativos",
    "Sondas y ostomias",
    "Acompanamiento nocturno",
    "Nebulizaciones y oxigenoterapia",
    "Higiene y confort",
]


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
            <h2 class="mc-hero-title">Red de profesionales domiciliarios</h2>
            <p class="mc-hero-text">Muestra servicios, perfiles y pedidos de atencion para que pacientes y familias contacten al profesional correcto segun necesidad, zona y disponibilidad.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Perfil publico</span>
                <span class="mc-chip">Servicios ofrecidos</span>
                <span class="mc-chip">Solicitudes de pacientes</span>
                <span class="mc-chip">Contacto rapido</span>
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
            titulo = col2.text_input("Titulo profesional", value=actual.get("titulo", "Enfermero/a domiciliario/a"))
            col3, col4 = st.columns(2)
            matricula = col3.text_input("Matricula", value=actual.get("matricula", user.get("matricula", "")))
            zona = col4.text_input("Zona de cobertura", value=actual.get("zona", "Rio Cuarto y alrededores"))
            col5, col6 = st.columns(2)
            whatsapp = col5.text_input("WhatsApp de contacto", value=actual.get("whatsapp", ""))
            disponibilidad = col6.selectbox(
                "Disponibilidad",
                ["Hoy", "24 hs", "Manana", "Tarde", "Noche", "Guardias programadas"],
                index=0 if not actual.get("disponibilidad") else ["Hoy", "24 hs", "Manana", "Tarde", "Noche", "Guardias programadas"].index(actual.get("disponibilidad")),
            )
            servicios = st.multiselect(
                "Servicios que ofreces",
                SERVICIOS_BASE,
                default=actual.get("servicios", []),
            )
            descripcion = st.text_area(
                "Descripcion breve",
                value=actual.get(
                    "descripcion",
                    "Atencion profesional en domicilio con seguimiento, trazabilidad y contacto directo para pacientes y familiares.",
                ),
                height=120,
            )

            if st.button("Guardar perfil profesional", use_container_width=True, type="primary"):
                nuevo = {
                    "nombre": nombre.strip() or user.get("nombre", ""),
                    "titulo": titulo.strip(),
                    "matricula": matricula.strip(),
                    "zona": zona.strip(),
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
            st.markdown("### Vista previa de tu perfil")
            servicios_txt = " | ".join(vista.get("servicios", [])) or "Sin servicios cargados"
            st.markdown(
                f"""
                <div class="mc-card">
                    <h3>{vista.get("nombre", "")}</h3>
                    <p><strong>{vista.get("titulo", "")}</strong> | Matricula: {vista.get("matricula", "S/D")}</p>
                    <p>Zona: {vista.get("zona", "S/D")} | Disponibilidad: {vista.get("disponibilidad", "S/D")}</p>
                    <p>{vista.get("descripcion", "")}</p>
                    <p><strong>Servicios:</strong> {servicios_txt}</p>
                    <p><strong>WhatsApp:</strong> {vista.get("whatsapp", "S/D")}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with tab_busqueda:
        st.markdown("### Profesionales disponibles")
        registros = pd.DataFrame(st.session_state.get("profesionales_red_db", []))
        if registros.empty:
            st.info("Todavia no hay perfiles profesionales cargados.")
        else:
            colf1, colf2 = st.columns(2)
            servicio = colf1.selectbox("Filtrar por servicio", ["Todos"] + SERVICIOS_BASE)
            zona = colf2.text_input("Buscar por zona")
            df = registros.copy()
            if servicio != "Todos":
                df = df[df["servicios"].apply(lambda xs: servicio in xs if isinstance(xs, list) else False)]
            if zona.strip():
                df = df[df["zona"].astype(str).str.contains(zona.strip(), case=False, na=False)]

            if df.empty:
                st.warning("No hay profesionales que coincidan con ese filtro.")
            else:
                limite = seleccionar_limite_registros(
                    "Perfiles a mostrar",
                    len(df),
                    key=f"limite_red_profesionales_{mi_empresa}",
                    default=20,
                    opciones=(5, 10, 20, 30, 50, 100),
                )
                with st.container(height=520):
                    for _, reg in df.head(limite).iterrows():
                        with st.container(border=True):
                            st.markdown(f"**{reg.get('nombre', '')}** | {reg.get('titulo', '')}")
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
        st.markdown("### Pedidos de pacientes y familiares")
        with st.container(border=True):
            col1, col2 = st.columns(2)
            nombre_paciente = col1.text_input("Nombre del paciente o familiar", key="sol_nombre")
            telefono = col2.text_input("Telefono de contacto", key="sol_tel")
            col3, col4 = st.columns(2)
            servicio = col3.selectbox("Servicio solicitado", SERVICIOS_BASE, key="sol_serv")
            prioridad = col4.selectbox("Prioridad", ["Programado", "Hoy", "Urgente", "Critico"], key="sol_prio")
            zona = st.text_input("Zona / direccion", key="sol_zona")
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
                            "servicio": servicio,
                            "prioridad": prioridad,
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
