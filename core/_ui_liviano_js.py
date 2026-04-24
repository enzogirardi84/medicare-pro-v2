"""Fragmentos JavaScript para core/ui_liviano.py.

Extraído de core/ui_liviano.py para reducir el tamaño del módulo principal.
Los strings contienen placeholders {modo_js} y {server_js} que se rellenan en render_mc_liviano_cliente.
"""

# Template JS para detección de equipo liviano. Usar con .format(modo_js=..., server_js=...)
LIVIANO_JS_TEMPLATE = """\
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

    /* --- Deteccion de browser legacy (Android <=8, iOS <=12, sin CSS moderno) --- */
    var isLegacy = false;
    /* Android <= 8 */
    if (av <= 8) isLegacy = true;
    /* iOS <= 12 */
    if (oldIOS) isLegacy = true;
    /* Opera Mini: no soporta WebSocket completo */
    if (operaMini) isLegacy = true;
    /* IE / IEMobile */
    if (oldIE) isLegacy = true;
    /* Samsung Internet < 8 (UA: SamsungBrowser/7) */
    var sbMatch = u.match(/SamsungBrowser\\/([0-9]+)/);
    if (sbMatch && parseInt(sbMatch[1], 10) < 8) isLegacy = true;
    /* UC Browser (muy limitado) */
    if (/UCBrowser/i.test(u)) isLegacy = true;
    /* Deteccion de capacidad: si no soporta CSS custom properties o flexbox gap */
    try {{
      if (typeof CSS !== "undefined" && CSS.supports) {{
        /* :has() requiere Chrome 105+, Safari 15.4+ */
        if (!CSS.supports("selector(:has(*))")) isLegacy = true;
      }} else {{
        /* No hay CSS.supports = browser muy viejo */
        isLegacy = true;
      }}
    }} catch(e) {{ isLegacy = true; }}
    /* RAM muy baja (<=1GB) o 1 core = hardware muy viejo */
    if (typeof dm === "number" && dm <= 1) isLegacy = true;

    if (isLegacy) {{
      root.classList.add("mc-legacy");
    }} else {{
      root.classList.remove("mc-legacy");
    }}
  }} catch (e) {{}}
}})();
</script>
"""

