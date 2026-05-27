from __future__ import annotations

from core.alert_toasts import queue_toast
import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core._patient_index import get_patient_records
from core.view_helpers import aviso_sin_paciente, bloque_mc_grid_tarjetas, lista_plegable
from core.utils import ahora, mapa_detalles_pacientes, mostrar_dataframe_con_scroll, registrar_auditoria_legal, seleccionar_limite_registros
from core.db_sql import get_escalas_by_paciente, insert_escala
from core.nextgen_sync import _obtener_uuid_empresa, _obtener_uuid_paciente
from core.app_logging import log_event

ESCALAS = ["Glasgow", "Braden", "Barthel", "EVA"]

GLASGOW_ITEMS = {
    "Ocular": {"icono": "👁️", "opts": {1: "No abre los ojos", 2: "Al dolor", 3: "Al llamado", 4: "Espontánea"}},
    "Verbal": {"icono": "🗣️", "opts": {1: "Sin respuesta", 2: "Sonidos incomprensibles", 3: "Palabras inapropiadas", 4: "Desorientado / confuso", 5: "Orientado / conversa"}},
    "Motora": {"icono": "🏃", "opts": {1: "Sin respuesta", 2: "Extensión al dolor", 3: "Flexión al dolor", 4: "Retirada al dolor", 5: "Localiza el dolor", 6: "Obedece órdenes"}},
}

BRADEN_ITEMS = {
    "Percepción sensorial": {"icono": "🧠", "opts": {1: "Completamente limitado", 2: "Muy limitado", 3: "Ligeramente limitado", 4: "Sin limitación"}},
    "Humedad": {"icono": "💧", "opts": {1: "Constantemente húmeda", 2: "Muy húmeda", 3: "Ocasionalmente húmeda", 4: "Raramente húmeda"}},
    "Actividad": {"icono": "🏃", "opts": {1: "En cama", 2: "Puede sentarse", 3: "Camina ocasionalmente", 4: "Camina frecuentemente"}},
    "Movilidad": {"icono": "🔄", "opts": {1: "Completamente inmóvil", 2: "Muy limitada", 3: "Ligeramente limitada", 4: "Sin limitación"}},
    "Nutrición": {"icono": "🍽️", "opts": {1: "Muy pobre", 2: "Probablemente inadecuada", 3: "Adecuada", 4: "Excelente"}},
    "Fricción / roce": {"icono": "⚡", "opts": {1: "Problema severo", 2: "Problema potencial", 3: "Sin problema aparente"}},
}

EVA_FACES = {
    0: "😊 Sin dolor", 1: "🙂 1", 2: "😐 2", 3: "😐 3",
    4: "😣 4", 5: "😣 5", 6: "😣 6",
    7: "😫 7", 8: "😫 8", 9: "😫 9", 10: "😖 10",
}

CSS = """
<style>
.escala-card {
    background: rgba(15,23,42,0.5);
    border: 1px solid rgba(51,65,85,0.3);
    border-radius: 12px;
    padding: 14px 16px;
    margin: 4px 0;
}
.escala-card .ec-titulo {
    font-size:0.78rem;
    font-weight:700;
    text-transform:uppercase;
    letter-spacing:0.06em;
    color:#94a3b8;
    margin-bottom:6px;
}
.escala-card .ec-valor {
    font-size:1.5rem;
    font-weight:800;
    color:#f1f5f9;
}
.escala-card .ec-desc {
    font-size:0.82rem;
    color:#64748b;
    margin-top:2px;
}
.escala-badge {
    display:inline-block;
    padding:2px 10px;
    border-radius:20px;
    font-size:0.72rem;
    font-weight:700;
    text-transform:uppercase;
    letter-spacing:0.04em;
}
.eva-container {
    background: linear-gradient(135deg, rgba(34,197,94,0.08) 0%, rgba(239,68,68,0.08) 100%);
    border-radius: 16px;
    padding: 24px;
    text-align: center;
    border: 1px solid rgba(148,163,184,0.15);
}
.eva-emoji {
    font-size: 4rem;
    line-height: 1.1;
    transition: all 0.2s;
}
.eva-score {
    font-size: 2rem;
    font-weight: 800;
    margin-top: 4px;
}
.eva-label {
    font-size: 0.88rem;
    font-weight: 600;
    color: #94a3b8;
    margin-top: 2px;
}
.result-card {
    border-radius: 14px;
    padding: 20px 22px;
    margin: 12px 0;
    display: flex;
    align-items: center;
    gap: 16px;
}
.result-card .rc-icon {
    font-size: 2.4rem;
    flex-shrink: 0;
}
.result-card .rc-content {
    flex: 1;
}
.result-card .rc-label {
    font-size:0.72rem;
    font-weight:700;
    text-transform:uppercase;
    letter-spacing:0.08em;
    margin-bottom:2px;
}
.result-card .rc-title {
    font-size:1.3rem;
    font-weight:800;
    margin:2px 0;
}
.result-card .rc-puntos {
    font-size:1rem;
    font-weight:600;
    opacity:0.85;
}
.result-card .rc-detail {
    font-size:0.9rem;
    opacity:0.75;
    margin-top:4px;
}
</style>
"""


