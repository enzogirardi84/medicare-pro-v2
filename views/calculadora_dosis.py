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


def _normalizar_medicamento(nombre: str) -> tuple:
    """Parsea nombre de medicamento extrayendo concentracion.
    Ej: 'Ibuprofeno 400mg' -> ('Ibuprofeno', 400)
        'Amoxicilina 500mg/5ml' -> ('Amoxicilina', 500)
        'Paracetamol' -> ('Paracetamol', None)
    """
    import re
    nombre = nombre.strip()
    # Intentar extraer concentracion al final
    m = re.match(r"^(.+?)\s+(\d+)\s*mg(?:\/\d+ml)?$", nombre)
    if m:
        return m.group(1).strip(), int(m.group(2))
    # Sin concentracion
    return nombre, None


def _completar_con_vademecum() -> dict:
    """Combina MEDICAMENTOS (con dosis) + vademecum (solo nombres).
    Reconoce nombres con concentracion: 'Ibuprofeno 400mg' -> 'Ibuprofeno'
    """
    combinado = dict(MEDICAMENTOS)
    for nombre in _VADEMECUM:
        nombre = nombre.strip()
        if not nombre:
            continue
        # Saltar insumos no farmacos
        if any(p in nombre.lower() for p in ["abocath", "aguja", "sonda", "guante", "jeringa", "cateter", "baja lengua",
                                                "bajo lengua", "alcohol", "gasas", "algo torn", "cotonete", "esparadrapo"]):
            continue

        base_nombre, _ = _normalizar_medicamento(nombre)

        # Buscar si el base_nombre ya esta en MEDICAMENTOS
        encontrado = None
        for k in MEDICAMENTOS:
            if base_nombre.lower() in k.lower() or k.lower() in base_nombre.lower():
                encontrado = k
                break

        if encontrado:
            # Es un alias de un medicamento con datos - agregar con referencia
            if nombre not in combinado:
                combinado[nombre] = encontrado  # Referencia al nombre con datos
        elif nombre not in combinado:
            combinado[nombre] = None  # Sin datos
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
    "Adrenalina (Epinefrina)": {
        "dosis_por_kg": "0.01 mg/kg/dosis (1:1000 IM / 1:10000 EV)",
        "dosis_mg_kg": (0.01, 0.01),
        "intervalo_hs": "cada 5-15 min segun respuesta",
        "intervalo_min_hs": 0.083,
        "dosis_max_diaria_mg_kg": 0.05,
        "dosis_max_por_dosis_mg": 0.5,
        "presentacion": "Ampolla 1 mg/ml (1:1000), Ampolla 0.1 mg/ml (1:10000)",
        "via": "IM, EV",
        "observaciones": "Primera linea en anafilaxia. IM en vasto lateral externo. En paro: 0.01 mg/kg EV cada 3-5 min.",
        "alerta": "NO usar SC en anafilaxia. Diluir siempre para via EV. Monitorizar ritmo cardiaco",
    },
    "Prednisolona": {
        "dosis_por_kg": "1-2 mg/kg/dia dividido c/12-24hs",
        "dosis_mg_kg": (0.5, 1),
        "intervalo_hs": "cada 12-24 hs",
        "intervalo_min_hs": 12,
        "dosis_max_diaria_mg_kg": 2,
        "dosis_max_por_dosis_mg": 60,
        "presentacion": "Jarabe 15 mg/5ml, Comp 5/20 mg, Solucion oral 10 mg/ml",
        "via": "Oral",
        "observaciones": "Corticoide oral. En asma aguda: 1-2 mg/kg/dosis. Usar dosis minima efectiva. No suspender bruscamente si uso >14 dias.",
        "alerta": "Uso prolongado: supresion suprarrenal, retraso del crecimiento, hiperglucemia",
    },
    "Furosemida": {
        "dosis_por_kg": "1-2 mg/kg/dosis oral / 0.5-1 mg/kg/dosis EV",
        "dosis_mg_kg": (1, 2),
        "intervalo_hs": "cada 6-12 hs",
        "intervalo_min_hs": 6,
        "dosis_max_diaria_mg_kg": 6,
        "dosis_max_por_dosis_mg": 40,
        "presentacion": "Comp 40 mg, Jarabe 10 mg/ml, Inyectable 10 mg/ml",
        "via": "Oral, EV",
        "observaciones": "Diuretico de asa. Monitorizar K+, Na+, funcion renal. Administrar EV lento (>2 min).",
        "alerta": "Hipocaliemia, ototoxicidad, deshidratacion. Contraindicado en anuria",
    },
    "Cefalexina": {
        "dosis_por_kg": "50-100 mg/kg/dia dividido c/6-8hs",
        "dosis_mg_kg": (12.5, 25),
        "intervalo_hs": "cada 6-8 hs",
        "intervalo_min_hs": 6,
        "dosis_max_diaria_mg_kg": 100,
        "dosis_max_por_dosis_mg": 1000,
        "presentacion": "Suspension 250 mg/5ml, 500 mg/5ml, Comp 500 mg",
        "via": "Oral",
        "observaciones": "Cefalosporina 1ra gen. Eficaz en infecciones piel, partes blandas, S. aureus. Completar 7-10 dias.",
        "alerta": "10% alergia cruzada con penicilina. Verificar alergia a betalactamicos",
    },
    "Metoclopramida": {
        "dosis_por_kg": "0.1-0.2 mg/kg/dosis",
        "dosis_mg_kg": (0.1, 0.2),
        "intervalo_hs": "cada 6-8 hs",
        "intervalo_min_hs": 6,
        "dosis_max_diaria_mg_kg": 0.5,
        "dosis_max_por_dosis_mg": 10,
        "presentacion": "Comp 10 mg, Jarabe 5 mg/5ml, Inyectable 5 mg/ml",
        "via": "Oral, EV, IM",
        "observaciones": "Antiemetico. Administrar 30 min antes de comidas. Riesgo de sintomas extrapiramidales en <2 anios.",
        "alerta": "Sintomas extrapiramidales (distonia aguda). Contraindicado en <1 anio",
    },
    "Omeprazol": {
        "dosis_por_kg": "0.5-1 mg/kg/dosis c/12-24hs",
        "dosis_mg_kg": (0.5, 1),
        "intervalo_hs": "cada 12-24 hs",
        "intervalo_min_hs": 12,
        "dosis_max_diaria_mg_kg": 2,
        "dosis_max_por_dosis_mg": 40,
        "presentacion": "Comp 20 mg, Comp masticable 10 mg, Suspension 20 mg/5ml (prep. magistral)",
        "via": "Oral",
        "observaciones": "Inhibidor de bomba de protones. Administrar en ayunas 30-60 min antes del desayuno. No masticar comprimidos.",
        "alerta": "Uso prolongado: riesgo de infecciones intestinales, deficiencia de B12, osteoporosis",
    },
    "Loratadina": {
        "dosis_por_kg": "0.1-0.2 mg/kg/dosis una vez al dia",
        "dosis_mg_kg": (0.1, 0.2),
        "intervalo_hs": "cada 24 hs",
        "intervalo_min_hs": 24,
        "dosis_max_diaria_mg_kg": 0.2,
        "dosis_max_por_dosis_mg": 10,
        "presentacion": "Jarabe 5 mg/5ml, Comp 10 mg",
        "via": "Oral",
        "observaciones": "Antihistaminico H1 2da generacion. No causa somnolencia significativa. Rinitis alergica y urticaria.",
        "alerta": None,
    },
    "Sulfametoxazol + Trimetoprima": {
        "dosis_por_kg": "6-12 mg/kg/dia (de TMP) dividido c/12hs",
        "dosis_mg_kg": (3, 6),
        "intervalo_hs": "cada 12 hs",
        "intervalo_min_hs": 12,
        "dosis_max_diaria_mg_kg": 12,
        "dosis_max_por_dosis_mg": 160,
        "presentacion": "Suspension 40+200 mg/5ml, Comp 80+400 mg, Comp 160+800 mg",
        "via": "Oral",
        "observaciones": "Dosis calculada sobre componente trimetoprima. ITU, neumonia, profilaxis PCP. Administrar con abundante agua.",
        "alerta": "No usar en <2 meses. Riesgo de Sindrome Stevens-Johnson. Fotosensibilidad",
    },
    "Clindamicina": {
        "dosis_por_kg": "10-30 mg/kg/dia dividido c/6-8hs",
        "dosis_mg_kg": (5, 10),
        "intervalo_hs": "cada 6-8 hs",
        "intervalo_min_hs": 6,
        "dosis_max_diaria_mg_kg": 30,
        "dosis_max_por_dosis_mg": 600,
        "presentacion": "Suspension 75 mg/5ml, Capsula 150/300 mg, Inyectable 150 mg/ml",
        "via": "Oral, EV, IM",
        "observaciones": "Activo contra anaerobios y S. aureus (incluyendo SAMR comunitario). Alternativa en alergia a penicilina.",
        "alerta": "Colitis pseudomembranosa por C. difficile. Suspender si diarrea severa",
    },
    "Gentamicina": {
        "dosis_por_kg": "5-7.5 mg/kg/dia en dosis unica diaria",
        "dosis_mg_kg": (5, 7.5),
        "intervalo_hs": "cada 24 hs",
        "intervalo_min_hs": 24,
        "dosis_max_diaria_mg_kg": 7.5,
        "dosis_max_por_dosis_mg": 240,
        "presentacion": "Inyectable 40 mg/ml, 80 mg/2ml",
        "via": "EV, IM",
        "observaciones": "Aminoglucosido. Monitorizar funcion renal y niveles sericos. Dosis ajustada por clearance de creatinina.",
        "alerta": "Nefrotoxicidad y ototoxicidad. Monitorizar niveles (valle <2 mcg/ml)",
    },
    "Fenitoina": {
        "dosis_por_kg": "4-8 mg/kg/dia dividido c/8-12hs",
        "dosis_mg_kg": (2, 4),
        "intervalo_hs": "cada 8-12 hs",
        "intervalo_min_hs": 8,
        "dosis_max_diaria_mg_kg": 10,
        "dosis_max_por_dosis_mg": 200,
        "presentacion": "Suspension 125 mg/5ml, Comp 100 mg, Inyectable 50 mg/ml",
        "via": "Oral, EV (lento)",
        "observaciones": "Anticonvulsivante. Dosis de carga: 15-20 mg/kg EV. Iniciar mantenimiento 24hs post-carga. Monitorizar niveles.",
        "alerta": "Arritmias si EV rapido. No mezclar con dextrosa. Hiperplasia gingival. Sindrome de Steven Johnson",
    },
    "Midazolam": {
        "dosis_por_kg": "0.05-0.1 mg/kg/dosis (sedacion)",
        "dosis_mg_kg": (0.05, 0.1),
        "intervalo_hs": "cada 2-4 hs segun necesidad",
        "intervalo_min_hs": 2,
        "dosis_max_diaria_mg_kg": 0.5,
        "dosis_max_por_dosis_mg": 5,
        "presentacion": "Ampolla 5 mg/ml, 15 mg/3ml, Sol oral 2 mg/ml (prep. magistral)",
        "via": "EV, IM, intranasal",
        "observaciones": "Benzodiazepina de accion corta. Sedacion consciente, premedicacion. Tener flumazenilo disponible.",
        "alerta": "Depresion respiratoria. Administrar solo con monitorizacion por personal entrenado",
    },
    "Naloxona": {
        "dosis_por_kg": "0.01-0.1 mg/kg/dosis",
        "dosis_mg_kg": (0.01, 0.1),
        "intervalo_hs": "cada 2-3 min segun respuesta",
        "intervalo_min_hs": 0.05,
        "dosis_max_diaria_mg_kg": 10,
        "dosis_max_por_dosis_mg": 2,
        "presentacion": "Inyectable 0.4 mg/ml, 1 mg/ml, Spray nasal 4 mg/dosis",
        "via": "EV, IM, intranasal",
        "observaciones": "Antagonista opioide. Revertir depresion respiratoria por opioides. Repetir c/2-3 min hasta respuesta.",
        "alerta": "Sindrome de abstinencia aguda si dependencia opioide (agitacion, vomitos, convulsiones)",
    },
    "Gluconato de Calcio": {
        "dosis_por_kg": "50-100 mg/kg/dosis (0.5-1 ml/kg de sol 10%)",
        "dosis_mg_kg": (50, 100),
        "intervalo_hs": "cada 6-8 hs segun calcemia",
        "intervalo_min_hs": 6,
        "dosis_max_diaria_mg_kg": 300,
        "dosis_max_por_dosis_mg": 2000,
        "presentacion": "Ampolla gluconato Ca 10% (100 mg/ml), Comp 500 mg",
        "via": "EV (lento), Oral",
        "observaciones": "Hipocalcemia, hipercaliemia. EV lento en 5-10 min con monitorizacion cardiaca. Extravesacion causa necrosis.",
        "alerta": "Bradicardia si EV rapido. No mezclar con bicarbonato de sodio",
    },
    "Vitamina K (Fitomenadiona)": {
        "dosis_por_kg": "0.5-1 mg/kg/dosis",
        "dosis_mg_kg": (0.5, 1),
        "intervalo_hs": "dosis unica, repetir segun INR",
        "intervalo_min_hs": 24,
        "dosis_max_diaria_mg_kg": 5,
        "dosis_max_por_dosis_mg": 10,
        "presentacion": "Inyectable 10 mg/ml, Ampolla pediatrica 1 mg/0.25ml",
        "via": "EV (lento), IM, oral",
        "observaciones": "Profilaxis RN: 0.5-1 mg IM al nacer. Reversion de anticoagulacion. Corregir coagulopatia por malabsorcion.",
        "alerta": "Reaccion anafilactoide si EV rapido. Monitorizar INR",
    },
    "Penicilina G Benzatínica": {
        "dosis_por_kg": "50000 UI/kg/dosis unica",
        "dosis_mg_kg": (50, 50),
        "intervalo_hs": "dosis unica, repetir segun indicacion",
        "intervalo_min_hs": 168,
        "dosis_max_diaria_mg_kg": 600,
        "dosis_max_por_dosis_mg": 2000,
        "presentacion": "Polvo para reconstituir 600.000 UI, 1.200.000 UI",
        "via": "IM profunda",
        "observaciones": "Fiebre reumatica: 1.2 M UI c/21-28 dias. Faringitis estreptococica: 600.000 UI <25kg, 1.2 M UI >25kg.",
        "alerta": "Verificar alergia a penicilina. Riesgo de shock anafilactico. Tener adrenalina disponible",
    },
}


