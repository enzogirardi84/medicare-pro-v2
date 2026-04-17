"""
Core module - Sistema optimizado para millones de usuarios.

Nuevos componentes de escalabilidad:
- connection_pool: Pool de conexiones por tenant
- cache_manager: Caché multi-nivel L1/L2
- rate_limiter: Rate limiting con circuit breaker
- pagination: Paginación cursor-based y virtualizada
- batch_processor: Procesamiento batch con checkpointing
- health_monitor: Monitoreo y health checks

Uso:
    from core import get_cache_manager, get_connection_pool
    from core.cache_manager import cached
    from core.rate_limiter import check_rate_limit, LimitType
"""

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

__all__ = [
    # Cache
    "TieredCacheManager",
    "get_cache_manager",
    "cached",
    "invalidate_cache",
    # Connection Pool
    "TenantConnectionPool",
    "CircuitBreaker",
    "get_connection_pool",
    "execute_with_pool",
    # Rate Limiter
    "SlidingWindowRateLimiter",
    "LimitType",
    "PenaltyLevel",
    "get_sliding_limiter",
    "check_rate_limit",
    "get_client_identifier",
    # Pagination
    "CursorPaginator",
    "SearchablePaginator",
    "VirtualizedDataLoader",
    "get_cursor_paginator",
    # Batch Processing
    "BatchProcessor",
    "BatchJob",
    "BatchResult",
    "ProcessingStrategy",
    "get_batch_processor",
    # Health Monitor
    "HealthMonitor",
    "HealthCheck",
    "HealthStatus",
    "get_health_monitor",
    "quick_health_check",
    # Data Validator
    "DataValidator",
    "ValidationSchema",
    "ValidationResult",
    "ValidationSeverity",
    "get_validator",
    "validate_paciente",
    "validate_usuario",
    # Query Optimizer
    "QueryOptimizer",
    "BloomFilter",
    "InMemoryIndex",
    "BinarySearchHelper",
    "get_query_optimizer",
    # UI Optimizer
    "Debouncer",
    "Throttler",
    "VirtualListRenderer",
    "LazyComponentLoader",
    "get_debouncer",
    "get_throttler",
]
