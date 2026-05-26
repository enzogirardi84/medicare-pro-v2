"""Calculadora de dosis pediatricas por peso - UI solamente.
La logica de calculo reside en services/farmaco_data.py"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from core.app_logging import log_event
from core.view_helpers import aviso_sin_paciente
from services.farmaco_data import (
    MEDICAMENTOS,
    calcular_dosis_pediatrica_completa,
    normalizar_medicamento,
    parse_intervalo,
)

_VADEMECUM_PATH = Path(__file__).resolve().parents[1] / "assets" / "vademecum.json"
_VADEMECUM = []
if _VADEMECUM_PATH.exists():
    try:
        _VADEMECUM = json.loads(_VADEMECUM_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass


def _normalizar_para_match(s: str) -> str:
    import unicodedata, re
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'[^a-z0-9]+', '', s.lower())
    return s


def _completar_con_vademecum() -> dict:
    combinado = dict(MEDICAMENTOS)
    _KEYS_NORM = {k: _normalizar_para_match(k) for k in MEDICAMENTOS}
    for nombre in _VADEMECUM:
        nombre = nombre.strip()
        if not nombre:
            continue
        if any(p in nombre.lower() for p in ["abocath", "aguja", "sonda", "guante", "jeringa", "cateter",
                                                "baja lengua", "bajo lengua", "alcohol", "gasas", "algo torn",
                                                "cotonete", "esparadrapo"]):
            continue
        base_nombre, _ = normalizar_medicamento(nombre)
        encontrado = None
        norm_base = _normalizar_para_match(base_nombre)
        for k in MEDICAMENTOS:
            if norm_base in _KEYS_NORM[k] or _KEYS_NORM[k] in norm_base:
                encontrado = k
                break
        if encontrado:
            if nombre not in combinado:
                combinado[nombre] = encontrado
        elif nombre not in combinado:
            combinado[nombre] = None
    return combinado


def _mostrar_resultado(r):
    cols = st.columns([1, 1, 1])
    cols[0].metric("Dosis por dosis", f"{r['dosis_min_mg']} - {r['dosis_max_mg']} mg")
    cols[1].metric("Dosis recomendada", f"{r['dosis_recomendada_mg']} mg")
    cols[2].metric("Maximo por dosis", f"{r['dosis_max_por_dosis_mg']} mg")

    cols2 = st.columns([1, 1, 1])
    int_sel = r.get("intervalo_seleccionado_hs")
    if int_sel:
        dosis_x_dia = r.get("dosis_por_dia", round(24 / int_sel))
        cols2[0].metric("Intervalo", f"cada {int_sel} hs ({dosis_x_dia}/dia)")
    else:
        cols2[0].metric("Intervalo", r["intervalo"])
    cols2[1].metric("Dosis diaria max", f"{r['dosis_diaria_max_mg']} mg/dia")
    cols2[2].metric("Dosis diaria min", f"{r.get('dosis_diaria_min_mg', '?')} mg/dia")

    with st.expander("Presentaciones disponibles", expanded=False):
        st.markdown(f"**{r['presentacion']}**")
        for desc in r["presentacion"].split(","):
            desc = desc.strip()
            if "mg/" in desc:
                try:
                    conc_val = float(desc.split("mg/")[0].strip().split()[-1])
                    vol_min = round(r["dosis_min_mg"] / conc_val, 1)
                    vol_max = round(r["dosis_max_mg"] / conc_val, 1)
                    vol_rec = round(r["dosis_recomendada_mg"] / conc_val, 1)
                    st.markdown(f"- **{desc}**: {vol_min}-{vol_max} ml (recomendado: {vol_rec} ml)")
                except (ValueError, IndexError):
                    st.markdown(f"- {desc}")


def render_calculadora_dosis(paciente_sel, mi_empresa, user, rol):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    _TODOS_MEDICAMENTOS = _completar_con_vademecum()
    st.markdown("""
        <div class="mc-hero">
            <h2 class="mc-hero-title">Calculadora de Dosis Pediatricas</h2>
            <p class="mc-hero-text">Calculo automatico de dosis segun peso del paciente.</p>
        </div>
    """, unsafe_allow_html=True)
    st.warning("Guia de referencia. La dosis final debe ser confirmada por el medico prescriptor.", icon="⚠️")

    detalles = st.session_state.get("detalles_pacientes_db", {}).get(paciente_sel, {})
    c1, c2 = st.columns([1, 1])
    _MANUAL_KEY = "✏️ Ingreso manual..."

    with c1:
        peso = st.number_input("Peso del paciente (kg) *", min_value=0.5, max_value=100.0, step=0.1, value=10.0)
        fnac = detalles.get("fnac", detalles.get("fecha_nacimiento", ""))
        if fnac:
            try:
                from datetime import datetime
                nac = datetime.strptime(fnac, "%d/%m/%Y")
                edad_dias = (datetime.now() - nac).days
                if edad_dias < 30:
                    st.caption(f"Edad: {edad_dias} dias")
                elif edad_dias < 365:
                    st.caption(f"Edad: {edad_dias // 30} meses")
                else:
                    anios = edad_dias // 365; meses = (edad_dias % 365) // 30
                    st.caption(f"Edad: {anios} anios {meses} meses")
            except Exception as _e_dc:
                log_event("calculadora_dosis", f"edad_error:{type(_e_dc).__name__}")

    with c2:
        _todos = sorted(k for k, v in _TODOS_MEDICAMENTOS.items() if isinstance(v, dict)) + [_MANUAL_KEY]
        medicamento = st.selectbox("Medicamento *", _todos)
        es_manual = medicamento == _MANUAL_KEY
        if es_manual:
            with st.expander("Parametros del medicamento", expanded=False):
                st.text_input("Nombre del medicamento", key="m_nombre")
                st.columns(2)[0].number_input("Dosis min (mg/kg/dosis)", min_value=0.0, step=0.1, value=10.0, key="m_min")
                st.columns(2)[0].number_input("Dosis max (mg/kg/dosis)", min_value=0.0, step=0.1, value=15.0, key="m_max")
                st.columns(2)[0].number_input("Intervalo minimo (hs)", min_value=0.0, step=1.0, value=6.0, key="m_int")
                st.columns(2)[1].number_input("Dosis max diaria (mg/kg)", min_value=0.0, step=1.0, value=60.0, key="m_diaria")
                st.columns(2)[1].number_input("Dosis max por dosis (mg)", min_value=0.0, step=1.0, value=500.0, key="m_maxdosis")
        else:
            info = _TODOS_MEDICAMENTOS.get(medicamento)
            if isinstance(info, dict):
                int_min, int_max = parse_intervalo(info["intervalo_hs"])
                if int_min > 0 and int_max > int_min:
                    intervalo_sel = st.slider("Intervalo (hs)", min_value=int_min, max_value=int_max, value=int_max, step=1.0, key="int_selector")
                else:
                    intervalo_sel = int_min or info["intervalo_min_hs"]
                    st.caption(f"Intervalo: cada {intervalo_sel:.0f} hs")
                st.session_state["int_selector_val"] = intervalo_sel
                st.caption(f"Dosis por dia: ~{round(24 / intervalo_sel)} toma(s) | Via: {info['via']}")
                if info.get("alerta"):
                    log_event("calculadora_dosis", f"ALERTA - {info['alerta']}")
                    st.error(f"ALERTA: {info['alerta']}", icon="🚨")

    st.divider()
    if st.button("Calcular dosis", width="stretch", type="primary", key="calc_dosis"):
        if peso <= 0:
            st.error("El peso debe ser mayor a 0.")
        elif es_manual:
            nom = st.session_state.get("m_nombre", "").strip()
            if not nom:
                st.error("Debe ingresar el nombre del medicamento.")
            else:
                m_min = st.session_state["m_min"]; m_max = st.session_state["m_max"]
                m_int = st.session_state["m_int"]; m_maxd = st.session_state["m_maxdosis"]
                m_dia = st.session_state["m_diaria"]
                dd_max = min(round(peso * m_dia, 1), round(m_maxd * (24 / m_int), 1))
                res = {"medicamento": nom, "peso": peso, "dosis_por_kg": f"{m_min}-{m_max} mg/kg/dosis",
                       "dosis_min_mg": round(peso * m_min, 1), "dosis_max_mg": round(peso * m_max, 1),
                       "dosis_recomendada_mg": min(round(peso * m_max, 1), m_maxd),
                       "intervalo": f"cada {m_int} hs", "dosis_diaria_min_mg": round(peso * m_min * (24 / m_int), 1),
                       "dosis_diaria_max_mg": dd_max, "dosis_max_por_dosis_mg": m_maxd,
                       "presentacion": st.session_state.get("m_pres", ""), "via": st.session_state.get("m_via", "Oral"),
                       "observaciones": st.session_state.get("m_obs", ""), "alerta": None}
                st.markdown(f"### Resultado — {nom} (manual)")
                _mostrar_resultado(res)
                log_event("calculadora_dosis", f"MANUAL:{nom} - {peso}kg")
        else:
            intervalo_sel = st.session_state.get("int_selector_val", None)
            try:
                resultado = calcular_dosis_pediatrica_completa(medicamento, peso, _TODOS_MEDICAMENTOS, intervalo_sel)
                st.markdown("### Resultado del calculo")
                _mostrar_resultado(resultado)
                st.markdown("### Observaciones")
                st.info(resultado["observaciones"])
                if resultado.get("alerta"):
                    st.error(f"ALERTA: {resultado['alerta']}", icon="🚨")
                log_event("calculadora_dosis", f"{medicamento} - {peso}kg")
            except ValueError as e:
                st.error("Datos inválidos. Verificá el peso, dosis y medicamento ingresados.")
                log_event("calculadora_dosis", f"error:{type(e).__name__}:{e}")

    with st.expander("Informacion de seguridad", expanded=False):
        st.markdown("""
**Precauciones generales:**
- Verificar alergias del paciente antes de administrar
- Confirmar via de administracion correcta
- Usar jeringa dosificadora adecuada
- Registrar dosis administrada en la evolucion del paciente
        """)