def calcular_dosis(medicamento: str, peso_kg: float, todos_medicamentos: dict = None) -> dict:
    """Calcula dosis pediatrica segun peso del paciente."""
    # Resolver si es una referencia (string) o tiene datos directos
    info = None
    if todos_medicamentos and isinstance(todos_medicamentos.get(medicamento), str):
        # Es una referencia a otro nombre
        medicamento_real = todos_medicamentos[medicamento]
        info = MEDICAMENTOS.get(medicamento_real)
    else:
        info = MEDICAMENTOS.get(medicamento)

    if info is None:
        # Intentar buscar por nombre base
        base, _ = _normalizar_medicamento(medicamento)
        for k, v in MEDICAMENTOS.items():
            if base.lower() in k.lower() or k.lower() in base.lower():
                info = v
                break

    if info is None:
        raise ValueError(f"No hay datos de dosis pediatrica para '{medicamento}'")
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


def _mostrar_resultado(resultado, presentacion, dosis_min, dosis_max, dosis_rec, dosis_max_por_dosis):
    """Renderiza las tarjetas de resultado y presentaciones disponibles."""
    cols = st.columns([1, 1, 1])
    cols[0].metric("Dosis por dosis", f"{dosis_min} - {dosis_max} mg")
    cols[1].metric("Dosis recomendada", f"{dosis_rec} mg")
    cols[2].metric("Maximo por dosis", f"{dosis_max_por_dosis} mg")

    cols2 = st.columns([1, 1, 1])
    cols2[0].metric("Intervalo", resultado["intervalo"])
    cols2[1].metric("Dosis diaria max", f"{resultado['dosis_diaria_max_mg']} mg/dia")
    cols2[2].metric("Presentacion", presentacion[:30], help=presentacion)

    with st.expander("Presentaciones disponibles", expanded=False):
        st.markdown(f"**{presentacion}**")
        for desc in presentacion.split(","):
            desc = desc.strip()
            if "mg/" in desc:
                try:
                    conc_val = float(desc.split("mg/")[0].strip().split()[-1])
                    vol_min = round(dosis_min / conc_val, 1)
                    vol_max = round(dosis_max / conc_val, 1)
                    vol_rec = round(dosis_rec / conc_val, 1)
                    st.markdown(f"- **{desc}**: {vol_min}-{vol_max} ml (recomendado: {vol_rec} ml)")
                except (ValueError, IndexError):
                    st.markdown(f"- {desc}")


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
        _MANUAL_KEY = "✏️ Ingreso manual..."
        _todos = sorted(k for k, v in _TODOS_MEDICAMENTOS.items() if isinstance(v, dict)) + [_MANUAL_KEY]

        medicamento = st.selectbox(
            "Medicamento *",
            _todos,
            format_func=lambda x: x,
            help="Seleccionar un medicamento de la base pediatrica o elija 'Ingreso manual' para personalizar.",
        )

        es_manual = medicamento == _MANUAL_KEY
        if es_manual:
            with st.expander("Parametros del medicamento", expanded=True):
                manual_nombre = st.text_input("Nombre del medicamento", key="m_nombre")
                mc1, mc2 = st.columns(2)
                with mc1:
                    manual_dosis_min = st.number_input("Dosis min (mg/kg/dosis)", min_value=0.0, step=0.1, value=10.0, key="m_min")
                    manual_dosis_max = st.number_input("Dosis max (mg/kg/dosis)", min_value=0.0, step=0.1, value=15.0, key="m_max")
                    manual_intervalo_val = st.number_input("Intervalo minimo (hs)", min_value=0.0, step=1.0, value=6.0, key="m_int")
                with mc2:
                    manual_max_diaria = st.number_input("Dosis max diaria (mg/kg)", min_value=0.0, step=1.0, value=60.0, key="m_diaria")
                    manual_max_dosis = st.number_input("Dosis max por dosis (mg)", min_value=0.0, step=1.0, value=500.0, key="m_maxdosis")
                manual_via = st.text_input("Via de administracion", value="Oral", key="m_via")
                manual_presentacion = st.text_input("Presentacion (presentaciones disponibles)", value="Comp 500 mg", key="m_pres")
                manual_obs = st.text_area("Observaciones", value="", key="m_obs")
        else:
            info = _TODOS_MEDICAMENTOS[medicamento]
            if isinstance(info, str):
                st.caption(f"Disponible como '{info}'. Via y dosis segun base de datos.")
            else:
                st.caption(f"Via: {info['via']} | Intervalo: {info['intervalo_hs']} | Dosis calculada segun peso")

    st.divider()

    if st.button("Calcular dosis", width="stretch", type="primary", key="calc_dosis"):
        if peso <= 0:
            st.error("El peso debe ser mayor a 0.")
        elif es_manual:
            if not st.session_state.get("m_nombre", "").strip():
                st.error("Debe ingresar el nombre del medicamento en 'Ingreso manual'.")
            else:
                res = {
                    "medicamento": st.session_state["m_nombre"].strip(),
                    "peso": peso,
                    "dosis_por_kg": f"{st.session_state['m_min']}-{st.session_state['m_max']} mg/kg/dosis",
                    "dosis_min_mg": round(peso * st.session_state["m_min"], 1),
                    "dosis_max_mg": round(peso * st.session_state["m_max"], 1),
                    "dosis_recomendada_mg": min(round(peso * st.session_state["m_max"], 1), st.session_state["m_maxdosis"]),
                    "intervalo": f"cada {st.session_state['m_int']} hs",
                    "dosis_diaria_max_mg": round(peso * st.session_state["m_diaria"], 1),
                    "dosis_max_por_dosis_mg": st.session_state["m_maxdosis"],
                    "presentacion": st.session_state["m_pres"],
                    "via": st.session_state["m_via"],
                    "observaciones": st.session_state["m_obs"],
                    "alerta": None,
                }
                st.markdown(f"### Resultado del calculo — {res['medicamento']} (ingreso manual)")
                _mostrar_resultado(res, res["presentacion"], res["dosis_min_mg"], res["dosis_max_mg"], res["dosis_recomendada_mg"], res["dosis_max_por_dosis_mg"])
                st.markdown("### Observaciones")
                obs = res["observaciones"] or "Sin observaciones."
                st.info(obs)
                log_event("calculadora_dosis", f"MANUAL:{res['medicamento']} - {peso}kg - {paciente_sel}")
        else:
            info = _TODOS_MEDICAMENTOS[medicamento]
            resultado = calcular_dosis(medicamento, peso, _TODOS_MEDICAMENTOS)
            raw = _TODOS_MEDICAMENTOS[medicamento]
            if isinstance(raw, str):
                info = MEDICAMENTOS[raw]
            else:
                info = raw

            st.markdown("### Resultado del calculo")
            _mostrar_resultado(resultado, resultado["presentacion"], resultado["dosis_min_mg"], resultado["dosis_max_mg"], resultado["dosis_recomendada_mg"], resultado["dosis_max_por_dosis_mg"])

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

            st.markdown("### Observaciones")
            st.info(resultado["observaciones"])

            if resultado["alerta"]:
                st.error(f"ALERTA: {resultado['alerta']}", icon="🚨")

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
