from __future__ import annotations

from core.backup_automated import (
    BackupStatus,
    BackupType,
    BackupEntry,
    BackupManager,
    get_backup_manager,
    get_backup_status,
    create_manual_backup,
)


def test_backup_status_enum_values():
    assert BackupStatus.PENDING.value == "pending"
    assert BackupStatus.RUNNING.value == "running"
    assert BackupStatus.SUCCESS.value == "success"
    assert BackupStatus.FAILED.value == "failed"
    assert BackupStatus.VERIFYING.value == "verifying"


def test_backup_type_enum_values():
    assert BackupType.FULL.value == "full"
    assert BackupType.INCREMENTAL.value == "incremental"
    assert BackupType.TABLE_SPECIFIC.value == "table"


def test_backup_entry_dataclass():
    entry = BackupEntry(
        id="b1",
        timestamp="2024-01-01T00:00:00",
        status=BackupStatus.SUCCESS.value,
        type=BackupType.FULL.value,
        tables=["pacientes"],
        size_bytes=1024,
        checksum="abc123",
        compressed=True,
        encrypted=True,
        file_path="/tmp/backup.enc",
        storage_path=None,
    )
    assert entry.id == "b1"
    assert entry.status == "success"
    assert entry.type == "full"
    assert entry.metadata == {}


def test_backup_manager_constructs():
    mgr = BackupManager()
    assert mgr._backups is not None
    assert mgr.BACKUP_DIR == ".backups"
    assert len(mgr.CRITICAL_TABLES) > 0


def test_get_backup_manager_returns_singleton():
    m1 = get_backup_manager()
    m2 = get_backup_manager()
    assert m1 is m2


def test_get_backup_status_returns_dict():
    result = get_backup_status()
    assert isinstance(result, dict)
    assert "total_backups" in result
    assert "critical_tables" in result


def test_create_manual_backup_is_callable():
    assert callable(create_manual_backup)