# JS para cerrar el sidebar automáticamente en móviles al navegar (inyectado en main.py)
MOBILE_SIDEBAR_AUTOCLOSE_JS = """
<script>
(function() {
    var MOBILE_QUERY = "(max-width: 767px)";

    function isMobile() {
        try {
            return !!(window.matchMedia && window.matchMedia(MOBILE_QUERY).matches);
        } catch (e) {
            return window.innerWidth <= 767;
        }
    }

    if (isMobile()) {
        document.documentElement.classList.add("mc-sidebar-mobile-closed");
        document.documentElement.classList.remove("mc-sidebar-mobile-open");
    }

    function getSidebar() {
        return document.querySelector('section[data-testid="stSidebar"]');
    }

    function getCollapseButton() {
        return document.querySelector(
            '[data-testid="stSidebarCollapseButton"] button, [data-testid="stSidebarCollapseButton"], [data-testid="stSidebar"] button[kind="header"]'
        );
    }

    function getMobileSidebarBridge() {
        try {
            return window.parent && window.parent !== window ? window.parent : window;
        } catch (e) {
            return window;
        }
    }

    function sidebarIsOpen() {
        try {
            var bridge = getMobileSidebarBridge();
            if (bridge && typeof bridge.__mcSidebarMobileIsOpen === "function") {
                return !!bridge.__mcSidebarMobileIsOpen();
            }
        } catch (e) {}

        var sidebar = getSidebar();
        if (!sidebar) return false;
        var expanded = sidebar.getAttribute("aria-expanded");
        if (expanded === "true") return true;
        if (expanded === "false") return false;

        var rect = sidebar.getBoundingClientRect();
        return rect.width > 48 && rect.left > (-rect.width + 8);
    }

    function syncFloatingToggle() {
        try {
            var parentWin = window.parent && window.parent !== window ? window.parent : window;
            if (parentWin && typeof parentWin.__mcSidebarToggleSync === "function") {
                parentWin.__mcSidebarToggleSync();
            }
        } catch (e) {}
    }

    function closeSidebar() {
        if (!isMobile() || !sidebarIsOpen()) return false;
        try {
            var bridge = getMobileSidebarBridge();
            if (bridge && typeof bridge.__mcSidebarMobileClose === "function") {
                bridge.__mcSidebarMobileClose();
                syncFloatingToggle();
                return true;
            }
        } catch (e) {}
        var collapseBtn = getCollapseButton();
        if (!collapseBtn) return false;
        collapseBtn.click();
        syncFloatingToggle();
        return true;
    }

    function shouldCloseFromSidebarTarget(target) {
        if (!target || !target.closest) return false;
        if (target.closest('[data-testid="stSidebarCollapseButton"], [data-testid="stSidebar"] button[kind="header"]')) {
            return false;
        }
        return !!target.closest('button, [role="button"], a, label');
    }

    function clickCameFromFloatingToggle(target) {
        if (!target || !target.closest) return false;
        return !!target.closest('#mc-mobile-sidebar-toggle-btn-v2');
    }

    function setupMobileSidebar() {
        if (window.__mcMobileSidebarAutoCloseInstalled) return;
        window.__mcMobileSidebarAutoCloseInstalled = true;

        setTimeout(function() {
            var sidebar = getSidebar();
            if (sidebar && sidebarIsOpen()) {
                var closed = closeSidebar();
                if (closed) {
                    syncFloatingToggle();
                }
            }
        }, 800);

        document.addEventListener('click', function(e) {
            if (!isMobile()) return;
            if (clickCameFromFloatingToggle(e.target)) return;
            var sidebar = getSidebar();
            if (!sidebar || !sidebarIsOpen()) return;
            if (sidebar.contains(e.target) && shouldCloseFromSidebarTarget(e.target)) {
                window.setTimeout(closeSidebar, 180);
                return;
            }
            if (!sidebar.contains(e.target)) {
                var rect = sidebar.getBoundingClientRect();
                if (rect.width > 50 && rect.left >= 0) {
                    setTimeout(closeSidebar, 150);
                }
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupMobileSidebar);
    } else {
        setupMobileSidebar();
    }

    window.setTimeout(syncFloatingToggle, 160);
    window.setTimeout(syncFloatingToggle, 700);
    window.setTimeout(syncFloatingToggle, 1800);

    window.addEventListener('load', function() {
        setupMobileSidebar();
        syncFloatingToggle();
    });
})();
</script>
"""

