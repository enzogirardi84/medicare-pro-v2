"""Secciones UI de admisión. Extraído de views/admision.py."""
from datetime import date

import streamlit as st

from core.alert_toasts import queue_toast
from core.database import guardar_datos
from core.view_helpers import lista_plegable
from core.utils import (
    ahora,
    asegurar_detalles_pacientes_en_sesion,
    mapa_detalles_pacientes,
    mostrar_dataframe_con_scroll,
    registrar_auditoria_legal,
    seleccionar_limite_registros,
)
from views._admision_utils import (
    _buscar_coincidencias_legajo,
    _dataframe_pacientes,
    _eliminar_referencias_paciente,
    _listar_pacientes_gestion,
    _nombre_legible,
    _normalizar_dni,
    _paciente_id,
    _parsear_fecha_guardada,
    _renombrar_referencias_paciente,
    _resumen_impacto_paciente,
    _sincronizar_alta_paciente_best_effort,
    _sincronizar_edicion_paciente_sql_best_effort,
    _sincronizar_eliminacion_paciente_sql_best_effort,
    _texto_unilinea,
    _validar_legajo,
)

DB_LABELS = {
    "vitales_db": "Signos vitales",
    "indicaciones_db": "Recetas e indicaciones",
    "evoluciones_db": "Evoluciones",
    "balance_db": "Balance",
    "pediatria_db": "Pediatria",
    "fotos_heridas_db": "Fotos de heridas",
    "consumos_db": "Materiales",
    "estudios_db": "Estudios",
    "administracion_med_db": "Administracion medicacion",
    "consentimientos_db": "Consentimientos",
    "emergencias_db": "Emergencias",
    "cuidados_enfermeria_db": "Cuidados de enfermeria",
    "escalas_clinicas_db": "Escalas clinicas",
    "auditoria_legal_db": "Auditoria legal",
    "facturacion_db": "Caja y facturacion",
    "firmas_tactiles_db": "Firmas",
    "plantillas_whatsapp_db": "Plantillas WhatsApp",
}


