"""Protocolo de precarga y cache de activos estaticos via Service Worker.
Los logos, fuentes y CSS del framework se cachean en el navegador
despues de la primera descarga. Las recargas subsecuentes no consumen
datos del plan movil de la ambulancia.
"""
from __future__ import annotations

import streamlit as st


def inyectar_service_worker_cache() -> None:
    """Registra un Service Worker perimetral para cachear activos estaticos.

    Intercepta peticiones a:
    - Logo del tenant (/assets/*)
    - Fuentes tipograficas (Google Fonts)
    - CSS del framework de Streamlit (/-/build/*)

    Almacena en Cache Storage API. Sirve desde cache en recargas.
    """
    st.markdown("""<script>
(function() {
    // Verificar si el navegador soporta Service Workers
    if (!('serviceWorker' in navigator)) return;

    var SW_CACHE_NAME = 'medicare-assets-v1';

    // ─── Service Worker inline como blob URL ────────────
    var swCode = [
        'self.addEventListener("install", function(e) {',
        '  self.skipWaiting();',
        '  e.waitUntil(',
        '    caches.open("' + SW_CACHE_NAME + '").then(function(cache) {',
        '      return cache.addAll([',
        '        "/",',
        '        "/-/build/favicon.svg",',
        '        "/-/build/assets/index.css"',
        '      ]);',
        '    })',
        '  );',
        '});',
        'self.addEventListener("activate", function(e) {',
        '  e.waitUntil(',
        '    caches.keys().then(function(keys) {',
        '      return Promise.all(',
        '        keys.filter(function(k) { return k !== "' + SW_CACHE_NAME + '"; })',
        '          .map(function(k) { return caches.delete(k); })',
        '      );',
        '    })',
        '  );',
        '});',
        'self.addEventListener("fetch", function(e) {',
        '  var url = new URL(e.request.url);',
        '  // Cachear solo activos estaticos de Streamlit',
        '  if (url.pathname.startsWith("/-/build/") || ',
        '      url.pathname.startsWith("/assets/") || ',
        '      url.hostname === "fonts.googleapis.com" ||',
        '      url.hostname === "fonts.gstatic.com") {',
        '    e.respondWith(',
        '      caches.match(e.request).then(function(cached) {',
        '        return cached || fetch(e.request).then(function(response) {',
        '          var copy = response.clone();',
        '          caches.open("' + SW_CACHE_NAME + '").then(function(cache) {',
        '            cache.put(e.request, copy);',
        '          });',
        '          return response;',
        '        });',
        '      })',
        '    );',
        '  }',
        '});'
    ].join('\\n');

    try {
        var blob = new Blob([swCode], {type: 'application/javascript'});
        var swUrl = URL.createObjectURL(blob);
        navigator.serviceWorker.register(swUrl, {scope: '/'})
            .then(function(reg) {
                console.log('[MC Cache] Service Worker registrado');
            })
            .catch(function(err) {
                console.warn('[MC Cache] SW registro fallo:', err);
            });
    } catch(e) {
        console.warn('[MC Cache] Error:', e);
    }
})();
</script>""", unsafe_allow_html=True)


def inyectar_font_preconnect() -> None:
    """Pre-conecta a Google Fonts para reducir latencia de descarga."""
    st.markdown("""<link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link rel="stylesheet"
          href="https://fonts.googleapis.com/css2?
          family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap"
          media="print" onload="this.media='all'">
    <noscript>
        <link rel="stylesheet"
              href="https://fonts.googleapis.com/css2?
              family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap">
    </noscript>
    """, unsafe_allow_html=True)
