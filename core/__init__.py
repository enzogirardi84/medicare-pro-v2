"""
Core package - Modular imports only, no circular deps.
Access submodules directly: ``from core.app_logging import log_event``
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.cache_manager import (
        TieredCacheManager,
        cached,
        get_cache_manager,
        invalidate_cache,
    )
    from core.connection_pool import (
        CircuitBreaker,
        TenantConnectionPool,
        execute_with_pool,
        get_connection_pool,
    )
    from core.rate_limiter import (
        LimitType,
        PenaltyLevel,
        SlidingWindowRateLimiter,
        check_rate_limit,
        get_client_identifier,
        get_sliding_limiter,
    )
    from core.pagination import (
        CursorPaginator,
        SearchablePaginator,
        VirtualizedDataLoader,
        get_cursor_paginator,
    )
    from core.batch_processor import (
        BatchJob,
        BatchProcessor,
        BatchResult,
        ProcessingStrategy,
        get_batch_processor,
    )
    from core.health_monitor import (
        HealthCheck,
        HealthMonitor,
        HealthStatus,
        get_health_monitor,
        quick_health_check,
    )
    from core.data_validator import (
        DataValidator,
        ValidationSchema,
        ValidationResult,
        ValidationSeverity,
        get_validator,
        validate_paciente,
        validate_usuario,
    )
    from core.query_optimizer import (
        QueryOptimizer,
        BloomFilter,
        InMemoryIndex,
        BinarySearchHelper,
        get_query_optimizer,
    )
    from core.ui_optimizer import (
        Debouncer,
        Throttler,
        VirtualListRenderer,
        LazyComponentLoader,
        get_debouncer,
        get_throttler,
    )


def __getattr__(name: str):
    """Lazy import: load from submodule only when accessed."""
    _LAZY_MAP: dict[str, str] = {
        "TieredCacheManager": "core.cache_manager",
        "cached": "core.cache_manager",
        "get_cache_manager": "core.cache_manager",
        "invalidate_cache": "core.cache_manager",
        "TenantConnectionPool": "core.connection_pool",
        "CircuitBreaker": "core.connection_pool",
        "get_connection_pool": "core.connection_pool",
        "execute_with_pool": "core.connection_pool",
        "SlidingWindowRateLimiter": "core.rate_limiter",
        "LimitType": "core.rate_limiter",
        "PenaltyLevel": "core.rate_limiter",
        "get_sliding_limiter": "core.rate_limiter",
        "check_rate_limit": "core.rate_limiter",
        "get_client_identifier": "core.rate_limiter",
        "CursorPaginator": "core.pagination",
        "SearchablePaginator": "core.pagination",
        "VirtualizedDataLoader": "core.pagination",
        "get_cursor_paginator": "core.pagination",
        "BatchProcessor": "core.batch_processor",
        "BatchJob": "core.batch_processor",
        "BatchResult": "core.batch_processor",
        "ProcessingStrategy": "core.batch_processor",
        "get_batch_processor": "core.batch_processor",
        "HealthMonitor": "core.health_monitor",
        "HealthCheck": "core.health_monitor",
        "HealthStatus": "core.health_monitor",
        "get_health_monitor": "core.health_monitor",
        "quick_health_check": "core.health_monitor",
        "DataValidator": "core.data_validator",
        "ValidationSchema": "core.data_validator",
        "ValidationResult": "core.data_validator",
        "ValidationSeverity": "core.data_validator",
        "get_validator": "core.data_validator",
        "validate_paciente": "core.data_validator",
        "validate_usuario": "core.data_validator",
        "QueryOptimizer": "core.query_optimizer",
        "BloomFilter": "core.query_optimizer",
        "InMemoryIndex": "core.query_optimizer",
        "BinarySearchHelper": "core.query_optimizer",
        "get_query_optimizer": "core.query_optimizer",
        "Debouncer": "core.ui_optimizer",
        "Throttler": "core.ui_optimizer",
        "VirtualListRenderer": "core.ui_optimizer",
        "LazyComponentLoader": "core.ui_optimizer",
        "get_debouncer": "core.ui_optimizer",
        "get_throttler": "core.ui_optimizer",
    }
    mod = _LAZY_MAP.get(name)
    if mod is None:
        raise AttributeError(f"module 'core' has no attribute {name!r}")
    return getattr(importlib.import_module(mod), name)


__all__ = [
    "TieredCacheManager", "get_cache_manager", "cached", "invalidate_cache",
    "TenantConnectionPool", "CircuitBreaker", "get_connection_pool", "execute_with_pool",
    "SlidingWindowRateLimiter", "LimitType", "PenaltyLevel",
    "get_sliding_limiter", "check_rate_limit", "get_client_identifier",
    "CursorPaginator", "SearchablePaginator", "VirtualizedDataLoader", "get_cursor_paginator",
    "BatchProcessor", "BatchJob", "BatchResult", "ProcessingStrategy", "get_batch_processor",
    "HealthMonitor", "HealthCheck", "HealthStatus", "get_health_monitor", "quick_health_check",
    "DataValidator", "ValidationSchema", "ValidationResult", "ValidationSeverity",
    "get_validator", "validate_paciente", "validate_usuario",
    "QueryOptimizer", "BloomFilter", "InMemoryIndex", "BinarySearchHelper", "get_query_optimizer",
    "Debouncer", "Throttler", "VirtualListRenderer", "LazyComponentLoader",
    "get_debouncer", "get_throttler",
]
