"""Tests para core.backup_manager."""
from __future__ import annotations

import pytest


class TestBackupManager:
    """Tests para funciones públicas de core.backup_manager."""

    def test_backup_manager_importable(self):
        import core.backup_manager
        assert core.backup_manager is not None

    def test_functions_exist(self):
        import core.backup_manager
        assert callable(core.backup_manager.get_backup_manager)
        assert callable(core.backup_manager.setup_default_backups)
        assert callable(core.backup_manager.add_config)
        assert callable(core.backup_manager.remove_config)
        assert callable(core.backup_manager.list_configs)
        assert callable(core.backup_manager.execute_backup)
        assert callable(core.backup_manager.cleanup_old_backups)
        assert callable(core.backup_manager.verify_backup)
        assert callable(core.backup_manager.restore_backup)
        assert callable(core.backup_manager.get_backup_list)
