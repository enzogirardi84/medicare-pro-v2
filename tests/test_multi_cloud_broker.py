"""Tests para core.multi_cloud_broker — Multi-Cloud Storage Abstraction."""
from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestStorageProvider:
    def test_providers_exist(self):
        from core.multi_cloud_broker import StorageProvider
        assert StorageProvider.REDIS.value == "redis"
        assert StorageProvider.MEMORY.value == "memory"
        assert StorageProvider.POSTGRES.value == "postgres"


class TestProviderConfig:
    def test_config_defaults(self):
        from core.multi_cloud_broker import ProviderConfig, StorageProvider
        cfg = ProviderConfig(provider=StorageProvider.REDIS, connection_string="redis://localhost")
        assert cfg.priority == 100
        assert cfg.timeout == 5.0


class TestMultiCloudBroker:
    def test_configure_sets_primary(self):
        from core.multi_cloud_broker import MultiCloudBroker, ProviderConfig, StorageProvider
        broker = MultiCloudBroker()
        broker.configure([
            ProviderConfig(provider=StorageProvider.REDIS, priority=1, connection_string="redis://r1"),
            ProviderConfig(provider=StorageProvider.MEMORY, priority=2),
        ])
        assert broker._current_primary == StorageProvider.REDIS

    def test_set_get_memory(self):
        from core.multi_cloud_broker import MultiCloudBroker, ProviderConfig, StorageProvider
        broker = MultiCloudBroker()
        broker.configure([ProviderConfig(provider=StorageProvider.MEMORY, priority=1)])
        asyncio.run(broker.set("key1", {"data": "value1"}))
        result = asyncio.run(broker.get("key1"))
        assert result == {"data": "value1"}

    def test_get_nonexistent_key(self):
        from core.multi_cloud_broker import MultiCloudBroker
        broker = MultiCloudBroker()
        result = asyncio.run(broker.get("nonexistent"))
        assert result is None

    def test_delete_removes_key(self):
        from core.multi_cloud_broker import MultiCloudBroker, ProviderConfig, StorageProvider
        broker = MultiCloudBroker()
        broker.configure([ProviderConfig(provider=StorageProvider.MEMORY, priority=1)])
        asyncio.run(broker.set("k", "v"))
        asyncio.run(broker.delete("k"))
        assert asyncio.run(broker.get("k")) is None

    def test_health_check_all(self):
        from core.multi_cloud_broker import MultiCloudBroker, ProviderConfig, StorageProvider
        broker = MultiCloudBroker()
        broker.configure([ProviderConfig(provider=StorageProvider.MEMORY, priority=1)])
        health = broker.health_check_all()
        assert "memory" in health

    def test_fallback_to_second_provider(self):
        from core.multi_cloud_broker import MultiCloudBroker, ProviderConfig, StorageProvider
        broker = MultiCloudBroker()
        broker.configure([
            ProviderConfig(provider=StorageProvider.REDIS, priority=1, connection_string="redis://down"),
            ProviderConfig(provider=StorageProvider.MEMORY, priority=2),
        ])
        # El primario (REDIS) falla, debe conmutar a MEMORY
        broker._status[StorageProvider.REDIS] = provider_status = "DOWN"

        from core.multi_cloud_broker import ProviderStatus
        broker._status[StorageProvider.REDIS] = ProviderStatus.DOWN

        asyncio.run(broker.set("k", "v"))
        result = asyncio.run(broker.get("k"))
        assert result == "v"

    def test_broker_sql_contains_table(self):
        from core.multi_cloud_broker import BROKER_SQL
        assert "broker_store" in BROKER_SQL

    def test_persist_to_file(self):
        from core.multi_cloud_broker import MultiCloudBroker
        import tempfile
        broker = MultiCloudBroker()
        broker._local_file_path = tempfile.mktemp(suffix=".json")
        asyncio.run(broker.set("file_key", "file_value"))
        assert os.path.exists(broker._local_file_path)
        import json
        with open(broker._local_file_path) as f:
            data = json.load(f)
        assert data.get("file_key") == "file_value"
        os.unlink(broker._local_file_path)
