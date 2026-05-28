"""Tests para core.rate_limiter_distributed."""
from __future__ import annotations

import pytest


class TestRateLimiterDistributed:
    """Tests para funciones públicas de core.rate_limiter_distributed."""

    def test_rate_limiter_distributed_importable(self):
        import core.rate_limiter_distributed
        assert core.rate_limiter_distributed is not None

    def test_functions_exist(self):
        import core.rate_limiter_distributed
        assert callable(core.rate_limiter_distributed.get_rate_limiter)
        assert callable(core.rate_limiter_distributed.rate_limit)
        assert callable(core.rate_limiter_distributed.check_login_rate_limit)
        assert callable(core.rate_limiter_distributed.check_api_rate_limit)
        assert callable(core.rate_limiter_distributed.reset_login_attempts)
        assert callable(core.rate_limiter_distributed.check_rate_limit)
        assert callable(core.rate_limiter_distributed.reset_limit)
        assert callable(core.rate_limiter_distributed.decorator)
        assert callable(core.rate_limiter_distributed.wrapper)
