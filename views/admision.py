from datetime import date

import streamlit as st

from core.database import guardar_datos
from core.utils import ahora


def render_admision(mi_empresa, rol):
    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Admision de nuevo paciente</h2>
            <p class="mc-hero-text">Carga el legajo inicial con datos personales, cobertura y alertas clinicas. La vista esta pensada para evitar duplicados y dejar toda la informacion lista para visitas, PDF y control medico.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">1. Buscar si ya existe</span>
                <span class="mc-chip">2. Completar datos obligatorios</span>
                <span class="mc-chip">3. Guardar legajo</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("##### Buscar paciente existente")
    buscar_adm = st.text_input("Nombre, DNI o apellido", placeholder="Ej: Juan Perez o 35123456")

    if buscar_adm:
        coincidencias = [
            p
            for p in st.session_state["pacientes_db"]
            if buscar_adm.lower() in p.lower()
            or (buscar_adm.isdigit() and buscar_adm in st.session_state["detalles_pacientes_db"].get(p, {}).get("dni", ""))
        ]
        if coincidencias:
            st.warning(f"Se encontraron {len(coincidencias)} pacientes similares.")
            for p in coincidencias[:5]:
                det = st.session_state["detalles_pacientes_db"].get(p, {})
                st.caption(f"{p} | DNI: {det.get('dni', 'S/D')} | Empresa: {det.get('empresa', 'S/D')}")
        else:
            st.success("No hay pacientes con ese nombre o DNI.")

    st.markdown(
        """
        <div class="mc-grid-3">
            <div class="mc-card"><h4>Datos personales</h4><p>Nombre, DNI, fecha de nacimiento, sexo y telefono quedan visibles en todo el sistema.</p></div>
            <div class="mc-card"><h4>Datos administrativos</h4><p>La obra social y la empresa asignada se usan en historia clinica, reportes y documentos.</p></div>
            <div class="mc-card"><h4>Alertas clinicas</h4><p>Alergias y patologias se muestran en la barra lateral para reducir errores del equipo.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("adm_form", clear_on_submit=True):
        st.markdown("##### Datos del legajo")
        col_a, col_b = st.columns(2)
        n = col_a.text_input("Nombre y apellido *", placeholder="Juan Perez")
        o = col_b.text_input("Obra social / prepaga", placeholder="OSDE / PAMI / Particular")

        col_c, col_d = st.columns(2)
        d = col_c.text_input("DNI del paciente *", placeholder="35123456")
        f_nac = col_d.date_input(
            "Fecha de nacimiento",
            value=date(1990, 1, 1),
            min_value=date(1900, 1, 1),
            max_value=ahora().date(),
        )

        col_e, col_f = st.columns(2)
        se = col_e.selectbox("Sexo", ["F", "M", "Otro"])
        tel = col_f.text_input("WhatsApp / telefono", placeholder="3584302024")

        dir_p = st.text_input("Direccion exacta", placeholder="Calle 123, barrio, ciudad")

        st.markdown("##### Alertas y antecedentes")
        col_alg, col_pat = st.columns(2)
        alergias = col_alg.text_area("Alergias", placeholder="Ej: penicilina, ibuprofeno...", height=90)
        patologias = col_pat.text_area("Patologias previas / riesgos", placeholder="Ej: DBT, HTA, marcapasos...", height=90)

        if rol == "SuperAdmin":
            emp_d = st.text_input("Empresa / clinica", value=mi_empresa)
        else:
            emp_d = mi_empresa
            st.info(f"Paciente asignado a: {mi_empresa}")

        if st.form_submit_button("Habilitar paciente", use_container_width=True, type="primary"):
            if not n or not d:
                st.error("Nombre y DNI son obligatorios.")
            else:
                dni_existente = any(det.get("dni") == d for det in st.session_state["detalles_pacientes_db"].values())
                if dni_existente:
                    st.error("Ya existe un paciente con ese DNI.")
                else:
                    id_p = f"{n.strip()} - {d.strip()}"
                    st.session_state["pacientes_db"].append(id_p)
                    st.session_state["detalles_pacientes_db"][id_p] = {
                        "dni": d.strip(),
                        "fnac": f_nac.strftime("%d/%m/%Y"),
                        "sexo": se,
                        "telefono": tel.strip(),
                        "direccion": dir_p.strip(),
                        "empresa": emp_d.strip(),
                        "estado": "Activo",
                        "obra_social": o.strip(),
                        "alergias": alergias.strip(),
                        "patologias": patologias.strip(),
                    }
                    guardar_datos()
                    st.success(f"Paciente {n} dado de alta correctamente.")
                    st.rerun()

    st.caption("Los pacientes quedan disponibles en visitas, historia clinica y documentos.")
