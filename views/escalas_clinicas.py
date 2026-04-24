from core.alert_toasts import queue_toast
import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.view_helpers import aviso_sin_paciente, bloque_mc_grid_tarjetas, lista_plegable
from core.utils import ahora, mapa_detalles_pacientes, mostrar_dataframe_con_scroll, registrar_auditoria_legal, seleccionar_limite_registros
from core.db_sql import get_escalas_by_paciente, insert_escala
from core.nextgen_sync import _obtener_uuid_empresa, _obtener_uuid_paciente
from core.app_logging import log_event


def _glasgow(ocular, verbal, motora):
    return ocular + verbal + motora


def _braden(sensorial, humedad, actividad, movilidad, nutricion, friccion):
    return sensorial + humedad + actividad + movilidad + nutricion + friccion


def _interpretacion_visual(escala, puntaje, resumen):
    base = {
        "titulo": resumen,
        "detalle": "Lectura automatica del puntaje para apoyar la decision clinica.",
        "color": "#38bdf8",
        "fondo": "rgba(56, 189, 248, 0.12)",
    }
    recomendaciones = {
        "Glasgow": {
            "Compromiso severo": ("#ef4444", "Monitoreo intensivo y aviso medico inmediato."),
            "Compromiso moderado": ("#f59e0b", "Revalorar neurologia y seguimiento estrecho."),
            "Leve / normal": ("#22c55e", "Continuar control evolutivo segun cuadro clinico."),
        },
        "Braden": {
            "Alto riesgo UPP": ("#ef4444", "Rotacion, alivio de presion y vigilancia de piel."),
            "Riesgo moderado": ("#f59e0b", "Implementar medidas preventivas y control diario."),
            "Bajo riesgo": ("#22c55e", "Mantener prevencion basica y reevaluacion periodica."),
        },
        "Barthel": {
            "Dependencia total": ("#ef4444", "Requiere apoyo integral y plan intensivo de cuidados."),
            "Dependencia severa": ("#f59e0b", "Priorizar asistencia funcional y seguimiento familiar."),
            "Dependencia leve/moderada": ("#38bdf8", "Promover autonomia supervisada y reevaluacion."),
            "Independiente": ("#22c55e", "Mantener control periodico y objetivos de sostén."),
        },
        "EVA": {
            "Sin dolor": ("#22c55e", "Sin analgesia adicional inmediata."),
            "Dolor leve": ("#38bdf8", "Continuar seguimiento del dolor y respuesta clinica."),
            "Dolor moderado": ("#f59e0b", "Revisar analgesia indicada y reevaluar pronto."),
            "Dolor severo": ("#ef4444", "Escalar manejo del dolor y notificar conducta medica."),
        },
    }
    color, detalle = recomendaciones.get(escala, {}).get(resumen, (base["color"], base["detalle"]))
    base["color"] = color
    base["detalle"] = detalle
    base["fondo"] = {
        "#ef4444": "rgba(239, 68, 68, 0.14)",
        "#f59e0b": "rgba(245, 158, 11, 0.16)",
        "#22c55e": "rgba(34, 197, 94, 0.14)",
    }.get(color, "rgba(56, 189, 248, 0.12)")
    return base


def _resolver_uuid_paciente_sql(paciente_sel, empresa):
    partes = str(paciente_sel or "").rsplit(" - ", 1)
    dni = partes[1].strip() if len(partes) == 2 else ""
    empresa_id = _obtener_uuid_empresa(empresa) if empresa else None
    return _obtener_uuid_paciente(dni, empresa_id) if dni and empresa_id else None


