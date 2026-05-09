"""Módulo APS / Dispensario para MediCare Enterprise PRO.

Ventana general de Atención Primaria de la Salud:
- Panel diario con métricas y sala de espera
- Gestión de pacientes y núcleo familiar
- Turnos flexibles y demanda espontánea
- Atención APS
- Control Niño Sano y Embarazo
- Farmacia, leche e insumos
- Trabajo Social
- Epidemiología
- Visitas domiciliarias
- Reportes
"""

from datetime import date, datetime, timedelta

import streamlit as st

from core.database import guardar_json_db
from core.view_helpers import aviso_sin_paciente
from core.utils import puede_accion, cargar_json_asset
from core.export_utils import pdf_output_bytes, safe_text, sanitize_filename_component

FPDF_DISPONIBLE = False
try:
    from fpdf import FPDF
    FPDF_DISPONIBLE = True
except ImportError:
    pass


def _get_paciente_id_visual(paciente_sel):
    """Devuelve un ID limpio para guardar en la base de datos."""
    return str(paciente_sel or "").strip()


def _input_paciente_volatil(paciente_sel, key_prefix="aps_vol"):
    """Si hay paciente_sel, lo retorna. Si no, muestra inputs para paciente volátil."""
    if paciente_sel:
        st.success(f"Paciente seleccionado: **{paciente_sel}**")
        return _get_paciente_id_visual(paciente_sel), None

    st.info("No hay paciente seleccionado. Completá los datos del paciente voluntario:")
    col1, col2, col3 = st.columns(3)
    with col1:
        apellido = st.text_input("Apellido", key=f"{key_prefix}_apellido")
    with col2:
        nombre = st.text_input("Nombre", key=f"{key_prefix}_nombre")
    with col3:
        dni = st.text_input("DNI", key=f"{key_prefix}_dni")

    parts = [p for p in [apellido, nombre] if p and p.strip()]
    paciente_id = f"{' '.join(parts)} - {dni}".strip() if (parts or (dni and dni.strip())) else ""
    paciente_data = {"apellido": apellido, "nombre": nombre, "dni": dni}
    return paciente_id, paciente_data


def _header_paciente(paciente_sel, user):
    """Muestra la cabecera del paciente seleccionado."""
    from core.utils import mapa_detalles_pacientes

    detalles = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})
    dni = detalles.get("dni", "S/D")
    empresa = detalles.get("empresa", "S/D")
    estado = detalles.get("estado", "Activo")

    with st.container(border=True):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Paciente", paciente_sel or "-")
        col2.metric("DNI", dni)
        col3.metric("Empresa / Barrio", empresa)
        col4.metric("Estado", estado)


def _guardar_con_feedback(clave_db, payload, max_items=500):
    """Wrapper con try/except y feedback visual para escenarios de baja conectividad."""
    try:
        guardar_json_db(clave_db, payload, spinner=True, max_items=max_items)
        st.toast("Guardado correctamente", icon="✅")
        return True
    except Exception as e:
        st.error(f"Error al guardar: {e}")
        st.toast("Falló la conexión. Se guardará localmente.", icon="⚠️")
        return False


def _guardar_directo():
    """Fuerza guardado de session_state actual SIN agregar payload nuevo. Útil para actualizaciones in-place."""
    from core.database import guardar_datos
    try:
        guardar_datos(spinner=True)
        st.toast("Guardado correctamente", icon="✅")
        return True
    except Exception as e:
        st.error(f"Error al guardar: {e}")
        st.toast("Falló la conexión. Se guardará localmente.", icon="⚠️")
        return False


def _buscar_pacientes_por_texto(texto):
    """Búsqueda en tiempo real por nombre o DNI sobre pacientes_db global."""
    texto = str(texto or "").strip().lower()
    if not texto:
        return []
    pacientes = st.session_state.get("pacientes_db", [])
    resultados = []
    for p in pacientes:
        if not isinstance(p, dict):
            continue
        nombre = str(p.get("nombre", "")).lower()
        dni = str(p.get("dni", "")).lower()
        if texto in nombre or texto in dni:
            resultados.append(p)
    return resultados


def _calcular_edad(fecha_nacimiento_str):
    """Calcula edad en años desde string ISO o fecha."""
    try:
        if isinstance(fecha_nacimiento_str, str) and fecha_nacimiento_str:
            fn = datetime.fromisoformat(fecha_nacimiento_str.replace("Z", "+00:00")).date()
        elif isinstance(fecha_nacimiento_str, date):
            fn = fecha_nacimiento_str
        else:
            return None
        hoy = date.today()
        return hoy.year - fn.year - ((hoy.month, hoy.day) < (fn.month, fn.day))
    except Exception:
        return None


def _ya_entrego_mes(paciente_id, tipo_entrega, entregas_db):
    """Devuelve True si ya hubo una entrega de este tipo en el mes corriente."""
    hoy = date.today()
    inicio_mes = hoy.replace(day=1)
    for e in entregas_db:
        if not isinstance(e, dict):
            continue
        if e.get("paciente_id") != paciente_id:
            continue
        if e.get("tipo_entrega") != tipo_entrega:
            continue
        try:
            fecha = datetime.fromisoformat(str(e.get("fecha_entrega", ""))[:10]).date()
            if inicio_mes <= fecha <= hoy:
                return True
        except Exception:
            continue
    return False


def _calcular_edad_gestacional(fum_str):
    """Calcula edad gestacional en semanas desde FUM."""
    try:
        fum = datetime.fromisoformat(str(fum_str)).date()
        hoy = date.today()
        dias = (hoy - fum).days
        semanas = dias // 7
        return max(0, semanas)
    except Exception:
        return None


def _paciente_info_para_selector(p):
    """Formatea un paciente para mostrar en selectores."""
    nombre = p.get("nombre", "S/N")
    dni = p.get("dni", "S/D")
    return f"{nombre} — DNI {dni}"


def _metricas_aps_del_dia():
    """Métricas rápidas basadas en datos de hoy en session_state."""
    hoy_iso = date.today().isoformat()

    atenciones = st.session_state.get("atenciones_aps_db", [])
    entregas = st.session_state.get("entregas_aps_db", [])
    epi = st.session_state.get("epidemiologia_aps_db", [])
    visitas = st.session_state.get("visitas_domiciliarias_aps_db", [])

    pacientes_hoy = set()
    medicacion_hoy = 0
    alertas_epi = 0
    visitas_pend = 0

    for a in atenciones:
        if not isinstance(a, dict):
            continue
        if str(a.get("fecha_atencion", ""))[:10] == hoy_iso:
            pacientes_hoy.add(a.get("paciente_id"))

    for e in entregas:
        if not isinstance(e, dict):
            continue
        if str(e.get("fecha_entrega", ""))[:10] == hoy_iso:
            medicacion_hoy += 1

    for ep in epi:
        if not isinstance(ep, dict):
            continue
        if ep.get("estado") in ("Pendiente", "En seguimiento"):
            alertas_epi += 1
        if ep.get("requiere_visita") and ep.get("estado") == "Pendiente":
            visitas_pend += 1

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Pacientes atendidos hoy", len(pacientes_hoy))
    col2.metric("Medicación entregada hoy", medicacion_hoy)
    col3.metric("Alertas epidemiológicas", alertas_epi)
    col4.metric("Visitas domic. pendientes", visitas_pend)


