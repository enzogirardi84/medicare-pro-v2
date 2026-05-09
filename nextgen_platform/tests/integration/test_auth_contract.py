import os

import requests


BASE_URL = os.getenv("NEXTGEN_BASE_URL", "").rstrip("/")
TIMEOUT = 15


def _require_base_url() -> str:
    if not BASE_URL:
        raise RuntimeError("Set NEXTGEN_BASE_URL to run integration contract tests.")
    return BASE_URL


def test_register_login_refresh_logout_flow():
    base = _require_base_url()
    payload = {
        "tenant_name": "clinica-scale-test",
        "email": "admin-scale@test.com",
        "password": "StrongPass123!",
        "role": "admin",
    }

    reg = requests.post(f"{base}/v1/auth/register", json=payload, timeout=TIMEOUT)
    if reg.status_code not in (201, 409):
        raise AssertionError(f"unexpected register status: {reg.status_code} body={reg.text}")

    login = requests.post(
        f"{base}/v1/auth/login",
        json={
            "tenant_name": payload["tenant_name"],
            "email": payload["email"],
            "password": payload["password"],
        },
        timeout=TIMEOUT,
    )
    assert login.status_code == 200, login.text
    tokens = login.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    refresh = requests.post(
        f"{base}/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
        timeout=TIMEOUT,
    )
    assert refresh.status_code == 200, refresh.text
    rotated = refresh.json()
    assert "access_token" in rotated
    assert "refresh_token" in rotated

    logout = requests.post(
        f"{base}/v1/auth/logout",
        headers={"Authorization": f"Bearer {rotated['access_token']}"},
        json={"refresh_token": rotated["refresh_token"]},
        timeout=TIMEOUT,
    )
    assert logout.status_code == 204, logout.text

    after_logout = requests.get(
        f"{base}/v1/patients",
        headers={"Authorization": f"Bearer {rotated['access_token']}"},
        timeout=TIMEOUT,
    )
    assert after_logout.status_code == 401, after_logout.text