def _glasgow(ocular, verbal, motora):
    return ocular + verbal + motora


def _braden(*args):
    return sum(args)


def _interpretacion(escala, puntaje):
    mapa = {
        "Glasgow": [(0, "Compromiso severo", "Monitoreo intensivo y aviso médico inmediato.", "#ef4444", "🧠"),
                    (9, "Compromiso moderado", "Revalorar neurología y seguimiento estrecho.", "#f59e0b", "🧠"),
                    (13, "Leve / normal", "Continuar control evolutivo según cuadro clínico.", "#22c55e", "🧠")],
        "Braden": [(0, "Alto riesgo UPP", "Rotación, alivio de presión y vigilancia de piel.", "#ef4444", "🛏️"),
                   (13, "Riesgo moderado", "Implementar medidas preventivas y control diario.", "#f59e0b", "🛏️"),
                   (17, "Bajo riesgo", "Mantener prevención básica y reevaluación periódica.", "#22c55e", "🛏️")],
        "Barthel": [(0, "Dependencia total", "Requiere apoyo integral y plan intensivo de cuidados.", "#ef4444", "🚶"),
                    (21, "Dependencia severa", "Priorizar asistencia funcional y seguimiento familiar.", "#f59e0b", "🚶"),
                    (61, "Dependencia leve/moderada", "Promover autonomía supervisada y reevaluación.", "#38bdf8", "🚶"),
                    (100, "Independiente", "Mantener control periódico y objetivos de sostén.", "#22c55e", "🚶")],
        "EVA": [(0, "Sin dolor", "Sin analgesia adicional inmediata.", "#22c55e", "😊"),
                (1, "Dolor leve", "Continuar seguimiento del dolor y respuesta clínica.", "#38bdf8", "🙂"),
                (4, "Dolor moderado", "Revisar analgesia indicada y reevaluar pronto.", "#f59e0b", "😣"),
                (7, "Dolor severo", "Escalar manejo del dolor y notificar conducta médica.", "#ef4444", "😫")],
    }
    for umbral, titulo, detalle, color, icono in reversed(mapa.get(escala, [])):
        if puntaje >= umbral:
            return {"titulo": titulo, "detalle": detalle, "color": color, "icono": icono,
                    "fondo": {"#ef4444": "rgba(239,68,68,0.12)", "#f59e0b": "rgba(245,158,11,0.14)",
                              "#22c55e": "rgba(34,197,94,0.12)", "#38bdf8": "rgba(56,189,248,0.12)"}.get(color, "rgba(56,189,248,0.12)")}
    return {"titulo": "Sin datos", "detalle": "", "color": "#94a3b8", "icono": "📋", "fondo": "rgba(148,163,184,0.08)"}


def _render_selectbox_item(icono, label, opts, key):
    opts_labels = {k: f"{'★' * (k if k < 4 else k-2) if max(opts.keys()) == 4 or max(opts.keys()) in (5,6) else ''} {v}" for k, v in opts.items()}
    st.markdown(f"<div style='font-size:0.8rem;font-weight:600;color:#94a3b8;margin-bottom:4px;'>{icono} {label}</div>", unsafe_allow_html=True)
    return st.selectbox("", list(opts.keys()), format_func=lambda x: opts.get(x, ""), index=max(opts.keys()) - 1, label_visibility="collapsed", key=key)


def _resolver_uuid_paciente_sql(paciente_sel, empresa):
    partes = str(paciente_sel or "").rsplit(" - ", 1)
    dni = partes[1].strip() if len(partes) == 2 else ""
    empresa_id = _obtener_uuid_empresa(empresa) if empresa else None
    return _obtener_uuid_paciente(dni, empresa_id) if dni and empresa_id else None


