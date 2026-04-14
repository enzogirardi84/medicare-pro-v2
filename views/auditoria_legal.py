import pandas as pd
import streamlit as st

from core.export_utils import dataframe_csv_bytes, sanitize_filename_component
from core.view_helpers import bloque_mc_grid_tarjetas, lista_plegable
from core.utils import mostrar_dataframe_con_scroll, seleccionar_limite_registros


def _texto_filtro_registro(reg):
    piezas = [
        str(reg.get("paciente", "") or ""),
        str(reg.get("accion", "") or ""),
        str(reg.get("actor", "") or ""),
        str(reg.get("detalle", "") or ""),
        str(reg.get("referencia", "") or ""),
        str(reg.get("modulo", "") or ""),
        str(reg.get("criticidad", "") or ""),
    ]
    return " | ".join(piezas).lower()


def _clave_orden_desc(reg):
    iso = str(reg.get("fecha_iso", "") or "").strip()
    if iso:
        return iso
    fecha = str(reg.get("fecha", "") or "").strip()
    return fecha


def render_auditoria_legal(mi_empresa, user):
    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Auditoria legal central</h2>
            <p class="mc-hero-text">Concentra eventos clinicos y documentales con valor legal: medicacion, consentimientos, emergencias, escalas y cuidados.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Trazabilidad</span>
                <span class="mc-chip">Actor y matricula</span>
                <span class="mc-chip">Paciente</span>
                <span class="mc-chip">Fecha y hora</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ("Eventos", "Altas sensibles: equipo, medicacion, consentimientos, emergencias, clinicas."),
            ("Filtros", "Texto libre y paciente para acotar antes de exportar."),
            ("CSV", "Descarga completa del conjunto filtrado."),
        ]
    )
    st.caption(
        "Los registros se generan al usar modulos con auditoria (Recetas, Evolucion, Equipo, Clinicas, etc.). Ajusta el limite de filas si la lista es larga."
    )

    registros = list(st.session_state.get("auditoria_legal_db", []) or [])
    if not registros:
        st.warning(
            "Todavia no hay eventos en la auditoria legal. Apareceran cuando el equipo registre acciones auditadas (evoluciones, recetas, usuarios, suspension de clinicas, etc.)."
        )
        return

    filtro = st.text_input("Buscar por paciente, accion, actor o detalle")
    pacientes = sorted({str(r.get("paciente", "") or "").strip() for r in registros if str(r.get("paciente", "") or "").strip()})
    paciente_sel = st.selectbox("Paciente", ["Todos"] + pacientes)
    if paciente_sel != "Todos":
        registros = [r for r in registros if str(r.get("paciente", "") or "").strip() == paciente_sel]

    if filtro:
        f_low = str(filtro).strip().lower()
        registros = [r for r in registros if f_low in _texto_filtro_registro(r)]
        if not registros:
            st.warning("No hay coincidencias con la busqueda. Proba otro texto o limpia el filtro.")
            return

    if not registros:
        st.info("No hay eventos para el filtro seleccionado.")
        return

    registros = sorted(registros, key=_clave_orden_desc, reverse=True)
    total_filtrado = len(registros)

    limite = seleccionar_limite_registros(
        "Eventos por página",
        total_filtrado,
        key=f"auditoria_legal_{mi_empresa}_{user.get('nombre', '')}",
        default=50,
    )
    paginas = max((total_filtrado - 1) // max(limite, 1) + 1, 1)
    pagina = st.number_input("Página", min_value=1, max_value=paginas, value=1, step=1)
    inicio = (int(pagina) - 1) * limite
    fin = inicio + limite
    pagina_regs = registros[inicio:fin]
    st.caption(f"Mostrando {len(pagina_regs)} de {total_filtrado} evento(s) filtrado(s).")

    df_page = pd.DataFrame(pagina_regs)
    with lista_plegable("Eventos de auditoría legal", count=len(df_page), expanded=False, height=500):
        mostrar_dataframe_con_scroll(df_page, height=440)

    filtro_key = f"{paciente_sel}|{str(filtro or '').strip().lower()}|{total_filtrado}"
    cache_key = f"_csv_aud_legal_{sanitize_filename_component(mi_empresa, 'empresa')}_{user.get('nombre', '')}_{filtro_key}"
    if st.button("Preparar CSV auditoría legal", use_container_width=True):
        st.session_state[cache_key] = dataframe_csv_bytes(pd.DataFrame(registros))
    if st.session_state.get(cache_key):
        st.download_button(
            "Descargar CSV auditoria legal",
            data=st.session_state[cache_key],
            file_name=f"auditoria_legal_{sanitize_filename_component(mi_empresa, 'empresa')}.csv",
            mime="text/csv",
            use_container_width=True,
        )
