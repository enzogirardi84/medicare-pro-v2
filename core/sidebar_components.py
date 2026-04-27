"""Componentes del sidebar clínico de MediCare PRO.

Extraído de main.py para mantenerlo liviano.
Contiene: tarjeta de marca, tarjeta de paciente, panel de signos vitales,
contexto clínico rápido (semáforo, evolución, medicación) y selector de pacientes.
"""
from datetime import datetime
from html import escape

import streamlit as st


# ---------------------------------------------------------------------------
# Tarjetas de marca y paciente
# ---------------------------------------------------------------------------

def sidebar_patient_card(paciente_sel, detalles):
    with st.container(border=True):
        st.write(f"**Paciente activo**")
        st.write(f"{escape(paciente_sel)}")
        st.caption(
            f"DNI: {escape(detalles.get('dni', 'S/D'))}  |  "
            f"OS: {escape(detalles.get('obra_social', 'S/D'))}  |  "
            f"Empresa: {escape(detalles.get('empresa', 'S/D'))}  |  "
            f"Estado: {escape(detalles.get('estado', 'Activo'))}"
        )


def sidebar_brand_card(mi_empresa, user, rol, descripcion, logo_sidebar_b64):
    logo_html = (
        f'<div class="mc-brand-logo-shell">'
        f'<img src="data:image/jpeg;base64,{logo_sidebar_b64}" class="mc-brand-logo" />'
        f"</div>"
        if logo_sidebar_b64
        else ""
    )
    return (
        f'<div class="mc-brand-card">'
        f"{logo_html}"
        f'<div class="mc-brand-kicker">MediCare Enterprise PRO</div>'
        f'<div class="mc-brand-company">{escape(mi_empresa)}</div>'
        f'<div class="mc-brand-user">{escape(user.get("nombre", ""))} <span>({escape(rol)})</span></div>'
        f'<div class="mc-brand-copy">{escape(descripcion)}</div>'
        f"</div>"
    )


# ---------------------------------------------------------------------------
# Signos vitales en sidebar
# ---------------------------------------------------------------------------

def _vitales_valor_corto(registro, clave, default="S/D"):
    raw = registro.get(clave)
    if raw is None:
        return default
    s = str(raw).strip()
    return s if s else default


def semaforo_vital_sidebar(v):
    try:
        from views.clinica import _evaluar_ta_clinica, _evaluar_vit
        estados = [
            _evaluar_ta_clinica(v.get("TA", "")),
            _evaluar_vit("FC", v.get("FC")),
            _evaluar_vit("Sat", v.get("Sat")),
            _evaluar_vit("Temp", v.get("Temp")),
        ]
        if any(e == "critico" for e in estados):
            return "🔴"
        if any(e == "alerta" for e in estados):
            return "🟡"
        if any(e == "normal" for e in estados):
            return "🟢"
    except Exception as _exc:
        from core.app_logging import log_event
        log_event("sidebar_vital_error", f"semaforo_fallo:{type(_exc).__name__}")
    return "⚪"


# ---------------------------------------------------------------------------
# Contexto clínico rápido del sidebar
# ---------------------------------------------------------------------------

def render_sidebar_contexto_clinico(paciente_sel, vista_actual):
    if not paciente_sel:
        return

    from core.utils import mapa_detalles_pacientes
    detalles = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {}) or {}
    alergias = str(detalles.get("alergias", "") or "").strip()
    patologias = str(detalles.get("patologias", "") or detalles.get("diagnostico", "") or "").strip()

    vitales = st.session_state.get("vitales_db", [])
    vit_cache_key = f"_mc_cache_vit_top3_{paciente_sel}"
    vit_cached = st.session_state.get(vit_cache_key)
    # Clave de cache basada en contenido (len + fecha último) en vez de id() que cambia en cada rerun
    _vit_last_fecha = ""
    for v in reversed(vitales):
        if v.get("paciente") == paciente_sel:
            _vit_last_fecha = str(v.get("fecha", ""))
            break
    _vit_cache_hash = f"{len(vitales)}:{_vit_last_fecha}"
    if vit_cached and vit_cached.get("hash") == _vit_cache_hash:
        vitales_orden = vit_cached["top3"]
    else:
        vitales_orden = []
        for v in reversed(vitales):
            if v.get("paciente") != paciente_sel:
                continue
            vitales_orden.append(v)
            if len(vitales_orden) >= 3:
                break
        st.session_state[vit_cache_key] = {"hash": _vit_cache_hash, "top3": vitales_orden}

    st.sidebar.divider()
    st.sidebar.write("**Contexto clínico**")
    st.sidebar.caption("Panel rápido del paciente")
    if alergias:
        st.sidebar.warning(f"⚠️ Alergias: {alergias}")
    else:
        st.sidebar.caption("Sin alergias cargadas.")

    if vitales_orden:
        _sem = semaforo_vital_sidebar(vitales_orden[0])
        _fecha_v = vitales_orden[0].get("fecha", "S/D")[:16]
        st.sidebar.caption(f"{_sem} Últimos signos vitales — {escape(_fecha_v)}")
        v = vitales_orden[0]
        c1, c2, c3 = st.sidebar.columns(3)
        c1.metric("TA", _vitales_valor_corto(v, "TA"))
        c2.metric("FC", _vitales_valor_corto(v, "FC"))
        c3.metric("FR", _vitales_valor_corto(v, "FR"))
        c4, c5, c6 = st.sidebar.columns(3)
        c4.metric("SatO₂", _vitales_valor_corto(v, "Sat"))
        c5.metric("Temp", _vitales_valor_corto(v, "Temp"))
        c6.metric("HGT", _vitales_valor_corto(v, "HGT"))
    else:
        st.sidebar.caption("⚪ Sin registros vitales recientes.")

    evoluciones = st.session_state.get("evoluciones_db", [])
    evs_pac = [e for e in evoluciones if e.get("paciente") == paciente_sel]
    if evs_pac:
        ultima_ev = max(evs_pac, key=lambda x: x.get("fecha", ""))
        _prof_ev = (ultima_ev.get("firma") or "S/D")[:22]
        _fecha_ev = ultima_ev.get("fecha", "S/D")[:16]
        _nota_ev = str(ultima_ev.get("nota", ""))[:80].replace("\n", " ")
        st.sidebar.caption(f"📝 Última evolución: **{_fecha_ev}** — {_prof_ev}")
        if _nota_ev:
            st.sidebar.caption(f"{_nota_ev}{'...' if len(str(ultima_ev.get('nota', ''))) > 80 else ''}")
    else:
        st.sidebar.caption("📝 Sin evoluciones registradas.")

    indicaciones = st.session_state.get("indicaciones_db", [])
    activas = [
        r for r in indicaciones
        if r.get("paciente") == paciente_sel
        and str(r.get("estado_receta", "Activa")).strip().lower() not in ("suspendida", "cancelada")
        and r.get("tipo_indicacion", "Medicacion") == "Medicacion"
    ]
    if activas:
        st.sidebar.caption(f"💊 Medicación activa ({len(activas)} indicación/es):")
        for med in activas[:3]:
            _nom = (med.get("med") or "")[:40]
            _frec = (med.get("frecuencia") or med.get("via") or "")[:20]
            st.sidebar.caption(f"  • {_nom}" + (f" — {_frec}" if _frec else ""))
        if len(activas) > 3:
            st.sidebar.caption(f"  ... y {len(activas) - 3} más")
    else:
        st.sidebar.caption("💊 Sin medicación activa.")

    st.sidebar.caption("Diagnósticos activos")
    if patologias:
        st.sidebar.write(f"- {escape(patologias)}")
    else:
        st.sidebar.caption("Sin diagnósticos cargados.")


