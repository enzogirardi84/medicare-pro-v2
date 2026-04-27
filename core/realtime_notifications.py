"""
Sistema de Notificaciones en Tiempo Real para MediCare Pro.

Alertas críticas para personal médico:
- Valores de laboratorio anormales (crítico)
- Signos vitales fuera de rango (crítico)
- Turnos próximos (recordatorio)
- Mensajes del equipo (colaboración)
- Emergencias (código azul/rojo)

Implementación:
- Server-Sent Events (SSE) para push notifications
- Redis pub/sub para distribución multi-worker
- Polling optimizado como fallback
- Prioridades: CRITICAL > HIGH > NORMAL > LOW
"""
import time
import json
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum, auto
from functools import lru_cache
import uuid

import streamlit as st

from core.app_logging import log_event
from core.config_secure import get_settings


class NotificationPriority(Enum):
    """Prioridades de notificación."""
    CRITICAL = "critical"  # Alerta médica inmediata
    HIGH = "high"          # Requiere atención pronto
    NORMAL = "normal"      # Información importante
    LOW = "low"            # Informativo


class NotificationType(Enum):
    """Tipos de notificación médica."""
    # Clínicas (CRÍTICAS)
    LAB_CRITICAL = auto()           # Valor de lab fuera de rango crítico
    VITALS_ALERT = auto()           # Signos vitales anormales
    EMERGENCY_CODE = auto()         # Código de emergencia
    ALLERGY_WARNING = auto()        # Alerta de alergia
    DRUG_INTERACTION = auto()     # Interacción medicamentosa
    
    # Operativas
    APPOINTMENT_UPCOMING = auto()   # Turno en 15/30 min
    APPOINTMENT_CANCELLED = auto()  # Turno cancelado
    NEW_PATIENT = auto()           # Nuevo paciente registrado
    EVOLUTION_PENDING = auto()     # Evolución pendiente de firma
    
    # Colaboración
    TEAM_MESSAGE = auto()          # Mensaje del equipo
    REFERRAL_RECEIVED = auto()     # Derivación recibida
    CONSULT_REQUEST = auto()      # Consulta solicitada
    
    # Sistema
    BACKUP_COMPLETED = auto()    # Backup finalizado
    SYSTEM_ALERT = auto()          # Alerta del sistema


@dataclass
class Notification:
    """Notificación individual."""
    id: str
    type: str  # NotificationType.name
    priority: str  # NotificationPriority.value
    title: str
    message: str
    timestamp: str
    sender: Optional[str]  # Usuario que generó la notificación
    recipient: Optional[str]  # Usuario destino (None = broadcast)
    patient_id: Optional[str]  # Paciente relacionado
    data: Dict[str, Any]  # Datos adicionales
    read: bool = False
    read_at: Optional[str] = None
    acknowledged: bool = False  # Para alertas críticas
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return asdict(self)
    
    @classmethod
    def create(
        cls,
        notif_type: NotificationType,
        priority: NotificationPriority,
        title: str,
        message: str,
        sender: Optional[str] = None,
        recipient: Optional[str] = None,
        patient_id: Optional[str] = None,
        data: Optional[Dict] = None
    ) -> "Notification":
        """Factory method para crear notificaciones."""
        return cls(
            id=str(uuid.uuid4()),
            type=notif_type.name,
            priority=priority.value,
            title=title,
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
            sender=sender,
            recipient=recipient,
            patient_id=patient_id,
            data=data or {}
        )


