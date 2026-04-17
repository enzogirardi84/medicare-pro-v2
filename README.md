# MediCare Enterprise PRO (NextGen Architecture)

[![Pytest](https://github.com/enzogirardi84/medicare-pro-v2/actions/workflows/pytest.yml/badge.svg?branch=main)](https://github.com/enzogirardi84/medicare-pro-v2/actions/workflows/pytest.yml)

Sistema de gestión clínica y domiciliaria. Ahora potenciado con una **arquitectura distribuida (NextGen)** capaz de soportar **millones de usuarios** mediante FastAPI, Celery, Redis y PostgreSQL.

## Arquitectura NextGen

- **Frontend (Streamlit):** Interfaz rápida y optimizada con caché avanzado.
- **Backend API (FastAPI):** Motor asíncrono para validaciones, idempotencia y guardado en milisegundos (`/nextgen_platform/apps/api`).
- **Workers (Celery):** Procesamiento en segundo plano de PDFs pesados y notificaciones de WhatsApp (`/nextgen_platform/apps/worker`).
- **Base de Datos (PostgreSQL):** Esquemas preparados para Sharding y RLS (Row Level Security) por clínica.

## Módulos principales

- Admision y pacientes
- Clinica, evolucion y signos vitales (plan de enfermeria integrado en Evolucion)
- Recetas con firma y trazabilidad legal
- Estudios y adjuntos
- Emergencias y ambulancia
- Escalas clinicas
- PDF, consentimientos y respaldo clinico
- RRHH, fichajes y auditoria

## Requisitos

Instalar dependencias:

```bash
pip install -r requirements.txt
```

### Desarrollo y tests (opcional)

Para ejecutar la suite de pruebas en local o alinear con GitHub Actions:

```bash
pip install -r requirements-dev.txt
pytest
```

Opciones de pytest: `pyproject.toml` → `[tool.pytest.ini_options]`.

En produccion (Streamlit Cloud, Render) solo se usa `requirements.txt`.

El archivo `.python-version` y `runtime.txt` indican Python 3.12.x para entornos locales y Render.

## Ejecucion local

```bash
streamlit run main.py
```

## Deploy con dominio propio

La app tambien queda preparada para desplegarse en Render con dominio personalizado.

Archivos incluidos:

- `render.yaml`
- `runtime.txt`

Comando de arranque configurado:

```bash
streamlit run main.py --server.port $PORT --server.address 0.0.0.0
```

La guia paso a paso para Render + Donweb esta en:

- `DEPLOY_GUIDE.md`

## Configuracion

Si se quiere usar Supabase, crear:

`.streamlit/secrets.toml`

con variables como:

```toml
SUPABASE_URL="https://TU-PROYECTO.supabase.co"
SUPABASE_KEY="TU_KEY"
# URL publica HTTPS sin barra final (SEO, canonical, redireccion apex→www)
SITE_URL="https://www.tu-dominio.com"

# (Opcional) Contraseña de emergencia para logins superadmin (admin, enzogirardi)
# Permite acceso de recuperacion cuando el hash en base no coincide.
# Debe configurarse en produccion para habilitar el login de emergencia.
SUPERADMIN_EMERGENCY_PASSWORD="tu-password-segura-aqui"

# (Opcional) Logins adicionales con acceso de emergencia
SUPERADMIN_EMERGENCY_LOGINS_EXTRA=["backup_admin", "soporte"]
```

Si Supabase no esta configurado, la app funciona en modo local.

**Seguridad:** La contraseña de emergencia debe configurarse en `secrets.toml`.
Sin esta configuracion, el login de emergencia estara deshabilitado.

## Datos locales

Los datos locales no se versionan. Se guardan en:

- `.streamlit/local_data.json`
- `.streamlit/data_store/`

## Escalabilidad (Millones de Usuarios)

El sistema incluye componentes avanzados para escalar a millones de usuarios:

### Componentes de Escalabilidad

#### 1. Connection Pool (`core/connection_pool.py`)
- Pool de conexiones por tenant (aislamiento multiclínica)
- Circuit breaker para prevenir fallos en cascada
- Retry con exponential backoff
- Configuración: `POOL_MAX_PER_TENANT`, `POOL_MAX_TOTAL`, `CIRCUIT_FAILURE_THRESHOLD`

#### 2. Cache Manager (`core/cache_manager.py`)
- Caché multi-nivel (L1: memoria, L2: session_state)
- TTL automático y evicción LRU
- Invalidación selectiva por patrones
- Decorador `@cached` para funciones

#### 3. Rate Limiter (`core/rate_limiter.py`)
- Límites por usuario, IP, tenant y endpoint
- Ventana deslizante precisa
- Penalización progresiva (warning → throttle → block → ban)
- Protección contra abuso

#### 4. Paginación (`core/pagination.py`)
- Cursor-based pagination (O(1) para cualquier página)
- Lazy loading virtualizado
- Prefetching predictivo
- Búsqueda integrada con filtros

#### 5. Batch Processor (`core/batch_processor.py`)
- Procesamiento por chunks
- Checkpointing para reanudación
- Dead letter queue
- Paralelización controlada

#### 6. Health Monitor (`core/health_monitor.py`)
- Health checks periódicos
- Métricas agregadas
- Alertas automáticas por umbrales
- Dashboard de estado

#### 7. Data Validator (`core/data_validator.py`)
- Validación de tipos y rangos
- Sanitización de entrada
- Schemas predefinidos (paciente, usuario)
- Mensajes de error específicos

#### 8. Query Optimizer (`core/query_optimizer.py`)
- Índices en memoria O(1)
- Filtro Bloom para membership testing
- Búsqueda binaria para listas ordenadas
- Compresión de datos grandes

#### 9. UI Optimizer (`core/ui_optimizer.py`)
- Virtualización de listas grandes
- Debouncing de inputs
- Throttling de eventos
- Lazy loading de componentes
- Paginación de DataFrames

### Configuración en secrets.toml

```toml
# Connection Pool
POOL_MAX_PER_TENANT = 20
POOL_MAX_TOTAL = 500
POOL_TIMEOUT = 5.0
POOL_IDLE_TIMEOUT = 300.0
CIRCUIT_FAILURE_THRESHOLD = 5
CIRCUIT_RECOVERY_TIMEOUT = 30.0

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE = 100
RATE_LIMIT_BURST = 10
RATE_LIMIT_BLOCK_DURATION = 300

# Cache
CACHE_TTL_SECONDS = 60
CACHE_MAX_L1 = 100
CACHE_MAX_L2 = 1000
```

## Nota

Este proyecto esta preparado para compararse con una version anterior sin reemplazarla.
