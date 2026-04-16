import os
import time

from celery import Celery
from celery.result import AsyncResult

from app.core.config import settings
from app.infrastructure.metrics import imports_enqueued_total

redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
celery_client = Celery("nextgen_api_client", broker=redis_url, backend=redis_url)


def _priority_tenants() -> set[str]:
    raw = settings.import_priority_tenant_ids.strip()
    if not raw:
        return set()
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _import_priority_for_tenant(tenant_id: str) -> tuple[str, int]:
    if tenant_id.strip().lower() in _priority_tenants():
        return "high", max(settings.import_priority_high, 0)
    return "default", max(settings.import_priority_default, 0)


def publish_domain_event(event_type: str, payload: dict, attempts: int = 3) -> None:
    last_error = None
    for i in range(1, max(1, attempts) + 1):
        try:
            celery_client.send_task(
                "tasks.process_domain_event",
                kwargs={"event_type": event_type, "payload": payload},
                queue="events",
            )
            return
        except Exception as exc:
            last_error = exc
            if i < attempts:
                time.sleep(min(2.0, 0.2 * i))
    raise last_error


def enqueue_patients_csv_import(tenant_id: str, actor_user_id: str, import_job_id: str, csv_content: str) -> str:
    tier, priority_value = _import_priority_for_tenant(tenant_id)
    result = celery_client.send_task(
        "tasks.import_patients_csv",
        kwargs={
            "tenant_id": tenant_id,
            "actor_user_id": actor_user_id,
            "import_job_id": import_job_id,
            "csv_content": csv_content,
        },
        queue="imports",
        priority=priority_value,
    )
    imports_enqueued_total.labels(tier=tier).inc()
    return str(result.id)


def get_task_status(task_id: str) -> dict:
    result = AsyncResult(task_id, app=celery_client)
    payload = result.result if isinstance(result.result, dict) else {}
    return {
        "task_id": task_id,
        "state": str(result.state),
        "result": payload,
    }
