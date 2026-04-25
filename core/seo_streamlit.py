"""
SEO y metadatos para apps Streamlit: inyección en documento padre (Lighthouse / buscadores con JS).

Opcional en secrets o en el entorno: APP_CANONICAL_URL, PUBLIC_BASE_URL o SITE_URL
(URL pública HTTPS sin barra final) para canonical y og:url.
Si esa URL usa host www.*, se puede redirigir el apex al www (inyectar_redirect_apex_si_configurado).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

_URL_KEYS = ("APP_CANONICAL_URL", "PUBLIC_BASE_URL", "SITE_URL")

# Textos alineados a la landing comercial (core/landing_publicidad.py).
META_DESCRIPTION = (
    "MediCare Enterprise PRO: software para salud domiciliaria, operación clínica y auditoría. "
    "Agenda con GPS, historia clínica, roles, RRHH, recetas, emergencias y documentación defendible "
    "para instituciones y equipos en terreno."
)

PAGE_TITLE_PUBLIC = "MediCare Enterprise PRO V9.12 | Salud domiciliaria y operación clínica"

OG_TITLE = "MediCare Enterprise PRO — Operación clínica con trazabilidad"

THEME_COLOR = "#0b1020"


def schema_software_application(*, canonical_url: str = "") -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "MediCare Enterprise PRO",
        "applicationCategory": "HealthApplication",
        "operatingSystem": "Web",
        "description": META_DESCRIPTION,
        "offers": {"@type": "Offer", "availability": "https://schema.org/OnlineOnly"},
    }
    if canonical_url:
        base["url"] = canonical_url
    return base


def canonical_www_apex_hosts(canonical_url: str) -> Optional[Tuple[str, str]]:
    """
    Si la URL canónica usa host `www.algo`, devuelve (apex, host_www) en minúsculas.
    Ej.: https://www.ejemplo.com -> ("ejemplo.com", "www.ejemplo.com").
    """
    raw = (canonical_url or "").strip()
    if not raw:
        return None
    p = urlparse(raw)
    if p.scheme not in ("http", "https"):
        return None
    host = (p.netloc or "").strip().lower()
    if not host or not host.startswith("www."):
        return None
    apex = host[4:]
    if not apex:
        return None
    return (apex, host)


def resolve_public_site_url() -> str:
    """
    URL pública del sitio (sin barra final): primero `st.secrets`, luego variables de entorno.
    Claves aceptadas, en orden: APP_CANONICAL_URL, PUBLIC_BASE_URL, SITE_URL.
    """
    try:
        import streamlit as st

        for key in _URL_KEYS:
            raw = st.secrets.get(key, "")
            if raw:
                return str(raw).strip().rstrip("/")
    except Exception as _exc:
        import logging
        logging.getLogger("seo_streamlit").debug(f"fallo_secrets_url:{type(_exc).__name__}")
    for key in _URL_KEYS:
        raw = os.environ.get(key, "").strip()
        if raw:
            return raw.rstrip("/")
    return ""


def inyectar_redirect_apex_si_configurado(*, canonical_url: Optional[str] = None) -> None:
    """
    Si SITE_URL (u otra) es https://www.dominio... y el usuario abre https://dominio...,
    redirige en el navegador al mismo path en el host www (usa window.top por iframes de Streamlit).
    """
    canon = (canonical_url or resolve_public_site_url() or "").strip().rstrip("/")
    pair = canonical_www_apex_hosts(canon)
    if not pair:
        return
    apex, www_host = pair
    import streamlit as st

    payload = json.dumps({"apex": apex, "wwwHost": www_host}, ensure_ascii=False)
    html = f"""
<div style="display:none" aria-hidden="true"></div>
<script>
(function() {{
  const P = {payload};
  try {{
    const win = window.top;
    if (!win || !win.location) return;
    const h = (win.location.hostname || "").toLowerCase();
    if (h !== P.apex) return;
    const u = new URL(win.location.href);
    u.hostname = P.wwwHost;
    win.location.replace(u.href);
  }} catch (e) {{}}
}})();
</script>
"""
    st.html(html)


def inyectar_head_seo(*, canonical_url: Optional[str] = None) -> None:
    """
    Inserta meta description, Open Graph, Twitter Card, canonical, lang=es y JSON-LD.
    """
    import streamlit as st

    canon = (canonical_url or resolve_public_site_url() or "").strip().rstrip("/")
    schema = schema_software_application(canonical_url=canon)
    payload = {
        "description": META_DESCRIPTION,
        "ogTitle": OG_TITLE,
        "canonical": canon,
        "theme": THEME_COLOR,
        "schemaJson": json.dumps(schema, ensure_ascii=False),
    }
    js_payload = json.dumps(payload, ensure_ascii=False)
    html = f"""
<div style="display:none" aria-hidden="true"></div>
<script>
(function() {{
  const P = {js_payload};
  try {{
    const parentWin = window.parent || window;
    const doc = parentWin && parentWin.document;
    if (!doc) return;
    doc.documentElement.lang = 'es';
    function setMeta(name, content, isProp) {{
      if (content === undefined || content === null || content === '') return;
      const sel = isProp ? 'meta[property="' + name + '"]' : 'meta[name="' + name + '"]';
      let el = doc.querySelector(sel);
      if (!el) {{
        el = doc.createElement('meta');
        if (isProp) el.setAttribute('property', name);
        else el.setAttribute('name', name);
        doc.head.appendChild(el);
      }}
      el.setAttribute('content', content);
    }}
    setMeta('description', P.description);
    setMeta('robots', 'noindex, nofollow');
    setMeta('application-name', 'MediCare Enterprise PRO');
    setMeta('theme-color', P.theme);
    setMeta('og:title', P.ogTitle, true);
    setMeta('og:description', P.description, true);
    setMeta('og:type', 'website', true);
    if (P.canonical) {{
      setMeta('og:url', P.canonical, true);
      let link = doc.querySelector('link[rel="canonical"]');
      if (!link) {{
        link = doc.createElement('link');
        link.setAttribute('rel', 'canonical');
        doc.head.appendChild(link);
      }}
      link.setAttribute('href', P.canonical);
    }}
    setMeta('twitter:card', 'summary_large_image');
    setMeta('twitter:title', P.ogTitle);
    setMeta('twitter:description', P.description);
    const id = 'mc-jsonld-software';
    let s = doc.getElementById(id);
    if (!s) {{
      s = doc.createElement('script');
      s.type = 'application/ld+json';
      s.id = id;
      doc.head.appendChild(s);
    }}
    s.textContent = P.schemaJson;
  }} catch (e) {{}}
}})();
</script>
"""
    st.html(html)
