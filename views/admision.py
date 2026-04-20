from datetime import date, datetime

import streamlit as st

from core.utils import es_control_total
from views._admision_utils import NON_PATIENT_DB_KEYS
from views._admision_secciones import (
    DB_LABELS,
    _render_admision_gestion,
    _render_admision_alta,
)



def render_admision(mi_empresa, rol):
    admin_total = es_control_total(rol)

    if admin_total:
        hero_html = """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Admision de pacientes</h2>
            <p class="mc-hero-text">Correccion y borrado del legajo; mas abajo, alta de pacientes nuevos. Para <strong>dar de alta</strong> (archivar fin de atencion), elegi el paciente y en el formulario cambia <strong>Estado</strong> a <strong>De Alta</strong>.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Corregir legajo</span>
                <span class="mc-chip">Eliminar si hubo error</span>
                <span class="mc-chip">Alta nueva</span>
            </div>
        </div>
        """
    else:
        hero_html = """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Legajo y alta de paciente</h2>
            <p class="mc-hero-text">Busca el paciente, abri <strong>Editar legajo</strong> y en <strong>Estado</strong> elegi <strong>De Alta</strong> cuando termine la atencion. El alta de pacientes nuevos y el borrado total del legajo los gestiona coordinacion o recepcion.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Estado De Alta</span>
                <span class="mc-chip">Corregir datos</span>
            </div>
        </div>
        """
    st.markdown(hero_html, unsafe_allow_html=True)

    _render_admision_gestion(mi_empresa, rol, admin_total)
    if admin_total:
        _render_admision_alta(mi_empresa, rol, admin_total)
