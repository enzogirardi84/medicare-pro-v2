import importlib
import os
import sys
from pathlib import Path

# Setear env vars requeridas por el nuevo guardrail del worker (fix #7)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/medicare_nextgen")

WORKER_DIR = Path(__file__).resolve().parents[2] / "apps" / "worker"
sys.path.insert(0, str(WORKER_DIR))
tasks = importlib.import_module("tasks")


class FakeCursor:
    def __init__(self):
        self.patient_documents: set[str] = set()
        self.inserted_patients: list[tuple] = []
        self.job_updates: list[tuple] = []
        self.errors: list[tuple] = []
        self.audit_logs: list[tuple] = []
        self.outbox_events: list[tuple] = []
        self.deleted_error_jobs: list[str] = []
        self._fetchone = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params=()):
        normalized = " ".join(str(query).lower().split())
        if normalized.startswith("delete from import_job_errors"):
            self.deleted_error_jobs.append(params[0])
            return
        if normalized.startswith("update import_jobs"):
            self.job_updates.append(params)
            return
        if normalized.startswith("insert into patients"):
            document_number = params[3]
            if document_number in self.patient_documents:
                self._fetchone = None
                return
            self.patient_documents.add(document_number)
            self.inserted_patients.append(params)
            self._fetchone = (params[0],)
            return
        if normalized.startswith("insert into import_job_errors"):
            self.errors.append(params)
            return
        if normalized.startswith("insert into audit_logs"):
            self.audit_logs.append(params)
            return
        if normalized.startswith("insert into outbox_events"):
            self.outbox_events.append(params)
            return
        raise AssertionError(f"unexpected SQL: {query}")

    def fetchone(self):
        return self._fetchone


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commits += 1


class FakeRedisClient:
    def __init__(self):
        self.incr_keys: list[str] = []

    def incr(self, key):
        self.incr_keys.append(key)
        return len(self.incr_keys)


def _patch_worker_dependencies(monkeypatch, cursor):
    connection = FakeConnection(cursor)
    monkeypatch.setattr(tasks.psycopg, "connect", lambda _dsn: connection)
    redis_client = FakeRedisClient()
    monkeypatch.setattr(tasks, "redis_client", redis_client)
    return connection, redis_client


def test_parse_patient_csv_rejects_duplicate_documents_in_file():
    valid_rows, errors, missing_required_columns = tasks._parse_patient_csv(
        "full_name,document_number\n"
        "Paciente Uno,DOC-1\n"
        "Paciente Duplicado,DOC-1\n"
    )

    assert missing_required_columns is False
    assert len(valid_rows) == 1
    assert errors == [{"line_number": 3, "code": "duplicate_document", "message": "duplicate document in csv"}]


def test_import_patients_csv_inserts_patients_and_records_duplicate_errors(monkeypatch):
    cursor = FakeCursor()
    connection, redis_client = _patch_worker_dependencies(monkeypatch, cursor)

    result = tasks.import_patients_csv.run(
        tenant_id="tenant-1",
        actor_user_id="user-1",
        import_job_id="job-1",
        csv_content=(
            "full_name,document_number\n"
            "Paciente Uno,DOC-1\n"
            "Paciente Dos,DOC-2\n"
            "Paciente Duplicado,DOC-2\n"
        ),
    )

    assert result == {"status": "completed_with_errors", "rows_valid": 2, "rows_inserted": 2, "errors_count": 1}
    assert len(cursor.inserted_patients) == 2
    assert len(cursor.audit_logs) == 2
    assert len(cursor.outbox_events) == 2
    assert cursor.errors[0][3] == "duplicate_document"
    assert cursor.job_updates[-1][0] == "completed_with_errors"
    assert cursor.job_updates[-1][1] == 2
    assert cursor.job_updates[-1][2] == 2
    assert connection.commits == 1
    assert redis_client.incr_keys == ["list_cache_version:patients:tenant-1"]


def test_import_patients_csv_marks_missing_columns_as_failed(monkeypatch):
    cursor = FakeCursor()
    _patch_worker_dependencies(monkeypatch, cursor)

    result = tasks.import_patients_csv.run(
        tenant_id="tenant-1",
        actor_user_id="user-1",
        import_job_id="job-1",
        csv_content="name,document\nPaciente Uno,DOC-1\n",
    )

    assert result == {"status": "failed", "error": "missing_required_columns", "errors_count": 1}
    assert cursor.inserted_patients == []
    assert cursor.job_updates[-1][0] == "failed"
    assert cursor.errors[0][3] == "missing_required_columns"
