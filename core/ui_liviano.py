"""
Detección de equipos antiguos o limitados para activar modo UI liviano (menos sombras, sin blur, menos animaciones).

- Servidor: User-Agent y cabecera Save-Data (si Streamlit expone headers).
- Cliente: heurísticas en el navegador (Android/iOS viejos, RAM/cores, saveData).
"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

import streamlit as st
import streamlit.components.v1 as components


def _get_header(headers: Any, name: str) -> str:
    if headers is None:
        return ""
    if isinstance(headers, Mapping):
        v = headers.get(name)
        if v is not None:
            return str(v)
        low = name.lower()
        for k, val in headers.items():
            if str(k).lower() == low:
                return str(val)
    return ""


def _ctx_headers() -> Any:
    """Cabeceras HTTP del request (un solo acceso a st.context por uso)."""
    try:
        ctx = getattr(st, "context", None)
        if ctx is None:
            return None
        return getattr(ctx, "headers", None)
    except Exception:
        return None


def user_agent_sugiere_equipo_liviano(user_agent: str) -> bool:
    if not user_agent:
        return False
    u = user_agent.lower()

    if "opera mini" in u or "iemobile" in u or "msie " in u:
        return True

    m = re.search(r"android\s+(\d+)", u)
    if m and int(m.group(1)) <= 9:
        return True

    if "iphone" in u or "ipad" in u or "ipod" in u:
        m = re.search(r"(?:iphone os|cpu os|cpu iphone os)\s+(\d+)", u)
        if m and int(m.group(1)) <= 12:
            return True
        m = re.search(r"os (\d+)[_.]", u)
        if m and int(m.group(1)) <= 12:
            return True

    return False


def user_agent_desde_contexto() -> str:
    h = _ctx_headers()
    return _get_header(h, "user-agent") if h else ""


def headers_sugieren_equipo_liviano() -> bool:
    try:
        headers = _ctx_headers()
        if not headers:
            return False
        save = _get_header(headers, "save-data").strip().lower()
        if save == "on":
            return True
        ua = _get_header(headers, "user-agent")
        return user_agent_sugiere_equipo_liviano(ua)
    except Exception:
        return False


def user_agent_es_telefono_movil_probable(user_agent: str) -> bool:
    """
    PC de escritorio → False. Teléfonos (iPhone, Android típico) → True.
    Tablets: heurística conservadora (muchas usan UA tipo desktop en iPadOS).
    """
    if not user_agent:
        return False
    u = user_agent.lower()
    if "ipad" in u or "tablet" in u:
        return False
    if "iphone" in u or "ipod" in u:
        return True
    if "android" in u:
        if "mobile" in u:
            return True
        # Tablets Android a veces sin "Mobile"; modelos comunes tablet en UA
        if any(x in u for x in ("sm-t", "gt-p", "tab-", " lenovo tb-", " huawei mediapad")):
            return False
        return True
    if "windows phone" in u or "blackberry" in u:
        return True
    return False


def user_agent_es_tablet_probable(user_agent: str) -> bool:
    """
    Detecta tablets específicamente para optimización UI.
    Tablets tienen más espacio de pantalla que teléfonos.
    """
    if not user_agent:
        return False
    u = user_agent.lower()
    # Tablets directas
    if "ipad" in u or "tablet" in u:
        return True
    # iPadOS 13+ usa UA tipo desktop, pero tiene Macintosh + touch
    if "macintosh" in u and "ipad" not in u:
        if "touch" in u:
            return True
    # Modelos específicos de tablets Android
    if any(x in u for x in ("sm-t", "gt-p", "tab-", "lenovo tb-", "huawei mediapad", "kindle")):
        return True
    return False


def datos_compactos_por_cliente_sugerido() -> bool:
    """
    Sustituye el checkbox «Modo celular viejo»: listas/tablas más cortas en Python
    cuando el cliente parece móvil o el servidor detecta equipo limitado (UA/Save-Data).
    """
    try:
        headers = _ctx_headers()
        if not headers:
            return False
        save = _get_header(headers, "save-data").strip().lower()
        if save == "on":
            return True
        ua = _get_header(headers, "user-agent")
        if user_agent_sugiere_equipo_liviano(ua):
            return True
        return user_agent_es_telefono_movil_probable(ua)
    except Exception:
        return False


def render_mc_liviano_cliente(modo: str, server_hint: bool) -> None:
    """
    modo: 'auto' | 'on' | 'off'
    server_hint: True si el servidor sugiere liviano (UA / Save-Data).
    """
    modo = modo if modo in ("auto", "on", "off") else "auto"
    modo_js = json.dumps(modo)
    server_js = "true" if server_hint else "false"

    html = f"""
<div id="mc-liviano-anchor" style="height:0;width:0;overflow:hidden;"></div>
<script>
(function() {{
  try {{
    var root = window.parent && window.parent.document ? window.parent.document.documentElement : document.documentElement;
    if (!root) return;
    var MODO = {modo_js};
    var SERVER_HINT = {server_js};

    function applyLiviano(on) {{
      if (on) root.classList.add("mc-equipo-liviano");
      else root.classList.remove("mc-equipo-liviano");
    }}

    if (MODO === "off") {{
      applyLiviano(false);
      return;
    }}
    if (MODO === "on") {{
      applyLiviano(true);
      return;
    }}

    var u = navigator.userAgent || "";
    var verAndroid = u.match(/Android\\s+([0-9]+)/);
    var av = verAndroid ? parseInt(verAndroid[1], 10) : 100;
    var oldAndroid = av <= 9;

    var oldIOS = false;
    if (/iPhone|iPad|iPod/i.test(u)) {{
      var m1 = u.match(/(?:iPhone OS|CPU OS|CPU iPhone OS)\\s+([0-9]+)/i);
      var m2 = u.match(/OS\\s+([0-9]+)[_.]/i);
      var ios = m1 ? parseInt(m1[1], 10) : (m2 ? parseInt(m2[1], 10) : 100);
      oldIOS = ios <= 12;
    }}

    var operaMini = /Opera Mini/i.test(u);
    var oldIE = /MSIE |Trident\\/|IEMobile/i.test(u);

    var dm = navigator.deviceMemory;
    var hc = navigator.hardwareConcurrency;
    var lowSpec = (typeof dm === "number" && dm <= 2 && typeof hc === "number" && hc <= 4);

    var saveData = false;
    try {{
      var c = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
      if (c && c.saveData === true) saveData = true;
    }} catch (e) {{}}

    var want = SERVER_HINT || saveData || oldAndroid || oldIOS || operaMini || oldIE || lowSpec;
    applyLiviano(!!want);
  }} catch (e) {{}}
}})();
</script>
"""
    components.html(html, height=0, width=0)
