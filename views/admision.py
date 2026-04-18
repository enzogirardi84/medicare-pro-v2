from core.alert_toasts import queue_toast
from datetime import date, datetime

import streamlit as st

# Lazy import pandas - solo cargar cuando se necesite mostrar dataframe
_pandas = None
def get_pandas():
    global _pandas
    if _pandas is None:
        import pandas as pd
        _pandas = pd
    return _pandas

pd = get_pandas()

from core.app_logging import log_event
from core.database import guardar_datos
from core.view_helpers import lista_plegable
from core.utils import (
    ahora,
    asegurar_detalles_pacientes_en_sesion,
    empresas_clinica_coinciden,
    es_control_total,
    mapa_detalles_pacientes,
    mostrar_dataframe_con_scroll,
    obtener_pacientes_visibles,
    registrar_auditoria_legal,
    seleccionar_limite_registros,
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
NON_PATIENT_DB_KEYS = {
    "usuarios_db",
    "pacientes_db",
    "detalles_pacientes_db",
    "inventario_db",
    "nomenclador_db",
    "logs_db",
    "reportes_diarios_db",
    "profesionales_red_db",
    "solicitudes_servicios_db",
    "plantillas_whatsapp_db",
}


def _paciente_id(nombre, dni):
    return f"{_texto_unilinea(nombre)} - {_normalizar_dni(dni)}"


def _nombre_legible(paciente_id):
    partes = str(paciente_id or "").rsplit(" - ", 1)
    return partes[0].strip() if partes else ""


def _parsear_fecha_guardada(valor):
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(valor or "").strip(), formato).date()
        except Exception:
            continue
    return date(1990, 1, 1)


def _texto_unilinea(valor):
    return " ".join(str(valor or "").strip().split())


def _normalizar_dni(valor):
    return str(valor or "").strip().replace(".", "").replace(" ", "")


def _normalizar_campos_legajo(nombre, dni, empresa):
    return {
        "nombre": _texto_unilinea(nombre),
        "dni": _normalizar_dni(dni),
        "empresa": _texto_unilinea(empresa),
    }


def _dni_duplicado(dni, excluir_paciente=None):
    dni_limpio = _normalizar_dni(dni)
    for paciente_id, detalles in mapa_detalles_pacientes(st.session_state).items():
        if excluir_paciente and paciente_id == excluir_paciente:
            continue
        if _normalizar_dni(detalles.get("dni", "")) == dni_limpio:
            return True
    return False


def _existe_dni_en_legajos(dni, mi_empresa, rol, excluir_paciente=None):
    dni_norm = _normalizar_dni(dni)
    if not dni_norm:
        return False
    if _dni_duplicado(dni_norm, excluir_paciente=excluir_paciente):
        return True
    try:
        for item in _listar_pacientes_gestion(mi_empresa, rol, busqueda=dni_norm, incluir_altas=True):
            if excluir_paciente and item["id"] == excluir_paciente:
                continue
            if _normalizar_dni(item.get("dni", "")) == dni_norm:
                return True
    except Exception:
        return False
    return False


def _validar_legajo(nombre, dni, empresa, mi_empresa, rol, excluir_paciente=None):
    campos = _normalizar_campos_legajo(nombre, dni, empresa)
    if not campos["nombre"] or not campos["dni"]:
        return campos, "Nombre y DNI son obligatorios."
    if not campos["empresa"]:
        return campos, "La clinica / empresa es obligatoria."
    if _existe_dni_en_legajos(campos["dni"], mi_empresa, rol, excluir_paciente=excluir_paciente):
        return campos, "Ya existe otro paciente con ese DNI."
    return campos, ""


def _buscar_coincidencias_legajo(busqueda, mi_empresa, rol):
    consulta = _texto_unilinea(busqueda)
    if not consulta:
        return []

    coincidencias = {item["id"]: item for item in _listar_pacientes_gestion(mi_empresa, rol, busqueda=consulta, incluir_altas=True)}
    dni_norm = _normalizar_dni(consulta)
    if dni_norm and dni_norm != consulta:
        for item in _listar_pacientes_gestion(mi_empresa, rol, busqueda="", incluir_altas=True):
            if dni_norm and dni_norm in _normalizar_dni(item.get("dni", "")):
                coincidencias[item["id"]] = item
    return list(coincidencias.values())


