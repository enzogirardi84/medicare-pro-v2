"""Motor GIS para procesamiento de coordenadas GPS de visitas domiciliarias.
Incluye filtrado de ruido, compresion Douglas-Peucker, geofencing Haversine
y renderizado interactivo con Folium para Streamlit.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. ESTRUCTURAS DE DATOS
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Coordenada:
    """Un punto GPS con timestamp."""
    lat: float
    lon: float
    timestamp: float
    precision: float = 0.0  # metros, 0 = desconocida

    def __post_init__(self):
        self.lat = round(self.lat, 6)
        self.lon = round(self.lon, 6)


@dataclass
class Trayectoria:
    """Trayectoria completa de una visita."""
    puntos: list[Coordenada] = field(default_factory=list)
    profesional: str = ""
    paciente: str = ""
    fecha: str = ""

    def duracion_total(self) -> float:
        if len(self.puntos) < 2:
            return 0.0
        return self.puntos[-1].timestamp - self.puntos[0].timestamp


@dataclass
class VisitaDetectada:
    """Visita detectada por geofencing."""
    paciente: str
    lat: float
    lon: float
    radio_metros: float = 50.0
    entrada: float = 0.0
    salida: float = 0.0
    duracion_seg: float = 0.0
    coord_entrada: Optional[Coordenada] = None
    coord_salida: Optional[Coordenada] = None


# ═══════════════════════════════════════════════════════════════════
# 2. MOTOR DE FILTRADO Y COMPRESION
# ═══════════════════════════════════════════════════════════════════

class GPSProcessor:
    """Procesa trayectorias GPS: limpia ruido y comprime puntos redundantes.

    Algoritmos:
    - Filtro de velocidad maxima: descarta puntos con velocidad > MAX_SPEED_KMH
    - Douglas-Peucker: simplifica trayectorias rectilineas con tolerancia configurable
    - Filtro de estacionamiento: elimina puntos duplicados cuando el profesional esta quieto
    """

    MAX_SPEED_KMH = 180.0  # velocidad maxima plausible (ambulancia)
    EARTH_RADIUS_KM = 6371.0
    DOUGLAS_PEUCKER_EPSILON = 0.0005  # ~50m en coordenadas

    @staticmethod
    def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Distancia entre dos puntos en kilometros (formula de Haversine)."""
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (math.sin(d_lat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(d_lon / 2) ** 2)
        return GPSProcessor.EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Distancia en metros."""
        return GPSProcessor.haversine_km(lat1, lon1, lat2, lon2) * 1000.0

    @classmethod
    def limpiar_ruido(cls, puntos: list[Coordenada]) -> list[Coordenada]:
        """Filtro de velocidad maxima: elimina puntos fisicamente imposibles.

        Si la velocidad entre dos puntos consecutivos supera MAX_SPEED_KMH,
        el punto siguiente se descarta (error del sensor GPS).
        """
        if len(puntos) < 2:
            return puntos

        limpios = [puntos[0]]
        for i in range(1, len(puntos)):
            dt = puntos[i].timestamp - puntos[i - 1].timestamp
            if dt <= 0:
                continue
            dist = cls.haversine_km(puntos[i - 1].lat, puntos[i - 1].lon,
                                     puntos[i].lat, puntos[i].lon)
            vel_kmh = (dist / dt) * 3600.0
            if vel_kmh <= cls.MAX_SPEED_KMH:
                limpios.append(puntos[i])
            else:
                log_event("gps", f"ruido_descartado:vel={vel_kmh:.0f}kmh")

        return limpios

    @classmethod
    def comprimir_douglas_peucker(cls, puntos: list[Coordenada],
                                  epsilon: float | None = None) -> list[Coordenada]:
        """Simplifica una trayectoria usando el algoritmo Douglas-Peucker.

        Reduce puntos redundantes cuando la trayectoria es una linea recta
        o el profesional esta detenido.
        """
        if epsilon is None:
            epsilon = cls.DOUGLAS_PEUCKER_EPSILON
        if len(puntos) < 3:
            return puntos

        def _distancia_punto_a_recta(p: Coordenada, a: Coordenada, b: Coordenada) -> float:
            """Distancia perpendicular del punto p a la linea a-b."""
            if a.lat == b.lat and a.lon == b.lon:
                return cls.haversine_m(p.lat, p.lon, a.lat, a.lon)
            # Formula de distancia punto-recta en coordenadas geograficas aproximadas
            area = abs((b.lat - a.lat) * (a.lon - p.lon) -
                       (a.lat - p.lat) * (b.lon - a.lon))
            base = cls.haversine_m(a.lat, a.lon, b.lat, b.lon)
            return (area * cls.EARTH_RADIUS_KM * 1000.0) / base if base > 0 else 0.0

        def _dp(puntos: list[Coordenada]) -> list[Coordenada]:
            if len(puntos) < 3:
                return puntos
            dmax = 0.0
            idx = 0
            for i in range(1, len(puntos) - 1):
                d = _distancia_punto_a_recta(puntos[i], puntos[0], puntos[-1])
                if d > dmax:
                    dmax = d
                    idx = i
            if dmax > epsilon * cls.EARTH_RADIUS_KM * 1000.0:
                izquierda = _dp(puntos[:idx + 1])
                derecha = _dp(puntos[idx:])
                return izquierda[:-1] + derecha
            return [puntos[0], puntos[-1]]

        return _dp(puntos)

    @classmethod
    def comprimir_estacionario(cls, puntos: list[Coordenada],
                               umbral_metros: float = 20.0,
                               umbral_segundos: float = 30.0) -> list[Coordenada]:
        """Elimina puntos redundantes cuando el profesional esta detenido.

        Si la posicion no cambia mas de `umbral_metros` durante mas de
        `umbral_segundos`, solo conserva el primer y ultimo punto del periodo.
        """
        if len(puntos) < 3:
            return puntos

        compactos: list[Coordenada] = [puntos[0]]
        i = 0
        while i < len(puntos):
            j = i + 1
            while j < len(puntos):
                dist = cls.haversine_m(puntos[i].lat, puntos[i].lon,
                                       puntos[j].lat, puntos[j].lon)
                dt = puntos[j].timestamp - puntos[i].timestamp
                if dist > umbral_metros or dt > umbral_segundos:
                    break
                j += 1
            if j > i + 2:
                compactos.append(puntos[j - 1])
                i = j - 1
            else:
                if j < len(puntos):
                    compactos.append(puntos[j])
                i = j

        return compactos

    @classmethod
    def procesar_trayectoria(cls, puntos: list[Coordenada]) -> list[Coordenada]:
        """Pipeline completo de procesamiento.

        1. Limpiar ruido por velocidad
        2. Comprimir puntos estacionarios
        3. Simplificar con Douglas-Peucker
        """
        if not puntos:
            return []
        p = cls.limpiar_ruido(puntos)
        p = cls.comprimir_estacionario(p)
        p = cls.comprimir_douglas_peucker(p)
        return p


# ═══════════════════════════════════════════════════════════════════
# 3. GEOFENCING: DETECCION DE VISITAS EN DOMICILIO
# ═══════════════════════════════════════════════════════════════════

class GeofencingEngine:
    """Detecta automaticamente visitas a domicilios usando Haversine.

    Detecta cuando un profesional:
    - Entra al radio del domicilio del paciente (>50m)
    - Permanece dentro (duracion de la visita)
    - Sale del radio (fin de la visita)
    """

    RADIO_DOMICILIO_METROS = 50.0
    TIEMPO_MINIMO_VISITA_SEG = 60.0  # 1 minuto minimo para contar como visita

    @classmethod
    def detectar_visitas(
        cls,
        trayectoria: list[Coordenada],
        domicilio_paciente: tuple[float, float],
        radio_metros: float = RADIO_DOMICILIO_METROS,
    ) -> list[VisitaDetectada]:
        """Detecta visitas al domicilio de un paciente desde una trayectoria GPS.

        Args:
            trayectoria: Lista de coordenadas del profesional ordenadas por tiempo.
            domicilio_paciente: (lat, lon) del domicilio del paciente.
            radio_metros: Radio de tolerancia para considerar 'en domicilio'.

        Returns:
            Lista de VisitaDetectada con los periodos de visita.
        """
        if not trayectoria:
            return []

        lat_dom, lon_dom = domicilio_paciente
        dentro = False
        entrada = 0.0
        entrada_coord: Optional[Coordenada] = None
        visitas: list[VisitaDetectada] = []

        for p in trayectoria:
            dist = GPSProcessor.haversine_m(p.lat, p.lon, lat_dom, lon_dom)
            if dist <= radio_metros and not dentro:
                dentro = True
                entrada = p.timestamp
                entrada_coord = p
            elif dist > radio_metros and dentro:
                dentro = False
                duracion = p.timestamp - entrada
                if duracion >= cls.TIEMPO_MINIMO_VISITA_SEG:
                    visitas.append(VisitaDetectada(
                        paciente="",
                        lat=lat_dom, lon=lon_dom,
                        radio_metros=radio_metros,
                        entrada=entrada, salida=p.timestamp,
                        duracion_seg=duracion,
                        coord_entrada=entrada_coord,
                        coord_salida=p,
                    ))
                    log_event("gps", f"visita_detectada:{duracion:.0f}s")

        # Si termino dentro del radio, cerrar la visita
        if dentro:
            duracion = trayectoria[-1].timestamp - entrada
            if duracion >= cls.TIEMPO_MINIMO_VISITA_SEG:
                visitas.append(VisitaDetectada(
                    paciente="",
                    lat=lat_dom, lon=lon_dom,
                    radio_metros=radio_metros,
                    entrada=entrada, salida=trayectoria[-1].timestamp,
                    duracion_seg=duracion,
                    coord_entrada=entrada_coord,
                    coord_salida=trayectoria[-1],
                ))

        return visitas

    @classmethod
    def calcular_tiempo_atencion(cls, visitas: list[VisitaDetectada]) -> float:
        """Calcula el tiempo total de atencion en domicilio."""
        return sum(v.duracion_seg for v in visitas)


# ═══════════════════════════════════════════════════════════════════
# 4. RENDERIZADO INTERACTIVO CON FOLIUM + STREAMLIT
# ═══════════════════════════════════════════════════════════════════

def render_mapa_ruta(
    trayectoria: list[Coordenada],
    visitas: list[VisitaDetectada] | None = None,
    titulo: str = "Ruta de visitas",
    altura: int = 500,
) -> Any:
    """Renderiza un mapa interactivo con la ruta optimizada y visitas detectadas.

    Requiere: pip install folium streamlit-folium

    Args:
        trayectoria: Lista de coordenadas procesadas.
        visitas: Lista de visitas detectadas para marcar en el mapa.
        titulo: Titulo del mapa.
        altura: Altura del mapa en pixeles.

    Returns:
        Objeto Figure de Folium listo para st_folium() o st.components.v1.html().
    """
    try:
        import folium
        from folium import plugins
    except ImportError:
        log_event("gps", "folium_no_instalado")
        return None

    if not trayectoria:
        return None

    centro_lat = sum(p.lat for p in trayectoria) / len(trayectoria)
    centro_lon = sum(p.lon for p in trayectoria) / len(trayectoria)

    m = folium.Map(location=[centro_lat, centro_lon], zoom_start=14,
                   tiles="cartodbpositron",
                   control_scale=True)

    # Linea de ruta
    ruta_coords = [(p.lat, p.lon) for p in trayectoria]
    folium.PolyLine(ruta_coords, color="#2563eb", weight=3, opacity=0.8,
                    tooltip=titulo).add_to(m)

    # Punto de inicio (verde)
    inicio = trayectoria[0]
    folium.Marker(
        [inicio.lat, inicio.lon],
        popup="Inicio",
        icon=folium.Icon(color="green", icon="play", prefix="fa"),
    ).add_to(m)

    # Punto de fin (rojo)
    fin = trayectoria[-1]
    folium.Marker(
        [fin.lat, fin.lon],
        popup="Fin",
        icon=folium.Icon(color="red", icon="stop", prefix="fa"),
    ).add_to(m)

    # Marcadores de visitas detectadas
    if visitas:
        for v in visitas:
            from datetime import datetime
            h_entrada = datetime.fromtimestamp(v.entrada).strftime("%H:%M")
            h_salida = datetime.fromtimestamp(v.salida).strftime("%H:%M")
            duracion = f"{int(v.duracion_seg // 60)}m {int(v.duracion_seg % 60)}s"

            folium.Marker(
                [v.lat, v.lon],
                popup=f"Visita: {h_entrada} - {h_salida} ({duracion})",
                tooltip=f"{duracion} en domicilio",
                icon=folium.Icon(color="blue", icon="medkit", prefix="fa"),
            ).add_to(m)

            # Circulo del radio de geofencing
            folium.Circle(
                [v.lat, v.lon],
                radius=v.radio_metros,
                color="#2563eb",
                fill=True,
                fillOpacity=0.08,
                weight=1,
            ).add_to(m)

    # Control de capas
    folium.LayerControl().add_to(m)

    return m


def render_mapa_st(
    trayectoria: list[Coordenada],
    visitas: list[VisitaDetectada] | None = None,
    paciente_nombre: str = "",
    key: str = "mapa_ruta",
) -> None:
    """Renderiza el mapa en Streamlit usando st_folium o fallback a folium HTML.

    Args:
        trayectoria: Coordenadas procesadas.
        visitas: Visitas detectadas.
        paciente_nombre: Nombre del paciente para el titulo.
        key: Key unica para el componente Streamlit.
    """
    import streamlit as st

    if not trayectoria:
        st.caption("Sin datos de GPS disponibles para este recorrido.")
        return

    titulo = f"Ruta: {paciente_nombre}" if paciente_nombre else "Ruta de visitas"
    mapa = render_mapa_ruta(trayectoria, visitas, titulo=titulo)
    if mapa is None:
        st.caption("Mapa no disponible (instalar folium y streamlit-folium).")
        return

    try:
        from streamlit_folium import st_folium
        st_folium(mapa, width="100%", height=500, key=key)
    except ImportError:
        from streamlit.components.v1 import html
        html(mapa._repr_html_(), height=500, scrolling=True)


# ═══════════════════════════════════════════════════════════════════
# 5. PROTECCION DE PRIVACIDAD (Audit Trail en visualizacion)
# ═══════════════════════════════════════════════════════════════════

def auditoria_acceso_mapa(profesional: str, paciente: str, usuario: str, rol: str) -> None:
    """Registra en el audit trail que un usuario visualizo el mapa de ruta.

    Solo usuarios con rol Coordinador/Admin pueden ver datos de geolocalizacion.
    """
    if rol.lower() not in ("coordinador", "admin", "superadmin"):
        log_event("gps", f"acceso_denegado_mapa:{usuario}:rol={rol}")
        raise PermissionError(f"Rol '{rol}' no tiene permisos para ver mapas de ruta.")

    try:
        from core.audit_trail_immutable import ImmutableAuditTrail
        auditor = ImmutableAuditTrail()
        auditor.registrar(
            usuario=usuario,
            accion="lectura",
            recurso=f"gps_mapa:{profesional}:{paciente}",
            detalle=f"Coordinador {usuario} visualizo ruta GPS del profesional {profesional}",
        )
        log_event("gps", f"mapa_visualizado:{usuario}:{profesional}:{paciente}")
    except Exception as exc:
        log_event("gps", f"audit_error:{type(exc).__name__}")


def require_rol_mapa(rol: str) -> None:
    """Verifica que el rol tenga permisos para ver mapas."""
    if rol.lower() not in ("coordinador", "admin", "superadmin"):
        raise PermissionError(
            f"Acceso denegado. El rol '{rol}' no tiene permisos de visualizacion GIS."
        )
