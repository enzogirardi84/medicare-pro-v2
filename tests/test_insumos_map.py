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


# ---------------------------------------------------------------------------
# auto_facturar_servicio
# ---------------------------------------------------------------------------

def test_auto_facturar_servicio_crea_item(monkeypatch):
    import streamlit as st
    monkeypatch.setattr(st, "session_state", {"facturacion_db": []}, raising=False)
    from core._insumos_map import auto_facturar_servicio

    result = auto_facturar_servicio(
        "Paciente Test - 12345678", "Mi Empresa", {"nombre": "Dr. Test", "dni": "99"},
        "Curación de herida",
    )
    assert result is True
    assert len(st.session_state["facturacion_db"]) == 1
    item = st.session_state["facturacion_db"][0]
    assert item["paciente"] == "Paciente Test - 12345678"
    assert item["serv"] == "Curación de herida"
    assert item["estado"] == "Pendiente / A Facturar"
    assert item["metodo"] == "Pendiente"


def test_auto_facturar_servicio_evita_duplicado(monkeypatch):
    import streamlit as st
    from core._insumos_map import auto_facturar_servicio
    from core.utils import ahora

    hoy = ahora().strftime("%d/%m/%Y")
    monkeypatch.setattr(st, "session_state", {
        "facturacion_db": [{
            "paciente": "Paciente Test - 12345678",
            "serv": "Curación",
            "fecha": hoy,
        }],
    }, raising=False)

    result = auto_facturar_servicio(
        "Paciente Test - 12345678", "Mi Empresa", {"nombre": "Dr. Test"},
        "Curación",
    )
    assert result is False
    assert len(st.session_state["facturacion_db"]) == 1


# ---------------------------------------------------------------------------
# sugerencias_reposicion
# ---------------------------------------------------------------------------

def test_sugerencias_reposicion_filtra_por_empresa(monkeypatch):
    import streamlit as st
    monkeypatch.setattr(st, "session_state", {
        "inventario_db": [
            {"item": "Gasas", "stock": 2, "stock_minimo": 10, "empresa": "Mi Empresa"},
            {"item": "Jeringas", "stock": 50, "stock_minimo": 10, "empresa": "Mi Empresa"},
            {"item": "Otra Emp", "stock": 1, "stock_minimo": 5, "empresa": "Otra"},
        ],
    }, raising=False)
    from core._insumos_map import sugerencias_reposicion

    result = sugerencias_reposicion("Mi Empresa")
    assert len(result) == 1
    assert result[0]["item"] == "Gasas"
    assert result[0]["sugerido"] >= 1


def test_sugerencias_reposicion_stock_cero_sin_minimo(monkeypatch):
    import streamlit as st
    monkeypatch.setattr(st, "session_state", {
        "inventario_db": [
            {"item": "Algodón", "stock": 0, "empresa": "Mi Empresa"},
            {"item": "Vendas", "stock": 5, "empresa": "Mi Empresa"},
        ],
    }, raising=False)
    from core._insumos_map import sugerencias_reposicion

    result = sugerencias_reposicion("Mi Empresa")
    # Algodón: stock 0 <= 10 (umbral default) → incluido
    # Vendas: stock 5 <= 10 (umbral default) → incluido
    assert len(result) == 2
    assert all(r["sugerido"] >= 1 for r in result)
