from __future__ import annotations

"""Componentes del sidebar clínico de MediCare PRO.

Extraído de main.py para mantenerlo liviano.
Contiene: tarjeta de marca, tarjeta de paciente, panel de signos vitales,
contexto clínico rápido (semáforo, evolución, medicación) y selector de pacientes.
"""
import time
from html import escape

import streamlit as st

from core.app_logging import log_event
from core.utils_pacientes import estado_pacientes_sql, set_paciente_actual


def _cached_contexto(paciente_sel):
    """Retorna contexto clínico cacheado 10s en session_state."""
    _cache_key = f"_ctx_cache_{paciente_sel}"
    _cache_ts = f"_ctx_cache_ts_{paciente_sel}"
    now = time.time()
    cached = st.session_state.get(_cache_key)
    cached_ts = st.session_state.get(_cache_ts, 0.0)
    if cached is not None and (now - cached_ts) < 10.0:
        return cached
    from core.utils import mapa_detalles_pacientes
    detalles = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {}) or {}
    vitales = st.session_state.get("vitales_db", [])
    evoluciones = st.session_state.get("evoluciones_db", [])
    indicaciones = st.session_state.get("indicaciones_db", [])
    vitales_top3 = []
    for v in reversed(vitales):
        if v.get("paciente") != paciente_sel:
            continue
        vitales_top3.append(v)
        if len(vitales_top3) >= 3:
            break
    evs_pac = [e for e in evoluciones if e.get("paciente") == paciente_sel]
    ultima_ev = max(evs_pac, key=lambda x: x.get("fecha", "")) if evs_pac else None
    activas = [
        r for r in indicaciones
        if r.get("paciente") == paciente_sel
        and str(r.get("estado_receta", "Activa")).strip().lower() not in ("suspendida", "cancelada")
        and r.get("tipo_indicacion", "Medicacion") == "Medicacion"
    ]
    result = {"detalles": detalles, "vitales_top3": vitales_top3, "ultima_ev": ultima_ev, "activas": activas, "ultimo_mes": None, "ultimo_ano": None}
    
    # Determinar ultimo mes con datos del paciente
    _fechas = []
    for r in vitales:
        if r.get("paciente") == paciente_sel and r.get("fecha"):
            _fechas.append(r.get("fecha", ""))
    for r in evoluciones:
        if r.get("paciente") == paciente_sel and r.get("fecha"):
            _fechas.append(r.get("fecha", ""))
    for c in st.session_state.get("consumos_db", []):
        if c.get("paciente") == paciente_sel and c.get("fecha"):
            _fechas.append(c.get("fecha", ""))
    if _fechas:
        _fechas.sort(reverse=True)
        _ultima = _fechas[0][:10]
        try:
            from datetime import datetime
            _dt = datetime.strptime(_ultima, "%d/%m/%Y") if "/" in _ultima else datetime.fromisoformat(_ultima)
            meses = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
            result["ultimo_mes"] = meses[_dt.month]
            result["ultimo_ano"] = str(_dt.year)
        except Exception:
            pass
    
    st.session_state[_cache_key] = result
    st.session_state[_cache_ts] = now
    return result


def _foto_img_mime(b64: str) -> str:
    """Detecta MIME de imagen base64 por su header."""
    if not b64:
        return "image/jpeg"
    if b64.startswith("iVBOR"):
        return "image/png"
    if b64.startswith("R0lG"):
        return "image/gif"
    return "image/jpeg"


# ---------------------------------------------------------------------------
# Tarjetas de marca y paciente
# ---------------------------------------------------------------------------

