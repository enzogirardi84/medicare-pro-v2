FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /worker

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY tasks.py .

RUN groupadd --system --gid 10002 nextgenworker \
    && useradd --system --uid 10002 --gid nextgenworker --home-dir /worker --no-create-home --shell /usr/sbin/nologin nextgenworker \
    && chown -R nextgenworker:nextgenworker /worker

USER nextgenworker

CMD ["celery", "-A", "tasks", "worker", "--loglevel=info"]