_APS_SECCIONES = {
    "Panel Diario": {
        "descripcion": "Sala de espera, actividad del dia y alertas activas.",
        "requiere_paciente": False,
        "render": "_tab_panel_diario",
    },
    "Pacientes y Familia": {
        "descripcion": "Busqueda, alta territorial y nucleo familiar.",
        "requiere_paciente": False,
        "render": "_tab_pacientes_familia",
    },
    "Ficha APS": {
        "descripcion": "Equipo referente, riesgo general y programas asignados.",
        "requiere_paciente": True,
        "render": "_tab_ficha_aps",
    },
    "Turnos y Sala de Espera": {
        "descripcion": "Demanda espontanea, agenda y estado de espera.",
        "requiere_paciente": False,
        "render": "_tab_turnos",
    },
    "Historial APS": {
        "descripcion": "Movimientos del paciente dentro del centro de salud.",
        "requiere_paciente": False,
        "render": "_tab_historial_aps",
    },
    "Atencion APS": {
        "descripcion": "Consulta, signos, diagnostico e indicaciones.",
        "requiere_paciente": False,
        "render": "_tab_nueva_atencion",
    },
    "Nino Sano / Embarazo": {
        "descripcion": "Controles pediatricos y obstetricos.",
        "requiere_paciente": False,
        "render": "_tab_control_nino_embarazo",
    },
    "Farmacia y Leche": {
        "descripcion": "Entregas, cuota mensual y plan materno infantil.",
        "requiere_paciente": False,
        "render": "_tab_farmacia",
    },
    "Trabajo Social": {
        "descripcion": "Condiciones de vivienda, cobertura y riesgo social.",
        "requiere_paciente": False,
        "render": "_tab_trabajo_social",
    },
    "Epidemiologia": {
        "descripcion": "Eventos de seguimiento, notificacion y visitas requeridas.",
        "requiere_paciente": False,
        "render": "_tab_epidemiologia",
    },
    "Visitas Domiciliarias": {
        "descripcion": "Registro de visitas territoriales y proxima accion.",
        "requiere_paciente": False,
        "render": "_tab_visitas",
    },
    "Reportes": {
        "descripcion": "Indicadores exportables por periodo.",
        "requiere_paciente": False,
        "render": "_tab_reportes",
    },
}


def _tab_panel_diario(paciente_sel, user):
    st.subheader("Panel Diario APS")
    st.caption("Vista rápida para administración, enfermería y coordinación.")

    atenciones = st.session_state.get("atenciones_aps_db", [])
    entregas = st.session_state.get("entregas_aps_db", [])
    epi = st.session_state.get("epidemiologia_aps_db", [])
    visitas = st.session_state.get("visitas_domiciliarias_aps_db", [])
    turnos = st.session_state.get("turnos_aps_db", [])

    hoy_iso = date.today().isoformat()

    # Sala de espera
    en_espera = [t for t in turnos if isinstance(t, dict) and t.get("estado") == "en_espera"]
    pacientes_hoy = set()
    medicacion_hoy = 0
    alertas_epi = 0

    for a in atenciones:
        if not isinstance(a, dict):
            continue
        if str(a.get("fecha_atencion", ""))[:10] == hoy_iso:
            pacientes_hoy.add(a.get("paciente_id"))

    for e in entregas:
        if not isinstance(e, dict):
            continue
        if str(e.get("fecha_entrega", ""))[:10] == hoy_iso:
            medicacion_hoy += 1

    for ep in epi:
        if not isinstance(ep, dict):
            continue
        if ep.get("estado") in ("Pendiente", "En seguimiento"):
            alertas_epi += 1

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Pacientes hoy", len(pacientes_hoy))
    col2.metric("Medicación hoy", medicacion_hoy)
    col3.metric("Alertas epi.", alertas_epi)
    col4.metric("En sala de espera", len(en_espera), delta="pendientes")

    st.divider()

    # Sala de espera visual
    with st.container(border=True):
        st.markdown("### 🪑 Sala de espera")
        if en_espera:
            en_espera.sort(key=lambda x: x.get("hora_llegada", "") if isinstance(x, dict) else "")
            for t in en_espera:
                prio = t.get("prioridad", "Normal")
                color = "🔴" if prio == "Urgente" else "🟡" if prio == "Preferencial" else "🟢"
                with st.container(border=True):
                    col_a, col_b, col_c = st.columns([3, 2, 1])
                    with col_a:
                        st.write(f"{color} **{t.get('paciente_id', '-')}**")
                        st.caption(f"Motivo: {t.get('motivo', '-')}")
                    with col_b:
                        st.caption(f"Llegada: {str(t.get('hora_llegada', ''))[:16]}")
                        st.caption(f"Tipo: {t.get('tipo_turno', '-')}")
                    with col_c:
                        if st.button("Atender", key=f"btn_atender_{t.get('id_turno', t.get('hora_llegada', 'x'))}"):
                            t["estado"] = "atendido"
                            _guardar_directo()
                            st.rerun()
        else:
            st.caption("Sala de espera vacía.")

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown("### Últimas atenciones")
            recientes = [
                a for a in atenciones
                if isinstance(a, dict) and str(a.get("fecha_atencion", ""))[:10] == hoy_iso
            ][-10:]
            if recientes:
                for a in recientes:
                    st.write(f"• {a.get('paciente_id', '-')} — {a.get('motivo_consulta', '-')}")
            else:
                st.caption("Sin atenciones registradas hoy.")

    with col2:
        with st.container(border=True):
            st.markdown("### Alertas pendientes")
            alertas = [
                ep for ep in epi
                if isinstance(ep, dict) and ep.get("estado") in ("Pendiente", "En seguimiento")
            ]
            if alertas:
                for al in alertas[:5]:
                    nivel = al.get("prioridad", "Media")
                    if nivel in ("Alta", "Urgente"):
                        st.warning(f"{al.get('paciente_id', '-')} — {', '.join(al.get('enfermedades_seguimiento', []))}")
                    else:
                        st.info(f"{al.get('paciente_id', '-')} — {', '.join(al.get('enfermedades_seguimiento', []))}")
            else:
                st.caption("Sin alertas activas.")


def _tab_pacientes_familia(paciente_sel, user, centro_salud_id):
    st.subheader("Pacientes y Núcleo Familiar")
    st.caption("Gestión territorial y familiar del dispensario.")

    tab_buscar, tab_grupo = st.tabs(["Alta / Búsqueda", "Gestión de Núcleo Familiar"])

    with tab_buscar:
        busqueda = st.text_input("Buscar por DNI o Nombre", placeholder="Ej: 30123456 o Juan Pérez", key="aps_buscar_pac")
        if busqueda:
            resultados = _buscar_pacientes_por_texto(busqueda)
            if resultados:
                st.write(f"**{len(resultados)}** resultado(s)")
                for p in resultados[:10]:
                    with st.container(border=True):
                        col_a, col_b = st.columns([3, 1])
                        with col_a:
                            st.markdown(f"**{p.get('nombre', '-')}**")
                            st.caption(f"DNI: {p.get('dni', '-')} · Barrio: {p.get('barrio', p.get('empresa', '-'))}")
                        with col_b:
                            if st.button("Seleccionar", key=f"sel_pac_{p.get('dni', 'x')}"):
                                st.session_state["paciente_actual"] = p.get("nombre", p.get("dni", "-"))
                                st.toast(f"Paciente {p.get('nombre', '-')} seleccionado", icon="👤")
                                st.rerun()
            else:
                st.warning("No se encontraron pacientes. Verificá los datos o dá de alta en Admisión.")
        else:
            st.caption("Ingresá al menos 3 caracteres para buscar.")

    with tab_grupo:
        st.markdown("### Vinculación familiar / territorial")
        paciente_id = _get_paciente_id_visual(paciente_sel)
        if not paciente_id:
            st.info("Seleccioná un paciente para gestionar su grupo familiar.")
            return

        grupos = st.session_state.get("grupo_familiar_aps_db", [])
        grupo_existente = None
        for g in grupos:
            if not isinstance(g, dict):
                continue
            miembros = g.get("miembros", [])
            if paciente_id in miembros:
                grupo_existente = g
                break

        if grupo_existente:
            st.success(f"Paciente vinculado a familia ID: {grupo_existente.get('id_familia', '-')}")
            st.caption(f"Domicilio: {grupo_existente.get('domicilio', '-')} · Barrio: {grupo_existente.get('barrio', '-')}")
            st.write("Miembros:")
            for m in grupo_existente.get("miembros", []):
                st.write(f"• {m}")
        else:
            st.info("Este paciente no está vinculado a ningún núcleo familiar.")

        with st.form("form_grupo_familiar"):
            domicilio = st.text_input("Domicilio familiar")
            barrio = st.text_input("Barrio / Zona territorial")
            manzana = st.text_input("Manzana")
            lote = st.text_input("Lote")
            id_familia = st.text_input("ID Familia (opcional, se genera automático si vacío)", value=grupo_existente.get("id_familia", "") if grupo_existente else "")
            st.caption("Los miembros se vinculan automáticamente por domicilio compartido.")
            guardar = st.form_submit_button("Guardar / Vincular núcleo", use_container_width=True)

        if guardar:
            fid = id_familia.strip() or f"fam-{centro_salud_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            payload = {
                "id_familia": fid,
                "centro_salud_id": centro_salud_id,
                "domicilio": domicilio,
                "barrio": barrio,
                "manzana": manzana,
                "lote": lote,
                "miembros": list(set((grupo_existente.get("miembros", []) if grupo_existente else []) + [paciente_id])),
                "ultima_actualizacion": datetime.now().isoformat(),
            }
            if grupo_existente:
                idx = grupos.index(grupo_existente)
                st.session_state["grupo_familiar_aps_db"][idx] = payload
            else:
                if "grupo_familiar_aps_db" not in st.session_state or not isinstance(st.session_state["grupo_familiar_aps_db"], list):
                    st.session_state["grupo_familiar_aps_db"] = []
                st.session_state["grupo_familiar_aps_db"].append(payload)
            _guardar_con_feedback("grupo_familiar_aps_db", payload, max_items=500)
            st.success("Núcleo familiar guardado correctamente.")


