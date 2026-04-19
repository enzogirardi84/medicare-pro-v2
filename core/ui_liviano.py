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
    Boton flotante cliente-side para abrir/cerrar la sidebar en telefonos.
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
      var style = parentDoc.getElementById(STYLE_ID);
      if (!style) {
        style = parentDoc.createElement("style");
        style.id = STYLE_ID;
        parentDoc.head.appendChild(style);
      }
      style.textContent = [
        "#"+BUTTON_ID+"{position:fixed;left:0;top:50%;transform:translateY(-50%);z-index:10015;",
        "display:none;align-items:center;justify-content:center;width:34px;height:54px;padding:0;",
        "border:none;border-radius:0 12px 12px 0;background:linear-gradient(180deg,#14b8a6 0%,#2563eb 100%);",
        "color:#f8fafc;font:900 1rem/1 'Plus Jakarta Sans',sans-serif;letter-spacing:0;",
        "box-shadow:0 10px 22px rgba(2,6,23,.24), inset 0 1px 0 rgba(255,255,255,.16);",
        "cursor:pointer;opacity:.94;}",
        "#"+BUTTON_ID+":active{opacity:1;}",
        "#"+BUTTON_ID+".is-open{background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);}",
        "#"+BUTTON_ID+" .mc-mobile-sidebar-toggle-icon{display:block;line-height:1;transform:translateX(-1px);font-size:18px;}",
        "@media (max-width: 767px){#"+BUTTON_ID+"{display:inline-flex;}}",
        "@media (min-width: 768px){#"+BUTTON_ID+"{display:none !important;}}"
      ].join("");
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
        return !!(parentWin.matchMedia && parentWin.matchMedia("(max-width: 767px)").matches);
      } catch (e) {
        return (parentWin.innerWidth || 1280) <= 767;
      }
    }

    function getOpenControl() {
      return parentDoc.querySelector(
        '[data-testid="stExpandSidebarButton"] button, [data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapsedControl"] button, [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] button, [data-testid="collapsedControl"]'
      );
    }

    function getCloseControl() {
      return parentDoc.querySelector('[data-testid="stSidebarCollapseButton"] button, [data-testid="stSidebarCollapseButton"]');
    }

    function getSidebar() {
      return parentDoc.querySelector('[data-testid="stSidebar"]');
    }

    function getSidebarInner() {
      var sidebar = getSidebar();
      if (!sidebar) return null;
      return sidebar.firstElementChild || null;
    }

    function getMainPanel() {
      return (
        parentDoc.querySelector('[data-testid="stAppViewContainer"] > section:nth-child(2)') ||
        parentDoc.querySelector('[data-testid="stMain"]') ||
        parentDoc.querySelector('section.main')
      );
    }

    function getRoot() {
      return parentDoc.documentElement;
    }

    function nativeOpenControlSelectors() {
      return [
        '[data-testid="stSidebarCollapsedControl"]',
        '[data-testid="stSidebarCollapsedControl"] button',
        '[data-testid="collapsedControl"]',
        '[data-testid="collapsedControl"] button',
        '[data-testid="stExpandSidebarButton"]',
        '[data-testid="stExpandSidebarButton"] button',
        '[aria-label="Open sidebar"]'
      ];
    }

    function nativeCloseControlSelectors() {
      return [
        '[data-testid="stSidebarCollapseButton"]',
        '[data-testid="stSidebarCollapseButton"] button',
        '[data-testid="stSidebar"] button[kind="header"]',
        '[data-testid="baseButton-headerNoPadding"]',
        '[data-testid="baseButton-header"]',
        'button[kind="headerNoPadding"]',
        'button[kind="header"]',
        '[aria-label="Close sidebar"]'
      ];
    }

    function setImportant(el, name, value) {
      if (!el) return;
      el.style.setProperty(name, value, "important");
    }

    function clearInlineProps(el, props) {
      if (!el) return;
      for (var i = 0; i < props.length; i += 1) {
        el.style.removeProperty(props[i]);
      }
    }

    function collectUniqueNodes(selectors) {
      var out = [];
      var seen = new Set();
      for (var i = 0; i < selectors.length; i += 1) {
        var nodes = parentDoc.querySelectorAll(selectors[i]);
        for (var j = 0; j < nodes.length; j += 1) {
          var el = nodes[j];
          if (!seen.has(el)) {
            seen.add(el);
            out.push(el);
          }
        }
      }
      return out;
    }

    function isVisible(el) {
      if (!el) return false;
      var style = parentWin.getComputedStyle(el);
      if (!style) return false;
      if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity || "1") === 0) return false;
      var rect = el.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    }

    function sidebarState() {
      // En mobile las clases propias son la fuente de verdad, porque
      // Streamlit no actualiza aria-expanded cuando usamos el toggle custom.
      var root = getRoot();
      if (isMobileViewport() && root) {
        if (root.classList.contains("mc-sidebar-mobile-open")) return "open";
        if (root.classList.contains("mc-sidebar-mobile-closed")) return "closed";
      }

      // Desktop / fallback: aria-expanded del sidebar nativo
      var sidebar = getSidebar();
      if (sidebar) {
        var expanded = sidebar.getAttribute("aria-expanded");
        if (expanded === "true") return "open";
        if (expanded === "false") return "closed";
      }

      // Ultimo fallback: clases en cualquier viewport
      if (root) {
        if (root.classList.contains("mc-sidebar-mobile-open")) return "open";
        if (root.classList.contains("mc-sidebar-mobile-closed")) return "closed";
      }

      return "unknown";
    }

    function setSidebarOpen(open) {
      var root = getRoot();
      if (!root) return;
      if (!isMobileViewport()) {
        root.classList.remove("mc-sidebar-mobile-open");
        root.classList.remove("mc-sidebar-mobile-closed");
        return;
      }
      root.classList.toggle("mc-sidebar-mobile-open", !!open);
      root.classList.toggle("mc-sidebar-mobile-closed", !open);
    }

    function applyMobileSidebarLayout() {
      var sidebar = getSidebar();
      var inner = getSidebarInner();
      var mainPanel = getMainPanel();
      var mobile = isMobileViewport();
      var open = sidebarState() === "open";
      var sidebarProps = [
        "position", "top", "left", "bottom", "z-index", "width", "min-width", "max-width",
        "height", "margin", "padding", "transform", "opacity", "visibility", "pointer-events",
        "border-right", "box-shadow", "overflow", "transition", "will-change"
      ];
      var innerProps = [
        "display", "width", "min-width", "max-width", "height", "opacity", "visibility",
        "pointer-events", "overflow-y", "overflow-x", "padding"
      ];
      var mainProps = ["margin-left", "width", "max-width", "padding-left"];

      if (!mobile) {
        clearInlineProps(sidebar, sidebarProps);
        clearInlineProps(inner, innerProps);
        clearInlineProps(mainPanel, mainProps);
        // Forzar limpieza de width/transform que el modo movil puede haber dejado
        if (sidebar) {
          sidebar.style.removeProperty("width");
          sidebar.style.removeProperty("min-width");
          sidebar.style.removeProperty("max-width");
          sidebar.style.removeProperty("transform");
          sidebar.style.removeProperty("position");
          sidebar.style.removeProperty("visibility");
          sidebar.style.removeProperty("opacity");
        }
        var closeBtn = parentDoc.getElementById("mc-sidebar-close-btn");
        if (closeBtn) closeBtn.style.display = "none";
        return;
      }

      var width = isMobileViewport() ? "100vw" : "min(84vw, 320px)";
      setImportant(sidebar, "position", "fixed");
      setImportant(sidebar, "top", "0");
      setImportant(sidebar, "left", "0");
      setImportant(sidebar, "bottom", "0");
      setImportant(sidebar, "z-index", "10012");
      setImportant(sidebar, "height", "100dvh");
      setImportant(sidebar, "margin", "0");
      setImportant(sidebar, "padding", "0");
      setImportant(sidebar, "transition", "transform 0.18s ease, opacity 0.18s ease, width 0.18s ease");
      setImportant(sidebar, "will-change", "transform, opacity, width");

      if (open) {
        setImportant(sidebar, "width", width);
        setImportant(sidebar, "min-width", width);
        setImportant(sidebar, "max-width", width);
        setImportant(sidebar, "transform", "translateX(0)");
        setImportant(sidebar, "opacity", "1");
        setImportant(sidebar, "visibility", "visible");
        setImportant(sidebar, "pointer-events", "auto");
        setImportant(sidebar, "border-right", "1px solid rgba(148, 163, 184, 0.12)");
        setImportant(sidebar, "box-shadow", "0 16px 34px rgba(2, 6, 23, 0.34)");
        setImportant(sidebar, "overflow", "visible");
      } else {
        setImportant(sidebar, "width", "0px");
        setImportant(sidebar, "min-width", "0px");
        setImportant(sidebar, "max-width", "0px");
        setImportant(sidebar, "transform", "translateX(-100%)");
        setImportant(sidebar, "opacity", "0");
        setImportant(sidebar, "visibility", "hidden");
        setImportant(sidebar, "pointer-events", "none");
        setImportant(sidebar, "border-right", "none");
        setImportant(sidebar, "box-shadow", "none");
        setImportant(sidebar, "overflow", "hidden");
      }

      if (inner) {
        setImportant(inner, "height", "100%");
        setImportant(inner, "padding", "0.75rem 0.65rem");
        setImportant(inner, "overflow-y", "auto");
        setImportant(inner, "overflow-x", "hidden");
        if (open) {
          setImportant(inner, "display", "block");
          setImportant(inner, "width", width);
          setImportant(inner, "min-width", width);
          setImportant(inner, "max-width", width);
          setImportant(inner, "opacity", "1");
          setImportant(inner, "visibility", "visible");
          setImportant(inner, "pointer-events", "auto");
        } else {
          setImportant(inner, "display", "none");
          setImportant(inner, "width", "0px");
          setImportant(inner, "min-width", "0px");
          setImportant(inner, "max-width", "0px");
          setImportant(inner, "opacity", "0");
          setImportant(inner, "visibility", "hidden");
          setImportant(inner, "pointer-events", "none");
        }
      }

      if (mainPanel) {
        setImportant(mainPanel, "margin-left", "0");
        setImportant(mainPanel, "width", "100%");
        setImportant(mainPanel, "max-width", "100%");
        setImportant(mainPanel, "padding-left", "0");
      }
    }

    function syncNativeControls() {
      var mobile = isMobileViewport();
      var open = sidebarState() === "open";
      var openNodes = collectUniqueNodes(nativeOpenControlSelectors());
      var closeNodes = collectUniqueNodes(nativeCloseControlSelectors());
      var props = [
        "display", "position", "left", "top", "transform", "z-index", "width", "height",
        "min-width", "max-width", "min-height", "padding", "border", "border-radius",
        "background", "box-shadow", "visibility", "opacity", "pointer-events", "color",
        "fill", "stroke", "overflow"
      ];

      function showToggle(el) {
        setImportant(el, "display", "inline-flex");
        setImportant(el, "position", "fixed");
        setImportant(el, "left", "0");
        setImportant(el, "top", "50%");
        setImportant(el, "transform", "translateY(-50%)");
        setImportant(el, "z-index", "10016");
        setImportant(el, "width", "34px");
        setImportant(el, "height", "54px");
        setImportant(el, "min-width", "34px");
        setImportant(el, "max-width", "34px");
        setImportant(el, "min-height", "54px");
        setImportant(el, "padding", "0");
        setImportant(el, "border", "none");
        setImportant(el, "border-radius", "0 12px 12px 0");
        setImportant(el, "background", "linear-gradient(180deg,#14b8a6 0%,#2563eb 100%)");
        setImportant(el, "box-shadow", "0 10px 22px rgba(2,6,23,.24), inset 0 1px 0 rgba(255,255,255,.16)");
        setImportant(el, "visibility", "visible");
        setImportant(el, "opacity", "1");
        setImportant(el, "pointer-events", "auto");
        setImportant(el, "overflow", "hidden");
        var svg = el.querySelector ? el.querySelector("svg") : null;
        if (svg) {
          setImportant(svg, "width", "18px");
          setImportant(svg, "height", "18px");
          setImportant(svg, "color", "#f8fafc");
          setImportant(svg, "fill", "#f8fafc");
          setImportant(svg, "stroke", "#f8fafc");
        }
      }

      function hideToggle(el) {
        setImportant(el, "display", "none");
        setImportant(el, "visibility", "hidden");
        setImportant(el, "opacity", "0");
        setImportant(el, "pointer-events", "none");
      }

      function resetToggle(el) {
        clearInlineProps(el, props);
        var svg = el.querySelector ? el.querySelector("svg") : null;
        if (svg) {
          clearInlineProps(svg, ["width", "height", "color", "fill", "stroke"]);
        }
      }

      for (var i = 0; i < openNodes.length; i += 1) {
        if (!mobile) resetToggle(openNodes[i]);
        else if (open) hideToggle(openNodes[i]);
        else showToggle(openNodes[i]);
      }

      for (var j = 0; j < closeNodes.length; j += 1) {
        if (!mobile) resetToggle(closeNodes[j]);
        else if (open) showToggle(closeNodes[j]);
        else hideToggle(closeNodes[j]);
      }
    }

    function press(el) {
      if (!el) return false;
      var target = el;
      if (target && typeof target.matches === "function" && !target.matches("button")) {
        var nestedButton = target.querySelector ? target.querySelector("button") : null;
        if (nestedButton) target = nestedButton;
      }
      var eventNames = ["pointerdown", "mousedown", "touchstart", "pointerup", "mouseup", "touchend", "click"];
      for (var i = 0; i < eventNames.length; i += 1) {
        try {
          target.dispatchEvent(new MouseEvent(eventNames[i], { bubbles: true, cancelable: true, view: parentWin }));
        } catch (e) {}
      }
      try {
        if (typeof target.click === "function") {
          target.click();
          return true;
        }
      } catch (e) {}
      return true;
    }

    function injectMobileCloseBtn() {
      var CLOSE_ID = "mc-sidebar-close-btn";
      if (parentDoc.getElementById(CLOSE_ID)) return;
      var sidebar = getSidebar();
      if (!sidebar) return;
      var inner = sidebar.firstElementChild;
      if (!inner) return;
      var btn = parentDoc.createElement("button");
      btn.id = CLOSE_ID;
      btn.type = "button";
      btn.innerHTML = "&#8249; Cerrar";
      btn.setAttribute("style", [
        "position:fixed;top:12px;left:12px;z-index:10020;",
        "background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);",
        "color:#94a3b8;border:1px solid rgba(148,163,184,0.2);border-radius:10px;",
        "padding:8px 14px;font-size:15px;font-weight:600;cursor:pointer;",
        "display:none;"
      ].join(""));
      btn.addEventListener("click", function(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        setSidebarOpen(false);
        applyMobileSidebarLayout();
        parentWin.setTimeout(syncButton, 60);
      });
      inner.insertBefore(btn, inner.firstChild);
    }

    function syncCloseBtnVisibility(open) {
      var btn = parentDoc.getElementById("mc-sidebar-close-btn");
      if (!btn) return;
      btn.style.display = (open && isMobileViewport()) ? "inline-flex" : "none";
    }

    function toggleSidebar() {
      if (isMobileViewport()) {
        var opening = sidebarState() !== "open";
        setSidebarOpen(opening);
        applyMobileSidebarLayout();
        injectMobileCloseBtn();
        syncCloseBtnVisibility(opening);
        parentWin.setTimeout(syncButton, 90);
        parentWin.setTimeout(syncButton, 240);
      } else {
        var state = sidebarState();
        var done = false;
        if (state === "open") {
          done = press(getCloseControl());
        } else if (state === "closed") {
          done = press(getOpenControl());
        }
        if (!done) {
          done = press(getOpenControl());
        }
        if (!done) {
          press(getCloseControl());
        }
      }
      parentWin.setTimeout(syncButton, 180);
      parentWin.setTimeout(syncButton, 520);
    }

    function syncButton() {
      var btn = ensureButton();
      if (!isMobileViewport()) {
        syncNativeControls();
        setSidebarOpen(false);
        applyMobileSidebarLayout();
        btn.style.display = "none";
        return;
      }
      syncNativeControls();
      if (!getSidebar() && !getOpenControl() && !getCloseControl()) {
        btn.style.display = "none";
        return;
      }
      if (sidebarState() === "unknown") {
        setSidebarOpen(false);
      }
      applyMobileSidebarLayout();
      // Leer aria-expanded directo del DOM — es la fuente mas confiable
      var sidebarEl = getSidebar();
      var ariaVal = sidebarEl ? sidebarEl.getAttribute("aria-expanded") : null;
      var open = ariaVal === "true"
        || (ariaVal === null && sidebarState() === "open");
      btn.style.display = "inline-flex";
      btn.classList.toggle("is-open", open);
      btn.innerHTML = open
        ? '<span class="mc-mobile-sidebar-toggle-icon" aria-hidden="true" style="font-size:20px;line-height:1;">&#8249;</span>'
        : '<span class="mc-mobile-sidebar-toggle-icon" aria-hidden="true" style="font-size:20px;line-height:1;">&#8250;</span>';
      btn.setAttribute("aria-label", open ? "Cerrar panel lateral" : "Abrir panel lateral");
      btn.setAttribute("title", open ? "Cerrar panel" : "Abrir panel");
      injectMobileCloseBtn();
      syncCloseBtnVisibility(open);
    }

    ensureStyle();
    if (isMobileViewport() && sidebarState() === "unknown") {
      setSidebarOpen(false);
    }
    syncNativeControls();
    syncButton();
    parentWin.setTimeout(syncButton, 700);
    parentWin.setTimeout(syncButton, 1800);

    if (!parentWin.__mcSidebarToggleResizeHook) {
      parentWin.addEventListener("resize", syncButton, { passive: true });
      parentWin.__mcSidebarToggleResizeHook = true;
    }

    if (!parentWin.__mcSidebarToggleMutationHook && parentWin.MutationObserver && parentDoc.body) {
      var observer = new parentWin.MutationObserver(function() {
        try {
          parentWin.clearTimeout(parentWin.__mcSidebarToggleMutationTimer);
        } catch (e) {}
        parentWin.__mcSidebarToggleMutationTimer = parentWin.setTimeout(function() {
          syncNativeControls();
          syncButton();
        }, 40);
      });
      observer.observe(parentDoc.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["data-testid", "style", "class", "aria-expanded"]
      });
      parentWin.__mcSidebarToggleMutationHook = true;
    }

    parentWin.__mcSidebarToggleSync = syncButton;
    parentWin.__mcSidebarMobileIsOpen = function() {
      return sidebarState() === "open";
    };
    parentWin.__mcSidebarMobileSetOpen = function(open) {
      setSidebarOpen(!!open);
      syncButton();
    };
    parentWin.__mcSidebarMobileClose = function() {
      setSidebarOpen(false);
      syncButton();
    };
  } catch (e) {}
})();
</script>
"""
    components.html(html, height=0, width=0)
