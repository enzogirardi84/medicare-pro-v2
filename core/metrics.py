"""Sistema de metricas, health checks y observabilidad para produccion.
Expone endpoint de salud, metricas de negocio/seguridad y telemetria.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. ESTRUCTURA DE METRICAS
# ═══════════════════════════════════════════════════════════════════

@dataclass
class MetricasSistema:
    """Metricas agregadas del sistema."""
    timestamp: float = field(default_factory=time.time)
    # Operaciones
    total_operaciones_offline: int = 0
    operaciones_sincronizadas: int = 0
    operaciones_fallidas: int = 0
    # Seguridad
    intentos_login_totp_fallidos: int = 0
    archivos_bloqueados_sanitizer: int = 0
    firmas_ecdsa_exitosas: int = 0
    firmas_ecdsa_fallidas: int = 0
    # Performance
    tiempo_procesamiento_pdf_ms: list[float] = field(default_factory=list)
    tiempo_promedio_pdf_ms: float = 0.0
    # Disco
    audit_log_size_bytes: int = 0
    upload_dir_size_bytes: int = 0
    disco_libre_bytes: int = 0
    # Conexion
    supabase_online: bool = False
    cola_offline_pendientes: int = 0
    audit_trail_integridad_ok: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_prometheus(self) -> str:
        lines = [
            f"# HELP medicare_operaciones_offline Operaciones offline pendientes",
            f"# TYPE medicare_operaciones_offline gauge",
            f"medicare_operaciones_offline {self.total_operaciones_offline}",
            "",
            f"# HELP medicare_operaciones_sincronizadas Total sincronizadas",
            f"# TYPE medicare_operaciones_sincronizadas counter",
            f"medicare_operaciones_sincronizadas {self.operaciones_sincronizadas}",
            "",
            f"# HELP medicare_login_totp_fallidos Intentos TOTP fallidos",
            f"# TYPE medicare_login_totp_fallidos counter",
            f"medicare_login_totp_fallidos {self.intentos_login_totp_fallidos}",
            "",
            f"# HELP medicare_archivos_bloqueados Archivos rechazados por sanitizer",
            f"# TYPE medicare_archivos_bloqueados counter",
            f"medicare_archivos_bloqueados {self.archivos_bloqueados_sanitizer}",
            "",
            f"# HELP medicare_pdf_tiempo_ms Tiempo de generacion PDF en ms",
            f"# TYPE medicare_pdf_tiempo_ms gauge",
            f"medicare_pdf_tiempo_ms {self.tiempo_promedio_pdf_ms}",
            "",
            f"# HELP medicare_audit_traill_integridad Audit trail integro (1=ok, 0=fallo)",
            f"# TYPE medicare_audit_traill_integridad gauge",
            f"medicare_audit_traill_integridad {1 if self.audit_trail_integridad_ok else 0}",
            "",
            f"# HELP medicare_supabase_online Supabase accesible (1=si, 0=no)",
            f"# TYPE medicare_supabase_online gauge",
            f"medicare_supabase_online {1 if self.supabase_online else 0}",
        ]
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# 2. RECOLECTOR DE METRICAS
# ═══════════════════════════════════════════════════════════════════

class MetricsCollector:
    """Recolecta metricas del sistema en tiempo real.

    Las metricas se acumulan en session_state y se exponen
    via el endpoint de salud o el dashboard SRE.
    """

    _instance: Optional[MetricsCollector] = None

    def __new__(cls) -> MetricsCollector:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._metricas = MetricasSistema()

    # ── Contadores ─────────────────────────────────────────────

    def incrementar_offline(self, n: int = 1) -> None:
        self._metricas.total_operaciones_offline += n

    def incrementar_sincronizadas(self, n: int = 1) -> None:
        self._metricas.operaciones_sincronizadas += n

    def incrementar_sincronizadas_fallidas(self, n: int = 1) -> None:
        self._metricas.operaciones_fallidas += n

    def incrementar_totp_fallido(self) -> None:
        self._metricas.intentos_login_totp_fallidos += 1

    def incrementar_archivo_bloqueado(self) -> None:
        self._metricas.archivos_bloqueados_sanitizer += 1

    def incrementar_firma_ecdsa_ok(self) -> None:
        self._metricas.firmas_ecdsa_exitosas += 1

    def incrementar_firma_ecdsa_fallo(self) -> None:
        self._metricas.firmas_ecdsa_fallidas += 1

    def registrar_tiempo_pdf(self, ms: float) -> None:
        self._metricas.tiempo_procesamiento_pdf_ms.append(ms)
        if len(self._metricas.tiempo_procesamiento_pdf_ms) > 100:
            self._metricas.tiempo_procesamiento_pdf_ms = \
                self._metricas.tiempo_procesamiento_pdf_ms[-100:]
        self._metricas.tiempo_promedio_pdf_ms = (
            sum(self._metricas.tiempo_procesamiento_pdf_ms)
            / max(len(self._metricas.tiempo_procesamiento_pdf_ms), 1)
        )

    # ── Health Check profundo ──────────────────────────────────

    def health_check(self, tenant_id: str = "default") -> MetricasSistema:
        """Ejecuta chequeo de salud completo del sistema."""
        m = self._metricas

        # Espacio en disco de directorios criticos
        for dir_path, attr in [
            (".audit_logs", "audit_log_size_bytes"),
            ("storage/estudios", "upload_dir_size_bytes"),
        ]:
            p = Path(dir_path)
            if p.exists():
                total = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                setattr(m, attr, total)

        # Disco libre
        try:
            st = os.statvfs("/")
            m.disco_libre_bytes = st.f_bavail * st.f_frsize
        except Exception:
            m.disco_libre_bytes = 0

        # Cola offline
        try:
            queue_dir = Path(f"tenants/{tenant_id}/offline_queue")
            if queue_dir.exists():
                m.cola_offline_pendientes = len(list(queue_dir.glob("*.db")))
        except Exception:
            pass

        # Integridad del audit trail
        try:
            from core.audit_trail_immutable import ImmutableAuditTrail
            auditor = ImmutableAuditTrail()
            errores = auditor.verificar_integridad(max_entries=1000)
            m.audit_trail_integridad_ok = len(errores) == 0
            if errores:
                log_event("sre", f"health_check:audit_trail_integridad_fallo:{len(errores)}_errores")
        except Exception as exc:
            m.audit_trail_integridad_ok = False
            log_event("sre", f"health_check:audit_error:{type(exc).__name__}")

        # Supabase
        try:
            import urllib.request
            req = urllib.request.Request(
                "https://medicare-pro-v2-eyqvgkqwvd9e48r5z6klrf.streamlit.app/healthz",
                method="HEAD",
            )
            urllib.request.urlopen(req, timeout=5)
            m.supabase_online = True
        except Exception:
            m.supabase_online = False

        m.timestamp = time.time()
        return m

    def obtener_metricas(self) -> MetricasSistema:
        return self._metricas


# ═══════════════════════════════════════════════════════════════════
# 3. ENDPOINT DE SALUD (para /healthz)
# ═══════════════════════════════════════════════════════════════════

def health_check_endpoint(tenant_id: str = "default") -> str:
    """Endpoint de salud avanzado.

    Returns JSON con estado detallado del sistema.
    Uso: integrar en Uvicorn/FastAPI o como pagina oculta.
    """
    collector = MetricsCollector()
    m = collector.health_check(tenant_id)

    status_code = 200 if m.audit_trail_integridad_ok and m.supabase_online else 503
    status = "healthy" if status_code == 200 else "degraded"

    response = {
        "status": status,
        "status_code": status_code,
        "timestamp": datetime.fromtimestamp(m.timestamp).isoformat(),
        "tenant": tenant_id,
        "checks": {
            "audit_trail_integridad": m.audit_trail_integridad_ok,
            "supabase_online": m.supabase_online,
            "disco_libre_mb": round(m.disco_libre_bytes / (1024 * 1024), 1) if m.disco_libre_bytes else 0,
            "cola_offline_pendientes": m.cola_offline_pendientes,
            "audit_log_size_mb": round(m.audit_log_size_bytes / (1024 * 1024), 1),
            "upload_dir_size_mb": round(m.upload_dir_size_bytes / (1024 * 1024), 1),
        },
        "metrics": {
            "operaciones_offline": m.total_operaciones_offline,
            "operaciones_sincronizadas": m.operaciones_sincronizadas,
            "intentos_totp_fallidos": m.intentos_login_totp_fallidos,
            "archivos_bloqueados": m.archivos_bloqueados_sanitizer,
            "tiempo_promedio_pdf_ms": round(m.tiempo_promedio_pdf_ms, 1),
        },
    }
    return json.dumps(response, indent=2, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════
# 4. MOTOR DE NOTIFICACIONES DE EMERGENCIA
# ═══════════════════════════════════════════════════════════════════

class AlertManager:
    """Despachador de alertas criticas via webhook.

    Dispara notificaciones a Slack/Discord/Telegram cuando ocurren
    eventos de seguridad o fallos de infraestructura.
    """

    WEBHOOK_URL = os.environ.get(
        "ALERT_WEBHOOK_URL",
        "",  # Configurar en produccion
    )

    @dataclass
    class Alerta:
        """Estructura de una alerta."""
        nivel: str  # "CRITICAL" | "WARNING" | "INFO"
        mensaje: str
        tenant: str = "default"
        modulo: str = ""
        timestamp: float = field(default_factory=time.time)
        metrica: str = ""

        def to_dict(self) -> dict[str, Any]:
            return {
                "nivel": self.nivel,
                "mensaje": self.mensaje,
                "tenant": self.tenant,
                "modulo": self.modulo,
                "timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
                "metrica": self.metrica,
            }

    @classmethod
    def disparar_alerta(
        cls,
        nivel: str,
        mensaje: str,
        tenant: str = "default",
        modulo: str = "",
        metrica: str = "",
    ) -> None:
        """Dispara una alerta y la envia via webhook.

        La alerta SIEMPRE se registra en el log.
        Si hay webhook configurado, se envia asyncronicamente.
        """
        alerta = cls.Alerta(
            nivel=nivel, mensaje=mensaje, tenant=tenant,
            modulo=modulo, metrica=metrica,
        )
        payload = alerta.to_dict()

        # Siempre loguear
        log_event("alert", f"{nivel}:{mensaje}:{tenant}:{modulo}")

        # Enviar webhook si configurado
        if cls.WEBHOOK_URL:
            try:
                import urllib.request
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    cls.WEBHOOK_URL,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception as exc:
                log_event("alert", f"webhook_fallo:{type(exc).__name__}")

        # Alertas CRITICAL siempre se registran en audit trail
        if nivel == "CRITICAL":
            try:
                from core.audit_trail_immutable import ImmutableAuditTrail
                auditor = ImmutableAuditTrail()
                auditor.registrar(
                    usuario="__sre__",
                    accion=f"ALERTA_{nivel}",
                    recurso=f"sre:{modulo}",
                    detalle=mensaje,
                )
            except Exception as exc:
                log_event("alert", f"audit_trail_error:{type(exc).__name__}")


# ═══════════════════════════════════════════════════════════════════
# 5. PANEL SRE EN STREAMLIT
# ═══════════════════════════════════════════════════════════════════

def render_sre_panel(rol: str, tenant_id: str = "default") -> None:
    """Panel de telemetria SRE (solo SuperAdmin/Admin)."""
    import streamlit as st

    if rol.lower() not in ("superadmin", "admin"):
        st.error("Acceso denegado. Se requiere rol SuperAdmin o Admin.")
        return

    st.markdown("# Centro de Operaciones SRE")
    st.caption(f"Tenant: {tenant_id} · {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    collector = MetricsCollector()
    m = collector.health_check(tenant_id)

    # Metricas principales
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Audit Trail integro", "Si" if m.audit_trail_integridad_ok else "NO",
                delta="OK" if m.audit_trail_integridad_ok else "CRITICO")
    col2.metric("Supabase online", "Si" if m.supabase_online else "No")
    col3.metric("Offline pendientes", m.cola_offline_pendientes)
    col4.metric("Tiempo PDF prom.", f"{m.tiempo_promedio_pdf_ms:.0f}ms")

    # Disco
    st.markdown("### Almacenamiento")
    dc1, dc2, dc3 = st.columns(3)
    dc1.metric("Audit Logs", f"{m.audit_log_size_bytes / (1024*1024):.1f} MB")
    dc2.metric("Estudios subidos", f"{m.upload_dir_size_bytes / (1024*1024):.1f} MB")
    dc3.metric("Disco libre", f"{m.disco_libre_bytes / (1024*1024):.0f} MB"
               if m.disco_libre_bytes else "N/D")

    # Seguridad
    st.markdown("### Seguridad")
    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("TOTP fallidos", m.intentos_login_totp_fallidos)
    sc2.metric("Archivos bloqueados", m.archivos_bloqueados_sanitizer)
    sc3.metric("Firmas ECDSA ok", m.firmas_ecdsa_exitosas)
    sc4.metric("Firmas ECDSA fallidas", m.firmas_ecdsa_fallidas)

    # Sincronizacion
    st.markdown("### Sincronizacion Offline")
    os1, os2, os3 = st.columns(3)
    os1.metric("Operaciones offline", m.total_operaciones_offline)
    os2.metric("Sincronizadas", m.operaciones_sincronizadas)
    os3.metric("Fallidas", m.operaciones_fallidas)

    # Logs recientes del audit trail
    st.markdown("### Auditoria reciente")
    try:
        from core.audit_trail_immutable import ImmutableAuditTrail
        auditor = ImmutableAuditTrail()
        entries = auditor.obtener_entradas_recientes(limite=20)
        if entries:
            for e in entries[-10:]:
                ts = datetime.fromtimestamp(e.get("timestamp", 0)).strftime("%H:%M:%S")
                st.caption(f"[{ts}] {e.get('usuario', '?')} - {e.get('accion', '?')} - {e.get('recurso', '?')}")
        else:
            st.caption("Sin entradas de auditoria recientes.")
    except Exception as exc:
        st.caption(f"Error al leer audit trail: {type(exc).__name__}")

    # Boton de health check manual
    if st.button("Ejecutar health check completo", use_container_width=True, key="sre_health_btn"):
        with st.spinner("Ejecutando chequeos..."):
            result = collector.health_check(tenant_id)
        if result.audit_trail_integridad_ok:
            st.success("Health check: OK")
        else:
            st.error("Health check: ERROR - Audit trail comprometido!")
            AlertManager.disparar_alerta(
                nivel="CRITICAL",
                mensaje="Health check detecto auditoria comprometida",
                tenant=tenant_id,
                modulo="sre_panel",
                metrica="audit_trail_integridad",
            )
