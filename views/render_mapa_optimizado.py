"""Renderizado optimizado de mapas geograficos en Streamlit.
Usa @st.fragment + LRU cache para renderizar en <500ms.
Soporta Pydeck y Folium. Consume datos de la vista materializada.
"""
from __future__ import annotations

import time
from typing import Any, Optional

import streamlit as st

from core.app_logging import log_event
from core.tenant_cache import get_cache
from core.streamlit_async import run_async


@st.fragment
def render_mapa_calor(
    titulo: str = "Mapa de atenciones",
    altura: int = 500,
    tenant_id: str = "default",
    dias_historia: int = 90,
) -> None:
    """Renderiza mapa de calor geografico con datos cacheados.

    Usa @st.fragment para que solo este bloque se re-renderice.
    Los datos vienen de la vista materializada via cache LRU/Redis.

    Args:
        titulo: Titulo del mapa.
        altura: Altura en pixeles.
        tenant_id: Slug del tenant.
        dias_historia: Dias de historia a mostrar.
    """
    cache = get_cache()
    cache_key = f"mapa_calor:{tenant_id}:{dias_historia}"

    # Intentar cache primero
    datos = run_async(cache.get(cache_key))

    if datos is None:
        # Cargar desde la DB via vista materializada
        t0 = time.perf_counter()

        try:
            from core.tenant_repository import TenantRepository
            repo = TenantRepository()
            repo.set_tenant_context(tenant_id)

            import asyncio
            async def fetch():
                async with repo.connect() as conn:
                    rows = await conn.fetch("""
                        SELECT
                            ST_X(grid_centroid::GEOMETRY) as lon,
                            ST_Y(grid_centroid::GEOMETRY) as lat,
                            peso,
                            diagnostico
                        FROM mv_densidad_atenciones
                        ORDER BY peso DESC
                        LIMIT 1000
                    """)
                    return [dict(r) for r in rows]

            datos = asyncio.run(fetch())

            # Guardar en cache
            run_async(cache.set(cache_key, datos, ttl=300))

            dt = (time.perf_counter() - t0) * 1000
            log_event("mapa", f"cargado:{len(datos)}pts:{dt:.0f}ms")
        except Exception as exc:
            st.warning("No se pudieron cargar los datos del mapa")
            log_event("mapa", f"error:{type(exc).__name__}")
            return

    if not datos:
        st.caption("Sin datos geograficos para el periodo seleccionado.")
        return

    # Renderizar mapa con Pydeck (acelerado por GPU)
    try:
        import pydeck as pdk

        capa = pdk.Layer(
            "HeatmapLayer",
            data=datos,
            get_position=["lon", "lat"],
            get_weight="peso",
            radius_pixels=30,
            intensity=1,
            threshold=0.05,
        )

        vista_inicial = pdk.ViewState(
            latitude=sum(d["lat"] for d in datos) / len(datos),
            longitude=sum(d["lon"] for d in datos) / len(datos),
            zoom=10,
            pitch=0,
        )

        st.pydeck_chart(
            pdk.Deck(
                layers=[capa],
                initial_view_state=vista_inicial,
                map_style="dark",
                tooltip={"text": "Atenciones: {peso}"},
            ),
            use_container_width=True,
            height=altura,
        )
    except ImportError:
        # Fallback a Folium
        try:
            import folium
            from streamlit_folium import st_folium

            centro_lat = sum(d["lat"] for d in datos) / len(datos)
            centro_lon = sum(d["lon"] for d in datos) / len(datos)
            m = folium.Map(location=[centro_lat, centro_lon], zoom_start=10)

            for d in datos:
                folium.CircleMarker(
                    location=[d["lat"], d["lon"]],
                    radius=min(d["peso"], 15),
                    color="#2563eb",
                    fill=True,
                    fillOpacity=0.3,
                    popup=f"{d.get('diagnostico', '')} ({d['peso']} atenciones)",
                ).add_to(m)

            st_folium(m, width="100%", height=altura)
        except ImportError:
            st.caption("Instalar pydeck o folium para ver el mapa.")


@st.fragment
def render_trayectoria_profesional(
    profesional_id: str,
    tenant_id: str = "default",
    dias: int = 7,
) -> None:
    """Renderiza trayectoria de un profesional en los ultimos N dias.

    Los datos se sirven desde cache LRU/Redis.
    """
    cache = get_cache()
    cache_key = f"trayectoria:{tenant_id}:{profesional_id}:{dias}"

    datos = run_async(cache.get(cache_key))

    if datos is None:
        try:
            from core.tenant_repository import TenantRepository
            repo = TenantRepository()
            repo.set_tenant_context(tenant_id)

            import asyncio
            async def fetch():
                async with repo.connect() as conn:
                    rows = await conn.fetch("""
                        SELECT
                            ST_X(punto::GEOMETRY) as lon,
                            ST_Y(punto::GEOMETRY) as lat,
                            timestamp
                        FROM checkins_gps
                        WHERE profesional_id = $1
                          AND timestamp >= NOW() - $2::INTERVAL
                        ORDER BY timestamp
                    """, profesional_id, f"{dias} days")
                    return [dict(r) for r in rows]

            datos = asyncio.run(fetch())
            run_async(cache.set(cache_key, datos, ttl=300))
        except Exception:
            st.warning("Error al cargar trayectoria")
            return

    if not datos:
        st.caption("Sin datos de trayectoria para este profesional.")
        return

    try:
        import pydeck as pdk

        capa_linea = pdk.Layer(
            "LineLayer",
            data=datos,
            get_source_position=["lon", "lat"],
            get_target_position=["lon", "lat"],
            get_color=[37, 99, 235, 180],
            get_width=3,
        )
        capa_puntos = pdk.Layer(
            "ScatterplotLayer",
            data=datos,
            get_position=["lon", "lat"],
            get_fill_color=[14, 165, 233, 200],
            get_radius=30,
        )

        vista = pdk.ViewState(
            latitude=datos[0]["lat"],
            longitude=datos[0]["lon"],
            zoom=13,
        )

        st.pydeck_chart(
            pdk.Deck(
                layers=[capa_linea, capa_puntos],
                initial_view_state=vista,
                map_style="dark",
            ),
            use_container_width=True,
            height=400,
        )
    except ImportError:
        st.caption("Instalar pydeck para ver trayectorias.")
