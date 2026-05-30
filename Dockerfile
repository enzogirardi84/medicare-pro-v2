# =============================================================================
# Dockerfile - MediCare Enterprise PRO
# Multi-stage build: imagen final liviana para produccion
# Basado en python:3.12-slim para minimizar superficie de ataque
# =============================================================================

# ── Etapa 1: Dependencias ────────────────────────────────────────
FROM python:3.12-slim AS builder

# Variables de entorno para compilacion
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dependencias del sistema para compilar ReportLab, bcrypt, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cache de pip: copiar solo requirements primero
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ── Etapa 2: Imagen final ───────────────────────────────────────
FROM python:3.12-slim AS runner

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_PORT=8501 \
    TZ=America/Argentina/Buenos_Aires

# Dependencias runtime minimas (ReportLab, SQLite, crypto)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfontconfig1 \
    fonts-dejavu-core \
    fonts-liberation \
    sqlite3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar wheels desde builder
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Copiar codigo fuente
COPY . .

# Crear directorios de datos con permisos seguros
RUN mkdir -p /data/audit_logs /data/estudios /data/backups \
    && chmod 755 /data \
    && chmod 444 /data/audit_logs \
    && chmod 755 /data/estudios /data/backups \
    && ln -sf /data/audit_logs .audit_logs \
    && ln -sf /data/estudios storage/estudios \
    && ln -sf /data/backups backups

# Usuario no-root para seguridad
RUN groupadd -r medicare && useradd -r -g medicare -d /app -s /sbin/nologin medicare
RUN chown -R medicare:medicare /app /data
USER medicare

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/healthz', timeout=5)" || exit 1

EXPOSE 8501

CMD ["streamlit", "run", "main.py", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false", \
     "--server.maxUploadSize=20"]
