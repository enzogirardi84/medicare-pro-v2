import os
import time
import uuid

import requests


BASE_URL = os.getenv("NEXTGEN_BASE_URL", "").rstrip("/")
TIMEOUT = 20


def _require_base_url() -> str:
    if not BASE_URL:
        raise RuntimeError("Set NEXTGEN_BASE_URL to run integration contract tests.")
    return BASE_URL


def _auth_token(base: str) -> str:
    tenant_name = "clinica-import-test"
    email = "admin-import@test.com"
    password = "StrongPass123!"
    register = requests.post(
        f"{base}/v1/auth/register",
        json={"tenant_name": tenant_name, "email": email, "password": password, "role": "admin"},
        timeout=TIMEOUT,
    )
    if register.status_code not in (201, 409):
        raise AssertionError(f"register failed: {register.status_code} {register.text}")
    login = requests.post(
        f"{base}/v1/auth/login",
        json={"tenant_name": tenant_name, "email": email, "password": password},
        timeout=TIMEOUT,
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def test_import_csv_async_job_lifecycle():
    base = _require_base_url()
    token = _auth_token(base)
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:8]
    csv_content = (
        "full_name,document_number\n"
        f"Paciente Uno {suffix},DOC-{suffix}-1\n"
        f"Paciente Dos {suffix},DOC-{suffix}-2\n"
        f"Paciente Duplicado {suffix},DOC-{suffix}-2\n"
    )
    files = {"file": (f"import-{suffix}.csv", csv_content, "text/csv")}
    upload = requests.post(f"{base}/v1/patients/import/csv", headers=headers, files=files, timeout=TIMEOUT)
    assert upload.status_code == 202, upload.text
    payload = upload.json()
    import_job_id = payload.get("import_job_id")
    assert import_job_id

    deadline = time.time() + 60
    while time.time() < deadline:
        status_res = requests.get(
            f"{base}/v1/system/import-jobs/{import_job_id}",
            headers=headers,
            timeout=TIMEOUT,
        )
        assert status_res.status_code == 200, status_res.text
        status = status_res.json().get("status")
        if status in ("completed", "completed_with_errors", "failed"):
            assert status in ("completed", "completed_with_errors")
            errs = requests.get(
                f"{base}/v1/system/import-jobs/{import_job_id}/errors",
                headers=headers,
                timeout=TIMEOUT,
            )
            assert errs.status_code == 200, errs.text
            errs_csv = requests.get(
                f"{base}/v1/system/import-jobs/{import_job_id}/errors.csv",
                headers=headers,
                timeout=TIMEOUT,
            )
            assert errs_csv.status_code == 200, errs_csv.text
            assert "line_number,code,message,created_at" in errs_csv.text
            retry_one = requests.post(
                f"{base}/v1/system/import-jobs/{import_job_id}/retry?reason=integration_contract_import_retry_one",
                headers=headers,
                timeout=TIMEOUT,
            )
            assert retry_one.status_code == 200, retry_one.text
            one_body = retry_one.json()
            assert one_body.get("status") == "queued"
            assert one_body.get("reason") == "integration_contract_import_retry_one"
            assert "import_job_id" in one_body
            retry_batch = requests.post(
                f"{base}/v1/system/import-jobs/retry-failed?limit=5&reason=integration_contract_retry_failed_batch",
                headers=headers,
                timeout=TIMEOUT,
            )
            assert retry_batch.status_code == 200, retry_batch.text
            tenant_metrics = requests.get(
                f"{base}/v1/system/tenant/metrics",
                headers=headers,
                timeout=TIMEOUT,
            )
            assert tenant_metrics.status_code == 200, tenant_metrics.text
            return
        time.sleep(2)

    raise AssertionError("import job did not complete in expected time")
