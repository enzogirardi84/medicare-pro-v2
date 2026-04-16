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
}


def _psycopg_dsn(url: str) -> str:
    return str(url).replace("postgresql+psycopg://", "postgresql://", 1)


@celery_app.task(name="tasks.generate_report")
def generate_report(report_name: str) -> dict:
    time.sleep(2)
    return {"status": "done", "report_name": report_name}


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
        raise RuntimeError("CSV requires headers: full_name,document_number")
    rows = 0
    inserted = 0
    dsn = _psycopg_dsn(database_url)
    errors: list[dict] = []
    conn = psycopg.connect(dsn)
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM import_job_errors WHERE import_job_id = %s", (import_job_id,))
        cur.execute(
            """
            UPDATE import_jobs
            SET status = %s, rows_valid = 0, rows_inserted = 0, errors_json = %s, updated_at = NOW()
            WHERE id = %s
            """,
            ("running", "[]", import_job_id),
        )
        for idx, row in enumerate(reader, start=2):
            if not str(row.get("full_name", "")).strip():
                errors.append({"line_number": idx, "document_number": "", "reason": "missing_full_name"})
                continue
            if not str(row.get("document_number", "")).strip():
                errors.append({"line_number": idx, "document_number": "", "reason": "missing_document_number"})
                continue
            rows += 1
            pid = str(uuid.uuid4())
            full_name = str(row.get("full_name", "")).strip()
            document_number = str(row.get("document_number", "")).strip()
            cur.execute(
                """
                INSERT INTO patients (id, tenant_id, full_name, document_number, created_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (tenant_id, document_number) DO NOTHING
                """,
                (pid, tenant_id, full_name, document_number),
            )
            if cur.rowcount == 0:
                errors.append(
                    {"line_number": idx, "document_number": document_number, "reason": "duplicate_document_number"}
                )
            else:
                inserted += 1
        for err in errors:
            cur.execute(
                """
                INSERT INTO import_job_errors (id, import_job_id, line_number, code, message, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    import_job_id,
                    int(err.get("line_number", 0)),
                    str(err.get("reason", "unknown")),
                    str(err),
                    datetime.now(timezone.utc),
                ),
            )
        status = "completed_with_errors" if errors else "completed"
        cur.execute(
            """
            UPDATE import_jobs
            SET status = %s, rows_valid = %s, rows_inserted = %s, errors_json = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (status, rows, inserted, json.dumps(errors[:100], ensure_ascii=True), import_job_id),
        )
        conn.commit()
    except Exception as exc:
        cur.execute(
            """
            UPDATE import_jobs
            SET status = %s, errors_json = %s, updated_at = NOW()
            WHERE id = %s
            """,
            ("failed", json.dumps([{"reason": str(exc)}], ensure_ascii=True), import_job_id),
        )
        cur.execute(
            """
            INSERT INTO import_job_errors (id, import_job_id, line_number, code, message, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (str(uuid.uuid4()), import_job_id, 0, "worker_exception", str(exc), datetime.now(timezone.utc)),
        )
        conn.commit()
        raise
    finally:
        cur.close()
        conn.close()
    return {
        "status": "completed",
        "tenant_id": tenant_id,
        "actor_user_id": actor_user_id,
        "import_job_id": import_job_id,
        "rows_valid": rows,
        "rows_inserted": inserted,
        "errors_count": len(errors),
    }
