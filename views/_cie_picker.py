"""Componente reutilizable de seleccion de codigos CIE-10/11."""

import streamlit as st

from core._cie_data import buscar_cie10, obtener_cie10, mapear_a_cie11


def render_cie_picker(key_prefix: str = "cie") -> dict | None:
    """Renderiza un buscador+selector de codigos CIE con resultado estructurado.

    Returns
        dict con {"codigo", "descripcion", "categoria", "cie_version"} o None
    """
    result_key = f"{key_prefix}_resultado"
    if result_key not in st.session_state:
        st.session_state[result_key] = None

    col_b, col_c = st.columns([3, 1])
    with col_b:
        query = st.text_input(
            "Buscar diagnostico (CIE-10)",
            placeholder="Codigo o descripcion... ej: I10, Diabetes, HTA",
            key=f"{key_prefix}_busqueda",
        )
    with col_c:
        cie_version = st.selectbox(
            "Version",
            ["CIE-10", "CIE-11"],
            key=f"{key_prefix}_version",
        )

    if query:
        resultados = buscar_cie10(query)
        if resultados:
            opciones = {f"{r['codigo']} - {r['descripcion']}": r for r in resultados}
            seleccion = st.selectbox(
                "Resultados",
                ["-- Seleccionar --"] + list(opciones.keys()),
                key=f"{key_prefix}_seleccion",
            )
            if seleccion != "-- Seleccionar --":
                entry = opciones[seleccion]
                codigo = entry["codigo"]
                if cie_version == "CIE-11":
                    cie11 = mapear_a_cie11(codigo)
                    if cie11:
                        codigo = cie11
                st.session_state[result_key] = {
                    "codigo": codigo,
                    "descripcion": entry["descripcion"],
                    "categoria": entry["categoria"],
                    "cie_version": cie_version,
                }
            elif st.session_state.get(result_key):
                st.session_state[result_key] = None
        else:
            st.caption("Sin resultados. Use codigo manual si es necesario.")
            codigo_manual = st.text_input(
                "Codigo manual", placeholder="Ej: Z00.0",
                key=f"{key_prefix}_manual",
            )
            if codigo_manual:
                st.session_state[result_key] = {
                    "codigo": codigo_manual.strip().upper(),
                    "descripcion": "Codigo ingresado manualmente",
                    "categoria": "Manual",
                    "cie_version": cie_version,
                }

    resultado = st.session_state.get(result_key)
    if resultado:
        st.success(f"{resultado['codigo']} — {resultado['descripcion']}")
    return resultado


def render_cie_picker_compact(key_prefix: str = "cie_compact") -> dict | None:
    """Version compacta para integrar en formularios existentes (evoluciones, recetas).

    Returns
        dict con {"codigo", "descripcion", "categoria", "cie_version"} o None
    """
    result_key = f"{key_prefix}_result"
    if result_key not in st.session_state:
        st.session_state[result_key] = None

    query = st.text_input(
        "Diagnostico (CIE-10)",
        placeholder="Codigo o nombre...",
        key=f"{key_prefix}_q",
        label_visibility="collapsed",
    )
    if query:
        resultados = buscar_cie10(query)
        if resultados:
            opciones = {f"{r['codigo']} {r['descripcion'][:40]}": r for r in resultados}
            seleccion = st.selectbox(
                "Seleccionar", ["--"] + list(opciones.keys()),
                key=f"{key_prefix}_sel", label_visibility="collapsed",
            )
            if seleccion != "--":
                entry = opciones[seleccion]
                st.session_state[result_key] = {
                    "codigo": entry["codigo"],
                    "descripcion": entry["descripcion"],
                    "categoria": entry["categoria"],
                    "cie_version": "CIE-10",
                }

    resultado = st.session_state.get(result_key)
    if resultado:
        st.caption(f"{resultado['codigo']} — {resultado['descripcion'][:60]}")
        if st.button("Quitar", key=f"{key_prefix}_clear", help="Quitar diagnostico"):
            st.session_state[result_key] = None
            st.rerun()
    return resultado
