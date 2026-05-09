import os
import time
import csv
import io
import uuid
import json
from datetime import datetime, timezone

from celery import Celery
import psycopg
import redis

redis_url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL") or ""
database_url = os.getenv("DATABASE_URL") or ""

if not redis_url:
    raise RuntimeError("REDIS_URL or CELERY_BROKER_URL must be set for NextGen worker.")
if not database_url:
    raise RuntimeError("DATABASE_URL must be set for NextGen worker.")
celery_app = Celery("nextgen_worker", broker=redis_url, backend=redis_url)
redis_client = redis.from_url(redis_url, decode_responses=True)
celery_app.conf.task_routes = {
    "tasks.process_domain_event": {"queue": "events"},
    "tasks.import_patients_csv": {"queue": "imports"},
    "tasks.generate_report": {"queue": "reports"},
    "tasks.generate_pdf_report": {"queue": "reports"},
    "tasks.send_whatsapp_notification": {"queue": "events"},
}


def _psycopg_dsn(url: str) -> str:
    return str(url).replace("postgresql+psycopg://", "postgresql://", 1)


def _parse_patient_csv(csv_content: str) -> tuple[list[dict[str, object]], list[dict[str, object]], bool]:
    stream = io.StringIO(csv_content or "")
    reader = csv.DictReader(stream)
    required = {"full_name", "document_number"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        return [], [{"line_number": 1, "code": "missing_required_columns", "message": "missing required columns"}], True

    valid_rows: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    seen_documents: set[str] = set()
    for line_number, row in enumerate(reader, start=2):
        full_name = str(row.get("full_name") or "").strip()
        document_number = str(row.get("document_number") or "").strip()
        if len(full_name) < 2 or len(document_number) < 3:
            errors.append({"line_number": line_number, "code": "validation_error", "message": "invalid name or document"})
            continue
        if document_number in seen_documents:
            errors.append({"line_number": line_number, "code": "duplicate_document", "message": "duplicate document in csv"})
            continue
        seen_documents.add(document_number)
        valid_rows.append({"full_name": full_name, "document_number": document_number, "line_number": line_number})
    return valid_rows, errors, False


def _record_import_error(cur, import_job_id: str, error: dict[str, object], created_at: datetime) -> None:
    cur.execute(
        "INSERT INTO import_job_errors (id, import_job_id, line_number, code, message, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
        (
            str(uuid.uuid4()),
            import_job_id,
            int(error.get("line_number") or 0),
            str(error.get("code") or "import_error"),
            str(error.get("message") or "import error"),
            created_at,
        ),
    )


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
    Importa pacientes en segundo plano y registra auditoria, outbox y errores por fila.
    """
    valid_rows, errors, missing_required_columns = _parse_patient_csv(csv_content)
    now = datetime.now(timezone.utc)
    dsn = _psycopg_dsn(database_url)
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM import_job_errors WHERE import_job_id = %s", (import_job_id,))
                if missing_required_columns:
                    for error in errors[:100]:
                        _record_import_error(cur, import_job_id, error, now)
                    cur.execute(
                        "UPDATE import_jobs SET status = %s, rows_valid = %s, rows_inserted = %s, errors_json = %s, updated_at = %s WHERE id = %s AND tenant_id = %s",
                        ("failed", 0, 0, json.dumps(errors[:100]), now, import_job_id, tenant_id),
                    )
                    conn.commit()
                    return {"status": "failed", "error": "missing_required_columns", "errors_count": len(errors)}

                rows_inserted = 0
                for row in valid_rows:
                    patient_id = str(uuid.uuid4())
                    cur.execute(
                        """
                        INSERT INTO patients (id, tenant_id, full_name, document_number, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (tenant_id, document_number) DO NOTHING
                        RETURNING id
                        """,
                        (patient_id, tenant_id, row["full_name"], row["document_number"], now),
                    )
                    inserted = cur.fetchone()
                    if not inserted:
                        errors.append(
                            {
                                "line_number": row.get("line_number", 0),
                                "code": "duplicate_document",
                                "message": "duplicate document in database",
                            }
                        )
                        continue
                    inserted_patient_id = str(inserted[0])
                    rows_inserted += 1
                    cur.execute(
                        "INSERT INTO audit_logs (id, tenant_id, actor_user_id, action, entity, entity_id, details_json, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (
                            str(uuid.uuid4()),
                            tenant_id,
                            actor_user_id,
                            "patient.import_csv",
                            "patient",
                            inserted_patient_id,
                            json.dumps({"document_number": row["document_number"]}),
                            now,
                        ),
                    )
                    cur.execute(
                        "INSERT INTO outbox_events (id, tenant_id, aggregate_type, aggregate_id, event_type, payload_json, status, attempts, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (
                            str(uuid.uuid4()),
                            tenant_id,
                            "patient",
                            inserted_patient_id,
                            "patient.created",
                            json.dumps({"patient_id": inserted_patient_id, "document_number": row["document_number"]}),
                            "pending",
                            0,
                            now,
                        ),
                    )
                for error in errors[:100]:
                    _record_import_error(cur, import_job_id, error, now)
                status = "completed_with_errors" if errors else "completed"
                cur.execute(
                    "UPDATE import_jobs SET status = %s, rows_valid = %s, rows_inserted = %s, errors_json = %s, updated_at = %s WHERE id = %s AND tenant_id = %s",
                    (
                        status,
                        len(valid_rows),
                        rows_inserted,
                        json.dumps(errors[:100]),
                        now,
                        import_job_id,
                        tenant_id,
                    ),
                )
            conn.commit()
        try:
            redis_client.incr(f"list_cache_version:patients:{tenant_id}")
        except redis.RedisError:
            pass
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}

    return {"status": status, "rows_valid": len(valid_rows), "rows_inserted": rows_inserted, "errors_count": len(errors)}
