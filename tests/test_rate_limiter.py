import pytest
import time

from core.rate_limiter import SlidingWindowRateLimiter, RateLimitConfig, LimitType


class TestSlidingWindow:

    def test_sliding_window_creation(self):
        config = RateLimitConfig(requests_per_window=5, window_seconds=60)
        limiter = SlidingWindowRateLimiter(default_config=config)

        assert limiter.default_config.requests_per_window == 5
        assert limiter.default_config.window_seconds == 60

    def test_sliding_window_allow(self):
        config = RateLimitConfig(requests_per_window=1, window_seconds=1, burst_allowance=1)
        limiter = SlidingWindowRateLimiter(default_config=config)

        allowed, _ = limiter.check_rate_limit(LimitType.PER_USER, "key")
        assert allowed is True
        allowed, _ = limiter.check_rate_limit(LimitType.PER_USER, "key")
        assert allowed is True
        allowed, _ = limiter.check_rate_limit(LimitType.PER_USER, "key")
        assert allowed is False

        time.sleep(1.1)
        allowed, _ = limiter.check_rate_limit(LimitType.PER_USER, "key")
        assert allowed is True
