"""Geocodificación inversa vía Nominatim (OpenStreetMap)."""

from __future__ import annotations

import json
import urllib.request

_USER_AGENT = "MediCareProApp/1.0"


def reverse_geocode_short_label(lat, lon) -> str:
    """
    Devuelve una etiqueta corta de dirección a partir de lat/lon, o un mensaje de fallback.
    """
    try:
        url = (
            f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
            "&zoom=18&addressdetails=1"
        )
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            display_name = data.get("display_name", "Direccion no encontrada")
            partes = display_name.split(", ")
            if len(partes) > 3:
                return ", ".join(partes[:3])
            return display_name
    except Exception:
        return "Direccion exacta no disponible (solo coordenadas)"
