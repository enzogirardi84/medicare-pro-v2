import random
import time
from typing import Any, Dict, Optional

import requests
import streamlit as st

from core.app_logging import log_event


def get_api_base_url() -> str:
    """
    Obtiene la URL base de la nueva API (FastAPI) desde secrets.
    Si no está configurada, loguea warning y devuelve None para que el caller decida.
    """
    try:
        url = st.secrets.get("NEXTGEN_API_URL", "")
        if url:
            return url
    except Exception:
        pass
    log_event("api_client", "NEXTGEN_API_URL no configurado en secrets.")
    return ""


def get_api_headers(token: Optional[str] = None) -> Dict[str, str]:
    """
    Construye los headers base para la API, incluyendo el token de autorización si está disponible.
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    # Si tenemos un token en la sesión de Streamlit y no se pasó uno explícito
    elif "access_token" in st.session_state:
        headers["Authorization"] = f"Bearer {st.session_state['access_token']}"
        
    return headers


def request_with_retry(method: str, endpoint: str, max_retries: int = 3, **kwargs) -> requests.Response:
    """
    Ejecuta una petición HTTP a la API NextGen con política de reintentos
    (backoff exponencial + jitter) para manejar sobrecarga y timeouts,
    según la guía oficial de integración.
    """
    base_url = get_api_base_url()
    if not base_url:
        log_event("api_client", f"Saltando peticion {method} {endpoint}: NEXTGEN_API_URL no configurado.")
        raise requests.exceptions.ConnectionError("NEXTGEN_API_URL no configurado en secrets.")
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    
    # Inyectar headers por defecto si no vienen en kwargs
    if "headers" not in kwargs:
        kwargs["headers"] = get_api_headers()
    else:
        # Combinar con los headers base
        base_headers = get_api_headers()
        base_headers.update(kwargs["headers"])
        kwargs["headers"] = base_headers

    # Timeout por defecto si no se especifica
    if "timeout" not in kwargs:
        kwargs["timeout"] = 10.0

    for attempt in range(max_retries + 1):
        try:
            resp = requests.request(method, url, **kwargs)
            if resp.ok:
                return resp

            code = None
            retry_after_body = 0
            try:
                payload = resp.json()
                code = payload.get("error", {}).get("code")
                retry_after_body = int(payload.get("error", {}).get("details", {}).get("retry_after_seconds", 0))
            except Exception as _exc:
                log_event("api_client", f"fallo_parse_retry_body:{type(_exc).__name__}")

            retry_after_header = int(resp.headers.get("retry-after", "0"))
            retry_after = max(retry_after_header, retry_after_body, 1)
            
            # Solo reintentamos en errores específicos de la API NextGen
            retryable = (resp.status_code == 503 and code == "server_busy") or \
                        (resp.status_code == 504 and code == "request_timeout")

            if (not retryable) or attempt >= max_retries:
                if not resp.ok:
                    log_event("api_client", f"API error {resp.status_code} en {method} {url}: {resp.text}")
                resp.raise_for_status()

            # Backoff exponencial con jitter
            backoff = min(5.0, 0.2 * (2 ** attempt))
            jitter = backoff * random.uniform(-0.25, 0.25)
            sleep_seconds = max(float(retry_after), backoff + jitter)
            
            log_event("api_client", f"Reintento {attempt + 1}/{max_retries} para {url} en {sleep_seconds:.2f}s")
            time.sleep(sleep_seconds)
            
        except requests.exceptions.RequestException as e:
            # Errores de red (connection refused, timeout de requests, etc)
            if attempt >= max_retries:
                log_event("api_client", f"Fallo de red tras {max_retries} reintentos en {method} {url}: {e}")
                raise
            
            backoff = min(5.0, 0.2 * (2 ** attempt))
            jitter = backoff * random.uniform(-0.25, 0.25)
            time.sleep(backoff + jitter)

    raise RuntimeError("unreachable")


def get_api(endpoint: str, **kwargs) -> requests.Response:
    return request_with_retry("GET", endpoint, **kwargs)


def post_api(endpoint: str, json: Optional[Dict[str, Any]] = None, **kwargs) -> requests.Response:
    return request_with_retry("POST", endpoint, json=json, **kwargs)


def put_api(endpoint: str, json: Optional[Dict[str, Any]] = None, **kwargs) -> requests.Response:
    return request_with_retry("PUT", endpoint, json=json, **kwargs)


def delete_api(endpoint: str, **kwargs) -> requests.Response:
    return request_with_retry("DELETE", endpoint, **kwargs)
