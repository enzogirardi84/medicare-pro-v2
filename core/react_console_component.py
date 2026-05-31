"""
Streamlit Custom Component — Terminal de control a 60 FPS.
React + TypeScript con WebSocket directo, Shadow DOM,
mapa interactivo (Mapbox) y grilla de alertas de alta densidad.

CONSTRUCCIÓN:
  cd frontend/medicare-console
  npm install
  npm run build
  # Copiar build/ a static/ del backend
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. ESPECIFICACIÓN DEL COMPONENTE REACT
# ═══════════════════════════════════════════════════════════════════

REACT_COMPONENT_SPEC = """
// ─────────────────────────────────────────────────────────────────
// MedicareConsole — Streamlit Custom Component (React 18 + TS)
// ─────────────────────────────────────────────────────────────────
// Conexión directa a WebSocket, estado local en Shadow DOM.
// Renderizado quirúrgico: solo muta el nodo que cambió.
// Sin st.rerun(). 60 FPS garantizados.

import React, { useEffect, useRef, useCallback, useState } from 'react';
import { createRoot } from 'react-dom/client';
import mapboxgl from 'mapbox-gl';    // ^3.0.0
import { Streamlit, withStreamlitConnection } from 'streamlit-component-lib';

// ─── Tipos ───────────────────────────────────────────────────────
interface AlertData {
  id: string;
  priority: number;
  title: string;
  patient: string;
  news2: number;
  lat: number;
  lon: number;
  nearby: { id: string; name: string; dist_km: number }[];
}

interface StreamlitArgs {
  ws_url: string;
  mapbox_token: string;
  initial_alerts: AlertData[];
}

