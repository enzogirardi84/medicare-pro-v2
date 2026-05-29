"""Calculos medicos puros, sin dependencias de Streamlit ni base de datos.

Extraido de views/calculadora_dosis.py para permitir testing unitario
y reutilizacion desde API REST.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple


def calcular_dosis_pediatrica(peso_kg: float, dosis_mg_kg: float, max_dosis_diaria: Optional[float] = None) -> Dict[str, float]:
    """Calcula dosis pediatrica segun peso.

    Args:
        peso_kg: Peso del paciente en kilogramos
        dosis_mg_kg: Dosis en mg por kg
        max_dosis_diaria: Dosis maxima diaria en mg (opcional)

    Returns:
        Dict con dosis_calculada_mg, maximo_diario_mg

    Raises:
        ValueError: Si peso_kg <= 0 o dosis_mg_kg <= 0
    """
    if peso_kg <= 0:
        raise ValueError("El peso debe ser mayor a cero.")
    if dosis_mg_kg <= 0:
        raise ValueError("La dosis debe ser mayor a cero.")

    dosis = peso_kg * dosis_mg_kg
    resultado = {
        "dosis_calculada_mg": round(dosis, 2),
        "dosis_mg_kg": dosis_mg_kg,
        "peso_kg": peso_kg,
    }

    if max_dosis_diaria and dosis > max_dosis_diaria:
        resultado["dosis_calculada_mg"] = round(max_dosis_diaria, 2)
        resultado["maximo_diario_mg"] = max_dosis_diaria
        resultado["ajustada_por_maximo"] = True
    else:
        resultado["maximo_diario_mg"] = max_dosis_diaria or 0
        resultado["ajustada_por_maximo"] = False

    return resultado


def normalizar_medicamento(nombre: str) -> Tuple[str, str]:
    """Parsea nombre de medicamento extrayendo concentracion.

    Args:
        nombre: Ej. 'Amoxicilina 500mg' o 'Ibuprofeno 100mg/5ml'

    Returns:
        (nombre_base, concentracion_str)
    """
    import re
    nombre = (nombre or "").strip()

    # Patron: "Nombre Xmg" o "Nombre Xmg/Yml"
    m = re.match(r"^([A-Za-z\u00C0-\u00FF][A-Za-z\u00C0-\u00FF\s]+?)\s+([\d,]+(?:\s*mg)?(?:\s*/\s*[\d,]+\s*ml)?)$", nombre)
    if m:
        base = m.group(1).strip()
        conc = m.group(2).strip().replace(",", ".")
        return base, conc

    # Patron: "Nombre de X mg"
    m2 = re.match(r"^([A-Za-z\u00C0-\u00FF][A-Za-z\u00C0-\u00FF\s]+?)\s+de\s+([\d,]+)\s*mg", nombre)
    if m2:
        return m2.group(1).strip(), m2.group(2).strip().replace(",", ".")

    return nombre, ""


def validar_rango_vital(temperatura: Optional[float] = None, frecuencia_cardiaca: Optional[int] = None,
                         presion_sistolica: Optional[int] = None, saturacion_o2: Optional[int] = None) -> List[Dict]:
    """Valida signos vitales contra rangos normales.

    Returns:
        Lista de alertas: [{parametro, valor, rango, severidad}]
    """
    alertas = []

    if temperatura is not None:
        if temperatura < 35.0:
            alertas.append({"parametro": "Temperatura", "valor": temperatura, "rango": "36.1-37.2", "severidad": "critica"})
        elif temperatura > 38.5:
            alertas.append({"parametro": "Temperatura", "valor": temperatura, "rango": "36.1-37.2", "severidad": "alta"})

    if frecuencia_cardiaca is not None:
        if frecuencia_cardiaca < 50:
            alertas.append({"parametro": "FC", "valor": frecuencia_cardiaca, "rango": "60-100", "severidad": "critica"})
        elif frecuencia_cardiaca > 120:
            alertas.append({"parametro": "FC", "valor": frecuencia_cardiaca, "rango": "60-100", "severidad": "alta"})

    if presion_sistolica is not None:
        if presion_sistolica > 180:
            alertas.append({"parametro": "PA Sistolica", "valor": presion_sistolica, "rango": "90-140", "severidad": "critica"})

    if saturacion_o2 is not None:
        if saturacion_o2 < 90:
            alertas.append({"parametro": "SpO2", "valor": saturacion_o2, "rango": "95-100", "severidad": "critica"})
        elif saturacion_o2 < 95:
            alertas.append({"parametro": "SpO2", "valor": saturacion_o2, "rango": "95-100", "severidad": "media"})

    return alertas


def calcular_balance_hidrico(ingresos_ml: float, egresos_ml: float) -> float:
    """Calcula balance hidrico: ingresos - egresos."""
    return round(ingresos_ml - egresos_ml, 1)
