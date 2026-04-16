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
    tenant_name = "clinica-scheduler-test"
    email = "admin-scheduler@test.com"
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


def test_outbox_scheduler_auto_flush():
    base = _require_base_url()
    token = _auth_token(base)
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())}

    create = requests.post(
        f"{base}/v1/patients",
        json={"full_name": "Paciente Scheduler", "document_number": f"DOC-{uuid.uuid4().hex[:8]}"},
        headers=headers,
        timeout=TIMEOUT,
    )
    assert create.status_code == 201, create.text

    deadline = time.time() + 40
    observed_published = False
    while time.time() < deadline:
        status_res = requests.get(
            f"{base}/v1/system/outbox/status",
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
        assert status_res.status_code == 200, status_res.text
        body = status_res.json()
        pending = int(body.get("pending", 0)) + int(body.get("retry", 0))
        published = int(body.get("published", 0))
        if published >= 1:
            observed_published = True
        if pending == 0 and observed_published:
            return
        time.sleep(2)

    raise AssertionError("outbox scheduler did not flush events within expected time")
