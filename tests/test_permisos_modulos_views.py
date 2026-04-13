"""Los alias de menú en PERMISOS_MODULOS deben resolver a módulos en view_registry."""

from core.utils import PERMISOS_MODULOS, _modulo_canonico
from core.view_registry import VIEW_CONFIG_BASE


def test_cada_entrada_permisos_resuelve_a_vista_registrada():
    conocidos = set(VIEW_CONFIG_BASE)
    for perfil, items in PERMISOS_MODULOS.items():
        for corto in items:
            largo = _modulo_canonico(corto)
            assert largo in conocidos, (
                f"PERMISOS_MODULOS[{perfil!r}] tiene {corto!r} → {largo!r} "
                f"que no está en VIEW_CONFIG_BASE"
            )


def test_obtener_direccion_real_delega_en_nominatim(monkeypatch):
    from core import utils

    def fake(lat, lon):
        return f"x={lat},y={lon}"

    monkeypatch.setattr("services.nominatim.reverse_geocode_short_label", fake)
    assert utils.obtener_direccion_real(-1.0, 2.5) == "x=-1.0,y=2.5"