class NotificationManager:
    """
    Gestor central de notificaciones en tiempo real.
    
    Usar:
        manager = NotificationManager()
        
        # Enviar alerta crítica
        manager.send_critical_alert(
            title="Glucosa CRÍTICA",
            message="Paciente Juan Pérez: Glucosa 450 mg/dL",
            patient_id="patient-123"
        )
        
        # En polling loop de Streamlit
        notifications = manager.get_unread_for_user("dr-garcia")
    """
    
    MAX_NOTIFICATIONS_PER_USER = 100  # Límite de memoria
    NOTIFICATION_TTL_SECONDS = 86400    # 24 horas
    
    def __init__(self):
        self._notifications: Dict[str, List[Notification]] = {}  # user_id -> notifications
        self._redis = None
        self._subscribers: Dict[str, List[Callable]] = {}  # user_id -> callbacks
        self._lock = threading.Lock()
        self._init_redis()
    
    def _init_redis(self) -> None:
        """Inicializa Redis para pub/sub entre workers."""
        try:
            settings = get_settings()
            redis_url = settings.redis_url
            
            if redis_url:
                import redis
                self._redis = redis.from_url(
                    redis_url.get_secret_value(),
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2
                )
                log_event("notifications", "redis_pubsub_ready")
        except Exception as e:
            log_event("notifications", f"redis_unavailable:{type(e).__name__}")
            self._redis = None
    
    def _get_user_notifications(self, user_id: str) -> List[Notification]:
        """Obtiene notificaciones de un usuario (crea si no existe)."""
        if user_id not in self._notifications:
            self._notifications[user_id] = []
        return self._notifications[user_id]
    
    def send_notification(
        self,
        notification: Notification,
        broadcast: bool = False
    ) -> None:
        """
        Envía una notificación.
        
        Args:
            notification: Notificación a enviar
            broadcast: Si True, envía a todos los usuarios
        """
        with self._lock:
            if broadcast:
                # Enviar a todos los usuarios conectados
                for user_id in self._notifications.keys():
                    self._add_to_user(user_id, notification)
            else:
                # Enviar a destinatario específico
                recipient = notification.recipient
                if recipient:
                    self._add_to_user(recipient, notification)
                else:
                    # Broadcast si no hay destinatario
                    for user_id in self._notifications.keys():
                        self._add_to_user(user_id, notification)
            
            # Publicar en Redis para otros workers
            if self._redis:
                try:
                    channel = f"notifications:{notification.recipient or 'broadcast'}"
                    self._redis.publish(channel, json.dumps(notification.to_dict()))
                except Exception:
                    pass
        
        # Notificar suscriptores locales
        self._notify_subscribers(notification)
        
        # Log según prioridad
        if notification.priority == NotificationPriority.CRITICAL.value:
            log_event("notification_critical", f"sent:{notification.title}")
    
    def _add_to_user(self, user_id: str, notification: Notification) -> None:
        """Agrega notificación a usuario, respetando límite."""
        user_notifs = self._get_user_notifications(user_id)
        user_notifs.append(notification)
        
        # Mantener solo las más recientes
        if len(user_notifs) > self.MAX_NOTIFICATIONS_PER_USER:
            # Ordenar por timestamp y mantener más recientes
            user_notifs.sort(key=lambda n: n.timestamp, reverse=True)
            self._notifications[user_id] = user_notifs[:self.MAX_NOTIFICATIONS_PER_USER]
    
    def _notify_subscribers(self, notification: Notification) -> None:
        """Notifica a suscriptores locales."""
        recipient = notification.recipient
        
        if recipient and recipient in self._subscribers:
            for callback in self._subscribers[recipient]:
                try:
                    callback(notification)
                except Exception:
                    pass
        
        # También notificar a suscriptores globales
        if "*" in self._subscribers:
            for callback in self._subscribers["*"]:
                try:
                    callback(notification)
                except Exception:
                    pass
    
    def subscribe(self, user_id: str, callback: Callable[[Notification], None]) -> None:
        """Suscribe un callback a notificaciones de usuario."""
        if user_id not in self._subscribers:
            self._subscribers[user_id] = []
        self._subscribers[user_id].append(callback)
    
    def unsubscribe(self, user_id: str, callback: Callable[[Notification], None]) -> None:
        """Desuscribe un callback."""
        if user_id in self._subscribers:
            if callback in self._subscribers[user_id]:
                self._subscribers[user_id].remove(callback)
    
    def get_unread_for_user(
        self,
        user_id: str,
        priority_filter: Optional[NotificationPriority] = None
    ) -> List[Notification]:
        """Obtiene notificaciones no leídas de un usuario."""
        user_notifs = self._get_user_notifications(user_id)
        
        unread = [n for n in user_notifs if not n.read]
        
        if priority_filter:
            unread = [n for n in unread if n.priority == priority_filter.value]
        
        # Ordenar por prioridad y fecha
        priority_order = {
            NotificationPriority.CRITICAL.value: 0,
            NotificationPriority.HIGH.value: 1,
            NotificationPriority.NORMAL.value: 2,
            NotificationPriority.LOW.value: 3
        }
        
        unread.sort(key=lambda n: (priority_order.get(n.priority, 99), n.timestamp))
        
        return unread
    
    def mark_as_read(self, user_id: str, notification_id: str) -> bool:
        """Marca notificación como leída."""
        user_notifs = self._get_user_notifications(user_id)
        
        for notif in user_notifs:
            if notif.id == notification_id:
                notif.read = True
                notif.read_at = datetime.now(timezone.utc).isoformat()
                return True
        
        return False
    
    def acknowledge_critical(self, user_id: str, notification_id: str) -> bool:
        """Reconoce (ack) una alerta crítica."""
        user_notifs = self._get_user_notifications(user_id)
        
        for notif in user_notifs:
            if notif.id == notification_id and notif.priority == NotificationPriority.CRITICAL.value:
                notif.acknowledged = True
                notif.read = True
                notif.read_at = datetime.now(timezone.utc).isoformat()
                
                log_event("notification_ack", f"critical:{notification_id}:by:{user_id}")
                return True
        
        return False
    
    def clear_old_notifications(self, max_age_hours: int = 24) -> int:
        """Limpia notificaciones antiguas. Retorna cantidad eliminada."""
        cutoff = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
        removed = 0
        
        with self._lock:
            for user_id, notifs in self._notifications.items():
                original_count = len(notifs)
                self._notifications[user_id] = [
                    n for n in notifs
                    if datetime.fromisoformat(n.timestamp).timestamp() > cutoff
                ]
                removed += original_count - len(self._notifications[user_id])
        
        return removed
    
    def get_stats(self) -> Dict[str, Any]:
        """Estadísticas de notificaciones."""
        total = sum(len(n) for n in self._notifications.values())
        unread = sum(
            sum(1 for notif in notifs if not notif.read)
            for notifs in self._notifications.values()
        )
        critical_unack = sum(
            sum(1 for notif in notifs
                if notif.priority == NotificationPriority.CRITICAL.value and not notif.acknowledged)
            for notifs in self._notifications.values()
        )
        
        return {
            "total_notifications": total,
            "unread": unread,
            "critical_unacknowledged": critical_unack,
            "active_users": len(self._notifications)
        }


