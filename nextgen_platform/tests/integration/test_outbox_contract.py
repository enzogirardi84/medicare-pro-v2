import os
import uuid

import requests


BASE_URL = os.getenv("NEXTGEN_BASE_URL", "").rstrip("/")
TIMEOUT = 20


def _require_base_url() -> str:
    if not BASE_URL:
        raise RuntimeError("Set NEXTGEN_BASE_URL to run integration contract tests.")
    return BASE_URL


def _auth_token(base: str) -> str:
    tenant_name = "clinica-outbox-test"
    email = "admin-outbox@test.com"
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


def test_outbox_create_and_flush():
    base = _require_base_url()
    token = _auth_token(base)
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())}

    create = requests.post(
        f"{base}/v1/patients",
        json={"full_name": "Paciente Outbox", "document_number": f"DOC-{uuid.uuid4().hex[:8]}"},
        headers=headers,
        timeout=TIMEOUT,
    )
    assert create.status_code == 201, create.text

    status_before = requests.get(f"{base}/v1/system/outbox/status", headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
    assert status_before.status_code == 200, status_before.text
    pending_before = int(status_before.json().get("pending", 0)) + int(status_before.json().get("retry", 0))
    assert pending_before >= 1

    flush = requests.post(
        f"{base}/v1/system/outbox/flush?limit=100&reason=integration_contract_outbox_flush",
        headers={"Authorization": f"Bearer {token}"},
        timeout=TIMEOUT,
    )
    assert flush.status_code == 200, flush.text
    assert int(flush.json().get("published", 0)) >= 1

    status_after = requests.get(f"{base}/v1/system/outbox/status", headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
    assert status_after.status_code == 200, status_after.text
    assert int(status_after.json().get("pending", 0)) == 0
