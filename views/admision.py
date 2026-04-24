from datetime import date, datetime

import streamlit as st

from core.utils import es_control_total
from views._admision_utils import (
    NON_PATIENT_DB_KEYS,
    _existe_dni_en_legajos as _existe_dni_en_legajos_impl,
    _listar_pacientes_gestion as _listar_pacientes_gestion_impl,
    _normalizar_campos_legajo,
    _normalizar_dni as _normalizar_dni_impl,
    _paciente_id as _paciente_id_impl,
    _texto_unilinea,
)
from views._admision_secciones import (
    DB_LABELS,
    _render_admision_alta,
    _render_admision_gestion,
)


def _normalizar_dni(valor):
    return _normalizar_dni_impl(valor)


def _paciente_id(nombre, dni):
    return _paciente_id_impl(nombre, dni)


def _listar_pacientes_gestion(mi_empresa, rol, busqueda="", incluir_altas=False, empresa_filtro=""):
    return _listar_pacientes_gestion_impl(
        mi_empresa,
        rol,
        busqueda=busqueda,
        incluir_altas=incluir_altas,
        empresa_filtro=empresa_filtro,
    )


def _existe_dni_en_legajos(dni, mi_empresa, rol, excluir_paciente=None):
    return _existe_dni_en_legajos_impl(
        dni,
        mi_empresa,
        rol,
        excluir_paciente=excluir_paciente,
    )


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
    coincidencias = {
        item["id"]: item
        for item in _listar_pacientes_gestion(
            mi_empresa,
            rol,
            busqueda=consulta,
            incluir_altas=True,
        )
    }
    dni_norm = _normalizar_dni(consulta)
    if dni_norm and dni_norm != consulta:
        for item in _listar_pacientes_gestion(mi_empresa, rol, busqueda="", incluir_altas=True):
            if dni_norm and dni_norm in _normalizar_dni(item.get("dni", "")):
                coincidencias[item["id"]] = item
    return list(coincidencias.values())


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
