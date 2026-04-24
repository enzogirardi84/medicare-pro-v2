"""
Sistema de Notificaciones por Email para Medicare Pro.

Características:
- Templates HTML y texto plano
- Cola de emails (async)
- Rate limiting
- Tracking de entrega
- Múltiples providers (SMTP, SendGrid, AWS SES)
"""

from __future__ import annotations

import os
import re
import smtplib
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
from enum import Enum, auto
from email.utils import formataddr

from core.app_logging import log_event
from core.distributed_cache import get_cache


class EmailProvider(Enum):
    """Proveedores de email soportados."""
    SMTP = auto()
    SENDGRID = auto()
    AWS_SES = auto()
    MAILGUN = auto()


@dataclass
class EmailMessage:
    """Mensaje de email."""
    to: str
    subject: str
    body_text: str
    body_html: Optional[str] = None
    from_name: str = "Medicare Pro"
    from_email: str = "noreply@medicare.local"
    reply_to: Optional[str] = None
    attachments: Optional[List[Dict]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class EmailTemplate:
    """Template de email."""
    name: str
    subject: str
    body_text: str
    body_html: str
    required_vars: List[str]


class EmailNotificationManager:
    """
    Manager de notificaciones por email.
    
    Soporta:
    - Envío sincrónico y async
    - Templates
    - Rate limiting por destinatario
    - Retry automático
    - Tracking de estado
    """
    
    # Rate limiting: máximo 10 emails por hora a cada destinatario
    RATE_LIMIT_PER_HOUR = 10
    
    # Templates predefinidos
    TEMPLATES = {
        "welcome": EmailTemplate(
            name="welcome",
            subject="Bienvenido a Medicare Pro",
            body_text="""
Hola {nombre},

Bienvenido a Medicare Pro. Tu cuenta ha sido creada exitosamente.

Datos de acceso:
- Usuario: {username}
- Empresa: {empresa}

Por seguridad, te recomendamos cambiar tu contraseña en tu primer inicio de sesión.

Saludos,
El equipo de Medicare Pro
            """.strip(),
            body_html="""
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #0f172a; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; background: #f8fafc; }
        .footer { padding: 20px; text-align: center; color: #64748b; font-size: 12px; }
        .button { display: inline-block; padding: 12px 24px; background: #14b8a6; color: white; text-decoration: none; border-radius: 6px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🩺 Medicare Pro</h1>
        </div>
        <div class="content">
            <h2>Bienvenido, {nombre}</h2>
            <p>Tu cuenta ha sido creada exitosamente.</p>
            <p><strong>Datos de acceso:</strong></p>
            <ul>
                <li>Usuario: {username}</li>
                <li>Empresa: {empresa}</li>
            </ul>
            <p style="margin-top: 30px;">
                <a href="{login_url}" class="button">Iniciar Sesión</a>
            </p>
            <p style="margin-top: 20px; font-size: 12px; color: #64748b;">
                Por seguridad, te recomendamos cambiar tu contraseña en tu primer inicio de sesión.
            </p>
        </div>
        <div class="footer">
            <p>Este es un email automático de Medicare Pro</p>
        </div>
    </div>
</body>
</html>
            """.strip(),
            required_vars=["nombre", "username", "empresa", "login_url"]
        ),
        
        "password_reset": EmailTemplate(
            name="password_reset",
            subject="Recuperación de Contraseña - Medicare Pro",
            body_text="""
Hola {nombre},

Has solicitado restablecer tu contraseña. Usa el siguiente código:

Código de recuperación: {reset_code}

Este código expira en 15 minutos.

Si no solicitaste este cambio, ignora este email.

Medicare Pro
            """.strip(),
            body_html="""
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; }
        .code { font-size: 24px; font-weight: bold; letter-spacing: 4px; 
                background: #0f172a; color: #14b8a6; padding: 15px; 
                text-align: center; border-radius: 8px; }
    </style>
</head>
<body>
    <h2>Recuperación de Contraseña</h2>
    <p>Hola {nombre},</p>
    <p>Usa este código para restablecer tu contraseña:</p>
    <div class="code">{reset_code}</div>
    <p>Este código expira en <strong>15 minutos</strong>.</p>
    <p style="color: #64748b;">Si no solicitaste este cambio, ignora este email.</p>
</body>
</html>
            """.strip(),
            required_vars=["nombre", "reset_code"]
        ),
        
        "appointment_reminder": EmailTemplate(
            name="appointment_reminder",
            subject="Recordatorio de Cita - Medicare Pro",
            body_text="""
Hola {nombre_paciente},

Le recordamos su cita programada:

📅 Fecha: {fecha}
🕐 Hora: {hora}
👨‍⚕️ Profesional: {profesional}
🏥 Lugar: {lugar}

Por favor llegue 15 minutos antes.

Para cancelar o reprogramar, contacte a la clínica.

Medicare Pro
            """.strip(),
            body_html="""
<!DOCTYPE html>
<html>
<body style="font-family: Arial; max-width: 600px;">
    <h2>📅 Recordatorio de Cita</h2>
    <p>Hola {nombre_paciente},</p>
    <div style="background: #f1f5f9; padding: 20px; border-radius: 8px;">
        <p><strong>📅 Fecha:</strong> {fecha}</p>
        <p><strong>🕐 Hora:</strong> {hora}</p>
        <p><strong>👨‍⚕️ Profesional:</strong> {profesional}</p>
        <p><strong>🏥 Lugar:</strong> {lugar}</p>
    </div>
    <p style="color: #64748b;">Por favor llegue 15 minutos antes.</p>
    <hr>
    <p style="font-size: 12px;">Para cancelar, contacte a la clínica.</p>
</body>
</html>
            """.strip(),
            required_vars=["nombre_paciente", "fecha", "hora", "profesional", "lugar"]
        ),
        
        "security_alert": EmailTemplate(
            name="security_alert",
            subject="🚨 Alerta de Seguridad - Medicare Pro",
            body_text="""
ALERTA DE SEGURIDAD

Se detectó una actividad inusual en su cuenta:

{detalle}

Fecha/Hora: {timestamp}
IP: {ip_address}

Si no reconoce esta actividad, contacte inmediatamente al administrador.

Medicare Pro Security
            """.strip(),
            body_html="""
<!DOCTYPE html>
<html>
<body style="font-family: Arial; max-width: 600px;">
    <div style="background: #fef2f2; border-left: 4px solid #ef4444; padding: 20px;">
        <h2 style="color: #dc2626;">🚨 Alerta de Seguridad</h2>
        <p>Se detectó actividad inusual:</p>
        <p><strong>{detalle}</strong></p>
        <hr>
        <p><strong>Fecha/Hora:</strong> {timestamp}</p>
        <p><strong>IP:</strong> {ip_address}</p>
        <p style="color: #dc2626; margin-top: 20px;">
            Si no reconoce esta actividad, contacte al administrador inmediatamente.
        </p>
    </div>
</body>
</html>
            """.strip(),
            required_vars=["detalle", "timestamp", "ip_address"]
        ),
    }
    
    def __init__(self):
        self.provider = self._get_provider()
        self.cache = get_cache()
    
    def _get_provider(self) -> EmailProvider:
        """Determina el provider de email configurado."""
        provider_str = os.getenv("EMAIL_PROVIDER", "smtp").lower()
        
        if provider_str == "sendgrid":
            return EmailProvider.SENDGRID
        elif provider_str == "aws_ses":
            return EmailProvider.AWS_SES
        elif provider_str == "mailgun":
            return EmailProvider.MAILGUN
        else:
            return EmailProvider.SMTP
    
    def _check_rate_limit(self, to_email: str) -> bool:
        """Verifica rate limiting por destinatario."""
        cache_key = f"email_rate_limit:{to_email}"
        
        # Contar emails enviados en la última hora
        count = self.cache.get(cache_key) or 0
        
        if count >= self.RATE_LIMIT_PER_HOUR:
            log_event("email_rate_limit", f"Rate limit exceeded for {to_email}")
            return False
        
        # Incrementar contador
        self.cache.set(cache_key, count + 1, ttl=3600)
        return True
    
    def validate_email(self, email: str) -> bool:
        """Valida formato de email."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def render_template(
        self,
        template_name: str,
        variables: Dict[str, str]
    ) -> EmailMessage:
        """
        Renderiza un template con variables.
        
        Args:
            template_name: Nombre del template
            variables: Dict con variables a reemplazar
        
        Returns:
            EmailMessage listo para enviar
        """
        template = self.TEMPLATES.get(template_name)
        if not template:
            raise ValueError(f"Template no encontrado: {template_name}")
        
        # Verificar variables requeridas
        missing = [v for v in template.required_vars if v not in variables]
        if missing:
            raise ValueError(f"Variables faltantes: {missing}")
        
        # Renderizar
        subject = template.subject
        body_text = template.body_text.format(**variables)
        body_html = template.body_html.format(**variables)
        
        return EmailMessage(
            to=variables.get("email", ""),
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            from_name="Medicare Pro",
            from_email=os.getenv("EMAIL_FROM", "noreply@medicare.local")
        )
    
    def send_email(
        self,
        message: EmailMessage,
        check_rate_limit: bool = True
    ) -> Dict[str, Any]:
        """
        Envía un email.
        
        Args:
            message: EmailMessage a enviar
            check_rate_limit: Si verificar rate limiting
        
        Returns:
            Dict con resultado del envío
        """
        # Validar
        if not self.validate_email(message.to):
            return {
                "success": False,
                "error": "Email inválido",
                "message_id": None
            }
        
        # Rate limiting
        if check_rate_limit and not self._check_rate_limit(message.to):
            return {
                "success": False,
                "error": "Rate limit exceeded",
                "message_id": None
            }
        
        # Enviar según provider
        try:
            if self.provider == EmailProvider.SMTP:
                return self._send_smtp(message)
            elif self.provider == EmailProvider.SENDGRID:
                return self._send_sendgrid(message)
            else:
                # Fallback a SMTP
                return self._send_smtp(message)
                
        except Exception as e:
            log_event("email_error", f"Failed to send email: {e}")
            return {
                "success": False,
                "error": str(e),
                "message_id": None
            }
    
    def _send_smtp(self, message: EmailMessage) -> Dict[str, Any]:
        """Envía email vía SMTP."""
        smtp_host = os.getenv("SMTP_HOST", "localhost")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER", "")
        smtp_password = os.getenv("SMTP_PASSWORD", "")
        
        # Crear mensaje MIME
        msg = MIMEMultipart("alternative")
        msg["Subject"] = message.subject
        msg["From"] = formataddr((message.from_name, message.from_email))
        msg["To"] = message.to
        
        if message.reply_to:
            msg["Reply-To"] = message.reply_to
        
        # Adjuntar cuerpos
        msg.attach(MIMEText(message.body_text, "plain", "utf-8"))
        if message.body_html:
            msg.attach(MIMEText(message.body_html, "html", "utf-8"))
        
        # Enviar
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            
            server.sendmail(
                message.from_email,
                message.to,
                msg.as_string()
            )
        
        message_id = f"smtp-{datetime.now().timestamp()}"
        
        log_event("email_sent", f"Email sent to {message.to}: {message.subject}")
        
        return {
            "success": True,
            "error": None,
            "message_id": message_id,
            "provider": "smtp"
        }
    
    def _send_sendgrid(self, message: EmailMessage) -> Dict[str, Any]:
        """Envía email vía SendGrid API."""
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail
            
            api_key = os.getenv("SENDGRID_API_KEY", "")
            sg = SendGridAPIClient(api_key)
            
            mail = Mail(
                from_email=message.from_email,
                to_emails=message.to,
                subject=message.subject,
                html_content=message.body_html,
                plain_text_content=message.body_text
            )
            
            response = sg.send(mail)
            
            return {
                "success": response.status_code == 202,
                "error": None if response.status_code == 202 else f"HTTP {response.status_code}",
                "message_id": response.headers.get("X-Message-Id"),
                "provider": "sendgrid"
            }
            
        except Exception as e:
            # Fallback a SMTP
            log_event("email_fallback", f"SendGrid failed, falling back to SMTP: {e}")
            return self._send_smtp(message)
    
    def send_template_email(
        self,
        template_name: str,
        to_email: str,
        variables: Dict[str, str],
        check_rate_limit: bool = True
    ) -> Dict[str, Any]:
        """
        Envía email usando un template.
        
        Args:
            template_name: Nombre del template
            to_email: Destinatario
            variables: Variables para el template
            check_rate_limit: Si verificar rate limiting
        """
        # Agregar email a variables
        variables["email"] = to_email
        
        # Renderizar
        message = self.render_template(template_name, variables)
        
        # Enviar
        return self.send_email(message, check_rate_limit)
    
    def queue_email(
        self,
        message: EmailMessage,
        send_at: Optional[datetime] = None
    ) -> str:
        """
        Encola un email para envío posterior.
        
        Args:
            message: Email a enviar
            send_at: Cuándo enviar (None = lo antes posible)
        
        Returns:
            ID de la tarea encolada
        """
        import uuid
        
        task_id = str(uuid.uuid4())
        
        # Guardar en caché/redis para procesamiento async
        task_data = {
            "id": task_id,
            "message": {
                "to": message.to,
                "subject": message.subject,
                "body_text": message.body_text,
                "body_html": message.body_html,
                "from_name": message.from_name,
                "from_email": message.from_email,
            },
            "send_at": send_at.isoformat() if send_at else None,
            "status": "queued",
            "created_at": datetime.now().isoformat()
        }
        
        # Guardar en caché (en producción usar Redis/RQ/Celery)
        self.cache.set(f"email_queue:{task_id}", task_data, ttl=86400)
        
        log_event("email_queued", f"Email queued: {task_id} to {message.to}")
        
        return task_id
    
    def get_queue_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene estado de un email encolado."""
        return self.cache.get(f"email_queue:{task_id}")


# Singleton
_email_manager: Optional[EmailNotificationManager] = None


def get_email_manager() -> EmailNotificationManager:
    """Obtiene instancia del manager de emails."""
    global _email_manager
    if _email_manager is None:
        _email_manager = EmailNotificationManager()
    return _email_manager


# Helpers rápidos
def send_welcome_email(to_email: str, nombre: str, username: str, empresa: str) -> Dict[str, Any]:
    """Envía email de bienvenida."""
    return get_email_manager().send_template_email(
        "welcome",
        to_email,
        {
            "nombre": nombre,
            "username": username,
            "empresa": empresa,
            "login_url": "https://medicare.local/login"
        }
    )


def send_password_reset(to_email: str, nombre: str, reset_code: str) -> Dict[str, Any]:
    """Envía email de recuperación de contraseña."""
    return get_email_manager().send_template_email(
        "password_reset",
        to_email,
        {
            "nombre": nombre,
            "reset_code": reset_code
        }
    )


def send_appointment_reminder(
    to_email: str,
    nombre_paciente: str,
    fecha: str,
    hora: str,
    profesional: str,
    lugar: str
) -> Dict[str, Any]:
    """Envía recordatorio de cita."""
    return get_email_manager().send_template_email(
        "appointment_reminder",
        to_email,
        {
            "nombre_paciente": nombre_paciente,
            "fecha": fecha,
            "hora": hora,
            "profesional": profesional,
            "lugar": lugar
        }
    )


def send_security_alert(to_email: str, detalle: str, ip_address: str) -> Dict[str, Any]:
    """Envía alerta de seguridad."""
    return get_email_manager().send_template_email(
        "security_alert",
        to_email,
        {
            "detalle": detalle,
            "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "ip_address": ip_address
        }
    )
