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
    tenant_name = f"clinica-resilience-{uuid.uuid4().hex[:6]}"
    email = f"admin-resilience-{uuid.uuid4().hex[:6]}@test.com"
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


def test_resilience_status_and_precheck_contract():
    base = _require_base_url()
    token = _auth_token(base)
    headers = {"Authorization": f"Bearer {token}"}

    status_res = requests.get(f"{base}/v1/system/resilience/status", headers=headers, timeout=TIMEOUT)
    assert status_res.status_code == 200, status_res.text
    status_payload = status_res.json()
    assert "dependencies" in status_payload
    assert "limits" in status_payload
    assert "requirements" in status_payload
    req = status_payload["requirements"]
    assert req.get("reason_min_length") == 8
    assert req.get("manual_ops_use_reason_query") is True
    assert "policies" in status_payload
    assert "resilience_rollback_max_index" in status_payload["limits"]

    precheck_bad = requests.get(
        f"{base}/v1/system/resilience/precheck",
        params={
            "operation": "switch",
            "reason": "short",
            "ttl_seconds": 10,
        },
        headers=headers,
        timeout=TIMEOUT,
    )
    assert precheck_bad.status_code == 200, precheck_bad.text
    bad_payload = precheck_bad.json()
    assert bad_payload.get("ok") is False
    assert len(bad_payload.get("issues", [])) >= 1

    precheck_ok = requests.get(
        f"{base}/v1/system/resilience/precheck",
        params={
            "operation": "switch",
            "reason": "Validating resilience switch contract",
            "ttl_seconds": 1800,
            "rate_limit_fail_open": "true",
        },
        headers=headers,
        timeout=TIMEOUT,
    )
    assert precheck_ok.status_code == 200, precheck_ok.text
    ok_payload = precheck_ok.json()
    assert ok_payload.get("ok") is True
    assert ok_payload.get("operation") == "switch"