def _render_admision_gestion(mi_empresa, rol, admin_total):
    """Sección: Corregir o eliminar legajo."""
    st.markdown("## Corregir o eliminar legajo")
    st.caption(
        "Esta seccion esta arriba: busca el paciente y edita el legajo. "
        + (
            "Tambien podes eliminar un legajo cargado por error (abajo en esta misma seccion). El alta de pacientes nuevos esta mas abajo."
            if admin_total
            else "Para **dar de alta**, en el formulario de edicion cambia el campo **Estado** a **De Alta** y guarda."
        )
    )

    if admin_total:
        st.info(
            "Corregi un typo en el nombre, el DNI mal cargado, telefono u obra social, o **elimina** el legajo si se creo por error. "
            "Al guardar cambios de nombre/DNI, el sistema actualiza las referencias en agenda, visitas, historia, etc. "
            "Al eliminar, se borra el legajo y los registros vinculados (accion irreversible)."
        )
    else:
        st.info(
            "Con **Guardar cambios del legajo** actualizas datos y el **estado** del paciente. "
            "**De Alta** archiva el legajo en la lista habitual (coordinacion puede volver a mostrarlo con **Incluir altas**)."
        )
    st.markdown("##### Gestion de pacientes por clinica")
    col_f1, col_f2 = st.columns([2.2, 1])
    buscar_gestion = col_f1.text_input(
        "Buscar en legajos cargados",
        placeholder="Nombre, DNI, obra social, clinica o estado",
        key="adm_buscar_gestion",
    )
    incluir_altas = col_f2.checkbox("Incluir altas", key="adm_incluir_altas")

    empresa_filtro = ""
    if admin_total:
        empresas_disponibles = sorted(
            {
                str(det.get("empresa", "") or "").strip()
                for det in mapa_detalles_pacientes(st.session_state).values()
                if str(det.get("empresa", "") or "").strip()
            }
        )
        opciones_empresa = ["Todas las clinicas"] + empresas_disponibles
        empresa_sel = st.selectbox("Filtrar por clinica", opciones_empresa, key="adm_empresa_filtro")
        if empresa_sel != "Todas las clinicas":
            empresa_filtro = empresa_sel

    pacientes_gestion = _listar_pacientes_gestion(
        mi_empresa,
        rol,
        busqueda=buscar_gestion,
        incluir_altas=incluir_altas,
        empresa_filtro=empresa_filtro,
    )

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Pacientes visibles", len(pacientes_gestion))
    col_m2.metric("Activos", sum(1 for item in pacientes_gestion if item["estado"] == "Activo"))
    col_m3.metric("No activos", sum(1 for item in pacientes_gestion if item["estado"] != "Activo"))

    if pacientes_gestion:
        limite = seleccionar_limite_registros(
            "Pacientes a mostrar en la lista",
            len(pacientes_gestion),
            key="adm_limite_pacientes",
            default=30,
            opciones=(10, 20, 30, 50, 100, 200, 500),
        )
        with lista_plegable("Vista tabular de legajos", count=min(limite, len(pacientes_gestion)), expanded=False, height=440):
            mostrar_dataframe_con_scroll(_dataframe_pacientes(pacientes_gestion[:limite]), height=400)

        opciones_pacientes = [item["id"] for item in pacientes_gestion]
        pacientes_gestion_map = {item["id"]: item for item in pacientes_gestion}
        _dm_edicion = mapa_detalles_pacientes(st.session_state)
        _pac_actual = st.session_state.get("paciente_actual")
        _idx_sel = opciones_pacientes.index(_pac_actual) if _pac_actual in opciones_pacientes else 0
        paciente_sel_admin = st.selectbox(
            "Seleccionar paciente para editar o eliminar",
            opciones_pacientes,
            index=_idx_sel,
            format_func=lambda item, dm=_dm_edicion, gm=pacientes_gestion_map: (
                f"{_nombre_legible(item)} | DNI {(dm.get(item) or gm.get(item, {})).get('dni', 'S/D')} | "
                f"{(dm.get(item) or gm.get(item, {})).get('empresa', 'S/D')} | "
                f"{(dm.get(item) or gm.get(item, {})).get('estado', 'Activo')}"
            ),
            key="adm_paciente_edicion",
        )

        detalle_sel = dict(mapa_detalles_pacientes(st.session_state).get(paciente_sel_admin, {}))
        if not detalle_sel and paciente_sel_admin in pacientes_gestion_map:
            item_sel = pacientes_gestion_map[paciente_sel_admin]
            detalle_sel = {
                "dni": item_sel.get("dni", ""),
                "empresa": item_sel.get("empresa", ""),
                "estado": item_sel.get("estado", "Activo"),
                "obra_social": item_sel.get("obra_social", ""),
                "telefono": item_sel.get("telefono", ""),
                "direccion": item_sel.get("direccion", ""),
            }
        impacto_actual = _resumen_impacto_paciente(paciente_sel_admin)
        total_impacto = sum(impacto_actual.values())

        with st.expander("Editar legajo seleccionado", expanded=False):
            if impacto_actual:
                texto_impacto = " | ".join(
                    f"{DB_LABELS.get(clave, clave)}: {cantidad}" for clave, cantidad in list(impacto_actual.items())[:6]
                )
                st.caption(f"Registros vinculados detectados: {total_impacto}. {texto_impacto}")
            else:
                st.caption("Este legajo todavia no tiene registros clinicos vinculados.")

            estado_actual = detalle_sel.get("estado", "Activo") or "Activo"
            estados_disponibles = ["Activo", "De Alta"]
            if estado_actual not in estados_disponibles:
                estados_disponibles.append(estado_actual)

            with st.form("adm_edit_form"):
                with st.expander("Datos personales", expanded=True):
                    col_e1, col_e2, col_e3 = st.columns(3)
                    nombre_edit = col_e1.text_input("Nombre y apellido *", value=_nombre_legible(paciente_sel_admin))
                    dni_edit = col_e2.text_input("DNI del paciente *", value=detalle_sel.get("dni", ""))
                    fnac_edit = col_e3.date_input(
                        "Fecha de nacimiento",
                        value=_parsear_fecha_guardada(detalle_sel.get("fnac", "")),
                        min_value=date(1900, 1, 1),
                        max_value=ahora().date(),
                    )

                    col_e4, col_e5, col_e6 = st.columns(3)
                    sexo_opciones = ["F", "M", "Otro"]
                    sexo_actual = detalle_sel.get("sexo", "F")
                    if sexo_actual not in sexo_opciones:
                        sexo_opciones.append(sexo_actual)
                    sexo_edit = col_e4.selectbox("Sexo", sexo_opciones, index=sexo_opciones.index(sexo_actual))
                    estado_edit = col_e5.selectbox("Estado", estados_disponibles, index=estados_disponibles.index(estado_actual))
                    email_edit = col_e6.text_input("Email", value=detalle_sel.get("email", ""))

                with st.expander("Contacto y direccion", expanded=False):
                    col_e7, col_e8 = st.columns(2)
                    telefono_edit = col_e7.text_input("WhatsApp / telefono", value=detalle_sel.get("telefono", ""))
                    if admin_total:
                        empresa_edit = col_e8.text_input("Empresa / clinica", value=detalle_sel.get("empresa", mi_empresa))
                    else:
                        empresa_edit = mi_empresa
                        col_e8.info(f"Clinica fija: {mi_empresa}")

                    col_e9, col_e10 = st.columns(2)
                    contacto_emergencia_nombre_edit = col_e9.text_input("Contacto de emergencia (nombre)", value=detalle_sel.get("contacto_emergencia_nombre", ""))
                    contacto_emergencia_tel_edit = col_e10.text_input("Contacto de emergencia (telefono)", value=detalle_sel.get("contacto_emergencia_telefono", ""))

                    direccion_edit = st.text_input("Direccion exacta", value=detalle_sel.get("direccion", ""))
                    obra_edit = st.text_input("Obra social / prepaga", value=detalle_sel.get("obra_social", ""))

                with st.expander("Datos de ingreso", expanded=False):
                    col_e11, col_e12, col_e13 = st.columns(3)
                    fecha_ingreso_edit = col_e11.date_input(
                        "Fecha de ingreso",
                        value=_parsear_fecha_guardada(detalle_sel.get("fecha_ingreso", "")),
                        min_value=date(1900, 1, 1),
                        max_value=ahora().date(),
                    )
                    diagnostico_ingreso_edit = col_e12.text_input(
                        "Diagnostico principal de ingreso",
                        value=detalle_sel.get("diagnostico_ingreso", ""),
                    )
                    motivo_ingreso_edit = col_e13.text_input(
                        "Motivo de consulta / ingreso",
                        value=detalle_sel.get("motivo_ingreso", ""),
                    )
                    if estado_edit == "De Alta":
                        fecha_egreso_default = _parsear_fecha_guardada(detalle_sel.get("fecha_egreso", ""))
                        if fecha_egreso_default == date(1990, 1, 1):
                            fecha_egreso_default = ahora().date()
                        fecha_egreso_edit = st.date_input(
                            "Fecha de egreso",
                            value=fecha_egreso_default,
                            min_value=date(1900, 1, 1),
                            max_value=ahora().date(),
                        )
                    else:
                        fecha_egreso_edit = None

                with st.expander("Alertas clinicas", expanded=False):
                    col_e14, col_e15 = st.columns(2)
                    alergias_edit = col_e14.text_area("Alergias", value=detalle_sel.get("alergias", ""), height=90)
                    patologias_edit = col_e15.text_area(
                        "Patologias previas / riesgos",
                        value=detalle_sel.get("patologias", ""),
                        height=90,
                    )

                st.markdown("---")
                if st.form_submit_button("Guardar cambios del legajo", width='stretch', type="primary"):
                    campos_legajo, error_legajo = _validar_legajo(
                        nombre_edit,
                        dni_edit,
                        empresa_edit if admin_total else mi_empresa,
                        mi_empresa,
                        rol,
                        excluir_paciente=paciente_sel_admin,
                    )
                    if error_legajo:
                        st.error(error_legajo)
                    else:
                        paciente_nuevo = _paciente_id(campos_legajo["nombre"], campos_legajo["dni"])
                        if paciente_nuevo != paciente_sel_admin and paciente_nuevo in mapa_detalles_pacientes(st.session_state):
                            st.error("Ya existe un legajo con ese nombre y DNI.")
                        else:
                            detalle_anterior = dict(detalle_sel)
                            detalles_actualizados = dict(detalle_sel)
                            payload = {
                                "dni": campos_legajo["dni"],
                                "fnac": fnac_edit.strftime("%d/%m/%Y"),
                                "sexo": sexo_edit,
                                "telefono": _texto_unilinea(telefono_edit),
                                "direccion": _texto_unilinea(direccion_edit),
                                "empresa": campos_legajo["empresa"],
                                "estado": estado_edit,
                                "obra_social": _texto_unilinea(obra_edit),
                                "alergias": alergias_edit.strip(),
                                "patologias": patologias_edit.strip(),
                                "email": _texto_unilinea(email_edit),
                                "contacto_emergencia_nombre": _texto_unilinea(contacto_emergencia_nombre_edit),
                                "contacto_emergencia_telefono": _texto_unilinea(contacto_emergencia_tel_edit),
                                "fecha_ingreso": fecha_ingreso_edit.strftime("%d/%m/%Y"),
                                "diagnostico_ingreso": _texto_unilinea(diagnostico_ingreso_edit),
                                "motivo_ingreso": _texto_unilinea(motivo_ingreso_edit),
                            }
                            if estado_edit == "De Alta" and fecha_egreso_edit is not None:
                                payload["fecha_egreso"] = fecha_egreso_edit.strftime("%d/%m/%Y")
                            detalles_actualizados.update(payload)

                            pacientes_db = list(st.session_state.get("pacientes_db", []))
                            if paciente_sel_admin in pacientes_db:
                                indice = pacientes_db.index(paciente_sel_admin)
                                pacientes_db[indice] = paciente_nuevo
                            else:
                                pacientes_db.append(paciente_nuevo)
                            st.session_state["pacientes_db"] = list(dict.fromkeys(pacientes_db))

                            _det_mut = asegurar_detalles_pacientes_en_sesion(st.session_state)
                            _det_mut.pop(paciente_sel_admin, None)
                            _det_mut[paciente_nuevo] = detalles_actualizados
                            st.session_state["paciente_actual"] = paciente_nuevo

                            registros_actualizados = 0
                            if paciente_nuevo != paciente_sel_admin:
                                registros_actualizados = _renombrar_referencias_paciente(paciente_sel_admin, paciente_nuevo)

                            registrar_auditoria_legal(
                                "Admision",
                                paciente_nuevo,
                                "Actualizacion de legajo",
                                st.session_state.get("u_actual", {}).get("nombre", "Sistema"),
                                st.session_state.get("u_actual", {}).get("matricula", ""),
                                (
                                    "Legajo editado desde admision. "
                                    f"Paciente anterior: {paciente_sel_admin}. Registros actualizados: {registros_actualizados}."
                                ),
                                empresa=detalles_actualizados.get("empresa", mi_empresa),
                            )
                            st.session_state.pop("_mc_mapa_pacientes_cache", None)
                            guardar_datos(spinner=True)
                            _sincronizar_edicion_paciente_sql_best_effort(
                                detalle_anterior=detalle_anterior,
                                detalle_nuevo=detalles_actualizados,
                                nombre_nuevo=campos_legajo["nombre"],
                            )
                            queue_toast("Legajo actualizado correctamente.")
                            st.rerun()

        with st.expander("Eliminar paciente y registros asociados (solo si el legajo fue cargado por error)", expanded=False):
            if admin_total:
                st.warning(
                    "Accion irreversible. Se borraran tambien los registros clinicos, legales y operativos vinculados."
                )
                if impacto_actual:
                    for clave, cantidad in impacto_actual.items():
                        st.caption(f"{DB_LABELS.get(clave, clave)}: {cantidad} registro(s)")
                else:
                    st.caption("No se detectaron registros clinicos vinculados para este paciente.")

                confirmar_borrado = st.checkbox(
                    f"Confirmo eliminar por completo el legajo de {_nombre_legible(paciente_sel_admin)}",
                    key=f"adm_confirm_delete_{paciente_sel_admin}",
                )
                if st.button(
                    "Eliminar paciente y limpiar historial vinculado",
                    key=f"adm_delete_{paciente_sel_admin}",
                    width='stretch',
                    disabled=not confirmar_borrado,
                    type="primary" if confirmar_borrado else "secondary",
                ):
                    resumen_eliminado = _eliminar_referencias_paciente(paciente_sel_admin)
                    asegurar_detalles_pacientes_en_sesion(st.session_state).pop(paciente_sel_admin, None)
                    st.session_state["pacientes_db"] = [
                        item for item in st.session_state.get("pacientes_db", []) if item != paciente_sel_admin
                    ]
                    detalle_empresa = detalle_sel.get("empresa", mi_empresa)
                    detalle_texto = (
                        " | ".join(f"{DB_LABELS.get(clave, clave)}: {cantidad}" for clave, cantidad in resumen_eliminado.items())
                        if resumen_eliminado
                        else "Paciente eliminado sin registros asociados."
                    )
                    registrar_auditoria_legal(
                        "Admision",
                        paciente_sel_admin,
                        "Eliminacion de legajo",
                        st.session_state.get("u_actual", {}).get("nombre", "Sistema"),
                        st.session_state.get("u_actual", {}).get("matricula", ""),
                        f"Paciente eliminado desde admision. {detalle_texto}",
                        empresa=detalle_empresa,
                    )
                    st.session_state.pop("_mc_mapa_pacientes_cache", None)
                    guardar_datos(spinner=True)
                    _sincronizar_eliminacion_paciente_sql_best_effort(detalle_sel)
                    queue_toast("Paciente eliminado correctamente.")
                    st.rerun()
            else:
                st.info("El borrado total del legajo solo esta disponible para usuarios con permisos de administrador.")

        # ── Historial de admisiones ─────────────────────────────────────
        with st.expander("Historial de admisiones", expanded=False):
            eventos_adm = [r for r in st.session_state.get("auditoria_legal_db", [])
                          if isinstance(r, dict) and r.get("paciente") == paciente_sel_admin
                          and r.get("seccion") == "Admision"]
            if eventos_adm:
                eventos_adm.sort(key=lambda x: str(x.get("fecha_hora", x.get("fecha", ""))), reverse=True)
                for ev in eventos_adm[:20]:
                    fe = str(ev.get("fecha_hora", ev.get("fecha", "")))[:16]
                    usuario = ev.get("usuario", ev.get("profesional", "Sistema"))
                    accion = ev.get("accion", "S/D")
                    detalle = ev.get("detalle", "")
                    st.markdown(f"- **{fe}** — *{usuario}* — {accion}")
                    if detalle:
                        st.caption(detalle[:200])
            else:
                st.caption("Sin eventos de admision registrados para este paciente.")
    else:
        st.warning(
            "No aparece ningun paciente en la lista con los filtros actuales. "
            "Proba limpiar la busqueda, marcar **Incluir altas** o, si sos administrador, elegir otra clinica en el filtro. "
            "Cuando haya al menos un legajo visible, vas a ver la tabla, el selector y los botones de editar / eliminar."
        )