# ---------------------------------------------------------------------------
# Selector de pacientes + alertas en sidebar
# ---------------------------------------------------------------------------

def render_sidebar_pacientes_y_alertas(mi_empresa, rol, obtener_pacientes_fn, obtener_alertas_fn,
                                        mapa_detalles_fn, es_control_total_fn,
                                        valor_por_modo_liviano_fn, limite_pacientes_fn):
    st.markdown(
        """
        <div class="mc-sidebar-section">
            <div class="mc-sidebar-kicker">Pacientes</div>
            <div class="mc-sidebar-title">Buscador y seleccion</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    buscar = st.text_input("Buscar Paciente", placeholder="Nombre, DNI o palabra clave", key="mc_buscar_paciente")
    ver_altas = st.checkbox("Mostrar Pacientes de Alta", key="mc_ver_altas") if es_control_total_fn(rol) else False

    p_f = obtener_pacientes_fn(
        st.session_state,
        mi_empresa,
        rol,
        incluir_altas=ver_altas,
        busqueda=buscar,
    )
    limite_pacientes = valor_por_modo_liviano_fn(limite_pacientes_fn(), 36, st.session_state)
    if not buscar and len(p_f) > limite_pacientes:
        st.caption(f"Mostrando los primeros {limite_pacientes} pacientes. Escribi para filtrar y ahorrar memoria.")
        p_f = p_f[:limite_pacientes]

    if not p_f and buscar:
        st.caption("No hay pacientes que coincidan con la busqueda.")
    elif p_f:
        st.caption(f"{len(p_f)} paciente(s) visibles")

    paciente_actual = st.session_state.get("paciente_actual")
    opciones_ids = [item[0] for item in p_f]
    index_actual = opciones_ids.index(paciente_actual) if paciente_actual in opciones_ids else 0

    _stored_sel = st.session_state.get("paciente_actual_select")
    if isinstance(_stored_sel, tuple):
        st.session_state.pop("paciente_actual_select", None)

    _display_map = {item[0]: item[1] for item in p_f} if p_f else {}
    paciente_sel = (
        st.selectbox(
            "Seleccionar Paciente",
            opciones_ids,
            index=index_actual,
            format_func=lambda x: _display_map.get(x, x),
            key="paciente_actual_select",
        )
        if p_f
        else None
    )
    paciente_prev = st.session_state.get("paciente_actual")
    if paciente_sel:
        st.session_state["paciente_actual"] = paciente_sel
        # El selectbox de Streamlit ya dispara rerun nativo al cambiar;
        # st.rerun() adicional causa doble recarga innecesaria.
        det_sidebar = mapa_detalles_fn(st.session_state).get(paciente_sel, {})
        sidebar_patient_card(paciente_sel, det_sidebar)

    if paciente_sel:
        alertas = obtener_alertas_fn(st.session_state, paciente_sel)
        if alertas:
            with st.expander(f"🚨 Alertas clínicas ({len(alertas)})", expanded=True):
                for alerta in alertas:
                    nivel = str(alerta.get("nivel", "media")).lower()
                    msg = f"**{escape(alerta['titulo'])}**  \n{escape(alerta['detalle'])}"
                    if nivel == "critica":
                        st.error(msg)
                    elif nivel == "alta":
                        st.warning(msg)
                    else:
                        st.info(msg)
    return paciente_sel
