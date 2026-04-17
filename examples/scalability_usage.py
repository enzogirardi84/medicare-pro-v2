"""
Ejemplos de uso de los componentes de escalabilidad.

Este archivo demuestra cómo utilizar los nuevos componentes
para escalar Medicare Pro a millones de usuarios.
"""

# ============================================================================
# 1. CACHE MANAGER
# ============================================================================

from core.cache_manager import get_cache_manager, cached, invalidate_cache

def ejemplo_cache():
    cache = get_cache_manager()

    # Almacenar valor
    cache.set(
        prefix="pacientes",
        tenant_key="clinica_a",
        value=[{"id": 1, "nombre": "Juan"}],
        key_suffix="lista_activos",
        ttl_seconds=120,
    )

    # Recuperar valor
    hit, pacientes = cache.get(
        prefix="pacientes",
        tenant_key="clinica_a",
        key_suffix="lista_activos",
    )

    if hit:
        print(f"Cache hit: {len(pacientes)} pacientes")
    else:
        print("Cache miss")

    # Invalidar por tenant
    invalidate_cache(prefix="pacientes", tenant_key="clinica_a")

    # Ver estadísticas
    stats = cache.get_stats()
    print(f"Hit rate: {stats['hit_rate']:.1%}")


# Usar decorador
@cached(prefix="evoluciones", ttl_seconds=300)
def obtener_evoluciones(tenant_key, paciente_id, fecha_desde=None):
    """Esta función se cachea automáticamente."""
    # Consulta a base de datos
    return [{"id": 1, "nota": "Mejoría"}]


# ============================================================================
# 2. RATE LIMITER
# ============================================================================

from core.rate_limiter import (
    check_rate_limit,
    LimitType,
    get_sliding_limiter,
    get_client_identifier,
)

def ejemplo_rate_limit():
    user_id = "usuario_123"

    # Verificar límite
    allowed, metadata = check_rate_limit(
        limit_type=LimitType.PER_USER,
        identifier=user_id,
        endpoint="api/recetas",
        cost=1,
    )

    if not allowed:
        print(f"Rate limit exceeded. Retry after: {metadata['retry_after']}s")
        return False

    print(f"Requests remaining: {metadata['remaining']}")
    return True


def ejemplo_rate_limit_config():
    limiter = get_sliding_limiter()

    # Configurar límite personalizado
    from core.rate_limiter import RateLimitConfig

    limiter.set_config(
        limit_type=LimitType.PER_TENANT,
        identifier="clinica_premium",
        config=RateLimitConfig(
            requests_per_window=1000,
            window_seconds=60.0,
            burst_allowance=50,
        ),
    )


# ============================================================================
# 3. PAGINATION
# ============================================================================

from core.pagination import (
    get_cursor_paginator,
    get_searchable_paginator,
    VirtualizedDataLoader,
)

def ejemplo_cursor_pagination():
    # Simular lista grande
    pacientes = [
        {"id": i, "nombre": f"Paciente {i}"}
        for i in range(10000)
    ]

    paginator = get_cursor_paginator(page_size=50)

    # Primera página
    page1 = paginator.paginate(pacientes, cursor=None)
    print(f"Página 1: {len(page1.items)} items")
    print(f"Next cursor: {page1.next_cursor}")

    # Siguiente página
    if page1.next_cursor:
        page2 = paginator.paginate(pacientes, cursor=page1.next_cursor)
        print(f"Página 2: {len(page2.items)} items")


def ejemplo_virtualized_loading():
    # Función que carga datos desde DB
    def fetch_pacientes(offset, limit):
        # Simular consulta
        return [
            {"id": i, "nombre": f"Paciente {i}"}
            for i in range(offset, offset + limit)
        ]

    loader = VirtualizedDataLoader(
        fetch_callback=fetch_pacientes,
        page_size=100,
        prefetch_pages=2,
    )

    # Cargar 50 items desde el índice 1000
    items = loader.get_items("clinica_a", start_index=1000, count=50)
    print(f"Loaded {len(items)} items")


