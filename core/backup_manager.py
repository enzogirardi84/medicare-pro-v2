"""
Sistema de Backup Automatizado para Medicare Pro.

Características:
- Backup programado (diario/semanal/mensual)
- Múltiples destinos (local, cloud, SFTP)
- Compresión y encriptación
- Retención automática (política de limpieza)
- Verificación de integridad
- Notificaciones de éxito/fracaso
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tarfile
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from enum import Enum, auto

from core.app_logging import log_event
from core.audit_trail import audit_log, AuditEventType


class BackupType(Enum):
    """Tipos de backup."""
    FULL = auto()      # Completo
    INCREMENTAL = auto()  # Solo cambios desde último backup
    DIFFERENTIAL = auto() # Cambios desde último full


class BackupDestination(Enum):
    """Destinos de backup."""
    LOCAL = auto()
    SFTP = auto()
    S3 = auto()
    GCS = auto()  # Google Cloud Storage
    AZURE = auto()


@dataclass
class BackupConfig:
    """Configuración de backup."""
    name: str
    backup_type: BackupType
    destination: BackupDestination
    schedule: str  # cron format: "0 2 * * *" (daily at 2am)
    retention_days: int = 30
    compress: bool = True
    encrypt: bool = False
    encrypt_password: Optional[str] = None
    include_databases: List[str] = None
    include_files: List[str] = None
    exclude_patterns: List[str] = None
    enabled: bool = True


@dataclass
class BackupJob:
    """Job de backup individual."""
    id: str
    config_name: str
    status: str  # pending, running, completed, failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    size_bytes: int = 0
    checksum: Optional[str] = None
    error_message: Optional[str] = None
    file_path: Optional[str] = None


class BackupManager:
    """
    Manager central de backups.
    
    Gestiona:
    - Configuración de backups
    - Ejecución programada
    - Retención y limpieza
    - Verificación de integridad
    """
    
    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        
        self._configs: Dict[str, BackupConfig] = {}
        self._jobs: List[BackupJob] = []
        
        self._load_configs()
    
    def _load_configs(self):
        """Carga configuraciones desde archivo."""
        config_file = self.backup_dir / "backup_configs.json"
        
        if config_file.exists():
            try:
                with open(config_file) as f:
                    data = json.load(f)
                
                for name, cfg in data.items():
                    self._configs[name] = BackupConfig(
                        name=cfg["name"],
                        backup_type=BackupType[cfg["backup_type"]],
                        destination=BackupDestination[cfg["destination"]],
                        schedule=cfg["schedule"],
                        retention_days=cfg.get("retention_days", 30),
                        compress=cfg.get("compress", True),
                        encrypt=cfg.get("encrypt", False),
                        encrypt_password=cfg.get("encrypt_password"),
                        include_databases=cfg.get("include_databases", []),
                        include_files=cfg.get("include_files", []),
                        exclude_patterns=cfg.get("exclude_patterns", []),
                        enabled=cfg.get("enabled", True)
                    )
            except Exception as e:
                log_event("backup_error", f"Failed to load configs: {e}")
    
    def _save_configs(self):
        """Guarda configuraciones a archivo."""
        config_file = self.backup_dir / "backup_configs.json"
        
        data = {
            name: {
                **asdict(config),
                "backup_type": config.backup_type.name,
                "destination": config.destination.name
            }
            for name, config in self._configs.items()
        }
        
        with open(config_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add_config(self, config: BackupConfig) -> bool:
        """
        Agrega configuración de backup.
        
        Args:
            config: Configuración a agregar
        
        Returns:
            True si se agregó exitosamente
        """
        if config.name in self._configs:
            log_event("backup", f"Config '{config.name}' already exists, updating")
        
        self._configs[config.name] = config
        self._save_configs()
        
        log_event("backup", f"Config '{config.name}' added")
        return True
    
    def remove_config(self, name: str) -> bool:
        """Elimina configuración de backup."""
        if name not in self._configs:
            return False
        
        del self._configs[name]
        self._save_configs()
        
        log_event("backup", f"Config '{name}' removed")
        return True
    
    def list_configs(self) -> List[BackupConfig]:
        """Lista todas las configuraciones."""
        return list(self._configs.values())
    
    def execute_backup(self, config_name: str) -> BackupJob:
        """
        Ejecuta backup según configuración.
        
        Args:
            config_name: Nombre de la configuración
        
        Returns:
            BackupJob con resultado
        """
        import uuid
        
        if config_name not in self._configs:
            raise ValueError(f"Config '{config_name}' not found")
        
        config = self._configs[config_name]
        
        # Crear job
        job = BackupJob(
            id=str(uuid.uuid4()),
            config_name=config_name,
            status="running",
            started_at=datetime.now()
        )
        
        self._jobs.append(job)
        
        try:
            # Crear directorio temporal
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{config_name}_{timestamp}"
            temp_dir = self.backup_dir / "temp" / backup_name
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # 1. Backup de bases de datos
            if config.include_databases:
                self._backup_databases(config.include_databases, temp_dir / "databases")
            
            # 2. Backup de archivos
            if config.include_files:
                self._backup_files(config.include_files, temp_dir / "files", config.exclude_patterns)
            
            # 3. Crear manifest
            manifest = {
                "backup_name": backup_name,
                "created_at": datetime.now().isoformat(),
                "config": asdict(config),
                "databases": config.include_databases or [],
                "files": config.include_files or [],
            }
            
            with open(temp_dir / "manifest.json", 'w') as f:
                json.dump(manifest, f, indent=2)
            
            # 4. Comprimir
            final_path = self.backup_dir / f"{backup_name}.tar.gz"
            
            with tarfile.open(final_path, "w:gz") as tar:
                tar.add(temp_dir, arcname=backup_name)
            
            # 5. Encriptar si es necesario
            if config.encrypt and config.encrypt_password:
                final_path = self._encrypt_file(final_path, config.encrypt_password)
            
            # 6. Calcular checksum
            checksum = self._calculate_checksum(final_path)
            
            # 7. Copiar a destino
            if config.destination != BackupDestination.LOCAL:
                self._upload_to_destination(final_path, config.destination)
            
            # 8. Limpiar temp
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            # Actualizar job
            job.status = "completed"
            job.completed_at = datetime.now()
            job.size_bytes = final_path.stat().st_size
            job.checksum = checksum
            job.file_path = str(final_path)
            
            # Audit log
            audit_log(
                AuditEventType.DATA_BACKUP,
                resource_type="backup",
                resource_id=job.id,
                action="CREATE",
                description=f"Backup completed: {backup_name} ({job.size_bytes} bytes)",
                metadata={"config": config_name, "size": job.size_bytes}
            )
            
            log_event("backup", f"Backup '{backup_name}' completed successfully")
            
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now()
            
            log_event("backup_error", f"Backup '{config_name}' failed: {e}")
        
        return job
    
    def _backup_databases(self, databases: List[str], dest_dir: Path):
        """Backup de bases de datos."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        for db_name in databases:
            if db_name == "supabase":
                # Backup de Supabase (usando pg_dump o API)
                self._backup_supabase(dest_dir / "supabase_backup.sql")
            elif db_name == "local":
                # Backup de SQLite local
                self._backup_sqlite(dest_dir / "local_backup.db")
            elif db_name == "session_state":
                # Backup de session_state de Streamlit
                self._backup_session_state(dest_dir / "session_state.json")
    
    def _backup_supabase(self, dest_file: Path):
        """Backup de Supabase usando pg_dump de forma segura (sin exponer password)."""
        import subprocess
        import re
        
        db_url = os.getenv("DATABASE_URL", "")
        if not db_url:
            log_event("backup_error", "DATABASE_URL not set for Supabase backup")
            return
        
        # Parse DATABASE_URL para extraer componentes de forma segura
        # postgresql://user:pass@host:port/dbname
        try:
            match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(\w+)', db_url)
            if not match:
                log_event("backup_error", "Invalid DATABASE_URL format")
                return
            
            db_user, db_password, db_host, db_port, db_name = match.groups()
        except Exception as e:
            log_event("backup_error", f"Failed to parse DATABASE_URL: {e}")
            return
        
        try:
            # Copiamos el entorno actual para no afectarlo globalmente
            env = os.environ.copy()
            # Pasamos la contraseña de forma segura vía PGPASSWORD (no visible en ps)
            env["PGPASSWORD"] = db_password
            
            # Llamamos a pg_dump sin la contraseña en los argumentos visibles
            result = subprocess.run(
                [
                    "pg_dump", 
                    "-h", db_host, 
                    "-p", db_port,
                    "-U", db_user,
                    "-d", db_name,
                    "-Fc",  # Formato custom comprimido
                    "-f", str(dest_file)
                ],
                capture_output=True,
                text=True,
                timeout=300,
                env=env  # Entorno con PGPASSWORD
            )
            
            if result.returncode == 0:
                log_event("backup", "Supabase backup completed")
            else:
                log_event("backup_error", f"pg_dump failed: {result.stderr}")
                
        except FileNotFoundError:
            log_event("backup_error", "pg_dump not found, skipping Supabase backup")
        except Exception as e:
            log_event("backup_error", f"Supabase backup failed: {e}")
    
    def _backup_sqlite(self, dest_file: Path):
        """Backup de SQLite."""
        # Por ahora, solo copiar archivo si existe
        local_db = Path("local_data.db")
        if local_db.exists():
            shutil.copy2(local_db, dest_file)
            log_event("backup", "SQLite backup completed")
    
    def _backup_session_state(self, dest_file: Path):
        """Backup de session_state."""
        import streamlit as st
        
        # Exportar session_state relevante
        data_to_backup = {}
        keys_to_backup = [
            "usuarios_db", "pacientes_db", "evoluciones_db",
            "vitales_db", "recetas_db", "estudios_db"
        ]
        
        for key in keys_to_backup:
            if key in st.session_state:
                data_to_backup[key] = st.session_state[key]
        
        with open(dest_file, 'w') as f:
            json.dump(data_to_backup, f, indent=2, default=str)
        
        log_event("backup", "Session state backup completed")
    
    def _backup_files(self, paths: List[str], dest_dir: Path, exclude_patterns: Optional[List[str]] = None):
        """Backup de archivos."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        exclude_patterns = exclude_patterns or []
        
        for path_str in paths:
            source = Path(path_str)
            if not source.exists():
                continue
            
            if source.is_dir():
                # Copiar directorio
                dest_subdir = dest_dir / source.name
                shutil.copytree(
                    source, dest_subdir,
                    ignore=shutil.ignore_patterns(*exclude_patterns),
                    dirs_exist_ok=True
                )
            else:
                # Copiar archivo
                shutil.copy2(source, dest_dir)
        
        log_event("backup", f"Files backup completed: {len(paths)} sources")
    
    def _derive_fernet_key(self, password: str) -> bytes:
        """Deriva una clave Fernet válida (base64 URL-safe, 32 bytes) desde un password."""
        import base64
        raw = hashlib.sha256(password.encode()).digest()  # 32 bytes
        return base64.urlsafe_b64encode(raw)

    def _encrypt_file(self, file_path: Path, password: str) -> Path:
        """Encripta archivo usando Fernet (AES-256-CBC + HMAC)."""
        try:
            from cryptography.fernet import Fernet

            key = self._derive_fernet_key(password)
            f = Fernet(key)

            with open(file_path, 'rb') as file:
                data = file.read()

            encrypted = f.encrypt(data)

            enc_path = file_path.with_suffix(file_path.suffix + ".enc")
            with open(enc_path, 'wb') as file:
                file.write(encrypted)

            file_path.unlink()

            log_event("backup", f"File encrypted: {enc_path}")
            return enc_path

        except ImportError:
            log_event("backup_error", "cryptography not installed, skipping encryption")
            return file_path

    def _decrypt_file(self, file_path: Path, password: str) -> Path:
        """Desencripta archivo cifrado con _encrypt_file."""
        from cryptography.fernet import InvalidToken
        try:
            from cryptography.fernet import Fernet

            key = self._derive_fernet_key(password)
            f = Fernet(key)

            with open(file_path, 'rb') as file:
                encrypted = file.read()

            decrypted = f.decrypt(encrypted)

            dec_path = file_path.with_suffix('')  # remove .enc
            with open(dec_path, 'wb') as file:
                file.write(decrypted)

            file_path.unlink()

            log_event("backup", f"File decrypted: {dec_path}")
            return dec_path

        except ImportError:
            log_event("backup_error", "cryptography not installed, cannot decrypt")
            raise
        except InvalidToken:
            log_event("backup_error", "Invalid encryption password or corrupted file")
            raise
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calcula SHA256 checksum."""
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    def _upload_to_destination(self, file_path: Path, destination: BackupDestination):
        """Sube archivo a destino cloud."""
        if destination == BackupDestination.S3:
            self._upload_s3(file_path)
        elif destination == BackupDestination.SFTP:
            self._upload_sftp(file_path)
        # Implementar otros destinos según necesidad
    
    def _upload_s3(self, file_path: Path):
        """Sube a AWS S3."""
        try:
            import boto3
            
            s3 = boto3.client('s3')
            bucket = os.getenv("BACKUP_S3_BUCKET", "medicare-backups")
            
            s3.upload_file(
                str(file_path),
                bucket,
                f"backups/{file_path.name}"
            )
            
            log_event("backup", f"Uploaded to S3: {file_path.name}")
            
        except ImportError:
            log_event("backup_error", "boto3 not installed")
        except Exception as e:
            log_event("backup_error", f"S3 upload failed: {e}")
    
    def _upload_sftp(self, file_path: Path):
        """Sube vía SFTP."""
        log_event("backup", f"SFTP upload not implemented: {file_path.name}")
    
    def cleanup_old_backups(self, config_name: Optional[str] = None):
        """
        Limpia backups antiguos según política de retención.
        
        Args:
            config_name: Si especificado, solo limpia esa config
        """
        cutoff_date = datetime.now() - timedelta(days=30)  # Default
        
        for backup_file in self.backup_dir.glob("*.tar.gz*"):
            # Parsear fecha del nombre
            try:
                file_stat = backup_file.stat()
                file_mtime = datetime.fromtimestamp(file_stat.st_mtime)
                
                # Determinar retención según config
                for config in self._configs.values():
                    if backup_file.name.startswith(config.name):
                        cutoff_date = datetime.now() - timedelta(days=config.retention_days)
                        break
                
                if file_mtime < cutoff_date:
                    backup_file.unlink()
                    log_event("backup", f"Old backup removed: {backup_file.name}")
                    
            except Exception as e:
                log_event("backup_error", f"Cleanup error for {backup_file}: {e}")
    
    def verify_backup(self, job_id: str) -> bool:
        """
        Verifica integridad de un backup.
        
        Args:
            job_id: ID del job de backup
        
        Returns:
            True si el backup es válido
        """
        job = next((j for j in self._jobs if j.id == job_id), None)
        if not job or not job.file_path:
            return False
        
        file_path = Path(job.file_path)
        if not file_path.exists():
            return False
        
        # Recalcular checksum
        current_checksum = self._calculate_checksum(file_path)
        
        return current_checksum == job.checksum
    
    def restore_backup(self, job_id: str, target_dir: Optional[str] = None,
                       decrypt_password: Optional[str] = None) -> bool:
        """
        Restaura un backup.

        WARNING: Operación destructiva. Usar con precaución.

        Args:
            job_id: ID del backup a restaurar
            target_dir: Directorio destino (None = original)
            decrypt_password: Password para desencriptar (default: BACKUP_PASSWORD env)

        Returns:
            True si la restauración fue exitosa
        """
        job = next((j for j in self._jobs if j.id == job_id), None)
        if not job or not job.file_path:
            log_event("backup_error", f"Backup job {job_id} not found")
            return False

        if not self.verify_backup(job_id):
            log_event("backup_error", f"Backup {job_id} integrity check failed")
            return False

        restore_dir = None
        try:
            file_path = Path(job.file_path)

            # Desencriptar si el archivo termina en .enc
            if file_path.suffix == '.enc':
                password = decrypt_password or os.getenv("BACKUP_PASSWORD")
                if not password:
                    log_event("backup_error",
                              "Backup está encriptado pero no hay password "
                              "(pasar decrypt_password o variable BACKUP_PASSWORD)")
                    return False
                log_event("backup", f"Decrypting backup: {file_path.name}")
                file_path = self._decrypt_file(file_path, password)

            # Extraer tar.gz a directorio temporal
            backup_stem = file_path.stem  # e.g. "daily_full_20260425_020000"
            restore_dir = Path(target_dir) if target_dir else Path("restore_temp")
            restore_dir.mkdir(parents=True, exist_ok=True)
            extract_to = restore_dir / backup_stem

            if not extract_to.exists():
                with tarfile.open(file_path, "r:gz") as tar:
                    tar.extractall(restore_dir)

            # Leer manifest
            manifest_path = extract_to / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path) as f:
                    manifest = json.load(f)
            else:
                manifest = {"databases": [], "files": []}

            # Restaurar databases
            db_dir = extract_to / "databases"
            if db_dir.exists():
                self._restore_databases(manifest.get("databases", []), db_dir)

            # Restaurar archivos
            files_dir = extract_to / "files"
            if files_dir.exists():
                self._restore_files(manifest.get("files", []), files_dir)

            audit_log(
                AuditEventType.DATA_RESTORE,
                resource_type="backup",
                resource_id=job_id,
                action="RESTORE",
                description=f"Backup restored: {job_id}"
            )

            log_event("backup", f"Backup {job_id} restored successfully")
            return True

        except Exception as e:
            log_event("backup_error", f"Restore failed: {e}")
            return False
        finally:
            if restore_dir and restore_dir.exists():
                shutil.rmtree(restore_dir, ignore_errors=True)

    def _restore_databases(self, databases: List[str], db_dir: Path):
        """Restaura bases de datos desde un backup."""
        for db_name in databases:
            if db_name == "supabase":
                self._restore_supabase(db_dir / "supabase_backup.sql")
            elif db_name == "local":
                self._restore_sqlite(db_dir / "local_backup.db")
            elif db_name == "session_state":
                self._restore_session_state(db_dir / "session_state.json")

    def _restore_supabase(self, backup_file: Path):
        """Restaura Supabase usando pg_restore."""
        if not backup_file.exists():
            log_event("backup_error", "Supabase backup file not found for restore")
            return
        import re
        db_url = os.getenv("DATABASE_URL", "")
        if not db_url:
            log_event("backup_error", "DATABASE_URL not set for Supabase restore")
            return
        try:
            match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(\w+)', db_url)
            if not match:
                log_event("backup_error", "Invalid DATABASE_URL format")
                return
            db_user, db_password, db_host, db_port, db_name = match.groups()
        except Exception as e:
            log_event("backup_error", f"Failed to parse DATABASE_URL: {e}")
            return
        try:
            env = os.environ.copy()
            env["PGPASSWORD"] = db_password
            result = subprocess.run(
                [
                    "pg_restore",
                    "-h", db_host, "-p", db_port,
                    "-U", db_user,
                    "-d", db_name,
                    "--clean", "--if-exists",
                    str(backup_file)
                ],
                capture_output=True, text=True, timeout=600, env=env
            )
            if result.returncode == 0:
                log_event("backup", "Supabase restore completed")
            else:
                log_event("backup_error", f"pg_restore failed: {result.stderr[:500]}")
        except FileNotFoundError:
            log_event("backup_error", "pg_restore not found, skipping Supabase restore")
        except Exception as e:
            log_event("backup_error", f"Supabase restore failed: {e}")

    def _restore_sqlite(self, backup_file: Path):
        """Restaura base SQLite local desde backup."""
        if not backup_file.exists():
            log_event("backup_error", "SQLite backup file not found for restore")
            return
        try:
            local_db = Path("local_data.db")
            if local_db.exists():
                backup_path = local_db.with_suffix(local_db.suffix + ".before_restore")
                shutil.copy2(local_db, backup_path)
                log_event("backup", f"Current SQLite backed up to {backup_path}")
            shutil.copy2(backup_file, local_db)
            log_event("backup", "SQLite restore completed")
        except Exception as e:
            log_event("backup_error", f"SQLite restore failed: {e}")

    def _restore_session_state(self, backup_file: Path):
        """Restaura session_state de Streamlit desde backup JSON."""
        if not backup_file.exists():
            log_event("backup_error", "Session state backup file not found for restore")
            return
        try:
            import streamlit as st
            with open(backup_file) as f:
                data = json.load(f)
            for key, value in data.items():
                st.session_state[key] = value
            log_event("backup", f"Session state restore completed ({len(data)} keys)")
        except Exception as e:
            log_event("backup_error", f"Session state restore failed: {e}")

    def _restore_files(self, original_paths: List[str], files_dir: Path):
        """Restaura archivos desde backup a sus ubicaciones originales."""
        restored_count = 0
        for original_path_str in original_paths:
            original = Path(original_path_str)
            backup_item = files_dir / original.name
            if not backup_item.exists():
                log_event("backup_error", f"Backup file/dir not found: {backup_item}")
                continue
            try:
                if original.exists():
                    backup_orig = original.with_suffix(original.suffix + ".before_restore")
                    if not backup_orig.exists():
                        shutil.move(str(original), str(backup_orig))
                        log_event("backup", f"Current file backed up to {backup_orig}")
                    else:
                        shutil.rmtree(str(original), ignore_errors=True)
                if backup_item.is_dir():
                    shutil.copytree(backup_item, original, dirs_exist_ok=True)
                else:
                    original.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_item, original)
                restored_count += 1
                log_event("backup", f"Restored: {original}")
            except Exception as e:
                log_event("backup_error", f"Failed to restore {original}: {e}")
        log_event("backup", f"Files restore completed: {restored_count}/{len(original_paths)} items")
    
    def get_backup_list(self) -> List[Dict[str, Any]]:
        """Lista todos los backups disponibles."""
        backups = []
        
        for backup_file in sorted(self.backup_dir.glob("*.tar.gz*"), key=lambda p: p.stat().st_mtime, reverse=True):
            stat = backup_file.stat()
            backups.append({
                "filename": backup_file.name,
                "size_bytes": stat.st_size,
                "size_human": self._format_bytes(stat.st_size),
                "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "path": str(backup_file)
            })
        
        return backups
    
    def _format_bytes(self, size: int) -> str:
        """Formatea bytes a formato human readable."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    
    def schedule_backups(self):
        """Configura backups programados (requiere scheduler externo)."""
        log_event("backup", "Backup scheduling requires external scheduler (cron/systemd)")
        log_event("backup", "Example cron: 0 2 * * * /usr/bin/python -c 'from core.backup_manager import get_backup_manager; get_backup_manager().execute_backup(\"daily\")'")


# Singleton
_backup_manager: Optional[BackupManager] = None


def get_backup_manager() -> BackupManager:
    """Obtiene instancia del backup manager."""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = BackupManager()
    return _backup_manager


# Configuración por defecto
def setup_default_backups():
    """Configura backups por defecto."""
    manager = get_backup_manager()
    
    # Backup diario completo
    daily_config = BackupConfig(
        name="daily_full",
        backup_type=BackupType.FULL,
        destination=BackupDestination.LOCAL,
        schedule="0 2 * * *",  # 2 AM daily
        retention_days=7,
        compress=True,
        encrypt=False,
        include_databases=["local", "session_state"],
        include_files=["./assets", "./.streamlit"],
        exclude_patterns=["*.tmp", "*.cache", "__pycache__"]
    )
    
    manager.add_config(daily_config)
    
    # Backup semanal completo con encriptación
    weekly_config = BackupConfig(
        name="weekly_full",
        backup_type=BackupType.FULL,
        destination=BackupDestination.LOCAL,
        schedule="0 3 * * 0",  # 3 AM Sundays
        retention_days=30,
        compress=True,
        encrypt=True,
        encrypt_password=os.getenv("BACKUP_PASSWORD"),
        include_databases=["local", "session_state", "supabase"],
        include_files=["./assets", "./.streamlit", "./docs"]
    )
    
    manager.add_config(weekly_config)
    
    log_event("backup", "Default backup configurations created")
