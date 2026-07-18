from __future__ import annotations

"""Diagnostico seguro de deploy para MediCare Pro.

No imprime secretos. Solo valida presencia, formato y resolucion DNS.
"""

import os
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"


def _status(ok: bool) -> str:
    return "OK" if ok else "ERROR"


def _load_local_secrets() -> dict:
    if not SECRETS_PATH.exists():
        return {}
    raw = SECRETS_PATH.read_text(encoding="utf-8-sig")
    return tomllib.loads(raw)


def _get_config_value(secrets: dict, name: str) -> str:
    value = os.getenv(name)
    if value:
        return value.strip()
    raw = secrets.get(name)
    return str(raw or "").strip()


def _check_entrypoints() -> list[tuple[bool, str]]:
    checks: list[tuple[bool, str]] = []
    streamlit_app = ROOT / "streamlit_app.py"
    main_medicare = ROOT / "main_medicare.py"
    render_yaml = ROOT / "render.yaml"
    start_sh = ROOT / "start.sh"
    dockerfile = ROOT / "Dockerfile"

    checks.append((streamlit_app.exists(), "Existe streamlit_app.py"))
    checks.append((main_medicare.exists(), "Existe main_medicare.py"))
    if streamlit_app.exists():
        src = streamlit_app.read_text(encoding="utf-8", errors="replace")
        checks.append(("main_medicare.py" in src and "exec(" in src, "streamlit_app.py ejecuta main_medicare.py"))
    if render_yaml.exists():
        src = render_yaml.read_text(encoding="utf-8", errors="replace")
        checks.append(("streamlit run streamlit_app.py" in src, "Render apunta a streamlit_app.py"))
    if start_sh.exists():
        src = start_sh.read_text(encoding="utf-8", errors="replace")
        checks.append(("streamlit run streamlit_app.py" in src, "start.sh apunta a streamlit_app.py"))
    if dockerfile.exists():
        src = dockerfile.read_text(encoding="utf-8", errors="replace")
        checks.append(('CMD ["streamlit", "run", "streamlit_app.py"' in src, "Docker apunta a streamlit_app.py"))
    return checks


def _check_supabase(secrets: dict) -> list[tuple[bool, str]]:
    checks: list[tuple[bool, str]] = []
    url = _get_config_value(secrets, "SUPABASE_URL")
    key = _get_config_value(secrets, "SUPABASE_KEY")
    service_key = _get_config_value(secrets, "SUPABASE_SERVICE_ROLE_KEY") or _get_config_value(secrets, "SUPABASE_SERVICE_KEY")

    checks.append((bool(url), "SUPABASE_URL configurado"))
    checks.append((bool(key), "SUPABASE_KEY configurado"))
    checks.append((bool(service_key), "Service role key configurada (opcional para tareas admin)"))

    if not url:
        return checks

    parsed = urlparse(url)
    host = parsed.hostname or ""
    checks.append((parsed.scheme == "https", "SUPABASE_URL usa https"))
    checks.append((host.endswith(".supabase.co"), f"Host Supabase valido: {host or 'sin host'}"))

    if host:
        try:
            socket.getaddrinfo(host, 443)
            checks.append((True, f"DNS resuelve: {host}"))
        except OSError as exc:
            checks.append((False, f"DNS no resuelve {host}: {type(exc).__name__}"))

    return checks


def main() -> int:
    try:
        secrets = _load_local_secrets()
    except Exception as exc:
        print(f"[ERROR] No se pudo leer .streamlit/secrets.toml: {type(exc).__name__}")
        return 2

    checks = _check_entrypoints() + _check_supabase(secrets)
    failed = False
    print("Diagnostico de deploy MediCare Pro")
    print("=" * 38)
    for ok, message in checks:
        failed = failed or not ok
        print(f"[{_status(ok)}] {message}")
    if failed:
        print("\nAccion recomendada: corregir los items ERROR y reiniciar el deploy.")
        return 1
    print("\nTodo OK para el arranque basico.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
