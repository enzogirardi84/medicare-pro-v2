"""
Tests específicos para rate_limiter.py

EJECUTAR:
    python -m pytest tests/test_rate_limiter.py -v
"""

import pytest
import time
from datetime import datetime, timedelta


class TestRateLimiter:
    """Tests para RateLimiter"""
    
    def test_rate_limiter_creation(self):
        from core.rate_limiter import RateLimiter
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        
        assert limiter.max_requests == 10
        assert limiter.window_seconds == 60
    
    def test_allow_within_limit(self):
        from core.rate_limiter import RateLimiter
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        
        # 5 requests deben ser permitidos
        for i in range(5):
            assert limiter.allow(f"user_{i}") is True
    
    def test_deny_over_limit(self):
        from core.rate_limiter import RateLimiter
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        
        # 3 requests permitidos
        for _ in range(3):
            limiter.allow("user_1")
        
        # El cuarto debe ser denegado
        assert limiter.allow("user_1") is False
    
    def test_window_reset(self):
        from core.rate_limiter import RateLimiter
        limiter = RateLimiter(max_requests=2, window_seconds=0.1)
        
        # Usar el límite
        limiter.allow("user_1")
        limiter.allow("user_1")
        assert limiter.allow("user_1") is False
        
        # Esperar a que la ventana se resetee
        time.sleep(0.15)
        assert limiter.allow("user_1") is True
    
    def test_different_keys_independent(self):
        from core.rate_limiter import RateLimiter
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        
        # Usar límite para user_1
        limiter.allow("user_1")
        limiter.allow("user_1")
        assert limiter.allow("user_1") is False
        
        # user_2 tiene su propio contador
        assert limiter.allow("user_2") is True


class TestTokenBucket:
    """Tests para TokenBucket"""
    
    def test_bucket_creation(self):
        from core.rate_limiter import TokenBucket
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        
        assert bucket.capacity == 10
        assert bucket.tokens == 10  # Inicia lleno
    
    def test_consume_tokens(self):
        from core.rate_limiter import TokenBucket
        bucket = TokenBucket(capacity=5, refill_rate=10.0)
        
        # Consumir tokens
        assert bucket.consume(3) is True
        assert bucket.tokens == 2
        
        # Consumir más de lo disponible
        assert bucket.consume(5) is False
    
    def test_token_refill(self):
        from core.rate_limiter import TokenBucket
        bucket = TokenBucket(capacity=5, refill_rate=10.0)  # 10 tokens/segundo
        
        # Consumir todos los tokens
        bucket.consume(5)
        assert bucket.tokens == 0
        
        # Esperar refill
        time.sleep(0.3)  # ~3 tokens
        assert bucket.tokens >= 2


class TestSlidingWindow:
    """Tests para SlidingWindowRateLimiter"""
    
    def test_sliding_window_creation(self):
        from core.rate_limiter import SlidingWindowRateLimiter
        limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60)
        
        assert limiter.max_requests == 5
    
    def test_sliding_window_allow(self):
        from core.rate_limiter import SlidingWindowRateLimiter
        limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=1)
        
        assert limiter.allow("key") is True
        assert limiter.allow("key") is True
        assert limiter.allow("key") is False
        
        # Esperar a que expire el primer request
        time.sleep(1.1)
        assert limiter.allow("key") is True


class TestRateLimiterDecorator:
    """Tests para el decorador de rate limiting"""
    
    def test_decorator_blocks_when_limited(self):
        from core.rate_limiter import RateLimiter, rate_limit
        
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        
        @rate_limit(limiter=limiter, key_fn=lambda: "test_key")
        def limited_function():
            return "success"
        
        # Primera llamada debe funcionar
        assert limited_function() == "success"
        
        # Segunda debe lanzar RateLimitExceeded
        with pytest.raises(Exception):  # RateLimitExceeded
            limited_function()