def _tab_ficha_aps(paciente_sel, user, centro_salud_id):
    st.subheader("Ficha APS del Paciente")
    st.caption("Datos generales propios del centro de salud y equipo de salud.")

    paciente_id = _get_paciente_id_visual(paciente_sel)
    if not paciente_id:
        st.info("Seleccioná un paciente para cargar su ficha APS.")
        return

    fichas = st.session_state.get("ficha_aps_db", [])
    ficha_existente = None
    for f in fichas:
        if not isinstance(f, dict):
            continue
        if f.get("paciente_id") == paciente_id and f.get("centro_salud_id") == centro_salud_id:
            ficha_existente = f
            break

    fe = ficha_existente or {}

    # Inicializar session_state keys si no existen (para evitar conflictos value+key)
    _defaults = {
        "aps_med_nombre": fe.get("medico_nombre", ""),
        "aps_med_apellido": fe.get("medico_apellido", ""),
        "aps_med_matricula": fe.get("medico_matricula", ""),
        "aps_enf_nombre": fe.get("enfermero_nombre", ""),
        "aps_enf_apellido": fe.get("enfermero_apellido", ""),
        "aps_enf_matricula": fe.get("enfermero_matricula", ""),
        "aps_prom_nombre": fe.get("promotor_nombre", ""),
        "aps_prom_apellido": fe.get("promotor_apellido", ""),
        "aps_riesgo": fe.get("riesgo_general", "Bajo"),
        "aps_estado_ficha": fe.get("estado_ficha", "Activa"),
        "aps_obs_ficha": fe.get("observaciones_generales", ""),
    }
    for k, v in _defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # Profesionales adicionales (dinámicos)
    prof_key = f"prof_adic_{paciente_id}"
    if prof_key not in st.session_state:
        st.session_state[prof_key] = fe.get("profesionales_adicionales", [])

    st.markdown("### 🩺 Médico/a referente")
    col1, col2, col3 = st.columns(3)
    with col1:
        med_nombre = st.text_input("Nombre", key="aps_med_nombre")
    with col2:
        med_apellido = st.text_input("Apellido", key="aps_med_apellido")
    with col3:
        med_matricula = st.text_input("Matrícula", key="aps_med_matricula")

    st.markdown("### 🏥 Enfermero/a referente")
    col1, col2, col3 = st.columns(3)
    with col1:
        enf_nombre = st.text_input("Nombre", key="aps_enf_nombre")
    with col2:
        enf_apellido = st.text_input("Apellido", key="aps_enf_apellido")
    with col3:
        enf_matricula = st.text_input("Matrícula", key="aps_enf_matricula")

    st.markdown("### 🌿 Promotor/a de salud")
    col1, col2 = st.columns(2)
    with col1:
        prom_nombre = st.text_input("Nombre", key="aps_prom_nombre")
    with col2:
        prom_apellido = st.text_input("Apellido", key="aps_prom_apellido")

    col1, col2 = st.columns(2)
    with col1:
        riesgo_general = st.selectbox(
            "Riesgo general APS",
            ["Bajo", "Moderado", "Alto", "Crítico"],
            index=(["Bajo", "Moderado", "Alto", "Crítico"].index(st.session_state.get("aps_riesgo", "Bajo"))),
            key="aps_riesgo",
        )
    with col2:
        estado_ficha = st.selectbox(
            "Estado de ficha APS",
            ["Activa", "En seguimiento", "Derivada", "Inactiva"],
            index=(["Activa", "En seguimiento", "Derivada", "Inactiva"].index(st.session_state.get("aps_estado_ficha", "Activa"))),
            key="aps_estado_ficha",
        )

    programa_asignado = st.multiselect(
        "Programas asignados",
        [
            "HTA", "Diabetes", "Salud sexual", "Materno infantil",
            "Leche", "Adulto mayor", "Tuberculosis", "Dengue",
            "Salud mental", "Trabajo social",
        ],
        default=fe.get("programa_asignado", []),
        key="aps_programas",
    )

    observaciones_generales = st.text_area(
        "Observaciones generales APS",
        key="aps_obs_ficha",
    )

    st.divider()
    st.markdown("### ➕ Profesionales adicionales del equipo de salud")

    col_a, col_b, col_c, col_d = st.columns([2, 2, 2, 1])
    with col_a:
        prof_espec = st.selectbox(
            "Especialidad",
            ["Kinesiólogo/a", "Nutricionista", "Psicólogo/a", "Odontólogo/a", "Fonoaudiólogo/a", "Otro"],
            key="aps_prof_espec",
        )
    with col_b:
        prof_nombre = st.text_input("Nombre", key="aps_prof_nombre")
    with col_c:
        prof_apellido = st.text_input("Apellido", key="aps_prof_apellido")
    with col_d:
        prof_mat = st.text_input("Matrícula", key="aps_prof_matricula")

    if st.button("Agregar profesional", use_container_width=True, key="aps_btn_add_prof"):
        if prof_nombre.strip() and prof_apellido.strip():
            st.session_state[prof_key].append({
                "especialidad": prof_espec,
                "nombre": prof_nombre.strip(),
                "apellido": prof_apellido.strip(),
                "matricula": prof_mat.strip(),
            })
            st.rerun()
        else:
            st.warning("Completá nombre y apellido del profesional.")

    profesionales_actuales = st.session_state.get(prof_key, [])
    if profesionales_actuales:
        st.write("**Profesionales agregados:**")
        for i, prof in enumerate(profesionales_actuales):
            col_rem, col_txt = st.columns([1, 5])
            with col_txt:
                st.write(f"• **{prof['especialidad']}**: {prof['nombre']} {prof['apellido']} (Mat: {prof['matricula'] or 'S/D'})")
            with col_rem:
                if st.button("Quitar", key=f"aps_rem_prof_{i}_{paciente_id}"):
                    st.session_state[prof_key].pop(i)
                    st.rerun()
    else:
        st.caption("Sin profesionales adicionales asignados.")

    st.divider()
    if st.button("💾 Guardar ficha APS completa", use_container_width=True, key="aps_btn_guardar_ficha"):
        payload = {
            "paciente_id": paciente_id,
            "centro_salud_id": centro_salud_id,
            "medico_nombre": med_nombre,
            "medico_apellido": med_apellido,
            "medico_matricula": med_matricula,
            "enfermero_nombre": enf_nombre,
            "enfermero_apellido": enf_apellido,
            "enfermero_matricula": enf_matricula,
            "promotor_nombre": prom_nombre,
            "promotor_apellido": prom_apellido,
            "riesgo_general": riesgo_general,
            "programa_asignado": programa_asignado,
            "estado_ficha": estado_ficha,
            "observaciones_generales": observaciones_generales,
            "profesionales_adicionales": profesionales_actuales,
            "ultima_actualizacion": datetime.now().isoformat(),
        }
        if ficha_existente:
            idx = fichas.index(ficha_existente)
            st.session_state["ficha_aps_db"][idx] = payload
        else:
            if "ficha_aps_db" not in st.session_state or not isinstance(st.session_state["ficha_aps_db"], list):
                st.session_state["ficha_aps_db"] = []
            st.session_state["ficha_aps_db"].append(payload)
        _guardar_con_feedback("ficha_aps_db", payload, max_items=500)


