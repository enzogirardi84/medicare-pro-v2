"""Tests para core.multi_region_balancer — Geo Read Replicas."""
from __future__ import annotations

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch


class TestRegionConfig:
    def test_region_config_defaults(self):
        from core.multi_region_balancer import RegionConfig
        cfg = RegionConfig(name="sa-east-1")
        assert cfg.name == "sa-east-1"
        assert cfg.priority == 100
        assert cfg.replicas == []
        assert cfg.max_lag_seconds == 5.0


class TestRegionHealth:
    def test_health_defaults(self):
        from core.multi_region_balancer import RegionHealth, RegionStatus
        h = RegionHealth()
        assert h.status == RegionStatus.HEALTHY
        assert h.lag_seconds == 0.0
        assert h.consecutive_failures == 0


class TestMultiRegionBalancer:
    def test_load_config_empty_uses_default(self):
        from core.multi_region_balancer import MultiRegionBalancer
        with patch.dict(os.environ, {"DB_URL": "postgresql://local:5432/mydb"}, clear=True):
            balancer = MultiRegionBalancer()
            assert "primary" in balancer._regions

    def test_load_config_from_env(self):
        config = {
            "sa-east-1": {
                "priority": 1,
                "replicas": ["postgresql://replica.sa:5432/db"],
                "coordinates": [-34.6, -58.4],
            },
            "us-east-1": {
                "priority": 2,
                "replicas": ["postgresql://replica.us:5432/db"],
                "coordinates": [40.7, -74.0],
            },
        }
        from core.multi_region_balancer import MultiRegionBalancer
        with patch.dict(os.environ, {"REGIONS_CONFIG": json.dumps(config)}, clear=True):
            balancer = MultiRegionBalancer()
            assert "sa-east-1" in balancer._regions
            assert "us-east-1" in balancer._regions
            assert balancer._regions["sa-east-1"].priority == 1

    def test_detect_client_region_by_header(self):
        from core.multi_region_balancer import MultiRegionBalancer, RegionConfig
        balancer = MultiRegionBalancer()
        balancer._regions["sa-east-1"] = RegionConfig(name="sa-east-1", priority=1)
        balancer._regions["us-east-1"] = RegionConfig(name="us-east-1", priority=2)
        region = balancer._detect_client_region(region_header="sa-east-1")
        assert region == "sa-east-1"

    def test_haversine_distance(self):
        from core.multi_region_balancer import MultiRegionBalancer
        # Buenos Aires a Santiago de Chile ~ 1100 km
        dist = MultiRegionBalancer._haversine(-34.6, -58.4, -33.4, -70.6)
        assert 1000 < dist < 1200

    def test_get_nearest_region(self):
        from core.multi_region_balancer import MultiRegionBalancer, RegionConfig
        balancer = MultiRegionBalancer()
        balancer._regions["sa"] = RegionConfig(name="sa", coordinates=[-34.0, -58.0])
        balancer._regions["us"] = RegionConfig(name="us", coordinates=[40.0, -74.0])
        nearest = balancer._get_nearest_region(-34.5, -58.3)
        assert nearest == "sa"

    def test_get_healthy_replicas_returns_list(self):
        from core.multi_region_balancer import MultiRegionBalancer, RegionConfig, RegionHealth, RegionStatus
        balancer = MultiRegionBalancer()
        balancer._regions["test"] = RegionConfig(name="test", replicas=["pg://r1:5432/db"])
        balancer._health["test"] = RegionHealth(status=RegionStatus.HEALTHY)
        replicas = asyncio.run(balancer._get_healthy_replicas("test"))
        assert len(replicas) == 1

    def test_get_healthy_replicas_down_region(self):
        from core.multi_region_balancer import MultiRegionBalancer, RegionConfig, RegionHealth, RegionStatus
        balancer = MultiRegionBalancer()
        balancer._regions["down"] = RegionConfig(name="down", replicas=["pg://r1:5432/db"])
        balancer._health["down"] = RegionHealth(status=RegionStatus.DOWN)
        replicas = asyncio.run(balancer._get_healthy_replicas("down"))
        assert replicas == []

    def test_region_stats(self):
        from core.multi_region_balancer import MultiRegionBalancer, RegionConfig, RegionHealth
        balancer = MultiRegionBalancer()
        balancer._regions["test"] = RegionConfig(name="test", priority=5, replicas=["pg://r1"])
        balancer._health["test"] = RegionHealth()
        stats = asyncio.run(balancer.get_region_stats())
        assert "test" in stats
        assert stats["test"]["priority"] == 5

    def test_random_weighted(self):
        from core.multi_region_balancer import random_weighted
        result = random_weighted(["a", "b", "c"])
        assert result in ("a", "b", "c")

    def test_get_read_replica_fallback_to_primary(self):
        from core.multi_region_balancer import MultiRegionBalancer
        balancer = MultiRegionBalancer()
        url = asyncio.run(balancer.get_read_replica())
        assert url is not None
        assert isinstance(url, str)

    def test_singleton(self):
        from core.multi_region_balancer import get_multi_region_balancer
        b1 = get_multi_region_balancer()
        b2 = get_multi_region_balancer()
        assert b1 is b2

    def test_health_loop_started(self):
        import asyncio
        from core.multi_region_balancer import MultiRegionBalancer

        async def run():
            balancer = MultiRegionBalancer()
            balancer.start_health_checks()
            assert balancer._health_task is not None
            balancer._health_task.cancel()
            return True

        result = asyncio.run(run())
        assert result is True
