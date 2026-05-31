"""Consola de Despacho Automatico para Streamlit.
Interfaz reactiva que agrupa alertas NEWS2 criticas y turnos con
>70% de probabilidad de ausentismo. Un solo clic re-enruta
la hoja de ruta de un enfermero cercano via WebSockets.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE LA CONSOLA
# ═══════════════════════════════════════════════════════════════════

class AlertPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class DispatchAction:
    """Accion disponible en la consola de despacho."""
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    label: str = ""
    icon: str = "🚀"
    description: str = ""
    # Callback que ejecuta la accion (inyectado por el controlador)
    handler: Optional[Callable] = None


@dataclass
class AlertCard:
    """Tarjeta de alerta en la consola."""
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: AlertPriority = AlertPriority.MEDIUM
    title: str = ""
    description: str = ""
    patient_name: str = ""
    patient_id: str = ""
    professional_id: str = ""
    tenant_id: str = ""
    news2_score: int = 0
    absent_probability: float = 0.0       # 0.0 - 1.0
    location_lat: float = 0.0
    location_lon: float = 0.0
    nearby_professionals: list[dict] = field(default_factory=list)
    available_actions: list[DispatchAction] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_card_dict(self) -> dict:
        """Representacion para renderizado en Streamlit."""
        priority_color = {
            AlertPriority.LOW: "green",
            AlertPriority.MEDIUM: "orange",
            AlertPriority.HIGH: "red",
            AlertPriority.CRITICAL: "purple",
        }.get(self.priority, "gray")

        return {
            "id": self.alert_id,
            "priority": self.priority.value,
            "priority_color": priority_color,
            "title": self.title,
            "description": self.description,
            "patient": self.patient_name,
            "news2": self.news2_score,
            "absent_pct": round(self.absent_probability * 100, 0),
            "lat": self.location_lat,
            "lon": self.location_lon,
            "nearby": [
                {"id": p.get("id", ""), "name": p.get("name", ""), "dist_km": round(p.get("distance", 0), 1)}
                for p in self.nearby_professionals
            ],
            "actions": [
                {"id": a.action_id, "label": a.label, "icon": a.icon}
                for a in self.available_actions
            ],
            "time": datetime.fromtimestamp(self.created_at).strftime("%H:%M"),
        }


# ═══════════════════════════════════════════════════════════════════
# 2. CONSOLA DE DESPACHO
# ═══════════════════════════════════════════════════════════════════

class DispatchConsole:
    """Consola de despacho automatico.

    Logica de negocio detras de la UI de Streamlit.
    No contiene codigo de renderizado, solo logica de accion.
    """

    def __init__(self):
        self._alerts: list[AlertCard] = []
        self._action_history: list[dict] = []
        self._dispatch_hooks: list[Callable] = []

    def add_dispatch_hook(self, hook: Callable):
        """Registra un hook que se ejecuta al despachar una accion.

        El hook recibe (action, alert_card) y debe retornar True/False.
        Usado para conectar con WebSockets, DB, etc.
        """
        self._dispatch_hooks.append(hook)

    def add_alert(self, alert: AlertCard):
        """Agrega una alerta a la consola."""
        self._alerts.append(alert)

    def get_critical_alerts(self) -> list[AlertCard]:
        """Alertas NEWS2 criticas (score >= 7 o prioridad CRITICAL)."""
        return [
            a for a in self._alerts
            if a.news2_score >= 7 or a.priority == AlertPriority.CRITICAL
        ]

    def get_high_absent_alerts(self, threshold: float = 0.7) -> list[AlertCard]:
        """Alertas con probabilidad de ausentismo > threshold."""
        return [
            a for a in self._alerts
            if a.absent_probability >= threshold
        ]

    def get_all_active(self) -> list[AlertCard]:
        """Todas las alertas activas, ordenadas por prioridad descendente."""
        return sorted(self._alerts, key=lambda a: (a.priority.value, a.news2_score), reverse=True)

    def get_nearby_professionals(self, alert_id: str, max_distance_km: float = 5.0) -> list[dict]:
        """Obtiene profesionales cercanos a una alerta.

        En produccion usa PostGIS. Aqui filtramos del modelo.
        """
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                return [
                    p for p in alert.nearby_professionals
                    if p.get("distance", 999) <= max_distance_km
                ]
        return []

    async def dispatch_action(self, action_id: str, alert_id: str) -> dict:
        """Ejecuta una accion de despacho.

        Args:
            action_id: ID de la accion a ejecutar.
            alert_id: ID de la alerta asociada.

        Returns:
            dict con resultado de la accion.
        """
        alert = next((a for a in self._alerts if a.alert_id == alert_id), None)
        if not alert:
            return {"success": False, "error": "Alerta no encontrada"}

        action = next((a for a in alert.available_actions if a.action_id == action_id), None)
        if not action:
            return {"success": False, "error": "Accion no encontrada"}

        # Ejecutar hooks registrados
        results = []
        for hook in self._dispatch_hooks:
            try:
                if hook(action, alert):
                    results.append(True)
            except Exception as exc:
                results.append(False)

        # Registrar en historial
        entry = {
            "action_id": action_id,
            "alert_id": alert_id,
            "action_label": action.label,
            "patient": alert.patient_name,
            "timestamp": time.time(),
            "success": all(results) if results else True,
        }
        self._action_history.append(entry)

        return entry

    def get_dispatch_history(self, limit: int = 50) -> list[dict]:
        """Historial de acciones de despacho."""
        return sorted(self._action_history, key=lambda e: e["timestamp"], reverse=True)[:limit]

    def get_console_stats(self) -> dict:
        """Estadisticas de la consola."""
        return {
            "total_alerts": len(self._alerts),
            "critical": len(self.get_critical_alerts()),
            "high_absent": len(self.get_high_absent_alerts()),
            "actions_taken": len(self._action_history),
        }


# ═══════════════════════════════════════════════════════════════════
# 3. STREAMLIT RENDERIZER (ejemplo de uso)
# ═══════════════════════════════════════════════════════════════════

STREAMLIT_CONSOLE_CODE = """
# Ejemplo de uso en Streamlit:
#
# from core.dispatch_console import DispatchConsole, AlertCard, AlertPriority, DispatchAction
# import streamlit as st
#
# console = DispatchConsole()
#
# # Configurar hook de WebSocket
# async def notify_ws(action, alert):
#     from core.realtime_event_stream import create_ruta_cambio
#     msg = create_ruta_cambio(alert.tenant_id, alert.professional_id,
#                              action.label, f"{alert.location_lat},{alert.location_lon}")
#     # ws_bridge.publish(alert.tenant_id, msg)
#     return True
#
# console.add_dispatch_hook(notify_ws)
#
# st.set_page_config(layout="wide")
# st.title("🏥 Consola de Despacho - MediCare PRO")
#
# col1, col2, col3 = st.columns(3)
# stats = console.get_console_stats()
# col1.metric("Alertas Criticas", stats["critical"])
# col2.metric("Alto Ausentismo", stats["high_absent"])
# col3.metric("Acciones Hoy", stats["actions_taken"])
#
# for alert in console.get_all_active():
#     card = alert.to_card_dict()
#     with st.container():
#         cols = st.columns([1, 3, 2, 2])
#         cols[0].markdown(f"**{card['priority_color'].upper()}**")
#         cols[1].markdown(f"**{card['title']}** - {card['patient']}")
#         cols[2].markdown(f"NEWS2: {card['news2']} | Ausencia: {card['absent_pct']}%")
#         for action in card['actions']:
#             if cols[3].button(f"{action['icon']} {action['label']}", key=action['id']):
#                 st.write(f"Despachando: {action['label']}")
#         st.map(pd.DataFrame({'lat': [card['lat']], 'lon': [card['lon']]}))
"""


__all__ = [
    "DispatchConsole",
    "AlertCard",
    "AlertPriority",
    "DispatchAction",
    "STREAMLIT_CONSOLE_CODE",
]
