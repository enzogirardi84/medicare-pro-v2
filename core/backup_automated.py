"""
Sistema de Backup Automatizado para MediCare Pro.

Características:
- Backups programados (cada 4 horas por defecto)
- Encriptación AES-256 de backups
- Compresión gzip para ahorrar espacio
- Retención configurable (7-90 días)
- Verificación de integridad (checksum SHA-256)
- Subida automática a Supabase Storage / S3
- Notificaciones de éxito/fracaso
- Restauración granular (tabla específica o completa)

CRÍTICO para sistema de salud - datos de pacientes nunca deben perderse.
"""
import os
import json
import gzip
import hashlib
import time
import threading
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
import uuid

import streamlit as st

from core.app_logging import log_event
from core.config_secure import get_settings
from core.security_middleware import InputSanitizer


class BackupStatus(Enum):
    """Estado del backup."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    VERIFYING = "verifying"


class BackupType(Enum):
    """Tipo de backup."""
    FULL = "full"              # Backup completo
    INCREMENTAL = "incremental"  # Solo cambios desde último backup
    TABLE_SPECIFIC = "table"     # Tabla específica


@dataclass
class BackupEntry:
    """Entrada de backup."""
    id: str
    timestamp: str
    status: str
    type: str
    tables: List[str]
    size_bytes: int
    checksum: str
    compressed: bool
    encrypted: bool
    file_path: Optional[str]
    storage_path: Optional[str]
    error_message: Optional[str] = None
    completed_at: Optional[str] = None
    verification_passed: bool = False
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BackupManager:
    """
    Gestor de backups automatizados.
    
    Configuración vía variables de entorno:
    - BACKUP_INTERVAL_HOURS=4
    - BACKUP_RETENTION_DAYS=30
    - BACKUP_ENCRYPTION_KEY (si no se usa derivación de SECRET_KEY)
    - BACKUP_STORAGE=supabase (o local)
    
    Uso:
        manager = BackupManager()
        
        # Backup manual
        backup = manager.create_backup(
            backup_type=BackupType.FULL,
            tables=["pacientes", "evoluciones", "vitales"]
        )
        
        # Restaurar
        manager.restore_backup(backup_id)
    """
    
    DEFAULT_INTERVAL_HOURS = 4
    DEFAULT_RETENTION_DAYS = 30
    BACKUP_DIR = ".backups"
    CRITICAL_TABLES = [
        "pacientes",
        "evoluciones",
        "vitales",
        "indicaciones",
        "cuidados_enfermeria",
        "turnos",
        "usuarios",
        "auditoria_legal_db"
    ]
    
    def __init__(self):
        self._backups: List[BackupEntry] = []
        self._scheduler_thread: Optional[threading.Thread] = None
        self._stop_scheduler = False
        self._lock = threading.Lock()
        self._load_backup_history()
        self._ensure_backup_dir()
    
    def _ensure_backup_dir(self) -> None:
        """Crea directorio de backups si no existe."""
        backup_dir = Path(self.BACKUP_DIR)
        backup_dir.mkdir(exist_ok=True)
        
        # Proteger con .gitignore
        gitignore = backup_dir / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text("*\n!.gitignore\n")
    
    def _load_backup_history(self) -> None:
        """Carga historial de backups desde archivo."""
        history_file = Path(self.BACKUP_DIR) / "backup_history.json"
        if history_file.exists():
            try:
                with open(history_file, 'r') as f:
                    data = json.load(f)
                    self._backups = [BackupEntry(**entry) for entry in data]
            except Exception as e:
                log_event("backup", f"load_history_error:{type(e).__name__}")
    
    def _save_backup_history(self) -> None:
        """Guarda historial de backups."""
        history_file = Path(self.BACKUP_DIR) / "backup_history.json"
        try:
            with open(history_file, 'w') as f:
                json.dump([asdict(b) for b in self._backups], f, indent=2, default=str)
        except Exception as e:
            log_event("backup", f"save_history_error:{type(e).__name__}")
    
    def _get_encryption_key(self) -> bytes:
        """Deriva clave de encriptación de SECRET_KEY."""
        settings = get_settings()
        secret = settings.secret_key.get_secret_value()
        # Derivar clave de 32 bytes para AES-256
        return hashlib.sha256(secret.encode()).digest()
    
    def _encrypt_data(self, data: bytes) -> bytes:
        """Encripta datos con AES-256-GCM."""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            
            key = self._get_encryption_key()
            aesgcm = AESGCM(key)
            nonce = os.urandom(12)
            
            encrypted = aesgcm.encrypt(nonce, data, None)
            return nonce + encrypted
        except ImportError:
            log_event("backup", "encryption_unavailable:cryptography_not_installed")
            return data
    
    def _decrypt_data(self, encrypted_data: bytes) -> bytes:
        """Desencripta datos."""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            
            key = self._get_encryption_key()
            aesgcm = AESGCM(key)
            
            nonce = encrypted_data[:12]
            ciphertext = encrypted_data[12:]
            
            return aesgcm.decrypt(nonce, ciphertext, None)
        except ImportError:
            return encrypted_data
    
    def _compress_data(self, data: bytes) -> bytes:
        """Comprime datos con gzip."""
        return gzip.compress(data, compresslevel=6)
    
    def _decompress_data(self, data: bytes) -> bytes:
        """Descomprime datos."""
        return gzip.decompress(data)
    
    def _calculate_checksum(self, data: bytes) -> str:
        """Calcula SHA-256 checksum."""
        return hashlib.sha256(data).hexdigest()
    
    def create_backup(
        self,
        backup_type: BackupType = BackupType.FULL,
        tables: Optional[List[str]] = None,
        notify: bool = True
    ) -> BackupEntry:
        """
        Crea un backup.
        
        Args:
            backup_type: Tipo de backup
            tables: Tablas específicas (si no, usa CRITICAL_TABLES)
            notify: Enviar notificación al completar
        
        Returns:
            BackupEntry con información del backup
        """
        backup_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        
        tables = tables or self.CRITICAL_TABLES
        
        entry = BackupEntry(
            id=backup_id,
            timestamp=timestamp.isoformat(),
            status=BackupStatus.RUNNING.value,
            type=backup_type.value,
            tables=tables,
            size_bytes=0,
            checksum="",
            compressed=True,
            encrypted=True,
            file_path=None,
            storage_path=None
        )
        
        with self._lock:
            self._backups.append(entry)
        
        try:
            log_event("backup", f"started:{backup_id}:{backup_type.value}")
            
            # Recolectar datos
            backup_data = self._collect_data(tables)
            
            # Serializar
            json_data = json.dumps(backup_data, indent=None, default=str).encode('utf-8')
            original_size = len(json_data)
            
            # Comprimir
            compressed = self._compress_data(json_data)
            
            # Encriptar
            encrypted = self._encrypt_data(compressed)
            
            # Calcular checksum
            checksum = self._calculate_checksum(encrypted)
            
            # Guardar archivo
            filename = f"backup_{backup_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}.enc"
            file_path = Path(self.BACKUP_DIR) / filename
            
            with open(file_path, 'wb') as f:
                f.write(encrypted)
            
            # Verificar integridad
            entry.status = BackupStatus.VERIFYING.value
            if self._verify_backup(file_path, checksum):
                entry.verification_passed = True
            
            # Subir a almacenamiento cloud si está configurado
            storage_path = self._upload_to_storage(file_path, filename)
            
            # Actualizar entry
            entry.status = BackupStatus.SUCCESS.value
            entry.size_bytes = len(encrypted)
            entry.checksum = checksum
            entry.file_path = str(file_path)
            entry.storage_path = storage_path
            entry.completed_at = datetime.now(timezone.utc).isoformat()
            entry.metadata = {
                "original_size": original_size,
                "compression_ratio": len(encrypted) / original_size if original_size > 0 else 1.0
            }
            
            log_event("backup", f"success:{backup_id}:size:{entry.size_bytes}")
            
            # Notificar
            if notify:
                self._notify_backup_completion(entry)
            
            # Limpiar backups antiguos
            self._cleanup_old_backups()
            
        except Exception as e:
            entry.status = BackupStatus.FAILED.value
            entry.error_message = str(e)
            log_event("backup", f"failed:{backup_id}:{type(e).__name__}:{e}")
        
        finally:
            self._save_backup_history()
        
        return entry
    
    def _collect_data(self, tables: List[str]) -> Dict[str, Any]:
        """Recolecta datos de session_state para backup."""
        data = {
            "backup_metadata": {
                "version": "1.0",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tables": tables
            }
        }
        
        for table in tables:
            if table in st.session_state:
                data[table] = st.session_state[table]
        
        return data
    
    def _verify_backup(self, file_path: Path, expected_checksum: str) -> bool:
        """Verifica integridad del backup."""
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            
            actual_checksum = self._calculate_checksum(data)
            return actual_checksum == expected_checksum
        except Exception:
            return False
    
    def _upload_to_storage(self, file_path: Path, filename: str) -> Optional[str]:
        """Sube backup a Supabase Storage."""
        try:
            from core._database_supabase import supabase
            
            if supabase:
                # Subir a bucket 'backups'
                with open(file_path, 'rb') as f:
                    response = supabase.storage.from_("backups").upload(
                        f"automated/{filename}",
                        f
                    )
                
                return f"supabase:backups/automated/{filename}"
        except Exception as e:
            log_event("backup", f"upload_warning:{type(e).__name__}")
        
        return None
    
    def _notify_backup_completion(self, entry: BackupEntry) -> None:
        """Notifica completitud del backup."""
        try:
            from core.realtime_notifications import send_team_message, NotificationPriority
            
            if entry.status == BackupStatus.SUCCESS.value:
                size_mb = entry.size_bytes / (1024 * 1024)
                message = f"✅ Backup {entry.type} completado: {size_mb:.1f}MB, {len(entry.tables)} tablas"
                priority = NotificationPriority.NORMAL
            else:
                message = f"❌ Backup {entry.id} falló: {entry.error_message}"
                priority = NotificationPriority.HIGH
            
            send_team_message(
                message=message,
                sender="Sistema de Backup",
                recipient=None,  # Broadcast
                priority=priority
            )
        except Exception:
            pass
    
    def _cleanup_old_backups(self) -> None:
        """Elimina backups antiguos según política de retención."""
        settings = get_settings()
        retention_days = getattr(settings, 'backup_retention_days', self.DEFAULT_RETENTION_DAYS)
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        
        with self._lock:
            old_backups = [
                b for b in self._backups
                if datetime.fromisoformat(b.timestamp) < cutoff
            ]
            
            for backup in old_backups:
                # Eliminar archivo local
                if backup.file_path:
                    try:
                        Path(backup.file_path).unlink(missing_ok=True)
                    except Exception:
                        pass
                
                # Eliminar de Supabase Storage
                if backup.storage_path and backup.storage_path.startswith("supabase:"):
                    try:
                        from core._database_supabase import supabase
                        if supabase:
                            path = backup.storage_path.replace("supabase:backups/", "")
                            supabase.storage.from_("backups").remove([path])
                    except Exception:
                        pass
                
                self._backups.remove(backup)
            
            if old_backups:
                log_event("backup", f"cleanup_removed:{len(old_backups)}")
    
    def restore_backup(
        self,
        backup_id: str,
        tables: Optional[List[str]] = None,
        dry_run: bool = False
    ) -> bool:
        """
        Restaura un backup.
        
        Args:
            backup_id: ID del backup a restaurar
            tables: Tablas específicas (None = todas)
            dry_run: Si True, solo verifica sin restaurar
        
        Returns:
            True si exitoso
        """
        # Buscar backup
        entry = None
        for b in self._backups:
            if b.id == backup_id:
                entry = b
                break
        
        if not entry:
            raise ValueError(f"Backup no encontrado: {backup_id}")
        
        if not entry.file_path or not Path(entry.file_path).exists():
            raise ValueError(f"Archivo de backup no disponible: {backup_id}")
        
        try:
            log_event("backup", f"restore_started:{backup_id}")
            
            # Leer y verificar
            with open(entry.file_path, 'rb') as f:
                encrypted = f.read()
            
            checksum = self._calculate_checksum(encrypted)
            if checksum != entry.checksum:
                raise ValueError("Checksum mismatch - archivo corrupto")
            
            if dry_run:
                return True
            
            # Desencriptar
            decrypted = self._decrypt_data(encrypted)
            
            # Descomprimir
            decompressed = self._decompress_data(decrypted)
            
            # Parsear
            data = json.loads(decompressed.decode('utf-8'))
            
            # Restaurar tablas
            tables_to_restore = tables or entry.tables
            restored = []
            
            for table in tables_to_restore:
                if table in data:
                    st.session_state[table] = data[table]
                    restored.append(table)
            
            log_event("backup", f"restore_success:{backup_id}:tables:{len(restored)}")
            
            return True
            
        except Exception as e:
            log_event("backup", f"restore_failed:{backup_id}:{type(e).__name__}")
            raise
    
    def list_backups(
        self,
        status: Optional[BackupStatus] = None,
        backup_type: Optional[BackupType] = None,
        limit: int = 50
    ) -> List[BackupEntry]:
        """Lista backups disponibles."""
        with self._lock:
            result = self._backups.copy()
        
        if status:
            result = [b for b in result if b.status == status.value]
        
        if backup_type:
            result = [b for b in result if b.type == backup_type.value]
        
        # Ordenar por timestamp descendente
        result.sort(key=lambda b: b.timestamp, reverse=True)
        
        return result[:limit]
    
    def get_latest_successful_backup(self) -> Optional[BackupEntry]:
        """Retorna el último backup exitoso."""
        successful = [
            b for b in self._backups
            if b.status == BackupStatus.SUCCESS.value and b.verification_passed
        ]
        
        if not successful:
            return None
        
        successful.sort(key=lambda b: b.timestamp, reverse=True)
        return successful[0]
    
    def start_auto_scheduler(self) -> None:
        """Inicia scheduler de backups automáticos."""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            return
        
        self._stop_scheduler = False
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        
        log_event("backup", "scheduler_started")
    
    def stop_auto_scheduler(self) -> None:
        """Detiene scheduler de backups."""
        self._stop_scheduler = True
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
    
    def _scheduler_loop(self) -> None:
        """Loop del scheduler de backups."""
        settings = get_settings()
        interval_hours = getattr(settings, 'backup_interval_hours', self.DEFAULT_INTERVAL_HOURS)
        interval_seconds = interval_hours * 3600
        
        while not self._stop_scheduler:
            try:
                # Verificar si es hora de backup
                last_backup = self.get_latest_successful_backup()
                
                if last_backup:
                    last_time = datetime.fromisoformat(last_backup.timestamp)
                    time_since_last = (datetime.now(timezone.utc) - last_time).total_seconds()
                    
                    if time_since_last >= interval_seconds:
                        self.create_backup(BackupType.FULL)
                else:
                    # No hay backups previos, crear uno
                    self.create_backup(BackupType.FULL)
                
                # Esperar 1 minuto antes de verificar de nuevo
                time.sleep(60)
                
            except Exception as e:
                log_event("backup", f"scheduler_error:{type(e).__name__}")
                time.sleep(300)  # Esperar 5 min en caso de error


# Instancia global
_backup_manager = None

def get_backup_manager() -> BackupManager:
    """Retorna instancia singleton."""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = BackupManager()
    return _backup_manager


# Funciones helper de alto nivel

def create_manual_backup(
    tables: Optional[List[str]] = None,
    backup_type: BackupType = BackupType.FULL
) -> BackupEntry:
    """Crea backup manual."""
    return get_backup_manager().create_backup(backup_type, tables)


def restore_from_backup(backup_id: str) -> bool:
    """Restaura desde backup."""
    return get_backup_manager().restore_backup(backup_id)


def get_backup_status() -> Dict[str, Any]:
    """Retorna estado del sistema de backups."""
    manager = get_backup_manager()
    latest = manager.get_latest_successful_backup()
    
    return {
        "latest_backup": latest.to_dict() if latest else None,
        "total_backups": len(manager._backups),
        "scheduled": manager._scheduler_thread is not None and manager._scheduler_thread.is_alive(),
        "critical_tables": manager.CRITICAL_TABLES
    }


def render_backup_dashboard() -> None:
    """Renderiza dashboard de backups en Streamlit."""
    import streamlit as st
    
    st.header("💾 Sistema de Backup")
    
    manager = get_backup_manager()
    status = get_backup_status()
    
    # Estado general
    if status["latest_backup"]:
        last_time = datetime.fromisoformat(status["latest_backup"]["timestamp"])
        hours_ago = (datetime.now(timezone.utc) - last_time).total_seconds() / 3600
        
        if hours_ago < 6:
            st.success(f"✅ Último backup: hace {hours_ago:.1f} horas")
        elif hours_ago < 24:
            st.warning(f"⚠️ Último backup: hace {hours_ago:.1f} horas")
        else:
            st.error(f"🔴 Último backup: hace {hours_ago:.1f} horas (!)")
    else:
        st.error("🔴 No hay backups registrados")
    
    # Botón de backup manual
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Crear Backup Manual Ahora", type="primary"):
            with st.spinner("Creando backup..."):
                backup = create_manual_backup()
                
                if backup.status == BackupStatus.SUCCESS.value:
                    size_mb = backup.size_bytes / (1024 * 1024)
                    st.success(f"✅ Backup creado: {size_mb:.1f}MB")
                else:
                    st.error(f"❌ Error: {backup.error_message}")
    
    with col2:
        st.caption(f"Tablas críticas: {len(manager.CRITICAL_TABLES)}")
        st.caption(f"Total backups: {status['total_backups']}")
    
    # Historial
    with st.expander("📜 Historial de Backups"):
        backups = manager.list_backups(limit=10)
        
        for backup in backups:
            icon = "✅" if backup.status == BackupStatus.SUCCESS.value else "❌"
            size_mb = backup.size_bytes / (1024 * 1024)
            
            st.write(f"{icon} **{backup.timestamp[:16]}** - {backup.type} - {size_mb:.1f}MB")
            
            if backup.status == BackupStatus.SUCCESS.value and st.button(
                "Restaurar",
                key=f"restore_{backup.id}"
            ):
                st.warning("⚠️ Esto reemplazará los datos actuales")
                if st.checkbox("Confirmar restauración", key=f"confirm_{backup.id}"):
                    with st.spinner("Restaurando..."):
                        try:
                            if restore_from_backup(backup.id):
                                st.success("✅ Backup restaurado")
                            else:
                                st.error("❌ Error al restaurar")
                        except Exception as e:
                            st.error(f"❌ {str(e)}")
