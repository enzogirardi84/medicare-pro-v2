"""Consulta opcional de issues Jira Cloud (REST API v3) sin dependencias extra.

Configuracion en .streamlit/secrets.toml (bloque [jira]):

[jira]
base_url = "https://tu-empresa.atlassian.net"
email = "tu@correo.com"
api_token = "token_de_api_de_atlassian"
jql = "project = MC ORDER BY updated DESC"
# opcional:
# board_url = "https://tu-empresa.atlassian.net/jira/software/c/projects/MC/boards/1"
# max_issues = 25

Tambien se aceptan claves planas: JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_JQL.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _secrets_dict() -> Dict[str, Any]:
    try:
        import streamlit as st

        return dict(st.secrets)
    except Exception:
        return {}


def load_jira_config() -> Optional[Dict[str, Any]]:
    sec = _secrets_dict()
    block = sec.get("jira")
    if isinstance(block, dict):
        base = str(block.get("base_url", "")).strip().rstrip("/")
        email = str(block.get("email", "")).strip()
        token = str(block.get("api_token", "")).strip()
        jql = str(block.get("jql", "ORDER BY updated DESC")).strip() or "ORDER BY updated DESC"
        board_url = str(block.get("board_url", "")).strip()
        try:
            max_issues = int(block.get("max_issues", 25))
        except (TypeError, ValueError):
            max_issues = 25
        max_issues = max(1, min(max_issues, 50))
        if base and email and token:
            return {
                "base_url": base,
                "email": email,
                "api_token": token,
                "jql": jql,
                "board_url": board_url,
                "max_issues": max_issues,
            }

    base = str(sec.get("JIRA_BASE_URL", "")).strip().rstrip("/")
    email = str(sec.get("JIRA_EMAIL", "")).strip()
    token = str(sec.get("JIRA_API_TOKEN", "")).strip()
    jql = str(sec.get("JIRA_JQL", "ORDER BY updated DESC")).strip() or "ORDER BY updated DESC"
    board_url = str(sec.get("JIRA_BOARD_URL", "")).strip()
    try:
        max_issues = int(sec.get("JIRA_MAX_ISSUES", 25))
    except (TypeError, ValueError):
        max_issues = 25
    max_issues = max(1, min(max_issues, 50))
    if base and email and token:
        return {
            "base_url": base,
            "email": email,
            "api_token": token,
            "jql": jql,
            "board_url": board_url,
            "max_issues": max_issues,
        }
    return None


def fetch_jira_issues(cfg: Dict[str, Any]) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    base = cfg["base_url"]
    auth = base64.b64encode(f'{cfg["email"]}:{cfg["api_token"]}'.encode()).decode()
    max_n = cfg.get("max_issues", 25)
    fields = "summary,status,assignee,issuetype,priority,updated"
    q = urlencode(
        {
            "jql": cfg["jql"],
            "maxResults": str(max_n),
            "fields": fields,
        }
    )
    url = f"{base}/rest/api/3/search?{q}"
    req = Request(url, headers={"Authorization": f"Basic {auth}", "Accept": "application/json"})
    try:
        with urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")[:800]
        except Exception:
            body = ""
        return None, f"HTTP {e.code}: {body or e.reason}"
    except URLError as e:
        return None, f"Red: {e.reason!s}"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return None, f"JSON invalido: {e}"

    issues = data.get("issues") or []
    rows: List[Dict[str, Any]] = []
    for item in issues:
        key = item.get("key", "")
        fld = item.get("fields") or {}
        st_f = fld.get("status") or {}
        status = st_f.get("name", "")
        it = fld.get("issuetype") or {}
        tipo = it.get("name", "")
        pr = fld.get("priority") or {}
        prio = pr.get("name", "")
        asg = fld.get("assignee")
        assignee = (asg or {}).get("displayName", "Sin asignar") if asg else "Sin asignar"
        summary = fld.get("summary", "")
        updated = fld.get("updated", "")
        browse = f"{base}/browse/{key}" if key else ""
        rows.append(
            {
                "Clave": key,
                "Resumen": summary,
                "Estado": status,
                "Tipo": tipo,
                "Prioridad": prio,
                "Asignado": assignee,
                "Actualizado": updated[:10] if updated else "",
                "URL": browse,
            }
        )
    return rows, None


def jira_setup_hint() -> str:
    return (
        "Para ver issues aca, agrega en `.streamlit/secrets.toml` un bloque `[jira]` con "
        "`base_url` (https://tu-sitio.atlassian.net), `email`, `api_token` (Atlassian API token) "
        "y `jql` (por ejemplo `project = CLAVE ORDER BY updated DESC`). "
        "Opcional: `board_url` para un acceso directo al tablero."
    )
