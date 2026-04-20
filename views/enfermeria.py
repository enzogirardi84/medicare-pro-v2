import streamlit as st

from core.utils import mapa_detalles_pacientes
from core.view_helpers import aviso_sin_paciente
from views._enfermeria_plan import (
    _render_plan_cuidados_enfermeria_legacy,
    cargar_registros_enfermeria,
)


def render_enfermeria(paciente_sel, mi_empresa, user, *, compact=False):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    registros = cargar_registros_enfermeria(paciente_sel, mi_empresa)
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
