import os
import time
import csv
import io
import uuid
import json
from datetime import datetime, timezone

from celery import Celery
import psycopg

redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
database_url = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@db:5432/medicare_nextgen")
celery_app = Celery("nextgen_worker", broker=redis_url, backend=redis_url)
celery_app.conf.task_routes = {
    "tasks.process_domain_event": {"queue": "events"},
    "tasks.import_patients_csv": {"queue": "imports"},
    "tasks.generate_report": {"queue": "reports"},
    "tasks.generate_pdf_report": {"queue": "reports"},
    "tasks.send_whatsapp_notification": {"queue": "events"},
}


def _psycopg_dsn(url: str) -> str:
    return str(url).replace("postgresql+psycopg://", "postgresql://", 1)


@celery_app.task(name="tasks.generate_report")
def generate_report(report_name: str) -> dict:
    time.sleep(2)
    return {"status": "done", "report_name": report_name}


@celery_app.task(name="tasks.generate_pdf_report")
def generate_pdf_report(patient_id: str, report_type: str) -> dict:
    """
    Genera un PDF en segundo plano y lo guarda en storage (S3/GCS).
    """
    time.sleep(3) # Simula renderizado pesado
    return {"status": "done", "url": f"https://storage.medicare.com/reports/{patient_id}_{report_type}.pdf"}


@celery_app.task(name="tasks.send_whatsapp_notification")
def send_whatsapp_notification(phone: str, message: str) -> dict:
    """
    Envía una notificación por WhatsApp asíncronamente.
    """
    time.sleep(1) # Simula llamada a API de Twilio/Meta
    return {"status": "sent", "phone": phone}


@celery_app.task(name="tasks.process_domain_event")
def process_domain_event(event_type: str, payload: dict) -> dict:
    # Placeholder de consumo asincrono de eventos de dominio.
    # Aqui se conectan notificaciones, analytics, integraciones externas, etc.
    if payload.get("force_fail") is True:
        raise RuntimeError("forced event processing failure")
    return {"status": "processed", "event_type": event_type, "payload": payload}


@celery_app.task(name="tasks.import_patients_csv")
def import_patients_csv(tenant_id: str, actor_user_id: str, import_job_id: str, csv_content: str) -> dict:
    """
    Base async import task.
    Actualmente valida y parsea el CSV; siguiente paso: persistir en DB dentro de worker.
    """
    stream = io.StringIO(csv_content or "")
    reader = csv.DictReader(stream)
    required = {"full_name", "document_number"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        return {"status": "failed", "error": "missing_required_columns"}
    
    rows_valid = 0
    errors = []
    for i, row in enumerate(reader, start=2):
        name = str(row.get("full_name") or "").strip()
        doc = str(row.get("document_number") or "").strip()
        if len(name) < 2 or len(doc) < 3:
            errors.append({"line_number": i, "code": "validation_error", "message": "invalid name or document"})
            continue
        rows_valid += 1

    dsn = _psycopg_dsn(database_url)
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE import_jobs SET status = %s, rows_valid = %s, errors_json = %s, updated_at = %s WHERE id = %s AND tenant_id = %s",
                    (
                        "completed_with_errors" if errors else "completed",
                        rows_valid,
                        json.dumps(errors[:100]),
                        datetime.now(timezone.utc),
                        import_job_id,
                        tenant_id,
                    ),
                )
                if errors:
                    for err in errors[:100]:
                        cur.execute(
                            "INSERT INTO import_job_errors (id, import_job_id, line_number, code, message) VALUES (%s, %s, %s, %s, %s)",
                            (str(uuid.uuid4()), import_job_id, err["line_number"], err["code"], err["message"]),
                        )
            conn.commit()
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}

    return {"status": "completed", "rows_valid": rows_valid, "errors_count": len(errors)}