def _tab_turnos(paciente_sel, user, centro_salud_id):
    st.subheader("Turnos y Demanda Espontánea")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🚪 Registrar llegada espontánea")
        with st.form("form_llegada_espontanea"):
            dni_esp = st.text_input("DNI del paciente", placeholder="30123456")
            nombre_esp = st.text_input("Nombre (opcional)", placeholder="Juan Pérez")
            motivo_esp = st.selectbox(
                "Motivo de consulta",
                ["Control Niño Sano", "Enfermedad aguda", "Receta / Medicación", "Curación", "Vacunación",
                 "Control embarazo", "Control crónico (HTA/Diabetes)", "Otro"],
                key="aps_motivo_esp",
            )
            prioridad_esp = st.selectbox("Prioridad / Triage", ["Normal", "Preferencial", "Urgente"])
            guardar_esp = st.form_submit_button("Ingresar a sala de espera", use_container_width=True)

        if guardar_esp:
            payload = {
                "id_turno": f"esp-{datetime.now().strftime('%Y%m%d%H%M%S')}-{dni_esp}",
                "paciente_id": nombre_esp or f"DNI {dni_esp}",
                "dni": dni_esp,
                "centro_salud_id": centro_salud_id,
                "tipo_turno": "espontaneo",
                "motivo": motivo_esp,
                "prioridad": prioridad_esp,
                "estado": "en_espera",
                "hora_llegada": datetime.now().isoformat(),
                "registrado_por": st.session_state.get("u_actual", {}).get("nombre", "Operador APS"),
            }
            _guardar_con_feedback("turnos_aps_db", payload, max_items=2000)
            st.success("Paciente ingresado a sala de espera.")

    with col2:
        st.markdown("### 📅 Turno programado")
        with st.form("form_turno_programado"):
            paciente_prog = st.text_input("Paciente (Nombre o DNI)")
            fecha_prog = st.date_input("Fecha", value=date.today())
            hora_prog = st.time_input("Hora")
            motivo_prog = st.selectbox(
                "Motivo",
                ["Control general", "Vacunación", "Control Niño Sano", "Control embarazo",
                 "Receta", "Curación", "Otro"],
                key="aps_motivo_prog",
            )
            guardar_prog = st.form_submit_button("Agendar turno", use_container_width=True)

        if guardar_prog:
            payload = {
                "id_turno": f"prog-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "paciente_id": paciente_prog,
                "centro_salud_id": centro_salud_id,
                "tipo_turno": "programado",
                "motivo": motivo_prog,
                "fecha_turno": datetime.combine(fecha_prog, hora_prog).isoformat(),
                "estado": "programado",
                "hora_llegada": None,
                "prioridad": "Normal",
                "registrado_por": st.session_state.get("u_actual", {}).get("nombre", "Operador APS"),
            }
            _guardar_con_feedback("turnos_aps_db", payload, max_items=2000)
            st.success("Turno programado correctamente.")

    st.divider()
    st.markdown("### Fila de espera y turnos de hoy")
    hoy_iso = date.today().isoformat()
    turnos = st.session_state.get("turnos_aps_db", [])

    turnos_hoy = [
        t for t in turnos
        if isinstance(t, dict) and (
            (t.get("hora_llegada") and str(t.get("hora_llegada"))[:10] == hoy_iso)
            or (t.get("fecha_turno") and str(t.get("fecha_turno"))[:10] == hoy_iso)
        )
    ]

    if turnos_hoy:
        turnos_hoy.sort(key=lambda x: (x.get("hora_llegada") or x.get("fecha_turno") or "") if isinstance(x, dict) else "")
        for t in turnos_hoy:
            estado = t.get("estado", "-")
            if estado == "en_espera":
                icono = "🟡"
                tipo_label = "En espera"
            elif estado == "atendido":
                icono = "✅"
                tipo_label = "Atendido"
            elif estado == "programado":
                icono = "📅"
                tipo_label = "Programado"
            else:
                icono = "⚪"
                tipo_label = estado

            with st.container(border=True):
                col_a, col_b, col_c = st.columns([3, 2, 1])
                with col_a:
                    st.write(f"{icono} **{t.get('paciente_id', '-')}**")
                    st.caption(f"Motivo: {t.get('motivo', '-')} · Prioridad: {t.get('prioridad', 'Normal')}")
                with col_b:
                    if t.get("hora_llegada"):
                        st.caption(f"Llegada: {str(t['hora_llegada'])[:16]}")
                    elif t.get("fecha_turno"):
                        st.caption(f"Turno: {str(t['fecha_turno'])[:16]}")
                    st.caption(f"Tipo: {tipo_label}")
                with col_c:
                    if estado == "en_espera" and st.button("Atender", key=f"turno_atender_{t.get('id_turno', 'x')}"):
                        t["estado"] = "atendido"
                        _guardar_directo()
                        st.rerun()
                    if estado == "programado" and st.button("Llegó", key=f"turno_llego_{t.get('id_turno', 'x')}"):
                        t["estado"] = "en_espera"
                        t["hora_llegada"] = datetime.now().isoformat()
                        _guardar_directo()
                        st.rerun()
    else:
        st.caption("Sin turnos ni llegadas registradas hoy.")


def _generar_pdf_historial_paciente(paciente_id, registros, fd, fh, centro_salud_id):
    """Genera un PDF portrait con diseño profesional del historial APS del paciente."""
    if not FPDF_DISPONIBLE:
        return None

    def _clean(val):
        """Normaliza texto para FPDF (latin-1) reemplazando caracteres problemáticos."""
        if val is None:
            return ""
        val = str(val)
        replacements = {
            "\u2014": "-", "\u2013": "-", "\u2012": "-",
            "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
            "\u2022": "*", "\u2026": "...", "\u00b7": "-",
            "\u200b": "", "\ufeff": "",
        }
        for k, v in replacements.items():
            val = val.replace(k, v)
        return safe_text(val)

    class HistorialPDF(FPDF):
        def header(self):
            self.set_fill_color(25, 55, 95)
            self.rect(0, 0, 210, 18, "F")
            self.set_font("Arial", "B", 16)
            self.set_text_color(255, 255, 255)
            self.cell(0, 10, _clean("HISTORIAL APS  |  MEDICARE PRO"), ln=True, align="C")
            self.set_font("Arial", "", 9)
            self.cell(0, 5, _clean(f"Centro: {centro_salud_id}  |  Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"), ln=True, align="C")
            self.ln(2)

        def footer(self):
            self.set_y(-15)
            self.set_font("Arial", "I", 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, _clean(f"Pagina {self.page_no()} / {{nb}}"), align="C")

    pdf = HistorialPDF(orientation="P")
    pdf.alias_nb_pages()
    pdf.add_page()

    # Info box del paciente
    pdf.set_fill_color(240, 245, 250)
    pdf.set_draw_color(200, 210, 220)
    pdf.rect(10, 28, 190, 22, "DF")
    pdf.set_xy(14, 30)
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(25, 55, 95)
    pdf.cell(0, 6, _clean(f"Paciente: {paciente_id}"), ln=True)
    pdf.set_xy(14, 37)
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 5, _clean(f"Periodo del reporte: {fd}  al  {fh}"), ln=True)
    pdf.ln(10)

    if not registros:
        pdf.set_font("Arial", "", 11)
        pdf.set_text_color(180, 60, 60)
        pdf.cell(0, 10, _clean("No hay registros para el filtro y periodo seleccionados."), ln=True, align="C")
        return pdf_output_bytes(pdf)

    # Summary badge
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(25, 55, 95)
    pdf.cell(0, 6, _clean(f"Total de registros: {len(registros)}"), ln=True)
    pdf.ln(3)

    # Records
    for i, item in enumerate(registros[:300], 1):
        y_start = pdf.get_y()
        if y_start > 260:
            pdf.add_page()
            y_start = pdf.get_y()

        # Alternating background
        if i % 2 == 0:
            pdf.set_fill_color(248, 250, 252)
            pdf.rect(10, y_start, 190, 22, "F")

        pdf.set_xy(14, y_start + 1)
        pdf.set_font("Arial", "B", 9)
        pdf.set_text_color(25, 55, 95)
        pdf.cell(0, 5, _clean(f"#{i}  [{item['tipo']}]  {item['titulo']}"), ln=True)

        pdf.set_xy(14, y_start + 6)
        pdf.set_font("Arial", "", 8)
        pdf.set_text_color(80, 80, 80)
        fecha_str = item.get("fecha", "-")
        registrado = item.get("registrado_por", "-")
        pdf.cell(0, 4, _clean(f"Fecha: {fecha_str}    |    Registrado por: {registrado}"), ln=True)

        detalle = item.get("detalle", "")
        if detalle and detalle.strip():
            pdf.set_xy(14, y_start + 10)
            pdf.set_font("Arial", "", 8)
            pdf.set_text_color(60, 60, 60)
            pdf.multi_cell(182, 4, _clean(f"Detalle: {detalle}"))

        # Separator line
        pdf.set_draw_color(200, 210, 220)
        pdf.line(10, y_start + 22, 200, y_start + 22)
        pdf.set_xy(10, y_start + 22)

    return pdf_output_bytes(pdf)