def _sincronizar_alta_paciente_best_effort(nombre, dni, empresa):
    try:
        from core.nextgen_sync import sync_paciente_to_nextgen

        sync_paciente_to_nextgen(nombre, dni, empresa)
    except Exception as e:
        log_event("admision", f"alta_sync_error:{type(e).__name__}")


def _sincronizar_edicion_paciente_sql_best_effort(detalle_anterior, detalle_nuevo, nombre_nuevo):
    try:
        from core.db_sql import (
            get_empresa_by_nombre,
            get_paciente_by_dni_empresa,
            update_paciente_by_id,
        )

        empresa_origen = _texto_unilinea(detalle_anterior.get("empresa", ""))
        empresa_destino = _texto_unilinea(detalle_nuevo.get("empresa", ""))
        dni_origen = _normalizar_dni(detalle_anterior.get("dni", ""))
        dni_destino = _normalizar_dni(detalle_nuevo.get("dni", ""))

        empresa_sql_origen = get_empresa_by_nombre(empresa_origen) if empresa_origen else None
        empresa_sql_destino = (
            get_empresa_by_nombre(empresa_destino)
            if empresa_destino and empresa_destino != empresa_origen
            else empresa_sql_origen
        )

        paciente_sql = None
        if empresa_sql_origen and dni_origen:
            paciente_sql = get_paciente_by_dni_empresa(empresa_sql_origen.get("id", ""), dni_origen)
        if paciente_sql is None and empresa_sql_destino and dni_destino:
            paciente_sql = get_paciente_by_dni_empresa(empresa_sql_destino.get("id", ""), dni_destino)
        if not paciente_sql:
            return False

        payload = {
            "nombre_completo": nombre_nuevo,
            "dni": dni_destino,
            "estado": detalle_nuevo.get("estado", "Activo"),
        }
        if empresa_sql_destino and empresa_sql_destino.get("id"):
            payload["empresa_id"] = empresa_sql_destino["id"]

        updated = update_paciente_by_id(paciente_sql.get("id", ""), payload)
        return updated is not None
    except Exception as e:
        log_event("admision", f"edit_sync_error:{type(e).__name__}")
        return False


def _sincronizar_eliminacion_paciente_sql_best_effort(detalle_paciente):
    try:
        from core.db_sql import delete_paciente_by_id, get_empresa_by_nombre, get_paciente_by_dni_empresa

        empresa_txt = _texto_unilinea(detalle_paciente.get("empresa", ""))
        dni_txt = _normalizar_dni(detalle_paciente.get("dni", ""))
        empresa_sql = get_empresa_by_nombre(empresa_txt) if empresa_txt else None
        if not empresa_sql or not dni_txt:
            return False
        paciente_sql = get_paciente_by_dni_empresa(empresa_sql.get("id", ""), dni_txt)
        if not paciente_sql:
            return False
        return delete_paciente_by_id(paciente_sql.get("id", ""))
    except Exception as e:
        log_event("admision", f"delete_sync_error:{type(e).__name__}")
        return False


def _iterar_tablas_paciente():
    for clave, registros in st.session_state.items():
        if not clave.endswith("_db") or clave in NON_PATIENT_DB_KEYS or not isinstance(registros, list):
            continue
        yield clave, registros


def _resumen_impacto_paciente(paciente_id):
    resumen = {}
    for clave, registros in _iterar_tablas_paciente():
        cantidad = sum(
            1 for registro in registros if isinstance(registro, dict) and registro.get("paciente") == paciente_id
        )
        if cantidad:
            resumen[clave] = cantidad
    return dict(sorted(resumen.items(), key=lambda item: (-item[1], item[0])))


