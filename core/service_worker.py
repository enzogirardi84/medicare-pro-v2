"""Service Worker para modo offline y cache progresivo.

Permite que la aplicacion funcione sin conexion a internet,
cacheando recursos estaticos y datos clinicos esenciales.
"""

from __future__ import annotations

import streamlit as st


SW_SCRIPT = """
// Service Worker para MediCare Enterprise PRO - Cache offline
const CACHE_NAME = "medicare-cache-v1";
const STATIC_RESOURCES = [
  "/",
  "/_stcore/health",
];

// Instalacion: precachear recursos estaticos
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_RESOURCES);
    })
  );
  self.skipWaiting();
});

// Activacion: limpiar caches viejos
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      );
    })
  );
});

// Interceptar fetch: cache first, luego red
self.addEventListener("fetch", (event) => {
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request)
        .then((response) => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, clone);
            });
          }
          return response;
        })
        .catch(() => {
          // Fallback: mostrar pagina offline
          return caches.match("/offline.html");
        });
    })
  );
});
"""


def inject_service_worker():
    """Inyecta el Service Worker en la pagina via st.html."""
    sw_js = SW_SCRIPT.replace("\n", " ").replace("  ", " ").strip()
    st.html(
        f"""<script>
try {{
  if ('serviceWorker' in navigator) {{
    // Registrar SW con contenido inline via blob URL
    const blob = new Blob([`{sw_js}`], {{ type: 'application/javascript' }});
    const swUrl = URL.createObjectURL(blob);
    navigator.serviceWorker.register(swUrl, {{ scope: '/' }})
      .then(() => console.log('[SW] Service Worker registrado'))
      .catch((e) => console.warn('[SW] Error registrando SW:', e));
  }}
}} catch(e) {{}}
</script>"""
    )