def sidebar_patient_card(paciente_sel, detalles):
    with st.container(border=True):
        st.write("**Paciente activo**")
        foto_b64 = detalles.get("foto_perfil", "")
        if foto_b64:
            _mime = _foto_img_mime(foto_b64)
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;margin:4px 0;">'
                f'<img src="data:{_mime};base64,{foto_b64}" '
                f'style="width:48px;height:48px;border-radius:50%;object-fit:cover;'
                f'border:2px solid rgba(20,184,166,0.3);flex-shrink:0;">'
                f'<div><strong>{escape(paciente_sel)}</strong></div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.write(f"{escape(paciente_sel)}")
        
        # Mostrar ultimo mes con datos (rojo si es el mes actual)
        ctx = _cached_contexto(paciente_sel)
        _mes = ctx.get("ultimo_mes")
        _ano = ctx.get("ultimo_ano")
        if _mes and _ano:
            from datetime import datetime
            _hoy = datetime.now()
            meses = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
            _mes_actual = meses[_hoy.month]
            _es_actual = (_mes == _mes_actual and _ano == str(_hoy.year))
            _color = "#ef4444" if _es_actual else "#64748b"
            st.markdown(
                f'<span style="color:{_color};font-size:0.8rem;font-weight:600;">'
                f'{"● " if _es_actual else ""}Ult. datos: {_mes} {_ano}</span>',
                unsafe_allow_html=True,
            )
        
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

    ctx = _cached_contexto(paciente_sel)
    detalles = ctx["detalles"]
    vitales_orden = ctx["vitales_top3"]
    ultima_ev = ctx["ultima_ev"]
    activas = ctx["activas"]
    alergias = str(detalles.get("alergias", "") or "").strip()
    patologias = str(detalles.get("patologias", "") or detalles.get("diagnostico", "") or "").strip()

    st.sidebar.divider()
    # Foto + nombre del paciente
    foto_b64 = detalles.get("foto_perfil", "")
    if foto_b64:
        _mime = _foto_img_mime(foto_b64)
        st.sidebar.markdown(
            f'<div style="display:flex;align-items:center;gap:10px;margin:2px 0 6px;">'
            f'<img src="data:{_mime};base64,{foto_b64}" '
            f'style="width:56px;height:56px;border-radius:50%;object-fit:cover;'
            f'border:2px solid rgba(20,184,166,0.3);flex-shrink:0;">'
            f'<div><strong style="font-size:0.95rem;">{escape(paciente_sel)}</strong></div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.write(f"**{escape(paciente_sel)}**")
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

    if ultima_ev:
        _prof_ev = (ultima_ev.get("firma") or "S/D")[:22]
        _fecha_ev = ultima_ev.get("fecha", "S/D")[:16]
        _nota_ev = str(ultima_ev.get("nota", ""))[:80].replace("\n", " ")
        st.sidebar.caption(f"📝 Última evolución: **{_fecha_ev}** — {_prof_ev}")
        if _nota_ev:
            st.sidebar.caption(f"{_nota_ev}{'...' if len(str(ultima_ev.get('nota', ''))) > 80 else ''}")
    else:
        st.sidebar.caption("📝 Sin evoluciones registradas.")

    if activas:
        st.sidebar.caption(f"💊 Medicación activa ({len(activas)} indicación/es):")
        for med in activas[:3]:
            _nom = (med.get("med") or "")[:40]
            _frec = (med.get("frecuencia") or med.get("via") or "")[:20]
            st.sidebar.caption(f"  • {_nom}" + (f" — {_frec}" if _frec else ""))
        if len(activas) > 3:
            st.sidebar.caption(f"  ... y {len(activas) - 3} más")

    if alergias:
        try:
            from core.alertas_medicacion import verificar_alergias_medicacion
            alertas = verificar_alergias_medicacion(paciente_sel)
            for a in alertas:
                st.sidebar.error(f"🚨 {a['mensaje'][:120]}", icon=None)
        except Exception as _e:
            log_event("sidebar", f"alerta_medicacion:{type(_e).__name__}")

    st.sidebar.caption("Diagnósticos activos")
    if patologias:
        st.sidebar.write(f"- {escape(patologias)}")
    else:
        st.sidebar.caption("Sin diagnósticos cargados.")

    _help_key = "_ai_sidebar_show_help"
    if st.sidebar.button("💡 Ayuda IA para este módulo", key="_ai_sidebar_help", use_container_width=True):
        st.session_state[_help_key] = not st.session_state.get(_help_key, False)
        st.rerun()
    if st.session_state.get(_help_key, False):
        from core.ai_context import get_view_help, get_view_tips
        ayuda = get_view_help(vista_actual)
        st.sidebar.info(ayuda)
        tips = get_view_tips(vista_actual)
        for tip in tips:
            st.sidebar.caption(f"💡 {tip}")
        if st.sidebar.button("Cerrar ayuda", key="_ai_sidebar_help_close", use_container_width=True):
            st.session_state[_help_key] = False
            st.rerun()


# ---------------------------------------------------------------------------
# Contexto clínico para móvil (sidebar no visible en mobile)
# ---------------------------------------------------------------------------

def render_mobile_contexto_clinico(paciente_sel):
    """Renderiza el panel de contexto clínico en el área principal,
    visible solo en móviles (donde el sidebar está oculto)."""
    st.markdown('<div class="mc-mobile-only">', unsafe_allow_html=True)

    ctx = _cached_contexto(paciente_sel)
    detalles = ctx["detalles"]
    vitales_orden = ctx["vitales_top3"]
    ultima_ev = ctx["ultima_ev"]
    activas = ctx["activas"]
    alergias = str(detalles.get("alergias", "") or "").strip()
    patologias = str(detalles.get("patologias", "") or "").strip()

    # Foto + nombre
    foto_b64 = detalles.get("foto_perfil", "")
    if foto_b64:
        _mime = _foto_img_mime(foto_b64)
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:10px;margin:4px 0;">'
            f'<img src="data:{_mime};base64,{foto_b64}" '
            f'style="width:36px;height:36px;border-radius:50%;object-fit:cover;'
            f'border:2px solid rgba(20,184,166,0.3);flex-shrink:0;">'
            f'<strong>{escape(paciente_sel)}</strong></div>',
            unsafe_allow_html=True,
        )
    else:
        st.write(f"**{escape(paciente_sel)}**")

    with st.expander("📋 Contexto clínico", expanded=False):
        if alergias:
            st.warning(f"⚠️ Alergias: {alergias}")
        if vitales_orden:
            v = vitales_orden[0]
            mc1, mc2 = st.columns(2)
            mc1.metric("TA", _vitales_valor_corto(v, "TA"))
            mc1.metric("FC", _vitales_valor_corto(v, "FC"))
            mc1.metric("SatO₂", _vitales_valor_corto(v, "Sat"))
            mc2.metric("FR", _vitales_valor_corto(v, "FR"))
            mc2.metric("Temp", _vitales_valor_corto(v, "Temp"))
            mc2.metric("HGT", _vitales_valor_corto(v, "HGT"))
            _fecha_v = vitales_orden[0].get("fecha", "S/D")[:16]
            st.caption(f"Últimos signos — {_fecha_v}")
        if patologias:
            st.caption(f"**Diagnósticos:** {patologias}")
        if alergias:
            st.caption(f"**Alergias:** {alergias}")

        if ultima_ev:
            _nota_ev = str(ultima_ev.get("nota", ""))[:120].replace("\n", " ")
            st.caption(f"**Última evolución:** {_nota_ev}{'...' if len(str(ultima_ev.get('nota', ''))) > 120 else ''}")

        if activas:
            st.caption(f"**Medicación activa ({len(activas)}):**")
            for med in activas[:3]:
                _nom = (med.get("med") or "")[:50]
                _frec = (med.get("frecuencia") or med.get("via") or "")[:25]
                st.caption(f"  • {_nom}" + (f" — {_frec}" if _frec else ""))
            if len(activas) > 3:
                st.caption(f"  ... y {len(activas) - 3} más")

    st.markdown('</div>', unsafe_allow_html=True)


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
    sql_status = estado_pacientes_sql(st.session_state)
    if sql_status and not sql_status.get("ok"):
        st.caption("Modo local/cache activo para pacientes. La conexion SQL no respondio en esta lectura.")

    limite_pacientes = valor_por_modo_liviano_fn(limite_pacientes_fn(), 36, st.session_state)
    if not buscar and len(p_f) > limite_pacientes:
        st.caption(f"Mostrando los primeros {limite_pacientes} pacientes. Escribi para filtrar y ahorrar memoria.")
        p_f = p_f[:limite_pacientes]

    if not p_f and buscar:
        st.caption("No hay pacientes que coincidan con la busqueda.")
        return None
    elif not p_f:
        return None
    elif p_f:
        st.caption(f"{len(p_f)} paciente(s) visibles")

    _SEL_PLACEHOLDER_SB = "__sel__"
    paciente_actual = st.session_state.get("paciente_actual")
    opciones_ids = [_SEL_PLACEHOLDER_SB] + [item[0] for item in p_f]
    # Si hay un paciente activo previamente seleccionado por el usuario, mantenerlo
    if paciente_actual and paciente_actual in [item[0] for item in p_f]:
        index_actual = opciones_ids.index(paciente_actual)
    else:
        index_actual = 0  # placeholder

    _stored_sel = st.session_state.get("paciente_actual_select")
    if isinstance(_stored_sel, tuple):
        st.session_state.pop("paciente_actual_select", None)

    _display_map = {item[0]: item[1] for item in p_f} if p_f else {}
    _display_map[_SEL_PLACEHOLDER_SB] = "— Seleccionar paciente —"
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
    if paciente_sel and paciente_sel != _SEL_PLACEHOLDER_SB:
        set_paciente_actual(st.session_state, paciente_sel)
        det_sidebar = mapa_detalles_fn(st.session_state).get(paciente_sel, {})
        sidebar_patient_card(paciente_sel, det_sidebar)

    if paciente_sel and paciente_sel != _SEL_PLACEHOLDER_SB:
        alertas = obtener_alertas_fn(st.session_state, paciente_sel)
        if alertas:
            with st.expander(f"🚨 Alertas clínicas ({len(alertas)})", expanded=False):
                for alerta in alertas:
                    nivel = str(alerta.get("nivel", "media")).lower()
                    msg = f"**{escape(alerta['titulo'])}**  \n{escape(alerta['detalle'])}"
                    if nivel == "critica":
                        log_event("sidebar", f"error: alerta_critica:{escape(alerta['titulo'])}")
                        st.error(msg)
                    elif nivel == "alta":
                        st.warning(msg)
                    else:
                        st.info(msg)
    return paciente_sel