def _tab_historial_aps(paciente_sel, user, centro_salud_id):
    st.subheader("Historial APS del Dispensario")
    st.caption("Todos los movimientos del paciente dentro del centro de salud.")

    if paciente_sel:
        paciente_id = _get_paciente_id_visual(paciente_sel)
    else:
        st.info("Buscá un paciente por Apellido, Nombre o DNI (también funciona para pacientes voluntarios):")
        c1, c2, c3 = st.columns(3)
        with c1:
            bus_apellido = st.text_input("Apellido", key="aps_hist_bus_apellido")
        with c2:
            bus_nombre = st.text_input("Nombre", key="aps_hist_bus_nombre")
        with c3:
            bus_dni = st.text_input("DNI", key="aps_hist_bus_dni")
        parts = [p for p in [bus_apellido, bus_nombre] if p and p.strip()]
        paciente_id = f"{' '.join(parts)} - {bus_dni}".strip() if (parts or (bus_dni and bus_dni.strip())) else ""
        if not paciente_id:
            st.warning("Completá al menos un campo para buscar el historial.")
            return

    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_tipo = st.selectbox(
            "Filtrar por tipo",
            [
                "Todos", "Atención APS", "Farmacia", "Trabajo Social",
                "Epidemiología", "Visita domiciliaria", "Ficha APS",
                "Turnos", "Control Niño/Embarazo",
            ],
        )
    with col2:
        fecha_desde = st.date_input("Desde", value=date.today())
    with col3:
        fecha_hasta = st.date_input("Hasta", value=date.today())

    st.divider()

    registros = []

    for a in st.session_state.get("atenciones_aps_db", []):
        if not isinstance(a, dict):
            continue
        if paciente_id in str(a.get("paciente_id", "")):
            registros.append({
                "fecha": str(a.get("fecha_atencion", ""))[:16],
                "tipo": "Atención APS",
                "titulo": a.get("motivo_consulta", "-"),
                "detalle": f"PA: {a.get('presion_arterial', 'S/D')} · FC: {a.get('frecuencia_cardiaca', 'S/D')}",
                "registrado_por": a.get("registrado_por", "-"),
            })

    for e in st.session_state.get("entregas_aps_db", []):
        if not isinstance(e, dict):
            continue
        if paciente_id in str(e.get("paciente_id", "")):
            registros.append({
                "fecha": str(e.get("fecha_entrega", ""))[:16],
                "tipo": "Farmacia",
                "titulo": e.get("medicamento", "Entrega"),
                "detalle": f"{e.get('cantidad', '-')} {e.get('unidad', '')}",
                "registrado_por": e.get("registrado_por", "-"),
            })

    for s in st.session_state.get("trabajo_social_aps_db", []):
        if not isinstance(s, dict):
            continue
        if paciente_id in str(s.get("paciente_id", "")):
            registros.append({
                "fecha": str(s.get("fecha_registro", ""))[:16],
                "tipo": "Trabajo Social",
                "titulo": f"Riesgo: {s.get('riesgo_social', '-')}",
                "detalle": f"Vivienda: {s.get('tipo_vivienda', '-')} · Agua: {s.get('agua_potable', '-')}",
                "registrado_por": s.get("registrado_por", "-"),
            })

    for ep in st.session_state.get("epidemiologia_aps_db", []):
        if not isinstance(ep, dict):
            continue
        if paciente_id in str(ep.get("paciente_id", "")):
            registros.append({
                "fecha": str(ep.get("fecha_registro", ""))[:16],
                "tipo": "Epidemiología",
                "titulo": ", ".join(ep.get("enfermedades_seguimiento", [])),
                "detalle": f"Prioridad: {ep.get('prioridad', '-')} · Estado: {ep.get('estado', '-')}",
                "registrado_por": ep.get("registrado_por", "-"),
            })

    for v in st.session_state.get("visitas_domiciliarias_aps_db", []):
        if not isinstance(v, dict):
            continue
        if paciente_id in str(v.get("paciente_id", "")):
            registros.append({
                "fecha": str(v.get("fecha_visita", ""))[:16],
                "tipo": "Visita domiciliaria",
                "titulo": v.get("motivo_visita", "-"),
                "detalle": v.get("resultado_visita", "-"),
                "registrado_por": v.get("registrado_por", "-"),
            })

    for f in st.session_state.get("ficha_aps_db", []):
        if not isinstance(f, dict):
            continue
        if paciente_id in str(f.get("paciente_id", "")):
            registros.append({
                "fecha": str(f.get("ultima_actualizacion", ""))[:16],
                "tipo": "Ficha APS",
                "titulo": f"Riesgo: {f.get('riesgo_general', '-')} · Estado: {f.get('estado_ficha', '-')}",
                "detalle": f"Programas: {', '.join(f.get('programa_asignado', []))}",
                "registrado_por": "-",
            })

    for t in st.session_state.get("turnos_aps_db", []):
        if not isinstance(t, dict):
            continue
        if paciente_id in str(t.get("paciente_id", "")):
            registros.append({
                "fecha": str(t.get("hora_llegada") or t.get("fecha_turno") or "")[:16],
                "tipo": "Turnos",
                "titulo": f"{t.get('tipo_turno', '-').capitalize()} — {t.get('motivo', '-')}",
                "detalle": f"Prioridad: {t.get('prioridad', '-')} · Estado: {t.get('estado', '-')}",
                "registrado_por": t.get("registrado_por", "-"),
            })

    for c in st.session_state.get("controles_aps_db", []):
        if not isinstance(c, dict):
            continue
        if paciente_id in str(c.get("paciente_id", "")):
            tipo_label = "Niño Sano" if c.get("tipo_control") == "nino_sano" else "Embarazo"
            detalle = (
                f"Peso: {c.get('peso', '-')} · Talla: {c.get('talla', '-')} · Vacunas: {c.get('vacunas_al_dia', '-')}"
                if c.get("tipo_control") == "nino_sano"
                else f"EG: {c.get('semanas_gestacion', '-')} sem · PA: {c.get('presion_arterial', '-')}"
            )
            registros.append({
                "fecha": str(c.get("fecha_control", ""))[:16],
                "tipo": "Control Niño/Embarazo",
                "titulo": tipo_label,
                "detalle": detalle,
                "registrado_por": c.get("registrado_por", "-"),
            })

    # Filtros
    if filtro_tipo != "Todos":
        registros = [r for r in registros if r["tipo"] == filtro_tipo]

    fd = fecha_desde.isoformat()
    fh = fecha_hasta.isoformat()
    registros = [r for r in registros if fd <= r["fecha"][:10] <= fh]

    registros.sort(key=lambda x: x["fecha"], reverse=True)

    if not registros:
        st.warning("No hay registros para el filtro seleccionado.")
        return

    if FPDF_DISPONIBLE:
        pdf_bytes = _generar_pdf_historial_paciente(paciente_id, registros, fd, fh, centro_salud_id)
        if pdf_bytes:
            st.download_button(
                "📄 Descargar historial PDF",
                data=pdf_bytes,
                file_name=f"Historial_APS_{sanitize_filename_component(paciente_id, 'paciente')}_{date.today().isoformat()}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="aps_historial_pdf_btn",
            )
    else:
        st.caption("La librería FPDF no está disponible. No se puede generar PDF.")

    st.divider()

    for item in registros:
        with st.container(border=True):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"**{item['titulo']}**")
                st.caption(f"Tipo: {item['tipo']}")
                st.write(item["detalle"])
                st.caption(f"Registrado por: {item['registrado_por']}")
            with col_b:
                st.write(item["fecha"])


