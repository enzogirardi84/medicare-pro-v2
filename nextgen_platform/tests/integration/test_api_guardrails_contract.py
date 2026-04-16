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
    tenant_name = f"clinica-guardrails-{uuid.uuid4().hex[:6]}"
    email = f"admin-guardrails-{uuid.uuid4().hex[:6]}@test.com"
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


def _assert_standard_headers(res: requests.Response) -> None:
    assert res.headers.get("x-api-version")
    assert res.headers.get("x-environment")
    assert res.headers.get("x-deploy-id")
    assert res.headers.get("x-git-sha")
    assert res.headers.get("x-region")
    assert res.headers.get("x-node-id")
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "DENY"
    assert res.headers.get("referrer-policy") == "no-referrer"


def test_success_response_has_request_headers():
    base = _require_base_url()
    res = requests.get(f"{base}/health", timeout=TIMEOUT)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("build", {}).get("version")
    assert body.get("build", {}).get("deploy_id")
    assert body.get("build", {}).get("git_sha")
    assert body.get("build", {}).get("region")
    assert body.get("build", {}).get("node_id")
    assert res.headers.get("x-request-id")
    assert res.headers.get("x-process-time-ms")
    _assert_standard_headers(res)


def test_ready_response_exposes_build_metadata():
    base = _require_base_url()
    res = requests.get(f"{base}/ready", timeout=TIMEOUT)
    assert res.status_code in (200, 503), res.text
    body = res.json()
    assert body.get("build", {}).get("version")
    assert body.get("build", {}).get("deploy_id")
    assert body.get("build", {}).get("git_sha")
    assert body.get("build", {}).get("region")
    assert body.get("build", {}).get("node_id")
    _assert_standard_headers(res)


def test_auth_failure_returns_formal_error_envelope():
    base = _require_base_url()
    res = requests.get(f"{base}/v1/patients", timeout=TIMEOUT)
    assert res.status_code == 401, res.text
    body = res.json()
    assert "error" in body
    assert body["error"].get("code")
    assert body["error"].get("message")
    assert body["error"].get("request_id")
    assert body["error"].get("timestamp_utc")
    assert res.headers.get("x-request-id") == body["error"]["request_id"]
    assert res.headers.get("x-error-code") == body["error"]["code"]
    _assert_standard_headers(res)


def test_oversized_payload_is_rejected_with_413():
    base = _require_base_url()
    token = _auth_token(base)
    headers = {"Authorization": f"Bearer {token}"}
    oversized = "X" * 6_000_000
    res = requests.post(
        f"{base}/v1/patients/bulk",
        json={
            "items": [
                {
                    "full_name": oversized,
                    "document_number": f"OV-{uuid.uuid4().hex[:8]}",
                }
            ]
        },
        headers=headers,
        timeout=TIMEOUT,
    )
    assert res.status_code == 413, res.text
    body = res.json()
    assert body["error"]["code"] == "payload_too_large"
    assert body["error"].get("request_id")
    assert body["error"].get("timestamp_utc")
    assert res.headers.get("x-request-id") == body["error"]["request_id"]
    assert res.headers.get("x-error-code") == body["error"]["code"]
    _assert_standard_headers(res)


def test_repeated_oversized_payloads_trigger_temporary_block():
    base = _require_base_url()
    token = _auth_token(base)
    headers = {"Authorization": f"Bearer {token}", "X-Forwarded-For": "203.0.113.10"}
    oversized = "Y" * 6_000_000

    for _ in range(9):
        res = requests.post(
            f"{base}/v1/patients/bulk",
            json={
                "items": [
                    {
                        "full_name": oversized,
                        "document_number": f"OVB-{uuid.uuid4().hex[:8]}",
                    }
                ]
            },
            headers=headers,
            timeout=TIMEOUT,
        )
        assert res.status_code in (413, 429), res.text

    blocked = requests.post(
        f"{base}/v1/patients/bulk",
        json={
            "items": [
                {
                    "full_name": oversized,
                    "document_number": f"OVB-{uuid.uuid4().hex[:8]}",
                }
            ]
        },
        headers=headers,
        timeout=TIMEOUT,
    )
    assert blocked.status_code == 429, blocked.text
    body = blocked.json()
    assert body["error"]["code"] == "payload_abuse_blocked"
    assert body["error"].get("request_id")
    assert body["error"].get("timestamp_utc")
    retry_after_body = int(body["error"].get("details", {}).get("retry_after_seconds", 0))
    retry_after_header = int(blocked.headers.get("retry-after", "0"))
    assert retry_after_body >= 1
    assert retry_after_header >= 1
    assert retry_after_header == retry_after_body
    assert blocked.headers.get("x-request-id") == body["error"]["request_id"]
    assert blocked.headers.get("x-error-code") == body["error"]["code"]
    _assert_standard_headers(blocked)


def test_allowlisted_ip_keeps_413_without_abuse_block():
    base = _require_base_url()
    token = _auth_token(base)
    headers = {"Authorization": f"Bearer {token}", "X-Forwarded-For": "127.0.0.1"}
    oversized = "Z" * 6_000_000

    for _ in range(10):
        res = requests.post(
            f"{base}/v1/patients/bulk",
            json={
                "items": [
                    {
                        "full_name": oversized,
                        "document_number": f"OVA-{uuid.uuid4().hex[:8]}",
                    }
                ]
            },
            headers=headers,
            timeout=TIMEOUT,
        )
        assert res.status_code == 413, res.text
        body = res.json()
        assert body["error"]["code"] == "payload_too_large"
