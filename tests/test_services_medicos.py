"""Tests unitarios para services/calculos_medicos.py (sin dependencias de Streamlit)."""

from __future__ import annotations

from services.calculos_medicos import (
    calcular_dosis_pediatrica,
    normalizar_medicamento,
    validar_rango_vital,
    calcular_balance_hidrico,
)


def test_calcular_dosis_pediatrica_normal():
    res = calcular_dosis_pediatrica(40, 2.5)
    assert res["dosis_calculada_mg"] == 100.0
    assert not res["ajustada_por_maximo"]


def test_calcular_dosis_pediatrica_con_maximo():
    res = calcular_dosis_pediatrica(40, 2.5, max_dosis_diaria=80)
    assert res["dosis_calculada_mg"] == 80.0
    assert res["ajustada_por_maximo"]


def test_calcular_dosis_peso_cero_raise():
    import pytest
    with pytest.raises(ValueError, match="mayor a cero"):
        calcular_dosis_pediatrica(0, 2.5)


def test_normalizar_medicamento_concentracion():
    base, conc = normalizar_medicamento("Amoxicilina 500mg")
    assert base == "Amoxicilina"
    assert "500" in conc


def test_normalizar_medicamento_sin_concentracion():
    base, conc = normalizar_medicamento(" Paracetamol ")
    assert base == "Paracetamol"
    assert conc == ""


def test_validar_rango_vital_normal():
    alertas = validar_rango_vital(temperatura=36.5, frecuencia_cardiaca=72, saturacion_o2=98)
    assert len(alertas) == 0


def test_validar_rango_vital_fiebre():
    alertas = validar_rango_vital(temperatura=39.0)
    assert len(alertas) == 1
    assert alertas[0]["severidad"] == "alta"


def test_validar_rango_vital_hipoxemia_critica():
    alertas = validar_rango_vital(saturacion_o2=85)
    assert len(alertas) == 1
    assert alertas[0]["severidad"] == "critica"


def test_calcular_balance_hidrico_positivo():
    assert calcular_balance_hidrico(2000, 1500) == 500.0


def test_calcular_balance_hidrico_negativo():
    assert calcular_balance_hidrico(1000, 1800) == -800.0


def test_calcular_balance_hidrico_cero():
    assert calcular_balance_hidrico(1500, 1500) == 0.0
