"""Tests para core/_insumos_map.py — mapa clínico de insumos."""

from __future__ import annotations

from core._insumos_map import (
    MEDICAMENTO_A_INSUMOS,
    PROCEDIMIENTO_A_INSUMOS,
    insumos_para_medicamento,
    insumos_para_procedimiento,
)


# ---------------------------------------------------------------------------
# Búsqueda de medicamentos
# ---------------------------------------------------------------------------

def test_medicamento_conocido_ev():
    result = insumos_para_medicamento("Hiocina 20mg EV")
    items = [r["item"] for r in result]
    assert "Jeringa 5ml" in items
    assert "Aguja EV" in items


def test_medicamento_conocido_im():
    result = insumos_para_medicamento("Diclofenac 75mg IM")
    items = [r["item"] for r in result]
    assert "Jeringa 5ml" in items
    assert "Aguja IM" in items


def test_medicamento_conocido_sc():
    result = insumos_para_medicamento("Heparina 5000UI SC")
    items = [r["item"] for r in result]
    assert "Jeringa 1ml" in items
    assert "Aguja SC" in items


def test_medicamento_con_equipo_venoclisis():
    result = insumos_para_medicamento("Solucion fisiologica 500ml")
    items = [r["item"] for r in result]
    assert "Equipo de venoclisis" in items


def test_medicamento_oral_sin_insumos():
    result = insumos_para_medicamento("Paracetamol 1g comprimidos")
    assert result == []


def test_medicamento_desconocido():
    result = insumos_para_medicamento("medicamento-falso-xyz-999")
    assert result == []


# ---------------------------------------------------------------------------
# Búsqueda de procedimientos
# ---------------------------------------------------------------------------

def test_procedimiento_bano_en_cama():
    result = insumos_para_procedimiento("Se realizó baño en cama del paciente")
    items = [r["item"] for r in result]
    assert "Pañal descartable" in items
    assert "Toalla húmeda" in items
    assert "Guantes descartables" in items


def test_procedimiento_curacion():
    result = insumos_para_procedimiento("Curacion de herida quirurgica")
    items = [r["item"] for r in result]
    assert "Gasas estériles" in items
    assert "Apósito estéril" in items


def test_procedimiento_sondaje():
    result = insumos_para_procedimiento("Se colocó sonda vesical")
    items = [r["item"] for r in result]
    assert "Sonda vesical" in items
    assert "Bolsa colectora" in items


def test_procedimiento_glucemia():
    result = insumos_para_procedimiento("Control de glucemia matinal")
    items = [r["item"] for r in result]
    assert "Tira reactiva glucemia" in items or "Lanceta" in items


def test_procedimiento_nebulizacion():
    result = insumos_para_procedimiento("Se administró nebulizacion")
    items = [r["item"] for r in result]
    assert "Equipo de nebulización" in items


def test_procedimiento_sin_insumos():
    result = insumos_para_procedimiento("Paciente en buen estado general")
    assert result == []


def test_procedimiento_texto_vacio():
    assert insumos_para_procedimiento("") == []


# ---------------------------------------------------------------------------
# Preferencia por clave más larga (más específica)
# ---------------------------------------------------------------------------

def test_prefiere_clave_mas_larga():
    """'baño en cama' (más específico) debe ganar a 'baño'."""
    result = insumos_para_procedimiento("Se realizó baño en cama del paciente")
    items = [r["item"] for r in result]
    # 'baño en cama' tiene Sábana descartable y Jabón quirúrgico
    assert "Sábana descartable" in items
    assert "Jabón quirúrgico" in items


# ---------------------------------------------------------------------------
# Validación de estructura del mapa
# ---------------------------------------------------------------------------

def test_todas_las_claves_en_minusculas():
    for k in MEDICAMENTO_A_INSUMOS:
        assert k == k.lower(), f"Clave '{k}' debe estar en minúsculas"
    for k in PROCEDIMIENTO_A_INSUMOS:
        assert k == k.lower(), f"Clave '{k}' debe estar en minúsculas"


def test_todos_los_insumos_tienen_campos_requeridos():
    for nombre_clave, items in MEDICAMENTO_A_INSUMOS.items():
        for item in items:
            assert "item" in item, f"Falta 'item' en {nombre_clave}: {item}"
            assert "cantidad" in item, f"Falta 'cantidad' en {nombre_clave}: {item}"
            assert isinstance(item["cantidad"], int), f"'cantidad' debe ser int en {nombre_clave}: {item}"
            assert item["cantidad"] > 0, f"'cantidad' debe ser > 0 en {nombre_clave}: {item}"

    for nombre_clave, items in PROCEDIMIENTO_A_INSUMOS.items():
        for item in items:
            assert "item" in item, f"Falta 'item' en {nombre_clave}: {item}"
            assert "cantidad" in item, f"Falta 'cantidad' en {nombre_clave}: {item}"
            assert isinstance(item["cantidad"], int), f"'cantidad' debe ser int en {nombre_clave}: {item}"
            assert item["cantidad"] > 0, f"'cantidad' debe ser > 0 en {nombre_clave}: {item}"


def test_sin_claves_duplicadas():
    assert len(MEDICAMENTO_A_INSUMOS) == len(dict(MEDICAMENTO_A_INSUMOS)), "Claves duplicadas en MEDICAMENTO_A_INSUMOS"
    assert len(PROCEDIMIENTO_A_INSUMOS) == len(dict(PROCEDIMIENTO_A_INSUMOS)), "Claves duplicadas en PROCEDIMIENTO_A_INSUMOS"