def _tab_nueva_atencion(paciente_sel, user, centro_salud_id):
    st.subheader("Atención APS")

    paciente_id, paciente_volatil = _input_paciente_volatil(paciente_sel, key_prefix="aps_atencion")
    if not paciente_id:
        st.warning("Completá Apellido, Nombre y DNI del paciente para continuar.")
        return

    with st.form("form_nueva_atencion_aps"):
        motivo = st.selectbox(
            "Motivo de atención",
            [
                "Control general", "Control de presión arterial", "Control de diabetes",
                "Curación", "Vacunación", "Control niño sano", "Control embarazo",
                "Entrega de medicación", "Consulta respiratoria", "Consulta social", "Otro",
            ],
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            presion = st.text_input("Presión arterial", placeholder="120/80")
            frecuencia = st.number_input("Frecuencia cardíaca", min_value=0, max_value=250)
        with col2:
            temperatura = st.number_input("Temperatura", min_value=30.0, max_value=45.0, step=0.1)
            glucemia = st.number_input("Glucemia", min_value=0, max_value=600)
        with col3:
            saturacion = st.number_input("Saturación O2", min_value=0, max_value=100)
            peso = st.number_input("Peso", min_value=0.0, max_value=300.0, step=0.1)

        diagnostico_aps = st.text_input("Diagnóstico / impresión APS")
        conducta = st.text_area("Conducta / indicaciones")
        observaciones = st.text_area("Observaciones de la atención")

        requiere_derivacion = st.checkbox("Requiere derivación")
        destino_derivacion = st.text_input("Destino de derivación", placeholder="Hospital, guardia, especialista...")

        guardar = st.form_submit_button("Guardar atención", use_container_width=True)

    if guardar:
        payload = {
            "paciente_id": paciente_id,
            "paciente_volatil": paciente_volatil,
            "centro_salud_id": centro_salud_id,
            "fecha_atencion": datetime.now().isoformat(),
            "motivo_consulta": motivo,
            "presion_arterial": presion,
            "frecuencia_cardiaca": frecuencia,
            "temperatura": temperatura,
            "glucemia": glucemia,
            "saturacion": saturacion,
            "peso": peso,
            "diagnostico_aps": diagnostico_aps,
            "conducta": conducta,
            "observaciones": observaciones,
            "requiere_derivacion": requiere_derivacion,
            "destino_derivacion": destino_derivacion,
            "registrado_por": st.session_state.get("u_actual", {}).get("nombre", "Usuario APS"),
            "created_at": datetime.now().isoformat(),
        }
        _guardar_con_feedback("atenciones_aps_db", payload, max_items=1000)


def _tab_control_nino_embarazo(paciente_sel, user, centro_salud_id):
    st.subheader("Control Niño Sano y Embarazo")

    paciente_id, paciente_volatil = _input_paciente_volatil(paciente_sel, key_prefix="aps_control")
    if not paciente_id:
        st.warning("Completá Apellido, Nombre y DNI del paciente para continuar.")
        return

    pacientes_db = st.session_state.get("pacientes_db", [])
    paciente_data = None
    for p in pacientes_db:
        if not isinstance(p, dict):
            continue
        if p.get("nombre") == paciente_id or str(p.get("dni")) in paciente_id:
            paciente_data = p
            break

    edad = _calcular_edad(paciente_data.get("fecha_nacimiento")) if paciente_data else None

    tab_nino, tab_embarazo = st.tabs(["👶 Niño Sano", "🤰 Embarazo"])

    with tab_nino:
        if edad is not None and edad >= 18:
            st.info("El paciente seleccionado tiene 18+ años. Usá esta pestaña solo para menores.")

        with st.form("form_nino_sano"):
            col1, col2, col3 = st.columns(3)
            with col1:
                peso = st.number_input("Peso (kg)", min_value=0.0, max_value=150.0, step=0.1)
                talla = st.number_input("Talla (cm)", min_value=0.0, max_value=200.0, step=0.1)
            with col2:
                perimetro_cefalico = st.number_input("Perímetro cefálico (cm)", min_value=0.0, max_value=80.0, step=0.1)
                imc = round(peso / ((talla / 100) ** 2), 2) if talla > 0 else 0.0
                st.metric("IMC calculado", f"{imc:.1f}")
            with col3:
                vacunas_al_dia = st.selectbox("Vacunas al día", ["Sí", "No", "Parcial"])
                proximo_control = st.date_input("Próximo control", value=date.today() + timedelta(days=30))

            observaciones = st.text_area("Observaciones del control")
            guardar = st.form_submit_button("Guardar control niño sano", use_container_width=True)

        if guardar:
            payload = {
                "paciente_id": paciente_id,
                "paciente_volatil": paciente_volatil,
                "centro_salud_id": centro_salud_id,
                "tipo_control": "nino_sano",
                "fecha_control": datetime.now().isoformat(),
                "peso": peso,
                "talla": talla,
                "perimetro_cefalico": perimetro_cefalico,
                "imc": imc,
                "vacunas_al_dia": vacunas_al_dia,
                "proximo_control": proximo_control.isoformat(),
                "observaciones": observaciones,
                "registrado_por": st.session_state.get("u_actual", {}).get("nombre", "Operador APS"),
                "created_at": datetime.now().isoformat(),
            }
            _guardar_con_feedback("controles_aps_db", payload, max_items=500)

    with tab_embarazo:
        with st.form("form_embarazo"):
            fum = st.date_input("Fecha última menstruación (FUM)", value=None)
            semanas_gestacion = None
            if fum:
                semanas_gestacion = _calcular_edad_gestacional(fum.isoformat())
                st.metric("Edad gestacional", f"{semanas_gestacion} semanas" if semanas_gestacion is not None else "N/D")

            col1, col2 = st.columns(2)
            with col1:
                peso_pre = st.number_input("Peso pregestacional (kg)", min_value=0.0, max_value=200.0, step=0.1)
                ta = st.text_input("Presión arterial", placeholder="120/80")
            with col2:
                altura_uterina = st.number_input("Altura uterina (cm)", min_value=0, max_value=50)
                fcf = st.number_input("FCF (lat/min)", min_value=0, max_value=200)

            movimientos_fetales = st.selectbox("Movimientos fetales", ["Presentes", "Disminuidos", "No evaluado"])
            observaciones_emb = st.text_area("Observaciones obstétricas")
            guardar_emb = st.form_submit_button("Guardar control embarazo", use_container_width=True)

        if guardar_emb:
            payload = {
                "paciente_id": paciente_id,
                "paciente_volatil": paciente_volatil,
                "centro_salud_id": centro_salud_id,
                "tipo_control": "embarazo",
                "fecha_control": datetime.now().isoformat(),
                "fum": fum.isoformat() if fum else None,
                "semanas_gestacion": semanas_gestacion,
                "peso_pregestacional": peso_pre,
                "presion_arterial": ta,
                "altura_uterina": altura_uterina,
                "fcf": fcf,
                "movimientos_fetales": movimientos_fetales,
                "observaciones": observaciones_emb,
                "registrado_por": st.session_state.get("u_actual", {}).get("nombre", "Operador APS"),
                "created_at": datetime.now().isoformat(),
            }
            _guardar_con_feedback("controles_aps_db", payload, max_items=500)


def _tab_farmacia(paciente_sel, user, centro_salud_id):
    st.subheader("Farmacia y Entrega de Leche")
    st.caption("Medicación crónica, leche (Plan Materno Infantil) e insumos.")

    paciente_id, paciente_volatil = _input_paciente_volatil(paciente_sel, key_prefix="aps_farmacia")
    if not paciente_id:
        st.warning("Completá Apellido, Nombre y DNI del paciente para continuar.")
        return

    entregas_db = st.session_state.get("entregas_aps_db", [])

    tab_med, tab_leche = st.tabs(["💊 Medicación Crónica", "🥛 Leche"])

    with tab_med:
        try:
            vademecum_base = cargar_json_asset("vademecum.json")
        except Exception:
            vademecum_base = [
                "Enalapril 10 mg", "Losartán 50 mg", "Amlodipina 5 mg",
                "Metformina 850 mg", "Glibenclamida 5 mg", "Insulina NPH",
                "Salbutamol", "Levotiroxina", "Atorvastatina",
            ]

        col1, col2 = st.columns(2)
        with col1:
            med_vademecum = st.selectbox(
                "Medicamento",
                ["-- Seleccionar del vademecum --"] + vademecum_base,
                key="aps_med_select",
            )
            med_manual = ""
            if med_vademecum == "-- Seleccionar del vademecum --":
                med_manual = st.text_input("O escribir manualmente", key="aps_med_manual")
            medicamento = med_manual if med_vademecum == "-- Seleccionar del vademecum --" else med_vademecum
            cantidad = st.number_input("Cantidad", min_value=1, value=30, key="aps_med_cant")
        with col2:
            unidad = st.selectbox("Unidad", ["Comprimidos", "Cajas", "Frascos", "Ampollas", "Aerosoles"], key="aps_med_unidad")
            mes_corriente = _ya_entrego_mes(paciente_id, "farmacia_aps", entregas_db)
            if mes_corriente:
                st.warning("⚠️ Este paciente ya retiró medicación este mes.")
            else:
                st.success("✅ Cuota mensual disponible")

        observacion_med = st.text_area("Observación de farmacia", key="aps_med_obs")

        if st.button("Registrar entrega medicación", use_container_width=True, key="aps_btn_med"):
            if not medicamento:
                st.error("Seleccioná un medicamento del vademecum o escribí uno manualmente.")
            else:
                payload = {
                    "paciente_id": paciente_id,
                    "paciente_volatil": paciente_volatil,
                    "centro_salud_id": centro_salud_id,
                    "fecha_entrega": datetime.now().isoformat(),
                    "tipo_entrega": "farmacia_aps",
                    "medicamento": medicamento,
                    "cantidad": cantidad,
                    "unidad": unidad,
                    "observaciones": observacion_med,
                    "registrado_por": st.session_state.get("u_actual", {}).get("nombre", "Usuario APS"),
                    "created_at": datetime.now().isoformat(),
                }
                _guardar_con_feedback("entregas_aps_db", payload, max_items=1000)

    with tab_leche:
        pacientes_db = st.session_state.get("pacientes_db", [])
        paciente_data = None
        for p in pacientes_db:
            if not isinstance(p, dict):
                continue
            if p.get("nombre") == paciente_id or str(p.get("dni")) in paciente_id:
                paciente_data = p
                break

        dni_tutor = st.text_input("DNI del tutor/a", value=paciente_data.get("dni", "") if paciente_data else "", key="aps_leche_dni")
        edad_nino = _calcular_edad(paciente_data.get("fecha_nacimiento")) if paciente_data else None

        if edad_nino is not None:
            if edad_nino <= 2:
                st.success(f"✅ Edad válida para leche: {edad_nino} año(s)")
            else:
                st.error(f"❌ Edad fuera de rango: {edad_nino} año(s). El plan cubre hasta 2 años.")

        ya_leche_mes = _ya_entrego_mes(paciente_id, "leche_aps", entregas_db)
        if ya_leche_mes:
            st.warning("⚠️ Este beneficiario ya retiró leche este mes.")

        if st.button("Registrar entrega leche (2 kg)", use_container_width=True, key="aps_btn_leche"):
            if edad_nino is not None and edad_nino > 2:
                st.error("No se puede registrar: edad fuera del rango del plan.")
            elif ya_leche_mes:
                st.error("No se puede registrar: ya retiró la cuota mensual.")
            else:
                payload = {
                    "paciente_id": paciente_id,
                    "paciente_volatil": paciente_volatil,
                    "centro_salud_id": centro_salud_id,
                    "fecha_entrega": datetime.now().isoformat(),
                    "tipo_entrega": "leche_aps",
                    "medicamento": "Leche entera 2kg",
                    "cantidad": 2,
                    "unidad": "kg",
                    "dni_tutor": dni_tutor,
                    "observaciones": "Entrega leche Plan Materno Infantil",
                    "registrado_por": st.session_state.get("u_actual", {}).get("nombre", "Usuario APS"),
                    "created_at": datetime.now().isoformat(),
                }
                _guardar_con_feedback("entregas_aps_db", payload, max_items=1000)


def _tab_trabajo_social(paciente_sel, user, centro_salud_id):
    st.subheader("Trabajo Social APS")

    paciente_id, paciente_volatil = _input_paciente_volatil(paciente_sel, key_prefix="aps_tsocial")
    if not paciente_id:
        st.warning("Completá Apellido, Nombre y DNI del paciente para continuar.")
        return

    with st.form("form_trabajo_social_aps"):
        col1, col2 = st.columns(2)
        with col1:
            tipo_vivienda = st.selectbox(
                "Tipo de vivienda",
                ["Material", "Chapa", "Madera", "Mixta", "Rancho", "Situación de calle", "Otra"],
            )
            agua = st.selectbox(
                "Agua potable",
                ["Sí", "No", "Intermitente", "Pozo", "Canilla comunitaria"],
            )
            electricidad = st.selectbox(
                "Electricidad",
                ["Sí", "No", "Conexión precaria"],
            )
        with col2:
            gas = st.selectbox(
                "Gas",
                ["Gas natural", "Garrafa", "Leña / carbón", "No posee"],
            )
            cobertura = st.selectbox(
                "Cobertura social",
                ["Ninguna", "Obra social", "PAMI", "Incluir Salud", "Plan Alimentario", "Asignación", "Otro"],
            )
            riesgo_social = st.selectbox(
                "Riesgo social",
                ["Bajo", "Moderado", "Alto", "Crítico"],
            )

        grupo_familiar = st.number_input("Cantidad de convivientes", min_value=0, max_value=30)
        observaciones = st.text_area("Observaciones sociales")

        guardar = st.form_submit_button("Guardar registro social", use_container_width=True)

    if guardar:
        payload = {
            "paciente_id": paciente_id,
            "paciente_volatil": paciente_volatil,
            "centro_salud_id": centro_salud_id,
            "fecha_registro": datetime.now().isoformat(),
            "tipo_vivienda": tipo_vivienda,
            "agua_potable": agua,
            "electricidad": electricidad,
            "gas": gas,
            "grupo_familiar": grupo_familiar,
            "cobertura_social": cobertura,
            "riesgo_social": riesgo_social,
            "observaciones": observaciones,
            "registrado_por": st.session_state.get("u_actual", {}).get("nombre", "Trabajo Social APS"),
            "created_at": datetime.now().isoformat(),
        }
        _guardar_con_feedback("trabajo_social_aps_db", payload, max_items=500)


def _tab_epidemiologia(paciente_sel, user, centro_salud_id):
    st.subheader("Epidemiología APS")

    paciente_id, paciente_volatil = _input_paciente_volatil(paciente_sel, key_prefix="aps_epi")
    if not paciente_id:
        st.warning("Completá Apellido, Nombre y DNI del paciente para continuar.")
        return

    with st.form("form_epidemiologia_aps"):
        enfermedades = st.multiselect(
            "Enfermedades / eventos de seguimiento",
            [
                "Dengue", "Tuberculosis", "Sífilis", "VIH", "Chagas",
                "Hepatitis", "COVID-19", "Influenza", "ETA",
                "Escabiosis", "Pediculosis", "Desnutrición",
                "Embarazo adolescente", "Violencia familiar", "Otra",
            ],
        )

        col1, col2 = st.columns(2)
        with col1:
            requiere_notificacion = st.checkbox("Requiere notificación obligatoria")
            requiere_visita = st.checkbox("Requiere visita domiciliaria")
        with col2:
            prioridad = st.selectbox("Prioridad", ["Baja", "Media", "Alta", "Urgente"])
            estado = st.selectbox("Estado", ["Pendiente", "En seguimiento", "Resuelto", "Derivado"])

        observaciones = st.text_area("Observaciones para promotor de salud")

        guardar = st.form_submit_button("Guardar epidemiología", use_container_width=True)

    if guardar:
        payload = {
            "paciente_id": paciente_id,
            "paciente_volatil": paciente_volatil,
            "centro_salud_id": centro_salud_id,
            "fecha_registro": datetime.now().isoformat(),
            "enfermedades_seguimiento": enfermedades,
            "requiere_notificacion": requiere_notificacion,
            "requiere_visita": requiere_visita,
            "prioridad": prioridad,
            "estado": estado,
            "observaciones_promotor": observaciones,
            "registrado_por": st.session_state.get("u_actual", {}).get("nombre", "Usuario APS"),
            "created_at": datetime.now().isoformat(),
        }
        _guardar_con_feedback("epidemiologia_aps_db", payload, max_items=500)


def _tab_visitas(paciente_sel, user, centro_salud_id):
    st.subheader("Visitas Domiciliarias APS")

    paciente_id, paciente_volatil = _input_paciente_volatil(paciente_sel, key_prefix="aps_visitas")
    if not paciente_id:
        st.warning("Completá Apellido, Nombre y DNI del paciente para continuar.")
        return

    with st.form("form_visita_domiciliaria_aps"):
        motivo = st.selectbox(
            "Motivo de visita",
            [
                "Seguimiento social", "Control epidemiológico", "Control de tratamiento",
                "Paciente ausente a controles", "Embarazo / puerperio",
                "Niño en seguimiento", "Adulto mayor vulnerable", "Otro",
            ],
        )

        domicilio = st.text_input("Domicilio visitado")
        paciente_encontrado = st.checkbox("Paciente encontrado en domicilio")
        resultado = st.text_area("Resultado de la visita")
        requiere_nueva = st.checkbox("Requiere nueva visita")
        prioridad = st.selectbox("Prioridad", ["Baja", "Media", "Alta", "Urgente"])

        guardar = st.form_submit_button("Guardar visita", use_container_width=True)

    if guardar:
        payload = {
            "paciente_id": paciente_id,
            "paciente_volatil": paciente_volatil,
            "centro_salud_id": centro_salud_id,
            "fecha_visita": datetime.now().isoformat(),
            "motivo_visita": motivo,
            "domicilio_visitado": domicilio,
            "paciente_encontrado": paciente_encontrado,
            "resultado_visita": resultado,
            "requiere_nueva_visita": requiere_nueva,
            "prioridad": prioridad,
            "estado": "Pendiente" if requiere_nueva else "Completada",
            "registrado_por": st.session_state.get("u_actual", {}).get("nombre", "Promotor APS"),
            "created_at": datetime.now().isoformat(),
        }
        _guardar_con_feedback("visitas_domiciliarias_aps_db", payload, max_items=500)


def _generar_pdf_reporte_aps(titulo, registros, periodo, centro_salud_id):
    """Genera un PDF landscape genérico con los registros del reporte APS."""
    if not FPDF_DISPONIBLE:
        return None
    pdf = FPDF(orientation="L")
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, safe_text(titulo), ln=True, align="C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 8, safe_text(f"Periodo: {periodo}  |  Centro: {centro_salud_id}"), ln=True, align="C")
    pdf.ln(4)
    for i, r in enumerate(registros[:250], 1):
        pdf.set_font("Arial", "B", 9)
        pdf.cell(0, 6, safe_text(f"Registro #{i}"), ln=True)
        pdf.set_font("Arial", "", 8)
        for k, v in sorted(r.items()):
            line = f"  {k}: {v}"
            pdf.multi_cell(0, 5, safe_text(line))
        pdf.ln(1)
    return pdf_output_bytes(pdf)


def _tab_reportes(paciente_sel, user, centro_salud_id):
    st.subheader("Reportes APS")
    st.caption("Indicadores útiles para coordinación, municipio o centro de salud.")

    col1, col2 = st.columns(2)
    with col1:
        fecha_desde = st.date_input("Desde", value=date.today(), key="aps_rep_desde")
        fecha_hasta = st.date_input("Hasta", value=date.today(), key="aps_rep_hasta")
    with col2:
        tipo_reporte = st.selectbox(
            "Tipo de reporte",
            [
                "Atenciones APS", "Entregas de medicación", "Entregas de leche",
                "Casos epidemiológicos", "Pacientes con riesgo social", "Visitas domiciliarias",
                "Turnos y demanda espontánea", "Controles Niño Sano / Embarazo",
                "Grupos familiares",
            ],
            key="aps_rep_tipo",
        )

    if st.button("Generar reporte", use_container_width=True, key="aps_rep_btn"):
        fd = fecha_desde.isoformat()
        fh = fecha_hasta.isoformat()

        registros = []
        if tipo_reporte == "Atenciones APS":
            registros = [
                a for a in st.session_state.get("atenciones_aps_db", [])
                if isinstance(a, dict) and fd <= str(a.get("fecha_atencion", ""))[:10] <= fh
            ]
        elif tipo_reporte in ("Entregas de medicación", "Entregas de leche"):
            registros = [
                e for e in st.session_state.get("entregas_aps_db", [])
                if isinstance(e, dict) and fd <= str(e.get("fecha_entrega", ""))[:10] <= fh
            ]
        elif tipo_reporte == "Casos epidemiológicos":
            registros = [
                ep for ep in st.session_state.get("epidemiologia_aps_db", [])
                if isinstance(ep, dict) and fd <= str(ep.get("fecha_registro", ""))[:10] <= fh
            ]
        elif tipo_reporte == "Pacientes con riesgo social":
            registros = [
                s for s in st.session_state.get("trabajo_social_aps_db", [])
                if isinstance(s, dict) and fd <= str(s.get("fecha_registro", ""))[:10] <= fh
            ]
        elif tipo_reporte == "Visitas domiciliarias":
            registros = [
                v for v in st.session_state.get("visitas_domiciliarias_aps_db", [])
                if isinstance(v, dict) and fd <= str(v.get("fecha_visita", ""))[:10] <= fh
            ]
        elif tipo_reporte == "Turnos y demanda espontánea":
            registros = [
                t for t in st.session_state.get("turnos_aps_db", [])
                if isinstance(t, dict) and fd <= str(t.get("hora_llegada") or t.get("fecha_turno") or "")[:10] <= fh
            ]
        elif tipo_reporte == "Controles Niño Sano / Embarazo":
            registros = [
                c for c in st.session_state.get("controles_aps_db", [])
                if isinstance(c, dict) and fd <= str(c.get("fecha_control", ""))[:10] <= fh
            ]
        elif tipo_reporte == "Grupos familiares":
            registros = st.session_state.get("grupo_familiar_aps_db", [])

        st.session_state["aps_reporte_actual"] = registros
        st.session_state["aps_reporte_tipo"] = tipo_reporte
        st.session_state["aps_reporte_periodo"] = f"{fd} a {fh}"

    reporte_registros = st.session_state.get("aps_reporte_actual", [])
    reporte_tipo = st.session_state.get("aps_reporte_tipo", "")
    reporte_periodo = st.session_state.get("aps_reporte_periodo", "")
    if reporte_registros:
        st.write(f"**{len(reporte_registros)}** registros encontrados.")
        st.dataframe(reporte_registros, use_container_width=True, hide_index=True)
        if FPDF_DISPONIBLE:
            pdf_bytes = _generar_pdf_reporte_aps(
                f"Reporte APS — {reporte_tipo}",
                reporte_registros,
                reporte_periodo,
                centro_salud_id,
            )
            if pdf_bytes:
                st.download_button(
                    "📄 Descargar PDF",
                    data=pdf_bytes,
                    file_name=f"Reporte_APS_{sanitize_filename_component(reporte_tipo, 'reporte')}_{date.today().isoformat()}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="aps_rep_pdf_btn",
                )
        else:
            st.caption("La librería FPDF no está disponible. No se puede generar PDF.")
    else:
        st.info("Generá un reporte para visualizar los registros.")


def render_dispensario_aps(paciente_sel, mi_empresa, user, rol):
    """Entry point del módulo APS / Dispensario."""

    st.title("🏥 APS / Dispensario")
    st.caption("Atención Primaria de la Salud · Centro de Salud · Dispensario Comunitario")

    centro_salud_id = st.session_state.get("centro_salud_id", "dispensario-demo-001")

    _metricas_aps_del_dia()
    st.divider()

    # Si no hay paciente, mostrar aviso pero permitir acceso a Panel Diario y Reportes
    if not paciente_sel:
        st.info("Seleccioná un paciente desde el sidebar para registrar atenciones, farmacia, trabajo social, epidemiología y visitas.")

    opciones = list(_APS_SECCIONES)
    area = st.selectbox(
        "Area de trabajo APS",
        opciones,
        key="aps_area_activa",
        help="Renderiza solo el area elegida para mantener la pantalla liviana.",
    )
    meta = _APS_SECCIONES[area]
    st.caption(meta["descripcion"])

    if meta["requiere_paciente"] and not paciente_sel:
        aviso_sin_paciente()
        return

    render_fn = globals()[meta["render"]]
    if meta["render"] == "_tab_panel_diario":
        render_fn(paciente_sel, user)
    else:
        render_fn(paciente_sel, user, centro_salud_id)
