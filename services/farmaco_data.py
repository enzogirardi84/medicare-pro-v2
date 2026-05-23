"""Base de datos farmacologica pediatrica y formulas de dosificacion.

Fuentes: AAP, OMS, UpToDate, Formulario Nacional Pediatrico.
Sin dependencias de Streamlit. Testeable unitariamente.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ============================================================
# BASE DE DATOS FARMACOLOGICA PEDIATRICA
# ============================================================

MEDICAMENTOS: Dict[str, Dict[str, Any]] = {
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
        "alerta": "Verificar alergia a penicilina antes de administrar",
    },
    "Ceftriaxona": {
        "dosis_por_kg": "50-80 mg/kg/dia c/12-24hs",
        "dosis_mg_kg": (50, 80),
        "intervalo_hs": "cada 12-24 hs",
        "intervalo_min_hs": 12,
        "dosis_max_diaria_mg_kg": 80,
        "dosis_max_por_dosis_mg": 2000,
        "presentacion": "IM/IV 1g frasco ampolla",
        "via": "IM/IV",
        "observaciones": "No mezclar con calcio en neonatos. Diluir segun protocolo institucional.",
        "alerta": None,
    },
    "Dexametasona": {
        "dosis_por_kg": "0.15-0.6 mg/kg/dosis c/6-12hs",
        "dosis_mg_kg": (0.15, 0.6),
        "intervalo_hs": "cada 6-12 hs",
        "intervalo_min_hs": 6,
        "dosis_max_diaria_mg_kg": 2.4,
        "dosis_max_por_dosis_mg": 16,
        "presentacion": "Comp 0.5/0.75/1.5/4mg, Solucion 2mg/5ml, Inyectable 4mg/ml",
        "via": "Oral/IV/IM",
        "observaciones": "Usar el minimo tiempo posible. Contraindicado en infecciones fungicas sistemica.",
        "alerta": None,
    },
    "Diazepam": {
        "dosis_por_kg": "0.2-0.3 mg/kg/dosis",
        "dosis_mg_kg": (0.2, 0.3),
        "intervalo_hs": "cada 8 hs segun respuesta",
        "intervalo_min_hs": 8,
        "dosis_max_diaria_mg_kg": 0.9,
        "dosis_max_por_dosis_mg": 10,
        "presentacion": "Comp 2/5/10mg, Solucion 2mg/5ml, Inyectable 5mg/ml, Rectal 5/10mg",
        "via": "Oral/IV/IM/rectal",
        "observaciones": "Riesgo de depresion respiratoria. Tener flumazenilo disponible.",
        "alerta": "Riesgo de depresion respiratoria",
    },
    "Diclofenac": {
        "dosis_por_kg": "0.5-1 mg/kg/dosis c/8-12hs",
        "dosis_mg_kg": (0.5, 1),
        "intervalo_hs": "cada 8-12 hs",
        "intervalo_min_hs": 8,
        "dosis_max_diaria_mg_kg": 3,
        "dosis_max_por_dosis_mg": 50,
        "presentacion": "Comp 50/75mg, Gotas 15mg/ml, Inyectable 75mg/3ml",
        "via": "Oral/IM",
        "observaciones": "Contraindicado en <6 meses, asma, insuficiencia renal, ulcera peptica.",
        "alerta": "No usar en menores de 6 meses",
    },
    "Dipirona (Metamizol)": {
        "dosis_por_kg": "10-15 mg/kg/dosis c/6-8hs",
        "dosis_mg_kg": (10, 15),
        "intervalo_hs": "cada 6-8 hs",
        "intervalo_min_hs": 6,
        "dosis_max_diaria_mg_kg": 60,
        "dosis_max_por_dosis_mg": 1000,
        "presentacion": "Gotas 500mg/ml, Comp 500mg, Inyectable 1g/2ml",
        "via": "Oral/IV/IM",
        "observaciones": "Riesgo de agranulocitosis. No usar >7 dias. IV lento (1g/min).",
        "alerta": None,
    },
    "Enoxaparina": {
        "dosis_por_kg": "1 mg/kg/dosis c/12hs (terapeutico)",
        "dosis_mg_kg": (1, 1),
        "intervalo_hs": "cada 12 hs",
        "intervalo_min_hs": 12,
        "dosis_max_diaria_mg_kg": 2,
        "dosis_max_por_dosis_mg": 100,
        "presentacion": "Jeringa 40/60/80/100mg, Frasco 100mg/ml",
        "via": "SC",
        "observaciones": "No aplicar IM. Monitorear factor anti-Xa. Contraindicado si trombocitopenia.",
        "alerta": "Riesgo de sangrado. Monitorear anti-Xa",
    },
    "Fentanilo": {
        "dosis_por_kg": "1-2 mcg/kg/dosis c/30-60min (IV)",
        "dosis_mg_kg": (0.001, 0.002),
        "intervalo_hs": "cada 30-60 min (IV)",
        "intervalo_min_hs": 0.5,
        "dosis_max_diaria_mg_kg": 0.05,
        "dosis_max_por_dosis_mg": 0.1,
        "presentacion": "Inyectable 50 mcg/ml, 100 mcg/2ml",
        "via": "IV/IM/transdermico",
        "observaciones": "Riesgo de depresion respiratoria. Monitorear saturacion. Tener naloxona disponible.",
        "alerta": "Riesgo de depresion respiratoria severa",
    },
    "Fenitoina": {
        "dosis_por_kg": "15-20 mg/kg (dosis de carga) - 5 mg/kg/dia (mantenimiento)",
        "dosis_mg_kg": (5, 8),
        "intervalo_hs": "cada 8-12 hs",
        "intervalo_min_hs": 8,
        "dosis_max_diaria_mg_kg": 15,
        "dosis_max_por_dosis_mg": 300,
        "presentacion": "Comp 50/100mg, Suspension 125mg/5ml, Inyectable 250mg/5ml",
        "via": "Oral/IV",
        "observaciones": "Monitorear niveles plasmaticos (10-20 mcg/ml). No IM. IV lento (<50 mg/min).",
        "alerta": "Monitorear niveles plasmaticos",
    },
    "Fenobarbital": {
        "dosis_por_kg": "15-20 mg/kg (carga) - 3-5 mg/kg/dia (mantenimiento)",
        "dosis_mg_kg": (3, 5),
        "intervalo_hs": "cada 12-24 hs",
        "intervalo_min_hs": 12,
        "dosis_max_diaria_mg_kg": 5,
        "dosis_max_por_dosis_mg": 200,
        "presentacion": "Comp 15/50/100mg, Solucion 40mg/ml, Inyectable 100mg/ml",
        "via": "Oral/IV/IM",
        "observaciones": "Sedacion. Riesgo de dependencia. No discontinuar bruscamente.",
        "alerta": None,
    },
    "Fluconazol": {
        "dosis_por_kg": "3-12 mg/kg/dosis c/24hs",
        "dosis_mg_kg": (3, 12),
        "intervalo_hs": "cada 24 hs",
        "intervalo_min_hs": 24,
        "dosis_max_diaria_mg_kg": 12,
        "dosis_max_por_dosis_mg": 400,
        "presentacion": "Comp 50/100/150/200mg, Suspension 10mg/ml, Inyectable 2mg/ml",
        "via": "Oral/IV",
        "observaciones": "Ajustar en insuficiencia renal. Hepatotoxico. Monitorear funcion hepatica.",
        "alerta": None,
    },
    "Furosemida": {
        "dosis_por_kg": "1-2 mg/kg/dosis c/6-12hs",
        "dosis_mg_kg": (1, 2),
        "intervalo_hs": "cada 6-12 hs",
        "intervalo_min_hs": 6,
        "dosis_max_diaria_mg_kg": 6,
        "dosis_max_por_dosis_mg": 80,
        "presentacion": "Comp 20/40mg, Solucion 10mg/ml, Inyectable 20mg/2ml",
        "via": "Oral/IV/IM",
        "observaciones": "Monitorear K+, Na+, funcion renal. Ototoxico con aminoglucosidos.",
        "alerta": None,
    },
    "Heparina Sodica": {
        "dosis_por_kg": "50-100 UI/kg/dosis c/4hs (IV)",
        "dosis_mg_kg": (50, 100),
        "intervalo_hs": "cada 4 hs",
        "intervalo_min_hs": 4,
        "dosis_max_diaria_mg_kg": 600,
        "dosis_max_por_dosis_mg": 5000,
        "presentacion": "Frasco 1000/5000 UI/ml",
        "via": "IV/SC",
        "observaciones": "Monitorear TTPA cada 6hs. Tener protamina disponible. Riesgo de sangrado.",
        "alerta": "Riesgo de sangrado. Monitorear TTPA",
    },
    "Hidrocortisona": {
        "dosis_por_kg": "2-8 mg/kg/dosis c/6-8hs",
        "dosis_mg_kg": (2, 8),
        "intervalo_hs": "cada 6-8 hs",
        "intervalo_min_hs": 6,
        "dosis_max_diaria_mg_kg": 32,
        "dosis_max_por_dosis_mg": 200,
        "presentacion": "Comp 10/20mg, Inyectable 100/500mg",
        "via": "Oral/IV/IM",
        "observaciones": "Uso corto plazo (<7 dias). No discontinuar bruscamente en tratamiento >2 semanas.",
        "alerta": None,
    },
    "Ipratropio": {
        "dosis_por_kg": "250-500 mcg/dosis c/6-8hs (inhalado)",
        "dosis_mg_kg": (0.25, 0.5),
        "intervalo_hs": "cada 6-8 hs",
        "intervalo_min_hs": 6,
        "dosis_max_diaria_mg_kg": 1.5,
        "dosis_max_por_dosis_mg": 0.5,
        "presentacion": "Solucion inhalar 0.25/0.5mg/ml, Aerosol 20/40mcg",
        "via": "Inhalatorio",
        "observaciones": "Puede combinarse con salbutamol. Boca seca frecuente.",
        "alerta": None,
    },
    "Ketamina": {
        "dosis_por_kg": "1-2 mg/kg/dosis (IV sedacion)",
        "dosis_mg_kg": (1, 2),
        "intervalo_hs": "segun respuesta clinica",
        "intervalo_min_hs": 24,
        "dosis_max_diaria_mg_kg": 4,
        "dosis_max_por_dosis_mg": 100,
        "presentacion": "Inyectable 50mg/ml, 100mg/ml",
        "via": "IV/IM",
        "observaciones": "Alucinaciones. Riesgo de laringoespasmo. Tener atropina disponible.",
        "alerta": "Riesgo de laringoespasmo. Tener atropina disponible",
    },
    "Loratadina": {
        "dosis_por_kg": "0.1-0.2 mg/kg/dosis c/24hs",
        "dosis_mg_kg": (0.1, 0.2),
        "intervalo_hs": "cada 24 hs",
        "intervalo_min_hs": 24,
        "dosis_max_diaria_mg_kg": 0.2,
        "dosis_max_por_dosis_mg": 10,
        "presentacion": "Comp 10mg, Jarabe 5mg/5ml",
        "via": "Oral",
        "observaciones": "Antihistaminico no sedante. Efecto maximo 1-2hs. Administrar con o sin alimentos.",
        "alerta": None,
    },
    "Metoclopramida": {
        "dosis_por_kg": "0.1-0.2 mg/kg/dosis c/6-8hs",
        "dosis_mg_kg": (0.1, 0.2),
        "intervalo_hs": "cada 6-8 hs",
        "intervalo_min_hs": 6,
        "dosis_max_diaria_mg_kg": 0.6,
        "dosis_max_por_dosis_mg": 10,
        "presentacion": "Comp 10mg, Solucion 5mg/5ml, Inyectable 10mg/2ml",
        "via": "Oral/IV/IM",
        "observaciones": "Riesgo de sintomas extrapiramidales en ninos. Usar <5 dias.",
        "alerta": "Riesgo de sintomas extrapiramidales en ninos",
    },
    "Metronidazol": {
        "dosis_por_kg": "7.5-15 mg/kg/dosis c/8hs",
        "dosis_mg_kg": (7.5, 15),
        "intervalo_hs": "cada 8 hs",
        "intervalo_min_hs": 8,
        "dosis_max_diaria_mg_kg": 45,
        "dosis_max_por_dosis_mg": 500,
        "presentacion": "Comp 250/500mg, Suspension 125mg/5ml, Inyectable 500mg/100ml",
        "via": "Oral/IV",
        "observaciones": "Sabor metalico. No tomar alcohol. Ajustar en insuficiencia hepatica.",
        "alerta": None,
    },
    "Midazolam": {
        "dosis_por_kg": "0.05-0.1 mg/kg/dosis (IV sedacion consciente)",
        "dosis_mg_kg": (0.05, 0.1),
        "intervalo_hs": "cada 2-4 hs segun respuesta",
        "intervalo_min_hs": 2,
        "dosis_max_diaria_mg_kg": 0.4,
        "dosis_max_por_dosis_mg": 5,
        "presentacion": "Inyectable 5mg/ml, 15mg/3ml, Solucion oral 2mg/ml",
        "via": "IV/IM/Oral/Intranasal",
        "observaciones": "Riesgo de depresion respiratoria. Monitorear saturacion. Tener flumazenilo.",
        "alerta": "Riesgo de depresion respiratoria",
    },
    "Morfina": {
        "dosis_por_kg": "0.1-0.2 mg/kg/dosis c/4hs (IV)",
        "dosis_mg_kg": (0.1, 0.2),
        "intervalo_hs": "cada 4 hs",
        "intervalo_min_hs": 4,
        "dosis_max_diaria_mg_kg": 1.2,
        "dosis_max_por_dosis_mg": 10,
        "presentacion": "Inyectable 10mg/ml, Comp 10mg, Solucion 2mg/ml",
        "via": "IV/IM/SC/Oral",
        "observaciones": "Riesgo de depresion respiratoria. Tener naloxona disponible. Monitorear sedacion.",
        "alerta": "Riesgo de depresion respiratoria. Tener naloxona",
    },
    "Naloxona": {
        "dosis_por_kg": "0.01-0.1 mg/kg/dosis c/2-3min (IV)",
        "dosis_mg_kg": (0.01, 0.1),
        "intervalo_hs": "cada 2-3 min segun respuesta",
        "intervalo_min_hs": 0.05,
        "dosis_max_diaria_mg_kg": 10,
        "dosis_max_por_dosis_mg": 2,
        "presentacion": "Inyectable 0.4mg/ml, 1mg/ml",
        "via": "IV/IM/SC/Intranasal",
        "observaciones": "Titular hasta respuesta. Duracion <45min. Monitorear reaparicion de depresion.",
        "alerta": None,
    },
    "Omeprazol": {
        "dosis_por_kg": "0.5-1 mg/kg/dosis c/12-24hs",
        "dosis_mg_kg": (0.5, 1),
        "intervalo_hs": "cada 12-24 hs",
        "intervalo_min_hs": 12,
        "dosis_max_diaria_mg_kg": 2,
        "dosis_max_por_dosis_mg": 40,
        "presentacion": "Comp 20mg, Suspension 20mg, Inyectable 40mg",
        "via": "Oral/IV",
        "observaciones": "Administrar en ayunas 30-60min antes de comidas. No masticar comprimidos.",
        "alerta": None,
    },
    "Ondansetron": {
        "dosis_por_kg": "0.1-0.15 mg/kg/dosis c/8hs",
        "dosis_mg_kg": (0.1, 0.15),
        "intervalo_hs": "cada 8 hs",
        "intervalo_min_hs": 8,
        "dosis_max_diaria_mg_kg": 0.45,
        "dosis_max_por_dosis_mg": 8,
        "presentacion": "Comp 4/8mg, Solucion 4mg/5ml, OD T 4/8mg, Inyectable 4mg/2ml",
        "via": "Oral/IV/IM",
        "observaciones": "Prolongacion intervalo QT (dosis dependiente). Riesgo de cefalea y estrenimiento.",
        "alerta": None,
    },
    "Prednisona / Prednisolona": {
        "dosis_por_kg": "1-2 mg/kg/dia c/12-24hs",
        "dosis_mg_kg": (0.5, 1),
        "intervalo_hs": "cada 12-24 hs",
        "intervalo_min_hs": 12,
        "dosis_max_diaria_mg_kg": 2,
        "dosis_max_por_dosis_mg": 60,
        "presentacion": "Comp 5/20/50mg, Solucion 15mg/5ml",
        "via": "Oral",
        "observaciones": "No discontinuar bruscamente. Uso cronico: monitorear crecimiento.",
        "alerta": None,
    },
    "Propofol": {
        "dosis_por_kg": "1-2.5 mg/kg (induccion) - 25-100 mcg/kg/min (mantenimiento)",
        "dosis_mg_kg": (1, 2.5),
        "intervalo_hs": "segun respuesta (solo en UCI/quirófano)",
        "intervalo_min_hs": 24,
        "dosis_max_diaria_mg_kg": 24,
        "dosis_max_por_dosis_mg": 200,
        "presentacion": "Inyectable 10mg/ml, 20mg/ml",
        "via": "IV",
        "observaciones": "Solo en UCI/quirófano con via aerea segura. Riesgo de depresion respiratoria.",
        "alerta": "Solo en UCI/quirófano con via aerea segura",
    },
    "Salbutamol": {
        "dosis_por_kg": "0.1-0.15 mg/kg/dosis c/20min (inhalado crisis)",
        "dosis_mg_kg": (0.1, 0.15),
        "intervalo_hs": "cada 20 min (crisis) o c/4-6hs (mantenimiento)",
        "intervalo_min_hs": 0.3,
        "dosis_max_diaria_mg_kg": 2,
        "dosis_max_por_dosis_mg": 5,
        "presentacion": "Aerosol 100mcg, Solucion inhalar 5mg/ml, Inyectable 0.5mg/ml",
        "via": "Inhalatorio/IV/SC",
        "observaciones": "Taquicardia, temblor. Monitorear K+. No usar como monoterapia en crisis severa.",
        "alerta": None,
    },
}


def parse_intervalo(text: str) -> Tuple[float, float]:
    """Parsea texto de intervalo a (min_hs, max_hs). Ej: 'cada 4-6 hs' -> (4, 6)."""
    import re
    text = str(text or "").lower().strip()
    m = re.search(r"(\d+)\s*(?:-|a)\s*(\d+)\s*(?:h|hs)", text)
    if m:
        return float(m.group(1)), float(m.group(2))
    m2 = re.search(r"cada\s+(\d+)\s*(?:h|hs)", text)
    if m2:
        v = float(m2.group(1))
        return v, v
    return 4, 6


def normalizar_medicamento(nombre: str) -> Tuple[str, str]:
    """Parsea nombre de medicamento extrayendo concentracion."""
    import re
    nombre = (nombre or "").strip()
    m = re.match(r"^([A-Za-z\u00C0-\u00FF][A-Za-z\u00C0-\u00FF\s]+?)\s+([\d,]+(?:\s*mg)?(?:\s*/\s*[\d,]+\s*ml)?)$", nombre)
    if m:
        return m.group(1).strip(), m.group(2).strip().replace(",", ".")
    m2 = re.match(r"^([A-Za-z\u00C0-\u00FF][A-Za-z\u00C0-\u00FF\s]+?)\s+de\s+([\d,]+)\s*mg", nombre)
    if m2:
        return m2.group(1).strip(), m2.group(2).strip().replace(",", ".")
    return nombre, ""


def calcular_dosis_pediatrica_completa(
    medicamento: str,
    peso_kg: float,
    farmacos: Optional[Dict[str, Dict]] = None,
    intervalo_seleccionado_hs: Optional[float] = None,
) -> Dict[str, Any]:
    """Calcula dosis pediatrica completa con todas las variables.
    
    Args:
        medicamento: Nombre del medicamento
        peso_kg: Peso del paciente en kg
        farmacos: Diccionario de farmacos (usa MEDICAMENTOS global si no se provee)
        intervalo_seleccionado_hs: Intervalo personalizado en horas
    
    Returns:
        Dict con todos los parametros calculados
    
    Raises:
        ValueError: Si no hay datos para el medicamento o peso invalido
    """
    if peso_kg <= 0:
        raise ValueError("El peso debe ser mayor a cero.")
    
    farmacos = farmacos or MEDICAMENTOS
    info = farmacos.get(medicamento)
    
    if info is None:
        base, _ = normalizar_medicamento(medicamento)
        for k, v in farmacos.items():
            if base.lower() in k.lower() or k.lower() in base.lower():
                info = v
                break
    
    if info is None:
        raise ValueError(f"No hay datos de dosis pediatrica para '{medicamento}'")
    
    intervalo = intervalo_seleccionado_hs or info["intervalo_min_hs"]
    dosis_por_dia = 24 / intervalo
    
    dosis_min, dosis_max = info["dosis_mg_kg"]
    dosis_por_dosis_min = round(peso_kg * dosis_min, 1)
    dosis_por_dosis_max = round(peso_kg * dosis_max, 1)
    
    max_por_dosis = info["dosis_max_por_dosis_mg"]
    dosis_recomendada = min(dosis_por_dosis_max, max_por_dosis)
    
    dosis_diaria_min = round(peso_kg * dosis_min * dosis_por_dia, 1)
    dosis_diaria_max_por_peso = round(peso_kg * info["dosis_max_diaria_mg_kg"], 1)
    dosis_diaria_max = min(dosis_diaria_max_por_peso, round(max_por_dosis * dosis_por_dia, 1))
    
    return {
        "medicamento": medicamento,
        "peso": peso_kg,
        "dosis_por_kg": info.get("dosis_por_kg", ""),
        "dosis_min_mg": dosis_por_dosis_min,
        "dosis_max_mg": dosis_por_dosis_max,
        "dosis_recomendada_mg": dosis_recomendada,
        "intervalo": info.get("intervalo_hs", ""),
        "intervalo_seleccionado_hs": round(intervalo, 1),
        "dosis_por_dia": round(dosis_por_dia),
        "dosis_diaria_min_mg": dosis_diaria_min,
        "dosis_diaria_max_mg": dosis_diaria_max,
        "dosis_max_por_dosis_mg": max_por_dosis,
        "presentacion": info.get("presentacion", ""),
        "via": info.get("via", ""),
        "observaciones": info.get("observaciones", ""),
        "alerta": info.get("alerta"),
    }
