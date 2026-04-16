# API Client Retry Guide

## Objetivo

Definir una estrategia de retry formal para clientes que consumen la API bajo alta concurrencia, evitando sobrecarga adicional y mejorando estabilidad.

## Señales que expone la API

- Header `Retry-After` en errores de sobrecarga/timeout.
- Header `X-Error-Code` en respuestas de error para clasificación rápida.
- Header `X-API-Version` en todas las respuestas.
- Headers de seguridad base: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`.
- Error JSON estandar:
  - `error.code`
  - `error.message`
  - `error.request_id`
  - `error.timestamp_utc`
  - `error.details.retry_after_seconds` (cuando aplica)

## Códigos relevantes

- `503` + `error.code=server_busy`:
  - La API está saturada temporalmente.
  - Acción recomendada: respetar `Retry-After` y aplicar backoff exponencial con jitter.
- `504` + `error.code=request_timeout`:
  - La operación excedió el tiempo máximo.
  - Acción recomendada: respetar `Retry-After`, reducir concurrencia del cliente y reintentar con límite.
- `429` + `error.code=payload_abuse_blocked`:
  - El cliente fue bloqueado temporalmente por enviar payloads oversized repetidos.
  - Acción recomendada: respetar `Retry-After`, detener envíos grandes y corregir el contrato de integración.
- `413` + `error.code=payload_too_large`:
  - El payload excede el límite configurado.
  - Acción recomendada: no reintentar sin corregir tamaño del request.

## Política recomendada

- Máximo de reintentos por request: `3`
- Timeout cliente (lecturas): `2-5s` según endpoint
- Timeout cliente (escrituras): `5-10s` según endpoint
- Backoff base: `200ms`
- Backoff máximo: `5s`
- Jitter: `+-25%`

## Retry-After por tipo de error

- `server_busy` (`503`): usa `api_retry_after_busy_seconds`.
- `request_timeout` (`504`): usa `api_retry_after_timeout_seconds`.
- `payload_abuse_blocked` (`429`): usa ventana de bloqueo temporal por abuso.

## Identificación de cliente para guardrails de payload

- La API usa `X-Forwarded-For` (primer IP) cuando está presente.
- Si no existe ese header, usa la IP de conexión directa.
- Recomendación: en despliegues con proxy/LB, propagar correctamente `X-Forwarded-For`.
- Se puede excluir IPs o rangos CIDR confiables del bloqueo anti-abuso con `api_payload_guard_ip_allowlist` (lista separada por comas).
- Ejemplo: `127.0.0.1,::1,10.20.0.0/16,192.168.1.0/24`.
- Nota: la allowlist excluye del bloqueo temporal por abuso (`429`), pero no desactiva la validación de tamaño (`413`).

## Ejemplo JavaScript/TypeScript (frontend o Node)

```ts
async function callWithRetry(url: string, init: RequestInit, maxRetries = 3) {
  let attempt = 0;
  while (true) {
    const res = await fetch(url, init);
    if (res.ok) return res;

    const body = await res.json().catch(() => ({}));
    const code = body?.error?.code;
    const retryAfterHeader = Number(res.headers.get("retry-after") || "0");
    const retryAfterBody = Number(body?.error?.details?.retry_after_seconds || 0);
    const retryAfter = Math.max(retryAfterHeader, retryAfterBody, 1);

    const retryable = (res.status === 503 && code === "server_busy") || (res.status === 504 && code === "request_timeout");
    if (!retryable || attempt >= maxRetries) {
      throw new Error(`API error ${res.status} (${code || "unknown"})`);
    }

    const backoffMs = Math.min(5000, 200 * 2 ** attempt);
    const jitter = backoffMs * (Math.random() * 0.5 - 0.25);
    const waitMs = Math.max(retryAfter * 1000, backoffMs + jitter);
    await new Promise((r) => setTimeout(r, waitMs));
    attempt += 1;
  }
}
```

## Ejemplo Python (backend integrador)

```python
import random
import time
import requests

def request_with_retry(method: str, url: str, **kwargs):
    max_retries = 3
    for attempt in range(max_retries + 1):
        resp = requests.request(method, url, timeout=10, **kwargs)
        if resp.ok:
            return resp

        code = None
        retry_after_body = 0
        try:
            payload = resp.json()
            code = payload.get("error", {}).get("code")
            retry_after_body = int(payload.get("error", {}).get("details", {}).get("retry_after_seconds", 0))
        except Exception:
            pass

        retry_after_header = int(resp.headers.get("retry-after", "0"))
        retry_after = max(retry_after_header, retry_after_body, 1)
        retryable = (resp.status_code == 503 and code == "server_busy") or (resp.status_code == 504 and code == "request_timeout")

        if (not retryable) or attempt >= max_retries:
            resp.raise_for_status()

        backoff = min(5.0, 0.2 * (2 ** attempt))
        jitter = backoff * random.uniform(-0.25, 0.25)
        sleep_seconds = max(float(retry_after), backoff + jitter)
        time.sleep(sleep_seconds)

    raise RuntimeError("unreachable")
```

## Recomendaciones para móvil

- Reintentar solo en red estable (`wifi` o buena señal).
- Pausar retries si app queda en background.
- Usar cola local para operaciones offline y sincronizar luego.
- En `413`, corregir payload (compresión, chunking o reducción de campos) antes de reenviar.

## Observabilidad mínima recomendada en clientes

- Loggear `request_id` de respuestas no exitosas.
- Medir tasa de `503` y `504` por endpoint.
- Medir latencia de reintentos y cantidad de intentos por operación.