def _renombrar_referencias_paciente(paciente_anterior, paciente_nuevo):
    total_actualizado = 0
    for _, registros in _iterar_tablas_paciente():
        for registro in registros:
            if isinstance(registro, dict) and registro.get("paciente") == paciente_anterior:
                registro["paciente"] = paciente_nuevo
                total_actualizado += 1

    if st.session_state.get("paciente_actual") == paciente_anterior:
        st.session_state["paciente_actual"] = paciente_nuevo

    for clave in [k for k in st.session_state if k.startswith("lazy_export_")]:
        st.session_state.pop(clave, None)
    return total_actualizado


def _eliminar_referencias_paciente(paciente_id):
    resumen = {}
    for clave, registros in list(_iterar_tablas_paciente()):
        nuevos_registros = []
        eliminados = 0
        for registro in registros:
            if isinstance(registro, dict) and registro.get("paciente") == paciente_id:
                eliminados += 1
                continue
            nuevos_registros.append(registro)
        if eliminados:
            st.session_state[clave] = nuevos_registros
            resumen[clave] = eliminados

    if st.session_state.get("paciente_actual") == paciente_id:
        st.session_state.pop("paciente_actual", None)

    for clave in [k for k in st.session_state if k.startswith("lazy_export_")]:
        st.session_state.pop(clave, None)
    return dict(sorted(resumen.items(), key=lambda item: (-item[1], item[0])))


def _listar_pacientes_gestion(mi_empresa, rol, busqueda="", incluir_altas=False, empresa_filtro=""):
    pacientes = []
    for paciente_id, _, dni, obra_social, estado, empresa in obtener_pacientes_visibles(
        st.session_state,
        mi_empresa,
        rol,
        incluir_altas=incluir_altas,
        busqueda=busqueda,
    ):
        if empresa_filtro and not empresas_clinica_coinciden(empresa, empresa_filtro):
            continue
        detalles = mapa_detalles_pacientes(st.session_state).get(paciente_id, {})
        pacientes.append(
            {
                "id": paciente_id,
                "nombre": _nombre_legible(paciente_id),
                "dni": dni,
                "empresa": empresa,
                "obra_social": obra_social,
                "estado": estado,
                "telefono": detalles.get("telefono", ""),
                "direccion": detalles.get("direccion", ""),
            }
        )
    return pacientes


