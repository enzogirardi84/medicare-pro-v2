FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

RUN groupadd --system --gid 10001 nextgenapi \
    && useradd --system --uid 10001 --gid nextgenapi --home-dir /app --no-create-home --shell /usr/sbin/nologin nextgenapi \
    && chown -R nextgenapi:nextgenapi /app

USER nextgenapi

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
