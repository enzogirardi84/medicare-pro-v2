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


def render_mobile_sidebar_toggle() -> None:
    """
    Boton flotante cliente-side para abrir/cerrar la sidebar en telefonos y tablets.
    """
    html = """
<div id="mc-mobile-sidebar-toggle-anchor" style="height:0;width:0;overflow:hidden;"></div>
<script>
(function() {
  try {
    var parentWin = window.parent && window.parent.document ? window.parent : window;
    var parentDoc = parentWin.document || document;
    if (!parentDoc || !parentDoc.body) return;

    var STYLE_ID = "mc-mobile-sidebar-toggle-style";
    var BUTTON_ID = "mc-mobile-sidebar-toggle-btn";

    function ensureStyle() {
      if (parentDoc.getElementById(STYLE_ID)) return;
      var style = parentDoc.createElement("style");
      style.id = STYLE_ID;
      style.textContent = [
        "#"+BUTTON_ID+"{position:fixed;left:0;top:50%;transform:translateY(-50%);z-index:10015;",
        "display:none;align-items:center;justify-content:center;width:34px;height:54px;padding:0;",
        "border:none;border-radius:0 12px 12px 0;background:linear-gradient(180deg,#14b8a6 0%,#2563eb 100%);",
        "color:#f8fafc;font:900 1rem/1 'Plus Jakarta Sans',sans-serif;letter-spacing:0;",
        "box-shadow:0 10px 22px rgba(2,6,23,.24), inset 0 1px 0 rgba(255,255,255,.16);",
        "cursor:pointer;opacity:.94;}",
        "#"+BUTTON_ID+":active{opacity:1;}",
        "#"+BUTTON_ID+".is-open{background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);}",
        "#"+BUTTON_ID+" .mc-mobile-sidebar-toggle-icon{display:block;line-height:1;transform:translateX(-1px);}",
        "@media (max-width: 900px){#"+BUTTON_ID+"{display:inline-flex;}}",
        "@media (min-width: 901px){#"+BUTTON_ID+"{display:none !important;}}"
      ].join("");
      parentDoc.head.appendChild(style);
    }

    function ensureButton() {
      var btn = parentDoc.getElementById(BUTTON_ID);
      if (btn) return btn;
      btn = parentDoc.createElement("button");
      btn.id = BUTTON_ID;
      btn.type = "button";
      btn.setAttribute("aria-live", "polite");
      btn.addEventListener("click", function(ev) {
        ev.preventDefault();
        toggleSidebar();
      });
      parentDoc.body.appendChild(btn);
      return btn;
    }

    function isMobileViewport() {
      try {
        return !!(parentWin.matchMedia && parentWin.matchMedia("(max-width: 900px)").matches);
      } catch (e) {
        return (parentWin.innerWidth || 1280) <= 900;
      }
    }

    function getOpenControl() {
      return parentDoc.querySelector(
        '[data-testid="stExpandSidebarButton"], [data-testid="stExpandSidebarButton"] button, [data-testid="collapsedControl"] button, [data-testid="collapsedControl"]'
      );
    }

    function getCloseControl() {
      return parentDoc.querySelector('[data-testid="stSidebarCollapseButton"] button, [data-testid="stSidebarCollapseButton"]');
    }

    function getSidebar() {
      return parentDoc.querySelector('[data-testid="stSidebar"]');
    }

    function isVisible(el) {
      if (!el) return false;
      var style = parentWin.getComputedStyle(el);
      if (!style) return false;
      if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity || "1") === 0) return false;
      var rect = el.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    }

    function sidebarIsOpen() {
      var closeControl = getCloseControl();
      if (isVisible(closeControl)) return true;

      var openControl = getOpenControl();
      if (isVisible(openControl)) return false;

      var sidebar = getSidebar();
      if (!sidebar || !isVisible(sidebar)) return false;
      var rect = sidebar.getBoundingClientRect();
      return rect.width > 120 && rect.right > 40 && rect.left > (-rect.width * 0.55);
    }

    function press(el) {
      if (!el) return false;
      try {
        if (typeof el.click === "function") {
          el.click();
          return true;
        }
      } catch (e) {}
      try {
        el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: parentWin }));
        return true;
      } catch (e) {}
      return false;
    }

    function toggleSidebar() {
      if (sidebarIsOpen()) {
        press(getCloseControl());
      } else {
        press(getOpenControl());
      }
      parentWin.setTimeout(syncButton, 180);
      parentWin.setTimeout(syncButton, 520);
    }

    function syncButton() {
      var btn = ensureButton();
      if (!isMobileViewport()) {
        btn.style.display = "none";
        return;
      }
      if (!getSidebar() && !getOpenControl() && !getCloseControl()) {
        btn.style.display = "none";
        return;
      }
      btn.style.display = "inline-flex";
      var open = sidebarIsOpen();
      btn.classList.toggle("is-open", open);
      btn.innerHTML = open
        ? '<span class="mc-mobile-sidebar-toggle-icon" aria-hidden="true">&lt;</span>'
        : '<span class="mc-mobile-sidebar-toggle-icon" aria-hidden="true">&gt;</span>';
      btn.setAttribute("aria-label", open ? "Cerrar panel lateral de herramientas" : "Abrir panel lateral de herramientas");
      btn.setAttribute("title", open ? "Cerrar panel" : "Abrir pacientes");
    }

    ensureStyle();
    syncButton();
    parentWin.setTimeout(syncButton, 700);
    parentWin.setTimeout(syncButton, 1800);

    if (!parentWin.__mcSidebarToggleResizeHook) {
      parentWin.addEventListener("resize", syncButton, { passive: true });
      parentWin.__mcSidebarToggleResizeHook = true;
    }

    parentWin.__mcSidebarToggleSync = syncButton;
  } catch (e) {}
})();
</script>
"""
    components.html(html, height=0, width=0)