# JS para el toggle móvil de sidebar (sin placeholders — string literal directo)
SIDEBAR_TOGGLE_JS = """
<!-- rev-2026-04-23-02 -->
<div id="mc-mobile-sidebar-toggle-anchor" style="height:0;width:0;overflow:hidden;"></div>
<script>
(function() {
  try {
    var parentWin = window.parent && window.parent.document ? window.parent : window;
    var parentDoc = parentWin.document || document;
    if (!parentDoc || !parentDoc.body) return;

    // Invalidar cache: remover elementos viejos del DOM para forzar recreación
    var oldStyle = parentDoc.getElementById("mc-mobile-sidebar-toggle-style");
    if (oldStyle) oldStyle.remove();
    var oldBtn = parentDoc.getElementById("mc-mobile-sidebar-toggle-btn");
    if (oldBtn) oldBtn.remove();

    var STYLE_ID = "mc-mobile-sidebar-toggle-style-v2";
    var BUTTON_ID = "mc-mobile-sidebar-toggle-btn-v2";

    function ensureStyle() {
      var style = parentDoc.getElementById(STYLE_ID);
      if (!style) {
        style = parentDoc.createElement("style");
        style.id = STYLE_ID;
        parentDoc.head.appendChild(style);
      }
      style.textContent = [
        /* Ocultar SIEMPRE los botones nativos de Streamlit >> y << para evitar duplicado */
        "[data-testid='stSidebarCollapsedControl'],[data-testid='collapsedControl'],[data-testid='stExpandSidebarButton']{display:none !important;visibility:hidden !important;pointer-events:none !important;}",
        /* Botón custom — estado CERRADO: botón ancho con texto */
        "#"+BUTTON_ID+"{position:fixed;left:12px;top:12px;z-index:10015;",
        "display:none;align-items:center;justify-content:center;",
        "width:auto;min-width:44px;height:44px;padding:0 14px 0 12px;",
        "border:none;border-radius:14px;",
        "background:rgba(255,255,255,0.08);",
        "backdrop-filter:blur(16px) saturate(1.6);-webkit-backdrop-filter:blur(16px) saturate(1.6);",
        "color:#f8fafc;font:700 0.78rem/1 'Plus Jakarta Sans',sans-serif;letter-spacing:0.06em;",
        "gap:6px;white-space:nowrap;",
        "box-shadow:0 8px 28px rgba(2,6,23,.30), inset 0 1px 0 rgba(255,255,255,.08);",
        "border:1px solid rgba(255,255,255,0.12);",
        "cursor:pointer;opacity:.82;transition:opacity 0.15s,width 0.18s,background 0.2s;}",
        "#"+BUTTON_ID+":active{opacity:1;transform:scale(0.96);}",
        /* Estado ABIERTO: flechita pequeña arriba a la izquierda, mismo estilo glass */
        "#"+BUTTON_ID+".is-open{width:32px;min-width:32px;height:32px;padding:0;",
        "background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.12);",
        "backdrop-filter:blur(16px) saturate(1.6);-webkit-backdrop-filter:blur(16px) saturate(1.6);",
        "border-radius:10px;box-shadow:0 4px 14px rgba(2,6,23,.25);gap:0;}",
        "#"+BUTTON_ID+" .mc-btn-icon{font-size:20px;line-height:1;}",
        "#"+BUTTON_ID+" .mc-btn-label{font-size:0.75rem;font-weight:700;letter-spacing:0.05em;}",
        "#"+BUTTON_ID+".is-open .mc-btn-label{display:none !important;}",
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
      var root = getRoot();
      if (isMobileViewport() && root) {
        if (root.classList.contains("mc-sidebar-mobile-open")) return "open";
        if (root.classList.contains("mc-sidebar-mobile-closed")) return "closed";
      }
      var sidebar = getSidebar();
      if (sidebar) {
        var expanded = sidebar.getAttribute("aria-expanded");
        if (expanded === "true") return "open";
        if (expanded === "false") return "closed";
      }
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

      /* Siempre ocultar controles nativos — nuestro botón custom los reemplaza */
      for (var i = 0; i < openNodes.length; i += 1) {
        hideToggle(openNodes[i]);
      }
      for (var j = 0; j < closeNodes.length; j += 1) {
        if (mobile) hideToggle(closeNodes[j]);
        else resetToggle(closeNodes[j]);
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
      var open = sidebarState() === "open";
      btn.style.display = "inline-flex";
      btn.classList.toggle("is-open", open);
      if (open) {
        btn.innerHTML = '<span class="mc-btn-icon" aria-hidden="true">&#8249;</span>';
        btn.setAttribute("aria-label", "Cerrar panel lateral");
        btn.setAttribute("title", "Cerrar panel");
      } else {
        btn.innerHTML = '<span class="mc-btn-icon" aria-hidden="true">&#9776;</span><span class="mc-btn-label">Pacientes</span>';
        btn.setAttribute("aria-label", "Abrir panel de pacientes");
        btn.setAttribute("title", "Abrir panel de pacientes");
      }
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