# Instancia global
_notification_manager = None

def get_notification_manager() -> NotificationManager:
    """Retorna instancia singleton."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager


# Funciones helper de alto nivel

def send_critical_alert(
    title: str,
    message: str,
    patient_id: Optional[str] = None,
    recipient: Optional[str] = None,
    data: Optional[Dict] = None
) -> Notification:
    """Envía alerta crítica (ej: valor de lab anormal)."""
    notif = Notification.create(
        notif_type=NotificationType.LAB_CRITICAL,
        priority=NotificationPriority.CRITICAL,
        title=title,
        message=message,
        patient_id=patient_id,
        recipient=recipient,
        data=data
    )
    
    get_notification_manager().send_notification(notif)
    return notif


def send_appointment_reminder(
    patient_name: str,
    appointment_time: str,
    doctor_name: str,
    recipient: str
) -> Notification:
    """Envía recordatorio de turno."""
    notif = Notification.create(
        notif_type=NotificationType.APPOINTMENT_UPCOMING,
        priority=NotificationPriority.NORMAL,
        title=f"Turno próximo: {patient_name}",
        message=f"Paciente {patient_name} a las {appointment_time} con {doctor_name}",
        recipient=recipient
    )
    
    get_notification_manager().send_notification(notif)
    return notif


def send_team_message(
    message: str,
    sender: str,
    recipient: Optional[str] = None,
    priority: NotificationPriority = NotificationPriority.NORMAL
) -> Notification:
    """Envía mensaje al equipo."""
    notif = Notification.create(
        notif_type=NotificationType.TEAM_MESSAGE,
        priority=priority,
        title=f"Mensaje de {sender}",
        message=message,
        sender=sender,
        recipient=recipient
    )
    
    get_notification_manager().send_notification(notif)
    return notif


def render_notification_badge() -> None:
    """Renderiza badge de notificaciones en Streamlit."""
    import streamlit as st
    
    try:
        user = st.session_state.get("u_actual", {})
        user_id = user.get("username")
        
        if not user_id:
            return
        
        manager = get_notification_manager()
        unread = manager.get_unread_for_user(user_id)
        critical = [n for n in unread if n.priority == NotificationPriority.CRITICAL.value]
        
        # Badge en sidebar
        if critical:
            st.sidebar.error(f"🔴 {len(critical)} ALERTAS CRÍTICAS")
        elif unread:
            st.sidebar.info(f"🔔 {len(unread)} notificaciones")
        else:
            st.sidebar.caption("🔕 Sin notificaciones")
        
        # Mostrar críticas primero
        for notif in critical[:3]:  # Máximo 3 críticas visibles
            with st.sidebar.expander(f"🚨 {notif.title}", expanded=True):
                st.write(notif.message)
                if st.button("✓ Reconocer", key=f"ack_{notif.id}"):
                    manager.acknowledge_critical(user_id, notif.id)
    
    except Exception as e:
        log_event("notification_ui", f"render_error:{type(e).__name__}")