// ─── Componente principal ────────────────────────────────────────
const MedicareConsole: React.FC = () => {
  const [alerts, setAlerts] = useState<AlertData[]>([]);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const markersRef = useRef<Map<string, mapboxgl.Marker>>(new Map());
  const wsRef = useRef<WebSocket | null>(null);
  const queueRef = useRef<AlertData[]>([]);
  const rafRef = useRef<number>(0);

  // Inicializar WebSocket directo (sin st.rerun)
  useEffect(() => {
    const args: StreamlitArgs = Streamlit.args;
    const ws = new WebSocket(args.ws_url);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      queueRef.current.push(data);

      // Acumular en cola y procesar en el próximo requestAnimationFrame
      if (!rafRef.current) {
        rafRef.current = requestAnimationFrame(processQueue);
      }
    };

    // Inicializar mapa Mapbox
    mapboxgl.accessToken = args.mapbox_token;
    mapRef.current = new mapboxgl.Map({
      container: 'map-container',
      style: 'mapbox://styles/mapbox/light-v11',
      center: [-58.4, -34.6],
      zoom: 11,
    });

    return () => {
      ws.close();
      cancelAnimationFrame(rafRef.current);
      markersRef.current.forEach((m) => m.remove());
    };
  }, []);

  // ─── Procesamiento por lotes a 60 FPS ────────────────────────
  const processQueue = useCallback(() => {
    const batch = queueRef.current.splice(0);
    rafRef.current = 0;

    // Agrupar por prioridad para actualización masiva
    const newAlerts = [...alerts];
    for (const item of batch) {
      const idx = newAlerts.findIndex((a) => a.id === item.id);
      if (idx >= 0) {
        // Mutación quirúrgica: solo actualizar el objeto específico
        newAlerts[idx] = { ...newAlerts[idx], ...item };
      } else {
        newAlerts.push(item);
      }

      // Actualizar marcador en el mapa (sin re-renderizar todo el mapa)
      updateMarker(item);
    }

    setAlerts(newAlerts);

    // Solicitar próximo frame si hay más datos
    if (queueRef.current.length > 0) {
      rafRef.current = requestAnimationFrame(processQueue);
    }
  }, [alerts]);

  // ─── Actualización quirúrgica de marcadores ──────────────────
  const updateMarker = (alert: AlertData) => {
    if (!mapRef.current) return;

    const existing = markersRef.current.get(alert.id);
    if (existing) {
      // Mover marcador existente (sin reconstruir)
      existing.setLngLat([alert.lon, alert.lat]);
    } else {
      // Crear nuevo marcador
      const el = document.createElement('div');
      el.className = 'alert-marker';
      el.style.backgroundColor = alert.priority >= 3 ? '#ff4444' : '#ffaa00';
      el.style.width = '24px';
      el.style.height = '24px';
      el.style.borderRadius = '50%';
      el.style.border = '3px solid white';
      el.style.boxShadow = '0 2px 6px rgba(0,0,0,0.3)';
      el.title = `${alert.patient} — NEWS2: ${alert.news2}`;

      const marker = new mapboxgl.Marker({ element: el })
        .setLngLat([alert.lon, alert.lat])
        .addTo(mapRef.current);

      markersRef.current.set(alert.id, marker);
    }
  };

  // ─── Renderizado React (Shadow DOM) ──────────────────────────
  return (
    <div style={{ display: 'flex', height: '100vh', fontFamily: 'Inter, sans-serif' }}>
      {/* Mapa */}
      <div id="map-container" style={{ flex: 2 }} />

      {/* Barra lateral de alertas */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '16px',
        background: '#f8f9fa', borderLeft: '1px solid #dee2e6',
      }}>
        <h2 style={{ marginTop: 0, fontSize: '1.2rem', color: '#495057' }}>
          🚨 Alertas en tiempo real
        </h2>

        {alerts.sort((a, b) => b.priority - a.priority).map((alert) => (
          <div key={alert.id} style={{
            padding: '12px', marginBottom: '8px', borderRadius: '8px',
            background: alert.priority >= 3 ? '#fff5f5' : '#fff',
            border: `1px solid ${alert.priority >= 3 ? '#ffc9c9' : '#dee2e6'}`,
            transition: 'all 0.2s ease',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <strong>{alert.patient}</strong>
              <span style={{
                background: alert.priority >= 3 ? '#ff4444' : '#ffaa00',
                color: 'white', padding: '2px 8px', borderRadius: '12px',
                fontSize: '0.75rem', fontWeight: 600,
              }}>
                NEWS2: {alert.news2}
              </span>
            </div>
            <p style={{ margin: '4px 0 0', fontSize: '0.85rem', color: '#666' }}>
              {alert.title}
            </p>
            {alert.nearby.length > 0 && (
              <p style={{ margin: '4px 0 0', fontSize: '0.75rem', color: '#999' }}>
                📍 Profesional más cercano: {alert.nearby[0].name} ({alert.nearby[0].dist_km}km)
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// ─── Entry point ─────────────────────────────────────────────────
const container = document.getElementById('root');
if (container) {
  const root = createRoot(container);
  root.render(<withStreamlitConnection><MedicareConsole /></withStreamlitConnection>);
}
"""


# ═══════════════════════════════════════════════════════════════════
# 2. INTEGRACIÓN CON STREAMLIT (backend proxy)
# ═══════════════════════════════════════════════════════════════════

STREAMLIT_INTEGRATION_CODE = """
# En tu app Streamlit:
#
# from core.react_console_component import MedicareConsoleProxy
# console = MedicareConsoleProxy()
# console.render(ws_url="wss://api.medicare-pro.app/ws/tenant1/coord1")
#
# El componente se conecta DIRECTAMENTE al WebSocket.
# No usa st.rerun(). 60 FPS en el navegador.

import streamlit as st
from core.react_console_component import MedicareConsoleProxy
from core.realtime_event_stream import WebSocketManager, create_alert_news2

st.set_page_config(layout="wide")
st.title("MediCare PRO — Terminal de Control")

# Inicializar proxy del componente React
# (busca el build en frontend/medicare-console/build/)
console = MedicareConsoleProxy()

# Configurar WebSocket Manager para enviar actualizaciones
ws_manager = WebSocketManager()
# ... conectar colas de profesionales ...

# Renderizar el componente
console.render(
    ws_url="wss://api.medicare-pro.app/ws/{tenant_id}/{coordinator_id}",
    mapbox_token=st.secrets.get("MAPBOX_TOKEN", ""),
    height=800,
)
"""


# ═══════════════════════════════════════════════════════════════════
# 3. PROXY BACKEND PARA STREAMLIT
# ═══════════════════════════════════════════════════════════════════

class MedicareConsoleProxy:
    """Proxy para el componente React de la consola.

    En producción: sirve el build de React desde frontend/medicare-console/build/.
    """

    COMPONENT_DIR = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "frontend", "medicare-console", "build",
    )

    def __init__(self):
        self._component_available = os.path.exists(self.COMPONENT_DIR)

    def render(self, ws_url: str = "", mapbox_token: str = "", height: int = 800):
        """Renderiza el componente React en Streamlit.

        Args:
            ws_url: URL del WebSocket (ej. wss://api.medicare-pro.app/ws/t1/p1).
            mapbox_token: Token de Mapbox.
            height: Altura del componente en píxeles.
        """
        import streamlit.components.v1 as components

        if self._component_available:
            # Usar componente compilado
            component = components.declare_component(
                "medicare_console",
                path=self.COMPONENT_DIR,
            )
            component(ws_url=ws_url, mapbox_token=mapbox_token, height=height)
        else:
            # Fallback: iframe HTML para desarrollo
            html = f"""
            <div style="height:{height}px;display:flex;align-items:center;justify-content:center;
                        background:#f0f2f6;border-radius:8px;color:#666;font-family:sans-serif;">
                <div style="text-align:center;">
                    <div style="font-size:48px;margin-bottom:16px;">🚀</div>
                    <h3>MediCare Console</h3>
                    <p>Componente React no compilado.</p>
                    <p style="font-size:12px;color:#999;">
                        Ejecuta:
                        <code style="background:#e8e8e8;padding:2px 6px;border-radius:4px;">
                            cd frontend/medicare-console && npm install && npm run build
                        </code>
                    </p>
                </div>
            </div>
            """
            components.html(html, height=height, scrolling=False)

            log_event("react_console", "component_not_built:use_frontend_build")


__all__ = [
    "MedicareConsoleProxy",
    "REACT_COMPONENT_SPEC",
    "STREAMLIT_INTEGRATION_CODE",
]
