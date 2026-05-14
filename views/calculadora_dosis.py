"""Calculadora de dosis pediatricas por peso - Medicacion segura para ninos."""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from core.app_logging import log_event
from core.view_helpers import aviso_sin_paciente


# Cargar vademecum completo
_VADEMECUM_PATH = Path(__file__).resolve().parents[1] / "assets" / "vademecum.json"
_VADEMECUM = []
if _VADEMECUM_PATH.exists():
    try:
        _VADEMECUM = json.loads(_VADEMECUM_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass


def _completar_con_vademecum() -> dict:
    """Combina MEDICAMENTOS (con dosis) + vademecum (solo nombres)."""
    combinado = dict(MEDICAMENTOS)
    for nombre in _VADEMECUM:
        nombre = nombre.strip()
        if not nombre or nombre in combinado:
            continue
        # Saltar insumos no farmacos
        if any(p in nombre.lower() for p in ["abocath", "aguja", "sonda", "guante", "jeringa", "cateter", "baja lengua",
                                                "bajo lengua", "alcohol", "gasas", "algo torn", "cotonete", "esparadrapo"]):
            continue
        # Si ya existe con nombre similar, agregar como alias
        if not any(nombre.lower() in k.lower() or k.lower() in nombre.lower() for k in MEDICAMENTOS):
            combinado[nombre] = None  # Sin datos de dosis
    return combinado

# ============================================================
# BASE DE DATOS FARMACOLOGICA PEDIATRICA
# Fuentes: AAP, OMS, UpToDate, Formulario Nacional Pediatrico
# ============================================================

MEDICAMENTOS = {
    "Acetaminofen (Paracetamol)": {
        "dosis_por_kg": "10-15 mg/kg/dosis",
        "dosis_mg_kg": (10, 15),
        "intervalo_hs": "cada 4-6 hs",
        "intervalo_min_hs": 4,
        "dosis_max_diaria_mg_kg": 60,
        "dosis_max_por_dosis_mg": 500,
        "presentacion": "Gotas 100 mg/ml, Jarabe 120 mg/5ml, Comp 500 mg",
        "via": "Oral o rectal",
        "observaciones": "No superar 5 dosis en 24hs. Contraindicado en insuficiencia hepatica.",
        "alerta": None,
    },
    "Ibuprofeno": {
        "dosis_por_kg": "5-10 mg/kg/dosis",
        "dosis_mg_kg": (5, 10),
        "intervalo_hs": "cada 6-8 hs",
        "intervalo_min_hs": 6,
        "dosis_max_diaria_mg_kg": 30,
        "dosis_max_por_dosis_mg": 400,
        "presentacion": "Jarabe 100 mg/5ml, Gotas 200 mg/ml, Comp 400/600 mg",
        "via": "Oral",
        "observaciones": "Administrar con alimentos. Contraindicado <6 meses, asma, insuficiencia renal.",
        "alerta": "No usar en menores de 3 meses",
    },
    "Amoxicilina": {
        "dosis_por_kg": "50-100 mg/kg/dia dividido c/8hs",
        "dosis_mg_kg": (15, 35),
        "intervalo_hs": "cada 8 hs",
        "intervalo_min_hs": 8,
        "dosis_max_diaria_mg_kg": 100,
        "dosis_max_por_dosis_mg": 1000,
        "presentacion": "Suspension 250 mg/5ml, 500 mg/5ml",
        "via": "Oral",
        "observaciones": "Completar 7-10 dias de tratamiento. Alergia a penicilinas: contraindicado.",
        "alerta": "Verificar alergia a penicilina antes de administrar",
    },
    "Amoxicilina + Ac. Clavulanico": {
        "dosis_por_kg": "40-80 mg/kg/dia c/12hs (amoxicilina)",
        "dosis_mg_kg": (20, 40),
        "intervalo_hs": "cada 12 hs",
        "intervalo_min_hs": 12,
        "dosis_max_diaria_mg_kg": 80,
        "dosis_max_por_dosis_mg": 875,
        "presentacion": "Suspension 250+31.25 mg/5ml, 400+57 mg/5ml",
        "via": "Oral",
        "observaciones": "Dosis calculada sobre componente amoxicilina. Via间隔 12hs.",
        "alerta": "Verificar alergia a penicilina",
    },
    "Azitromicina": {
        "dosis_por_kg": "10 mg/kg/dia por 3 dias",
        "dosis_mg_kg": (10, 10),
        "intervalo_hs": "cada 24 hs",
        "intervalo_min_hs": 24,
        "dosis_max_diaria_mg_kg": 10,
        "dosis_max_por_dosis_mg": 500,
        "presentacion": "Suspension 200 mg/5ml, Comp 500 mg",
        "via": "Oral",
        "observaciones": "Administrar 1 hora antes o 2 horas despues de comidas. Curso tipico: 3 dias.",
        "alerta": None,
    },
    "Salbutamol (Inhalador)": {
        "dosis_por_kg": "0.1-0.15 mg/kg/dosis (nebulizar)",
        "dosis_mg_kg": (0.1, 0.15),
        "intervalo_hs": "cada 4-6 hs segun necesidad",
        "intervalo_min_hs": 4,
        "dosis_max_diaria_mg_kg": 2,
        "dosis_max_por_dosis_mg": 5,
        "presentacion": "Solucion nebulizar 5 mg/ml, Aerosol 100 mcg/dosis",
        "via": "Inhalatoria/nebulizar",
        "observaciones": "Agitar antes de usar. En crisis asmatica, puede repetirse cada 20 min x 3 dosis.",
        "alerta": "Taquicardia, temblor. Usar con precaucion en cardiopatas.",
    },
    "Dexametasona": {
        "dosis_por_kg": "0.15-0.6 mg/kg/dosis",
        "dosis_mg_kg": (0.15, 0.6),
        "intervalo_hs": "cada 6-12 hs segun indicacion",
        "intervalo_min_hs": 6,
        "dosis_max_diaria_mg_kg": 1.5,
        "dosis_max_por_dosis_mg": 8,
        "presentacion": "Comp 0.5/0.75/1.5 mg, Solucion 2 mg/5ml, Inyectable 4 mg/ml",
        "via": "Oral, IM, EV",
        "observaciones": "Uso agudo: dosis altas. Uso cronico: dosis minima efectiva. No suspender bruscamente.",
        "alerta": "Uso prolongado: supresion suprarrenal, hiperglucemia",
    },
    "Dipirona (Metamizol)": {
        "dosis_por_kg": "10-15 mg/kg/dosis",
        "dosis_mg_kg": (10, 15),
        "intervalo_hs": "cada 6-8 hs",
        "intervalo_min_hs": 6,
        "dosis_max_diaria_mg_kg": 50,
        "dosis_max_por_dosis_mg": 1000,
        "presentacion": "Gotas 500 mg/ml, Comp 500 mg, Inyectable 1g/2ml",
        "via": "Oral, IM, EV",
        "observaciones": "Riesgo de agranulocitosis (1:1.000.000). No usar >7 dias. Contraindicado <3 meses.",
        "alerta": "Riesgo de agranulocitosis. Suspender ante fiebre o dolor de garganta",
    },
    "Ceftriaxona": {
        "dosis_por_kg": "50-80 mg/kg/dia c/12-24hs",
        "dosis_mg_kg": (50, 80),
        "intervalo_hs": "cada 12-24 hs",
        "intervalo_min_hs": 12,
        "dosis_max_diaria_mg_kg": 80,
        "dosis_max_por_dosis_mg": 2000,
        "presentacion": "Polvo para reconstituir 1g",
        "via": "IM, EV",
        "observaciones": "No administrar con calcio (precipitacion). Dosis unica diaria en meningococemia.",
        "alerta": "No mezclar con calcio en neonatos",
    },
    "Ondansetron": {
        "dosis_por_kg": "0.1-0.15 mg/kg/dosis",
        "dosis_mg_kg": (0.1, 0.15),
        "intervalo_hs": "cada 8 hs",
        "intervalo_min_hs": 8,
        "dosis_max_diaria_mg_kg": 0.45,
        "dosis_max_por_dosis_mg": 8,
        "presentacion": "Comp 4/8 mg, Jarabe 4 mg/5ml, Inyectable 2 mg/ml",
        "via": "Oral, EV",
        "observaciones": "Administrar 30 min antes de la quimio/cirugia. Efecto: prevenir nausea/vomito.",
        "alerta": "Prolonga intervalo QT. Usar con precaucion en cardiopatas.",
    },
    "Diazepam": {
        "dosis_por_kg": "0.2-0.5 mg/kg/dosis",
        "dosis_mg_kg": (0.2, 0.5),
        "intervalo_hs": "cada 6-8 hs segun necesidad",
        "intervalo_min_hs": 6,
        "dosis_max_diaria_mg_kg": 2,
        "dosis_max_por_dosis_mg": 10,
        "presentacion": "Comp 2/5/10 mg, Solucion 2 mg/5ml, Inyectable 5 mg/ml, Rectal 5/10 mg",
        "via": "Oral, EV, rectal",
        "observaciones": "En emergencia convulsiva: 0.3-0.5 mg/kg EV lento o rectal. Depresion respiratoria.",
        "alerta": "Riesgo de depresion respiratoria. Tener equipamiento de reanimacion disponible",
    },
    "Ivermectina": {
        "dosis_por_kg": "0.15-0.2 mg/kg/dosis unica",
        "dosis_mg_kg": (0.15, 0.2),
        "intervalo_hs": "dosis unica, repetir a los 7 dias si es necesario",
        "intervalo_min_hs": 168,
        "dosis_max_diaria_mg_kg": 0.2,
        "dosis_max_por_dosis_mg": 15,
        "presentacion": "Comp 6 mg",
        "via": "Oral",
        "observaciones": "Tomar con agua, en ayunas. Escabicida y antiparasitario. Dosis unica.",
        "alerta": "Contraindicado <15 kg o embarazo",
    },
    "Hidroxizina": {
        "dosis_por_kg": "0.5-1 mg/kg/dosis",
        "dosis_mg_kg": (0.5, 1),
        "intervalo_hs": "cada 6-8 hs",
        "intervalo_min_hs": 6,
        "dosis_max_diaria_mg_kg": 3,
        "dosis_max_por_dosis_mg": 50,
        "presentacion": "Jarabe 10 mg/5ml, Comp 10/25 mg",
        "via": "Oral",
        "observaciones": "Antihistaminico. Usar con precaucion en <2 anios. Puede causar somnolencia.",
        "alerta": "Somnolencia intensa en dosis altas",
    },
}


def calcular_dosis(medicamento: str, peso_kg: float) -> dict:
    """Calcula dosis pediatrica segun peso del paciente."""
    info = MEDICAMENTOS[medicamento]
    dosis_min, dosis_max = info["dosis_mg_kg"]
    dosis_por_dosis_min = round(peso_kg * dosis_min, 1)
    dosis_por_dosis_max = round(peso_kg * dosis_max, 1)

    # Dosis max por dosis (no superar el maximo absoluto)
    max_por_dosis = info["dosis_max_por_dosis_mg"]
    dosis_recomendada = min(dosis_por_dosis_max, max_por_dosis)

    # Dosis diaria total
    dosis_diaria_min = round(peso_kg * dosis_min * (24 / info["intervalo_min_hs"]), 1)
    dosis_diaria_max = round(peso_kg * info["dosis_max_diaria_mg_kg"], 1)

    # Presentacion sugerida
    presentacion = info["presentacion"]

    return {
        "medicamento": medicamento,
        "peso": peso_kg,
        "dosis_por_kg": info["dosis_por_kg"],
        "dosis_min_mg": dosis_por_dosis_min,
        "dosis_max_mg": dosis_por_dosis_max,
        "dosis_recomendada_mg": dosis_recomendada,
        "intervalo": info["intervalo_hs"],
        "dosis_diaria_max_mg": dosis_diaria_max,
        "dosis_max_por_dosis_mg": max_por_dosis,
        "presentacion": presentacion,
        "via": info["via"],
        "observaciones": info["observaciones"],
        "alerta": info["alerta"],
    }


def render_calculadora_dosis(paciente_sel, mi_empresa, user, rol):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    # Combinar dosis conocidas + vademecum
    _TODOS_MEDICAMENTOS = _completar_con_vademecum()

    st.markdown("""
        <div class="mc-hero">
            <h2 class="mc-hero-title">Calculadora de Dosis Pediatricas</h2>
            <p class="mc-hero-text">Calculo automatico de dosis segun peso del paciente. Basado en AAP, OMS y UpToDate.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Por peso</span>
                <span class="mc-chip">Intervalos</span>
                <span class="mc-chip">Alertas</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.warning(
        "Esta calculadora es una guia de referencia. La dosis final debe ser confirmada por "
        "el medico prescriptor segun criterio clinico, funcion hepatica/renal y condiciones del paciente.",
        icon="⚠️",
    )

    # Obtener peso del paciente desde datos
    detalles = st.session_state.get("detalles_pacientes_db", {}).get(paciente_sel, {})

    c1, c2 = st.columns([1, 1])

    with c1:
        peso = st.number_input(
            "Peso del paciente (kg) *",
            min_value=0.5, max_value=100.0, step=0.1, value=10.0,
            help="Ingresar el peso actual del nino en kilogramos",
        )
        # Mostrar edad estimada si tenemos fecha de nacimiento
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
                    anios = edad_dias // 365
                    meses = (edad_dias % 365) // 30
                    st.caption(f"Edad: {anios} anios {meses} meses")
            except Exception:
                pass

    with c2:
        _todos = sorted(_TODOS_MEDICAMENTOS.keys())
        # Mostrar indicador de disponibilidad
        _labels = {}
        for m in _todos:
            if _TODOS_MEDICAMENTOS[m] is not None:
                _labels[m] = m + " (con dosis pediatrica)"
            else:
                _labels[m] = m + " (solo vademecum)"

        medicamento = st.selectbox(
            "Medicamento *",
            _todos,
            format_func=lambda x: _labels[x],
            help="Seleccionar el medicamento a calcular. Los que tienen dosis pediatrica aparecen indicados.",
        )

        info = _TODOS_MEDICAMENTOS[medicamento]
        if info is None:
            st.caption("Medicamento del vademecum sin dosis pediatrica cargada. Selecciona uno con '(con dosis pediatrica)' para calcular.")
        else:
            st.caption(f"Via: {info['via']} | Intervalo: {info['intervalo_hs']} | Dosis calculada segun peso")

    st.divider()

    if st.button("Calcular dosis", width="stretch", type="primary", key="calc_dosis"):
        if peso <= 0:
            st.error("El peso debe ser mayor a 0.")
        else:
            info = _TODOS_MEDICAMENTOS[medicamento]
            if info is None:
                st.warning(f"'{medicamento}' solo esta en el vademecum (sin dosis pediatrica cargada). Selecciona un medicamento que diga '(con dosis pediatrica)' para calcular.")
                log_event("calculadora_dosis", f"sin_datos:{medicamento}")
            else:
                resultado = calcular_dosis(medicamento, peso)
                info = MEDICAMENTOS[medicamento]

                st.markdown("### Resultado del calculo")

                # Tarjeta principal con dosis
                cols = st.columns([1, 1, 1])
                cols[0].metric("Dosis por dosis", f"{resultado['dosis_min_mg']} - {resultado['dosis_max_mg']} mg")
                cols[1].metric("Dosis recomendada", f"{resultado['dosis_recomendada_mg']} mg")
                cols[2].metric("Maximo por dosis", f"{resultado['dosis_max_por_dosis_mg']} mg")

                cols2 = st.columns([1, 1, 1])
                cols2[0].metric("Intervalo", resultado["intervalo"])
                cols2[1].metric("Dosis diaria max", f"{resultado['dosis_diaria_max_mg']} mg/dia")
                cols2[2].metric("Presentacion", resultado["presentacion"][:30], help=resultado["presentacion"])

                # Detalle del calculo
                with st.expander("Ver detalle del calculo", expanded=True):
                    st.markdown(f"""
**Calculo para {resultado['medicamento']}:**
- Peso del paciente: **{peso} kg**
- Dosis por kg: {resultado['dosis_por_kg']}
- Dosis minima: {resultado['dosis_min_mg']} mg (peso x {info['dosis_mg_kg'][0]} mg/kg)
- Dosis maxima: {resultado['dosis_max_mg']} mg (peso x {info['dosis_mg_kg'][1]} mg/kg)
- Dosis recomendada: {resultado['dosis_recomendada_mg']} mg (limitado a max {resultado['dosis_max_por_dosis_mg']} mg)
- Intervalo: {resultado['intervalo']}
- Via: {resultado['via']}
- Dosis diaria maxima: {resultado['dosis_diaria_max_mg']} mg
                    """)

                # Presentaciones disponibles
                with st.expander("Presentaciones disponibles", expanded=False):
                    st.markdown(f"**{resultado['presentacion']}**")
                    for desc in resultado["presentacion"].split(","):
                        desc = desc.strip()
                        if "mg/" in desc:
                            try:
                                conc = desc.split("mg/")[0].strip()
                                vol = desc.split("mg/")[1].strip()
                                conc_val = float(conc.split()[-1])
                                vol_min = round(resultado['dosis_min_mg'] / conc_val, 1)
                                vol_max = round(resultado['dosis_max_mg'] / conc_val, 1)
                                vol_rec = round(resultado['dosis_recomendada_mg'] / conc_val, 1)
                                st.markdown(f"- **{desc}**: {vol_min}-{vol_max} ml (recomendado: {vol_rec} ml)")
                            except (ValueError, IndexError):
                                st.markdown(f"- {desc}")

                # Observaciones
                st.markdown("### Observaciones")
                st.info(resultado["observaciones"])

                # Alertas
                if resultado["alerta"]:
                    st.error(f"ALERTA: {resultado['alerta']}", icon="🚨")

                # Log
                log_event("calculadora_dosis", f"{medicamento} - {peso}kg - {paciente_sel}")

    # Informacion de seguridad
    with st.expander("Informacion de seguridad", expanded=False):
        st.markdown("""
**Precauciones generales:**
- Verificar alergias del paciente antes de administrar
- Confirmar via de administracion correcta
- Usar jeringa dosificadora adecuada (no cucharas caseras)
- Registrar dosis administrada en la evolucion del paciente
- Ante duda, consultar con el medico prescriptor

**Contraindicaciones comunes:**
- Insuficiencia hepatica o renal: ajustar dosis
- Deshidratacion: riesgo de toxicidad por AINES
- Menores de 3 meses: evitar ibuprofeno y dipirona
        """)