def ejemplo_searchable_pagination():
    pacientes = [
        {"id": 1, "nombre": "Juan Pérez", "dni": "12345678"},
        {"id": 2, "nombre": "María García", "dni": "87654321"},
        {"id": 3, "nombre": "Juan García", "dni": "11111111"},
    ]

    paginator = get_searchable_paginator(
        page_size=10,
        search_fields=["nombre", "dni"],
    )

    # Buscar y paginar
    result = paginator.search_and_paginate(
        items=pacientes,
        search_query="Juan",
        page=1,
        sort_field="nombre",
    )

    print(f"Encontrados: {result.total_count}")
    print(f"Items: {result.items}")


# ============================================================================
# 4. BATCH PROCESSOR
# ============================================================================

from core.batch_processor import (
    get_batch_processor,
    create_batch_job,
    ProcessingStrategy,
    BatchResult,
)

def ejemplo_batch_processing():
    processor = get_batch_processor()

    # Items a procesar
    pacientes = [{"id": i, "nombre": f"Paciente {i}"} for i in range(1000)]

    # Función de procesamiento
    def procesar_paciente(paciente):
        # Procesar paciente
        print(f"Procesando {paciente['nombre']}")
        return True

    # Crear job
    job = create_batch_job(
        name="Actualización masiva",
        items=pacientes,
        processor=procesar_paciente,
        strategy=ProcessingStrategy.CHUNKED,
        chunk_size=100,
        checkpoint_interval=500,
    )

    # Subir job
    job_id = processor.submit_job(job, tenant="clinica_a")

    # Ejecutar con progreso
    def on_progress(processed, total):
        print(f"Progreso: {processed}/{total}")

    result = processor.run_job(
        job_id=job_id,
        tenant="clinica_a",
        progress_callback=on_progress,
    )

    print(f"Completado: {result.success_count}/{result.processed_count}")
    print(f"Tasa de éxito: {result.success_rate:.1%}")


# ============================================================================
# 5. HEALTH MONITOR
# ============================================================================

from core.health_monitor import (
    get_health_monitor,
    HealthStatus,
    create_db_health_check,
    quick_health_check,
)

def ejemplo_health_monitor():
    monitor = get_health_monitor()

    # Crear health check para DB
    def check_db():
        # Verificar conexión
        return True  # o False

    db_check = create_db_health_check(check_db)
    monitor.register_check(db_check)

    # Configurar alertas
    monitor.set_alert_threshold(
        metric_name="response_time",
        threshold=500.0,  # ms
    )

    # Ejecutar checks
    results = monitor.run_all_checks()

    # Obtener estado general
    status, details = monitor.get_system_health()
    print(f"Estado: {status.value}")

    # Health check rápido
    status, message = quick_health_check()
    print(f"{message}")


# ============================================================================
# 6. CONNECTION POOL
# ============================================================================

from core.connection_pool import get_connection_pool, execute_with_pool

def ejemplo_connection_pool():
    pool = get_connection_pool(
        max_connections_per_tenant=20,
        max_total_connections=500,
    )

    # Usar conexión del pool
    tenant = "clinica_a"

    try:
        with pool.acquire(tenant, timeout=5.0) as conn:
            # Usar conexión
            print(f"Conexión adquirida: {conn}")
    except TimeoutError:
        print("Timeout esperando conexión")
    except ConnectionError:
        print("Circuit breaker abierto")

    # Métricas
    metrics = pool.get_metrics(tenant)
    print(f"Conexiones activas: {metrics['active']}")


# ============================================================================
# EJECUCIÓN
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Ejemplos de Escalabilidad - Medicare Pro")
    print("=" * 60)

    # Nota: Estos ejemplos requieren configuración previa
    # y algunos componentes de Streamlit (session_state)

    print("\n1. Cache Manager")
    print("-" * 40)
    try:
        ejemplo_cache()
    except Exception as e:
        print(f"Nota: {e}")

    print("\n2. Rate Limiter")
    print("-" * 40)
    try:
        ejemplo_rate_limit()
    except Exception as e:
        print(f"Nota: {e}")

    print("\n3. Pagination")
    print("-" * 40)
    ejemplo_cursor_pagination()

    print("\n4. Batch Processor")
    print("-" * 40)
    try:
        ejemplo_batch_processing()
    except Exception as e:
        print(f"Nota: {e}")

    print("\n5. Health Monitor")
    print("-" * 40)
    try:
        ejemplo_health_monitor()
    except Exception as e:
        print(f"Nota: {e}")

    print("\n" + "=" * 60)
    print("Ejemplos completados")
    print("=" * 60)
