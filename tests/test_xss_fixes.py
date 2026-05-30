"""Tests para verificar que los modulos usen escape() en st.markdown."""
from __future__ import annotations

from pathlib import Path

VIEWS_DIR = Path(__file__).resolve().parents[1] / "views"
CORE_DIR = Path(__file__).resolve().parents[1] / "core"


def test_enfermeria_plan_has_escape():
    content = (VIEWS_DIR / "_enfermeria_plan.py").read_text(encoding="utf-8")
    assert "escape(str(reg.get" in content


def test_evolucion_panel_has_escape():
    content = (VIEWS_DIR / "_evolucion_panel.py").read_text(encoding="utf-8")
    assert "escape(str(foto.get" in content


def test_historial_render_has_escape():
    content = (VIEWS_DIR / "_historial_render.py").read_text(encoding="utf-8")
    assert "escape(str(reg.get" in content or "escape(str(fh.get" in content


def test_mi_equipo_bloques_has_escape():
    content = (VIEWS_DIR / "_mi_equipo_bloques.py").read_text(encoding="utf-8")
    assert "escape(" in content


def test_caja_has_escape():
    content = (VIEWS_DIR / "caja.py").read_text(encoding="utf-8")
    assert "escape(" in content


def test_mi_equipo_has_escape():
    content = (VIEWS_DIR / "mi_equipo.py").read_text(encoding="utf-8")
    assert "escape(" in content


def test_portal_paciente_has_escape():
    content = (VIEWS_DIR / "portal_paciente.py").read_text(encoding="utf-8")
    assert "escape(str(t.get" in content or "escape(str(c.get" in content


def test_recetas_mar_has_escape():
    content = (VIEWS_DIR / "_recetas_mar.py").read_text(encoding="utf-8")
    assert "escape(str(fila.get" in content


def test_red_profesionales_has_escape():
    content = (VIEWS_DIR / "red_profesionales.py").read_text(encoding="utf-8")
    assert "escape(str(reg.get" in content


def test_turnos_online_has_escape():
    content = (VIEWS_DIR / "turnos_online.py").read_text(encoding="utf-8")
    assert "escape(str(t.get" in content
