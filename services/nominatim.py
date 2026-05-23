"""Geocodificación inversa vía Nominatim (OpenStreetMap)."""

from __future__ import annotations

import json
import urllib.request
from urllib.parse import urlencode

_USER_AGENT = "MediCareProApp/1.0"


def reverse_geocode_short_label(lat, lon) -> str:
    """
    Devuelve una etiqueta corta de dirección a partir de lat/lon, o un mensaje de fallback.
    Valida que lat/lon sean coordenadas válidas antes de consultar la API.
    """
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (ValueError, TypeError):
        return "Direccion exacta no disponible (coordenadas invalidas)"
    if not (-90.0 <= lat_f <= 90.0) or not (-180.0 <= lon_f <= 180.0):
        return "Direccion exacta no disponible (coordenadas fuera de rango)"
    try:
        params = urlencode({"format": "json", "lat": lat_f, "lon": lon_f, "zoom": "18", "addressdetails": "1"})
        url = f"https://nominatim.openstreetmap.org/reverse?{params}"
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