def _dataframe_pacientes(registros):
    pd = get_pandas()
    filas = []
    for item in registros:
        filas.append(
            {
                "Paciente": item["nombre"],
                "DNI": item["dni"],
                "Clinica": item["empresa"],
                "Obra social": item["obra_social"] or "S/D",
                "Estado": item["estado"],
                "Telefono": item["telefono"] or "S/D",
                "Direccion": item["direccion"] or "S/D",
            }
        )
    return pd.DataFrame(filas)


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

        with st.container(border=True):
            st.markdown("#### Editar legajo seleccionado")
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
                col_e1, col_e2 = st.columns(2)
                nombre_edit = col_e1.text_input("Nombre y apellido *", value=_nombre_legible(paciente_sel_admin))
                obra_edit = col_e2.text_input("Obra social / prepaga", value=detalle_sel.get("obra_social", ""))

                col_e3, col_e4 = st.columns(2)
                dni_edit = col_e3.text_input("DNI del paciente *", value=detalle_sel.get("dni", ""))
                fnac_edit = col_e4.date_input(
                    "Fecha de nacimiento",
                    value=_parsear_fecha_guardada(detalle_sel.get("fnac", "")),
                    min_value=date(1900, 1, 1),
                    max_value=ahora().date(),
                )

                col_e5, col_e6 = st.columns(2)
                sexo_opciones = ["F", "M", "Otro"]
                sexo_actual = detalle_sel.get("sexo", "F")
                if sexo_actual not in sexo_opciones:
                    sexo_opciones.append(sexo_actual)
                sexo_edit = col_e5.selectbox("Sexo", sexo_opciones, index=sexo_opciones.index(sexo_actual))
                estado_edit = col_e6.selectbox("Estado", estados_disponibles, index=estados_disponibles.index(estado_actual))

                col_e7, col_e8 = st.columns(2)
                telefono_edit = col_e7.text_input("WhatsApp / telefono", value=detalle_sel.get("telefono", ""))
                if admin_total:
                    empresa_edit = col_e8.text_input("Empresa / clinica", value=detalle_sel.get("empresa", mi_empresa))
                else:
                    empresa_edit = mi_empresa
                    col_e8.info(f"Clinica fija: {mi_empresa}")

                direccion_edit = st.text_input("Direccion exacta", value=detalle_sel.get("direccion", ""))
                col_e9, col_e10 = st.columns(2)
                alergias_edit = col_e9.text_area("Alergias", value=detalle_sel.get("alergias", ""), height=90)
                patologias_edit = col_e10.text_area(
                    "Patologias previas / riesgos",
                    value=detalle_sel.get("patologias", ""),
                    height=90,
                )

                if st.form_submit_button("Guardar cambios del legajo", use_container_width=True, type="primary"):
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
                        if paciente_nuevo != paciente_sel_admin and paciente_nuevo in mapa_detalles_pacientes(
                            st.session_state
                        ):
                            st.error("Ya existe un legajo con ese nombre y DNI.")
                        else:
                            detalle_anterior = dict(detalle_sel)
                            detalles_actualizados = dict(detalle_sel)
                            detalles_actualizados.update(
                                {
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
                                }
                            )

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
                                    f"Legajo editado desde admision. "
                                    f"Paciente anterior: {paciente_sel_admin}. Registros actualizados: {registros_actualizados}."
                                ),
                                empresa=detalles_actualizados.get("empresa", mi_empresa),
                            )
                            guardar_datos(spinner=True)
                            _sincronizar_edicion_paciente_sql_best_effort(
                                detalle_anterior=detalle_anterior,
                                detalle_nuevo=detalles_actualizados,
                                nombre_nuevo=campos_legajo["nombre"],
                            )
                            queue_toast("Legajo actualizado correctamente.")
                            st.rerun()

        if admin_total:
            with st.container(border=True):
                st.markdown("#### Eliminar paciente y registros asociados")
                st.warning(
                    "Usa esta accion solo si el legajo fue cargado por error. Se borraran tambien los registros clinicos, legales y operativos vinculados."
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
                    use_container_width=True,
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
                    guardar_datos(spinner=True)
                    _sincronizar_eliminacion_paciente_sql_best_effort(detalle_sel)
                    queue_toast("Paciente eliminado correctamente.")
                    st.rerun()
    else:
        st.warning(
            "No aparece ningun paciente en la lista con los filtros actuales. "
            "Proba limpiar la busqueda, marcar **Incluir altas** o, si sos administrador, elegir otra clinica en el filtro. "
            "Cuando haya al menos un legajo visible, vas a ver la tabla, el selector y los botones de editar / eliminar."
        )

    if admin_total:
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
                    st.caption(
                        f"{item['id']} | DNI: {item.get('dni', 'S/D')} | Empresa: {item.get('empresa', 'S/D')}"
                    )
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

            if admin_total:
                emp_d = st.text_input("Empresa / clinica", value=mi_empresa)
            else:
                emp_d = mi_empresa
                st.info(f"Paciente asignado a: {mi_empresa}")

            if st.form_submit_button("Habilitar paciente", use_container_width=True, type="primary"):
                campos_legajo, error_legajo = _validar_legajo(
                    n,
                    d,
                    emp_d,
                    mi_empresa,
                    rol,
                )
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
                            "direccion": _texto_unilinea(dir_p),
                            "empresa": campos_legajo["empresa"],
                            "estado": "Activo",
                            "obra_social": _texto_unilinea(o),
                            "alergias": alergias.strip(),
                            "patologias": patologias.strip(),
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
                        guardar_datos(spinner=True)
                        _sincronizar_alta_paciente_best_effort(
                            campos_legajo["nombre"],
                            campos_legajo["dni"],
                            campos_legajo["empresa"],
                        )
                        queue_toast(f"Paciente {campos_legajo['nombre']} dado de alta correctamente.")
                        st.rerun()

        st.caption("Los pacientes quedan disponibles en visitas, historia clinica y documentos.")