def render_escalas_clinicas(paciente_sel, user):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    detalles = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})
    empresa_actual = str(
        detalles.get("empresa")
        or user.get("empresa", "")
        or st.session_state.get("u_actual", {}).get("empresa")
        or st.session_state.get("user", {}).get("empresa")
        or ""
    ).strip()

    # 1. Intentar leer desde PostgreSQL (Hybrid Read)
    registros = []
    try:
        paciente_uuid = _resolver_uuid_paciente_sql(paciente_sel, empresa_actual)
        if paciente_uuid:
            escalas_sql = get_escalas_by_paciente(paciente_uuid)
            if escalas_sql:
                for e in escalas_sql:
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

    # 2. Fallback a JSON si SQL falla o esta vacio
    if not registros:
        registros = [x for x in st.session_state.get("escalas_clinicas_db", []) if x.get("paciente") == paciente_sel]
        # Ordenar JSON por fecha descendente para igualar SQL
        registros.sort(key=lambda x: x.get("fecha", ""), reverse=True)

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Escalas clinicas</h2>
            <p class="mc-hero-text">Registra puntajes estructurados para neurologia, riesgo de ulceras, dependencia y dolor con lectura rapida del estado del paciente.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Glasgow</span>
                <span class="mc-chip">Braden</span>
                <span class="mc-chip">Barthel</span>
                <span class="mc-chip">EVA</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ("Glasgow / Braden", "Neurologia y riesgo de UPP con lectura automatica."),
            ("Barthel / EVA", "Dependencia funcional y escala de dolor."),
            ("Historial", "Cada registro queda vinculado al paciente."),
        ]
    )
    st.caption(
        "Elegi la escala en el selector; el bloque de abajo cambia los campos. Al guardar, el puntaje y la lectura sugerida quedan en el historial del paciente."
    )

    escala = st.radio("Escala", ["Glasgow", "Braden", "Barthel", "EVA"], horizontal=False)

    with st.container(border=True):
        st.markdown(f"### Registro de {escala}")
        resumen = ""
        puntaje = 0

        if escala == "Glasgow":
            c1, c2, c3 = st.columns(3)
            ocular = c1.selectbox("Respuesta ocular", [1, 2, 3, 4], index=3)
            verbal = c2.selectbox("Respuesta verbal", [1, 2, 3, 4, 5], index=4)
            motora = c3.selectbox("Respuesta motora", [1, 2, 3, 4, 5, 6], index=5)
            puntaje = _glasgow(ocular, verbal, motora)
            resumen = "Compromiso severo" if puntaje <= 8 else "Compromiso moderado" if puntaje <= 12 else "Leve / normal"
            st.metric("Puntaje Glasgow", puntaje)
        elif escala == "Braden":
            c1, c2, c3 = st.columns(3)
            sensorial = c1.selectbox("Percepcion sensorial", [1, 2, 3, 4], index=3)
            humedad = c2.selectbox("Humedad", [1, 2, 3, 4], index=3)
            actividad = c3.selectbox("Actividad", [1, 2, 3, 4], index=3)
            c4, c5, c6 = st.columns(3)
            movilidad = c4.selectbox("Movilidad", [1, 2, 3, 4], index=3)
            nutricion = c5.selectbox("Nutricion", [1, 2, 3, 4], index=3)
            friccion = c6.selectbox("Friccion / roce", [1, 2, 3], index=2)
            puntaje = _braden(sensorial, humedad, actividad, movilidad, nutricion, friccion)
            resumen = "Alto riesgo UPP" if puntaje <= 12 else "Riesgo moderado" if puntaje <= 16 else "Bajo riesgo"
            st.metric("Puntaje Braden", puntaje)
        elif escala == "Barthel":
            puntaje = st.slider("Indice de Barthel", min_value=0, max_value=100, value=60, step=5)
            resumen = "Dependencia total" if puntaje <= 20 else "Dependencia severa" if puntaje <= 60 else "Dependencia leve/moderada" if puntaje < 100 else "Independiente"
            st.metric("Puntaje Barthel", puntaje)
        else:
            puntaje = st.slider("Escala visual analogica del dolor", min_value=0, max_value=10, value=0, step=1)
            resumen = "Sin dolor" if puntaje == 0 else "Dolor leve" if puntaje <= 3 else "Dolor moderado" if puntaje <= 6 else "Dolor severo"
            st.metric("Puntaje EVA", puntaje)

        observaciones = st.text_area("Observaciones", height=90)
        card = _interpretacion_visual(escala, puntaje, resumen)
        st.markdown(
            f"""
            <div style="border:1px solid {card['color']}; background:{card['fondo']}; border-radius:18px; padding:16px 18px; margin:8px 0 12px 0;">
                <div style="font-size:0.82rem; letter-spacing:0.08em; text-transform:uppercase; color:{card['color']}; font-weight:700;">Interpretacion automatica</div>
                <div style="font-size:1.15rem; font-weight:700; color:#f8fafc; margin-top:4px;">{card['titulo']}</div>
                <div style="font-size:0.98rem; color:#cbd5e1; margin-top:6px;">{card['detalle']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(f"Guardar {escala}", use_container_width=True, type="primary"):
            fecha_str = ahora().strftime("%d/%m/%Y %H:%M:%S")
            
            # 1. Guardar en SQL (Dual-Write)
            try:
                paciente_uuid = _resolver_uuid_paciente_sql(paciente_sel, empresa_actual)
                if paciente_uuid:
                    datos_sql = {
                        "paciente_id": paciente_uuid,
                        "fecha_registro": ahora().isoformat(),
                        "tipo_escala": escala,
                        "puntaje_total": puntaje,
                        "interpretacion": resumen,
                        "observaciones": observaciones.strip()
                    }
                    insert_escala(datos_sql)
                    log_event("escala_sql_insert", f"Paciente: {paciente_uuid}")
            except Exception as e:
                log_event("error_escala_sql", str(e))

            # 2. Guardar en JSON (Legacy)
            nuevo = {
                "paciente": paciente_sel,
                "fecha": fecha_str,
                "escala": escala,
                "puntaje": puntaje,
                "interpretacion": resumen,
                "observaciones": observaciones.strip(),
                "profesional": user.get("nombre", ""),
                "matricula": user.get("matricula", ""),
            }
            if "escalas_clinicas_db" not in st.session_state:
                st.session_state["escalas_clinicas_db"] = []
            st.session_state["escalas_clinicas_db"].append(nuevo)
            from core.database import _trim_db_list
            _trim_db_list("escalas_clinicas_db", 500)
            
            registrar_auditoria_legal(
                "Escala Clinica",
                paciente_sel,
                f"Registro {escala}",
                user.get("nombre", ""),
                user.get("matricula", ""),
                f"Puntaje: {puntaje} | {resumen}",
            )
            guardar_datos(spinner=True)
            queue_toast(f"Escala {escala} guardada.")
            st.rerun()

    # ── Alerta empeoramiento vs último registro de la misma escala ──
    registros_misma_escala = [r for r in registros if r.get("escala") == escala]
    if len(registros_misma_escala) >= 2:
        _sorted = sorted(registros_misma_escala, key=lambda x: x.get("fecha", ""))
        p_prev = _sorted[-2].get("puntaje", 0)
        p_actual = puntaje
        # Braden y Barthel: mayor puntaje = mejor; Glasgow y EVA: menor = mejor
        if escala in {"Braden", "Barthel"}:
            empeoro = p_actual < p_prev
            mejoro = p_actual > p_prev
        else:
            empeoro = p_actual < p_prev  # Glasgow: menor es peor; EVA: mayor es peor
            mejoro = p_actual > p_prev
            if escala == "EVA":
                empeoro = p_actual > p_prev
                mejoro = p_actual < p_prev
        delta_val = p_actual - p_prev
        if empeoro:
            st.warning(
                f" **{escala} empeoró**: anterior {p_prev} → actual {p_actual} "
                f"({'+'  if delta_val > 0 else ''}{delta_val} pts). Revisar conducta."
            )
        elif mejoro:
            st.success(
                f" **{escala} mejoró**: anterior {p_prev} → actual {p_actual} "
                f"({'+'  if delta_val > 0 else ''}{delta_val} pts)."
            )

    st.divider()
    st.markdown("### Historial de escalas")
    if not registros:
        st.info("Todavia no hay escalas registradas para este paciente.")
        return

    # ── Resumen del último puntaje por escala ─────────────────────────────
    escalas_con_data = {}
    for r in registros:
        e_key = r.get("escala", "")
        if e_key and (e_key not in escalas_con_data or r.get("fecha", "") > escalas_con_data[e_key].get("fecha", "")):
            escalas_con_data[e_key] = r
    if escalas_con_data:
        _cols = st.columns(len(escalas_con_data))
        for idx, (e_key, r) in enumerate(escalas_con_data.items()):
            _icard = _interpretacion_visual(e_key, r.get("puntaje", 0), r.get("interpretacion") or r.get("resumen", ""))
            _cols[idx].metric(
                f"Último {e_key}",
                f"{r.get('puntaje', '?')} pts",
                delta=r.get("interpretacion") or r.get("resumen", ""),
                delta_color="off",
            )
            _cols[idx].caption(r.get("fecha", "")[:16])

    # ── Gráfico de evolución del puntaje por escala ──────────────────
    df_hist = pd.DataFrame(registros)
    if not df_hist.empty and "escala" in df_hist.columns and "puntaje" in df_hist.columns:
        df_hist["puntaje"] = pd.to_numeric(df_hist["puntaje"], errors="coerce")
        df_hist["fecha_dt"] = pd.to_datetime(df_hist["fecha"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
        df_hist = df_hist.dropna(subset=["fecha_dt"]).sort_values("fecha_dt")
        escalas_presentes = [e for e in ["Glasgow", "Braden", "Barthel", "EVA"] if e in df_hist["escala"].values]
        if escalas_presentes:
            for e_key in escalas_presentes:
                df_e = df_hist[df_hist["escala"] == e_key].set_index("fecha_dt")["puntaje"]
                if len(df_e) >= 2:
                    st.caption(f"Evolución {e_key} ({len(df_e)} registros)")
                    st.line_chart(df_e, use_container_width=True, height=140)

    limite = seleccionar_limite_registros(
        "Escalas a mostrar",
        len(registros),
        key=f"limite_escalas_{paciente_sel}",
        default=30,
    )
    with lista_plegable("Historial de escalas (tabla)", count=min(limite, len(registros)), expanded=False, height=460):
        mostrar_dataframe_con_scroll(
            pd.DataFrame(registros[-limite:]).drop(columns=["paciente"], errors="ignore").iloc[::-1],
            height=400,
        )
