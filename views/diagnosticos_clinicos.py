"""Gestion de diagnosticos clinicos con codificacion CIE-10/11."""

from datetime import datetime

import streamlit as st

from core.alert_toasts import queue_toast
from core._cie_data import CIE10_CATALOGO, CATEGORIAS, buscar_cie10, mapear_a_cie11
from core.utils import ahora
from views._cie_picker import render_cie_picker, render_cie_picker_compact


def render_diagnosticos_clinicos(paciente_sel, mi_empresa, user, rol):
    """Vista principal de gestion de diagnosticos clinicos con CIE-10/11."""
    st.markdown("### Codificacion CIE-10/11")
    st.caption("Diagnosticos clinicos con codificacion estandar internacional")

    if not paciente_sel:
        st.info("Seleccione un paciente para gestionar sus diagnosticos.")
        return

    paciente_id = paciente_sel.split(" - ")[-1] if " - " in paciente_sel else paciente_sel

    tab_nuevo, tab_lista, tab_catalogo = st.tabs([
        "Nuevo diagnostico", "Diagnosticos activos", "Catalogo CIE-10",
    ])

    with tab_nuevo:
        st.markdown("#### Registrar nuevo diagnostico")
        with st.form("nuevo_diag", clear_on_submit=True):
            cie_result = render_cie_picker("nuevo_diag")
            tipo_dx = st.selectbox(
                "Tipo",
                ["Principal", "Secundario", "Comorbilidad", "Antecedente", "Complicacion"],
            )
            estado_dx = st.selectbox(
                "Estado",
                ["Activo", "Confirmado", "Sospecha", "Descartado", "Resuelto"],
            )
            notas = st.text_area("Notas clinicas", height=80, placeholder="Contexto del diagnostico...")
            submitted = st.form_submit_button("Guardar diagnostico", type="primary", width="stretch")

            if submitted:
                if not cie_result:
                    st.error("Debe seleccionar o ingresar un codigo CIE.")
                else:
                    datos_sql = {
                        "paciente_id": paciente_id,
                        "cie_codigo": cie_result["codigo"],
                        "cie_version": cie_result["cie_version"],
                        "descripcion": cie_result["descripcion"],
                        "tipo_diagnostico": tipo_dx,
                        "estado": estado_dx,
                        "notas": notas,
                        "profesional": user.get("nombre", ""),
                        "fecha_diagnostico": ahora().isoformat(),
                    }
                    if "diagnosticos_db" not in st.session_state:
                        st.session_state["diagnosticos_db"] = []
                    st.session_state["diagnosticos_db"].append({
                        **datos_sql,
                        "paciente": paciente_sel,
                        "id_unico": f"diag_{len(st.session_state['diagnosticos_db'])}",
                    })
                    try:
                        from core.db_sql import insert_diagnostico
                        sql_res = insert_diagnostico(datos_sql)
                        if sql_res:
                            st.session_state["diagnosticos_db"][-1]["id_sql"] = sql_res.get("id")
                    except Exception:
                        pass
                    queue_toast("Diagnostico registrado.")
                    st.rerun()

    with tab_lista:
        diagnosticos = [
            d for d in st.session_state.get("diagnosticos_db", [])
            if d.get("paciente") == paciente_sel
        ]
        try:
            from core.db_sql import get_diagnosticos_by_paciente
            sql_dxs = get_diagnosticos_by_paciente(paciente_id)
            seen_ids = {d.get("id_sql") for d in diagnosticos if d.get("id_sql")}
            for sd in sql_dxs:
                if sd.get("id") not in seen_ids:
                    diagnosticos.append({
                        "paciente": paciente_sel,
                        "cie_codigo": sd.get("cie_codigo", ""),
                        "cie_version": sd.get("cie_version", "CIE-10"),
                        "descripcion": sd.get("descripcion", ""),
                        "tipo_diagnostico": sd.get("tipo_diagnostico", "Principal"),
                        "estado": sd.get("estado", "Activo"),
                        "notas": sd.get("notas", ""),
                        "profesional": sd.get("profesional", ""),
                        "fecha_diagnostico": sd.get("fecha_diagnostico", ""),
                        "id_sql": sd.get("id"),
                        "id_unico": f"sql_{sd.get('id', '')}",
                    })
        except Exception:
            pass

        if not diagnosticos:
            st.info("No hay diagnosticos registrados para este paciente.")
        else:
            activos = [d for d in diagnosticos if d.get("estado") in ("Activo", "Confirmado", "Sospecha")]
            resueltos = [d for d in diagnosticos if d.get("estado") == "Resuelto"]

            st.markdown(f"**{len(activos)} activos** | {len(resueltos)} resueltos | {len(diagnosticos)} totales")

            for dx in activos:
                with st.container(border=True):
                    cols = st.columns([1, 3, 1, 1])
                    cols[0].markdown(f"**{dx.get('cie_codigo', '')}**")
                    cols[1].markdown(f"_{dx.get('descripcion', '')}_")
                    cols[2].markdown(f"`{dx.get('tipo_diagnostico', '')}`")
                    cols[3].markdown(f"`{dx.get('estado', '')}`")
                    with st.expander("Ver detalle"):
                        st.caption(f"Version: {dx.get('cie_version', 'CIE-10')}")
                        st.caption(f"Profesional: {dx.get('profesional', '')}")
                        st.caption(f"Fecha: {str(dx.get('fecha_diagnostico', ''))[:16]}")
                        if dx.get("notas"):
                            st.text(dx["notas"])
                        col_a, col_b = st.columns(2)
                        if col_a.button("Marcar resuelto", key=f"res_{dx['id_unico']}"):
                            dx["estado"] = "Resuelto"
                            dx["fecha_resolucion"] = ahora().isoformat()
                            if dx.get("id_sql"):
                                try:
                                    from core.db_sql import update_diagnostico
                                    update_diagnostico(dx["id_sql"], {"estado": "Resuelto"})
                                except Exception:
                                    pass
                            queue_toast("Diagnostico marcado como resuelto.")
                            st.rerun()
                        if col_b.button("Eliminar", key=f"del_{dx['id_unico']}"):
                            if dx.get("id_sql"):
                                try:
                                    from core.db_sql import delete_diagnostico
                                    delete_diagnostico(dx["id_sql"])
                                except Exception:
                                    pass
                            st.session_state["diagnosticos_db"] = [
                                d for d in st.session_state["diagnosticos_db"]
                                if d.get("id_unico") != dx["id_unico"]
                            ]
                            queue_toast("Diagnostico eliminado.")
                            st.rerun()

            if resueltos:
                with st.expander(f"Historial de diagnosticos resueltos ({len(resueltos)})"):
                    for dx in resueltos:
                        st.markdown(f"- **{dx.get('cie_codigo', '')}** {dx.get('descripcion', '')} ({dx.get('tipo_diagnostico', '')})")

    with tab_catalogo:
        st.markdown("### Catalogo CIE-10 de referencia")
        cat_sel = st.selectbox("Filtrar por categoria", ["Todas"] + CATEGORIAS)
        busq = st.text_input("Buscar en catalogo", placeholder="Codigo o descripcion...")
        mostrar = CIE10_CATALOGO
        if cat_sel != "Todas":
            mostrar = [e for e in mostrar if e["categoria"] == cat_sel]
        if busq:
            q = busq.lower()
            mostrar = [e for e in mostrar if q in e["codigo"].lower() or q in e["descripcion"].lower()]
        st.caption(f"{len(mostrar)} codigos")
        for e in mostrar[:50]:
            cie11 = mapear_a_cie11(e["codigo"])
            extra = f" → CIE-11: {cie11}" if cie11 else ""
            st.caption(f"**{e['codigo']}** {e['descripcion']} ({e['categoria']}){extra}")
        if len(mostrar) > 50:
            st.caption(f"... y {len(mostrar) - 50} mas (refine la busqueda)")