def _render_admision_alta(mi_empresa, rol, admin_total):
    """Sección: Alta de paciente nuevo."""
    st.divider()
    st.markdown("## Alta de paciente nuevo")
    st.markdown("##### Antes de dar el alta: buscar si ya existe")
    buscar_adm = st.text_input("Nombre, DNI o apellido", placeholder="Ej: Juan Perez o 35123456", key="adm_buscar_duplicado")

    if buscar_adm:
        coincidencias = _buscar_coincidencias_legajo(buscar_adm, mi_empresa, rol)
        if coincidencias:
            st.warning(
                f"Se encontraron {len(coincidencias)} pacientes similares. Si es el mismo caso, no cargues de nuevo: "
                "subi a la seccion **Corregir o eliminar legajo** (arriba en esta misma pagina)."
            )
            for item in coincidencias[:5]:
                st.caption(f"{item['id']} | DNI: {item.get('dni', 'S/D')} | Empresa: {item.get('empresa', 'S/D')}")
        else:
            st.success("No hay pacientes con ese nombre o DNI. Podes continuar con el alta.")

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

    dni_preview = st.session_state.get("_adm_dni_preview", "").strip()
    dni_norm_preview = _normalizar_dni(dni_preview)
    if dni_norm_preview:
        _dup_preview = None
        for pid, det in mapa_detalles_pacientes(st.session_state).items():
            if _normalizar_dni(det.get("dni", "")) == dni_norm_preview:
                _dup_preview = (pid, det)
                break
        if _dup_preview:
            pid_dup, det_dup = _dup_preview
            st.error(
                f"⚠️ **DNI ya registrado**: {_nombre_legible(pid_dup)} — "
                f"Empresa: {det_dup.get('empresa', 'S/D')} — "
                f"Estado: {det_dup.get('estado', 'Activo')} — "
                f"Obra social: {det_dup.get('obra_social', 'S/D')}"
            )

    with st.form("adm_form", clear_on_submit=True):
        with st.expander("Datos personales", expanded=True):
            col_a, col_b, col_c = st.columns(3)
            n = col_a.text_input("Nombre y apellido *", placeholder="Juan Perez")
            d = col_b.text_input("DNI del paciente *", placeholder="35123456", key="_adm_dni_preview")
            f_nac = col_c.date_input(
                "Fecha de nacimiento",
                value=date(1990, 1, 1),
                min_value=date(1900, 1, 1),
                max_value=ahora().date(),
            )

            col_d, col_e, col_f = st.columns(3)
            se = col_d.selectbox("Sexo", ["F", "M", "Otro"])
            o = col_e.text_input("Obra social / prepaga", placeholder="OSDE / PAMI / Particular")
            email_alta = col_f.text_input("Email", placeholder="paciente@correo.com")

        with st.expander("Contacto y direccion", expanded=False):
            col_g, col_h = st.columns(2)
            tel = col_g.text_input("WhatsApp / telefono", placeholder="3584302024")
            contacto_emergencia_nombre = col_h.text_input("Contacto de emergencia (nombre)", placeholder="Familiar a cargo")

            col_i, col_j = st.columns(2)
            contacto_emergencia_tel = col_i.text_input("Contacto de emergencia (telefono)", placeholder="3584302024")
            dir_p = col_j.text_input("Direccion exacta", placeholder="Calle 123, barrio, ciudad")

        with st.expander("Datos de ingreso", expanded=False):
            col_k, col_l, col_m = st.columns(3)
            fecha_ingreso_alta = col_k.date_input(
                "Fecha de ingreso",
                value=ahora().date(),
                min_value=date(1900, 1, 1),
                max_value=ahora().date(),
            )
            diagnostico_ingreso = col_l.text_input(
                "Diagnostico principal de ingreso",
                placeholder="Ej: Neumonia, Fractura de cadera, ACV isquemico...",
                key="_adm_diag_ingreso",
            )
            motivo_ingreso = col_m.text_input(
                "Motivo de consulta / ingreso",
                placeholder="Ej: Disnea, dolor abdominal, trauma...",
                key="_adm_motivo_ingreso",
            )

        with st.expander("Alertas clinicas", expanded=False):
            col_n, col_o = st.columns(2)
            alergias = col_n.text_area("Alergias", placeholder="Ej: penicilina, ibuprofeno...", height=90)
            patologias = col_o.text_area("Patologias previas / riesgos", placeholder="Ej: DBT, HTA, marcapasos...", height=90)

        if admin_total:
            emp_d = st.text_input("Empresa / clinica", value=mi_empresa)
        else:
            emp_d = mi_empresa
            st.info(f"Paciente asignado a: {mi_empresa}")

        _faltantes = []
        if not n.strip():
            _faltantes.append("Nombre y apellido")
        if not d.strip():
            _faltantes.append("DNI")
        if _faltantes:
            st.warning(f"Campos obligatorios sin completar: {', '.join(_faltantes)}")

        if st.form_submit_button("Habilitar paciente", width='stretch', type="primary"):
            campos_legajo, error_legajo = _validar_legajo(n, d, emp_d, mi_empresa, rol)
            if error_legajo:
                st.error(error_legajo)
            else:
                id_p = _paciente_id(campos_legajo["nombre"], campos_legajo["dni"])
                if id_p in mapa_detalles_pacientes(st.session_state):
                    st.error("Ya existe un legajo con ese nombre y DNI.")
                else:
                    pacientes_db = list(st.session_state.get("pacientes_db", []))
                    pacientes_db.append(id_p)
                    st.session_state["pacientes_db"] = list(dict.fromkeys(pacientes_db))
                    asegurar_detalles_pacientes_en_sesion(st.session_state)[id_p] = {
                        "dni": campos_legajo["dni"],
                        "fnac": f_nac.strftime("%d/%m/%Y"),
                        "sexo": se,
                        "telefono": _texto_unilinea(tel),
                        "email": _texto_unilinea(email_alta),
                        "contacto_emergencia_nombre": _texto_unilinea(contacto_emergencia_nombre),
                        "contacto_emergencia_telefono": _texto_unilinea(contacto_emergencia_tel),
                        "direccion": _texto_unilinea(dir_p),
                        "empresa": campos_legajo["empresa"],
                        "estado": "Activo",
                        "obra_social": _texto_unilinea(o),
                        "alergias": alergias.strip(),
                        "patologias": patologias.strip(),
                        "diagnostico_ingreso": diagnostico_ingreso.strip(),
                        "motivo_ingreso": motivo_ingreso.strip(),
                        "fecha_ingreso": fecha_ingreso_alta.strftime("%d/%m/%Y"),
                    }
                    st.session_state["paciente_actual"] = id_p
                    registrar_auditoria_legal(
                        "Admision",
                        id_p,
                        "Alta de paciente",
                        st.session_state.get("u_actual", {}).get("nombre", "Sistema"),
                        st.session_state.get("u_actual", {}).get("matricula", ""),
                        "Alta inicial del legajo del paciente.",
                        empresa=campos_legajo["empresa"],
                    )
                    st.session_state.pop("_mc_mapa_pacientes_cache", None)
                    guardar_datos(spinner=True)
                    _sincronizar_alta_paciente_best_effort(
                        campos_legajo["nombre"],
                        campos_legajo["dni"],
                        campos_legajo["empresa"],
                    )
                    queue_toast(f"Paciente {campos_legajo['nombre']} dado de alta correctamente.")
                    st.rerun()

    st.caption("Los pacientes quedan disponibles en visitas, historia clinica y documentos.")