def _render_evolucion_eva(puntaje):
    color = "#22c55e" if puntaje == 0 else "#38bdf8" if puntaje <= 3 else "#f59e0b" if puntaje <= 6 else "#ef4444"
    emoji = EVA_FACES.get(puntaje, "😊").split(" ")[0]
    label = _interpretacion("EVA", puntaje)["titulo"]
    st.markdown(
        f'<div class="eva-container" style="border-color:{color}40;">'
        f'<div class="eva-emoji">{emoji}</div>'
        f'<div class="eva-score" style="color:{color};">{puntaje}/10</div>'
        f'<div class="eva-label">{label}</div></div>',
        unsafe_allow_html=True,
    )


def render_escalas_clinicas(paciente_sel, user):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    if not st.session_state.get("_escalas_css"):
        st.session_state["_escalas_css"] = True
        st.markdown(CSS, unsafe_allow_html=True)

    detalles = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})
    empresa_actual = str(detalles.get("empresa") or user.get("empresa", "") or st.session_state.get("u_actual", {}).get("empresa") or st.session_state.get("user", {}).get("empresa") or "").strip()

    registros = []
    try:
        paciente_uuid = _resolver_uuid_paciente_sql(paciente_sel, empresa_actual)
        if paciente_uuid:
            for e in get_escalas_by_paciente(paciente_uuid) or []:
                dt = pd.to_datetime(e.get("fecha_registro", ""), errors="coerce")
                registros.append({
                    "paciente": paciente_sel,
                    "fecha": dt.strftime("%d/%m/%Y %H:%M:%S") if pd.notnull(dt) else e.get("fecha_registro", ""),
                    "escala": e.get("tipo_escala", ""),
                    "puntaje": e.get("puntaje_total", 0),
                    "interpretacion": e.get("interpretacion", ""),
                    "observaciones": e.get("observaciones", ""),
                    "profesional": e.get("usuarios", {}).get("nombre", "Desconocido") if isinstance(e.get("usuarios"), dict) else "Desconocido",
                })
    except Exception as e:
        log_event("error_leer_escalas_sql", str(e))

    if not registros:
        registros = get_patient_records("escalas_clinicas_db", paciente_sel)
        registros.sort(key=lambda x: x.get("fecha", ""), reverse=True)

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Escalas clínicas</h2>
            <p class="mc-hero-text">Evaluación estructurada con lectura automatizada del puntaje para apoyo a la decisión clínica.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">🧠 Glasgow</span>
                <span class="mc-chip">🛏️ Braden</span>
                <span class="mc-chip">🚶 Barthel</span>
                <span class="mc-chip">😊 EVA</span>
            </div>
        </div>
        """, unsafe_allow_html=True,
    )

    escala = st.radio("Seleccionar escala", ESCALAS, horizontal=True, label_visibility="collapsed")
    form_key = f"es_f{escala}"

    with st.container(border=True):
        resumen = ""
        puntaje = 0

        if escala == "Glasgow":
            st.markdown("##### 🧠 Escala de Coma de Glasgow")
            st.caption("Evalúa el nivel de conciencia mediante tres componentes")
            c1, c2, c3 = st.columns(3)
            with c1:
                ocular = _render_selectbox_item("👁️", "Apertura ocular", GLASGOW_ITEMS["Ocular"]["opts"], f"gl_o_{form_key}")
            with c2:
                verbal = _render_selectbox_item("🗣️", "Respuesta verbal", GLASGOW_ITEMS["Verbal"]["opts"], f"gl_v_{form_key}")
            with c3:
                motora = _render_selectbox_item("🏃", "Respuesta motora", GLASGOW_ITEMS["Motora"]["opts"], f"gl_m_{form_key}")
            puntaje = _glasgow(ocular, verbal, motora)
            col_g1, _, col_g2 = st.columns([2, 1, 2])
            col_g1.markdown(
                f"<div class='escala-card'><div class='ec-titulo'>Puntaje total Glasgow</div>"
                f"<div class='ec-valor'>{puntaje}/15</div>"
                f"<div class='ec-desc'>Ocular {ocular} + Verbal {verbal} + Motora {motora}</div></div>",
                unsafe_allow_html=True,
            )

        elif escala == "Braden":
            st.markdown("##### 🛏️ Escala de Braden")
            st.caption("Valora el riesgo de úlceras por presión (UPP) en seis sub-puntajes")
            items = list(BRADEN_ITEMS.items())
            c_left, c_right = st.columns(2)
            vals = {}
            for i, (nombre, info) in enumerate(items[:3]):
                with c_left:
                    vals[nombre] = _render_selectbox_item(info["icono"], nombre, info["opts"], f"br_{i}_{form_key}")
            for i, (nombre, info) in enumerate(items[3:]):
                with c_right:
                    vals[nombre] = _render_selectbox_item(info["icono"], nombre, info["opts"], f"br_{i+3}_{form_key}")
            puntaje = _braden(*vals.values())
            col_b1, _, col_b2 = st.columns([2, 1, 2])
            col_b1.markdown(
                f"<div class='escala-card'><div class='ec-titulo'>Puntaje total Braden</div>"
                f"<div class='ec-valor'>{puntaje}/23</div>"
                f"<div class='ec-desc'>Menor puntaje = mayor riesgo de UPP</div></div>",
                unsafe_allow_html=True,
            )

        elif escala == "Barthel":
            st.markdown("##### 🚶 Índice de Barthel")
            st.caption("Mide la capacidad funcional y dependencia en actividades de la vida diaria")
            puntaje = st.slider("", 0, 100, 60, 5, label_visibility="collapsed", key=f"bar_{form_key}")
            bar_cat = "Dependencia total" if puntaje <= 20 else "Dependencia severa" if puntaje <= 60 else "Dependencia leve/moderada" if puntaje < 100 else "Independiente"
            col_ba1, col_ba2, col_ba3 = st.columns([2, 1, 2])
            col_ba1.markdown(
                f"<div class='escala-card'><div class='ec-titulo'>Índice de Barthel</div>"
                f"<div class='ec-valor'>{puntaje}/100</div>"
                f"<div class='ec-desc'>{bar_cat}</div></div>",
                unsafe_allow_html=True,
            )
            resumen = bar_cat

        else:
            st.markdown("##### 😊 Escala Visual Analógica (EVA)")
            st.caption("Evalúa la intensidad del dolor reportado por el paciente")
            col_e1, col_e2 = st.columns([2, 1])
            with col_e1:
                puntaje = st.select_slider("", options=list(range(11)), value=0,
                    format_func=lambda x: EVA_FACES.get(x, str(x)),
                    label_visibility="collapsed", key=f"eva_{form_key}")
            with col_e2:
                _render_evolucion_eva(puntaje)
            resumen = "Sin dolor" if puntaje == 0 else "Dolor leve" if puntaje <= 3 else "Dolor moderado" if puntaje <= 6 else "Dolor severo"

        if escala not in ("Barthel",):
            resumen = "Compromiso severo" if escala == "Glasgow" and puntaje <= 8 else "Compromiso moderado" if escala == "Glasgow" and puntaje <= 12 else "Leve / normal" if escala == "Glasgow" else "Alto riesgo UPP" if escala == "Braden" and puntaje <= 12 else "Riesgo moderado" if escala == "Braden" and puntaje <= 16 else "Bajo riesgo" if escala == "Braden" else "Sin dolor" if puntaje == 0 else "Dolor leve" if puntaje <= 3 else "Dolor moderado" if puntaje <= 6 else "Dolor severo"

        card = _interpretacion(escala, puntaje)
        st.markdown(
            f'<div class="result-card" style="background:{card["fondo"]};border:1px solid {card["color"]}40;">'
            f'<div class="rc-icon">{card["icono"]}</div>'
            f'<div class="rc-content">'
            f'<div class="rc-label" style="color:{card["color"]};">{card["titulo"]}</div>'
            f'<div class="rc-puntos" style="color:{card["color"]};">{puntaje} pts</div>'
            f'<div class="rc-detail">{card["detalle"]}</div>'
            f'</div></div>', unsafe_allow_html=True,
        )

        observaciones = st.text_area("📝 Observaciones clínicas", height=80, key=f"obs_{form_key}")

        if st.button(f"💾 Registrar {escala}", width='stretch', type="primary", key=f"sv_{form_key}"):
            fecha_str = ahora().strftime("%d/%m/%Y %H:%M:%S")
            try:
                paciente_uuid = _resolver_uuid_paciente_sql(paciente_sel, empresa_actual)
                if paciente_uuid:
                    insert_escala({"paciente_id": paciente_uuid, "fecha_registro": ahora().isoformat(),
                                   "tipo_escala": escala, "puntaje_total": puntaje, "interpretacion": card["titulo"],
                                   "observaciones": observaciones.strip()})
                    log_event("escala_sql_insert", f"Paciente: {paciente_uuid}")
            except Exception as e:
                log_event("error_escala_sql", str(e))
            nuevo = {"paciente": paciente_sel, "fecha": fecha_str, "escala": escala, "puntaje": puntaje,
                     "interpretacion": card["titulo"], "observaciones": observaciones.strip(),
                     "profesional": user.get("nombre", ""), "matricula": user.get("matricula", "")}
            if "escalas_clinicas_db" not in st.session_state:
                st.session_state["escalas_clinicas_db"] = []
            st.session_state["escalas_clinicas_db"].append(nuevo)
            from core.database import _trim_db_list
            _trim_db_list("escalas_clinicas_db", 500)
            registrar_auditoria_legal("Escala Clinica", paciente_sel, f"Registro {escala}",
                                      user.get("nombre", ""), user.get("matricula", ""), f"Puntaje: {puntaje} | {card['titulo']}")
            guardar_datos(spinner=True)
            queue_toast(f"Escala {escala} registrada.")
            st.rerun()

    # ── Alerta empeoramiento ──
    registros_misma_escala = [r for r in registros if r.get("escala") == escala]
    if len(registros_misma_escala) >= 2 and puntaje > 0:
        _sorted = sorted(registros_misma_escala, key=lambda x: x.get("fecha", ""))
        p_prev = _sorted[-2].get("puntaje", 0)
        p_actual = puntaje
        menor_es_peor = escala in {"Glasgow", "Braden", "Barthel"}
        empeoro = p_actual < p_prev if menor_es_peor else p_actual > p_prev
        mejoro = p_actual > p_prev if menor_es_peor else p_actual < p_prev
        delta_val = p_actual - p_prev
        if empeoro:
            st.warning(f"⚠️ **{escala} empeoró**: anterior {p_prev} → actual {p_actual} ({'+' if delta_val > 0 else ''}{delta_val} pts). Revisar conducta.")
        elif mejoro:
            st.success(f"✅ **{escala} mejoró**: anterior {p_prev} → actual {p_actual} ({'+' if delta_val > 0 else ''}{delta_val} pts).")

    # ── Historial ──
    st.divider()
    st.markdown("### 📋 Historial de escalas")
    if not registros:
        st.info("Todavía no hay escalas registradas para este paciente.")
        return

    escalas_con_data = {}
    for r in registros:
        e_key = r.get("escala", "")
        if e_key and (e_key not in escalas_con_data or r.get("fecha", "") > escalas_con_data[e_key].get("fecha", "")):
            escalas_con_data[e_key] = r

    if escalas_con_data:
        st.markdown("##### Último registro por escala")
        _cols = st.columns(len(escalas_con_data))
        for idx, (e_key, r) in enumerate(escalas_con_data.items()):
            ic = _interpretacion(e_key, r.get("puntaje", 0))
            with _cols[idx].container(border=True):
                st.markdown(f"<div style='font-size:1.8rem;text-align:center;'>{ic['icono']}</div>", unsafe_allow_html=True)
                st.metric(f"{e_key}", f"{r.get('puntaje', '?')} pts",
                          delta=r.get("interpretacion") or r.get("resumen", ""), delta_color="off")
                st.caption(r.get("fecha", "")[:16])

    df_hist = pd.DataFrame(registros)
    if not df_hist.empty and "escala" in df_hist.columns and "puntaje" in df_hist.columns:
        df_hist["puntaje"] = pd.to_numeric(df_hist["puntaje"], errors="coerce")
        df_hist["fecha_dt"] = pd.to_datetime(df_hist["fecha"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
        df_hist = df_hist.dropna(subset=["fecha_dt"]).sort_values("fecha_dt")
        escalas_presentes = [e for e in ESCALAS if e in df_hist["escala"].values]
        if escalas_presentes:
            st.markdown("##### Evolución por escala")
            for e_key in escalas_presentes:
                df_e = df_hist[df_hist["escala"] == e_key].set_index("fecha_dt")["puntaje"]
                if len(df_e) >= 2:
                    st.caption(f"{_interpretacion(e_key, 0)['icono']} {e_key} ({len(df_e)} registros)")
                    st.line_chart(df_e, width='stretch', height=130)

    limite = seleccionar_limite_registros("Escalas a mostrar", len(registros), key=f"lim_esc_{paciente_sel}", default=30)
    with lista_plegable(f"📄 Historial completo de escalas", count=min(limite, len(registros)), expanded=False, height=460):
        mostrar_dataframe_con_scroll(pd.DataFrame(registros[-limite:]).drop(columns=["paciente"], errors="ignore").iloc[::-1], height=400)
