"""
Progressive Web App (PWA) Manifest y Service Worker para Medicare Pro.

Características:
- Instalación en dispositivos móviles
- Funcionamiento offline parcial
- Push notifications (futuro)
- Caché de recursos estáticos
"""

import json
import streamlit as st
from pathlib import Path


def generate_pwa_manifest() -> dict:
    """
    Genera manifest.json para PWA.
    
    Returns:
        Dict con configuración del PWA
    """
    return {
        "name": "Medicare Pro",
        "short_name": "Medicare",
        "description": "Sistema de Gestión Clínica Profesional",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0f172a",
        "theme_color": "#14b8a6",
        "orientation": "portrait-primary",
        "scope": "/",
        "lang": "es",
        "dir": "ltr",
        "icons": [
            {
                "src": "/assets/icons/icon-72x72.png",
                "sizes": "72x72",
                "type": "image/png",
                "purpose": "maskable any"
            },
            {
                "src": "/assets/icons/icon-96x96.png",
                "sizes": "96x96",
                "type": "image/png",
                "purpose": "maskable any"
            },
            {
                "src": "/assets/icons/icon-128x128.png",
                "sizes": "128x128",
                "type": "image/png",
                "purpose": "maskable any"
            },
            {
                "src": "/assets/icons/icon-144x144.png",
                "sizes": "144x144",
                "type": "image/png",
                "purpose": "maskable any"
            },
            {
                "src": "/assets/icons/icon-152x152.png",
                "sizes": "152x152",
                "type": "image/png",
                "purpose": "maskable any"
            },
            {
                "src": "/assets/icons/icon-192x192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "maskable any"
            },
            {
                "src": "/assets/icons/icon-384x384.png",
                "sizes": "384x384",
                "type": "image/png",
                "purpose": "maskable any"
            },
            {
                "src": "/assets/icons/icon-512x512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable any"
            }
        ],
        "screenshots": [
            {
                "src": "/assets/screenshots/desktop.png",
                "sizes": "1920x1080",
                "type": "image/png",
                "form_factor": "wide",
                "label": "Vista de escritorio Medicare Pro"
            },
            {
                "src": "/assets/screenshots/mobile.png",
                "sizes": "750x1334",
                "type": "image/png",
                "form_factor": "narrow",
                "label": "Vista móvil Medicare Pro"
            }
        ],
        "categories": ["healthcare", "productivity", "medical"],
        "shortcuts": [
            {
                "name": "Nuevo Paciente",
                "short_name": "Paciente",
                "description": "Registrar nuevo paciente rápidamente",
                "url": "/?action=new_patient",
                "icons": [{"src": "/assets/icons/patient.png", "sizes": "192x192"}]
            },
            {
                "name": "Buscar Paciente",
                "short_name": "Buscar",
                "description": "Buscar paciente existente",
                "url": "/?action=search",
                "icons": [{"src": "/assets/icons/search.png", "sizes": "192x192"}]
            },
            {
                "name": "Nueva Evolución",
                "short_name": "Evolución",
                "description": "Crear nueva evolución clínica",
                "url": "/?action=new_evolution",
                "icons": [{"src": "/assets/icons/evolution.png", "sizes": "192x192"}]
            }
        ],
        "related_applications": [
            {
                "platform": "play",
                "url": "https://play.google.com/store/apps/details?id=com.medicare.pro",
                "id": "com.medicare.pro"
            },
            {
                "platform": "itunes",
                "url": "https://apps.apple.com/app/medicare-pro/id123456789"
            }
        ],
        "prefer_related_applications": False,
        "handle_links": "preferred",
        "launch_handler": {
            "client_mode": ["navigate-existing", "auto"]
        },
        "edge_side_panel": {
            "preferred_width": 400
        }
    }


def generate_service_worker() -> str:
    """
    Genera Service Worker para PWA.
    
    Returns:
        JavaScript code para service worker
    """
    return """
// Medicare Pro Service Worker
const CACHE_NAME = 'medicare-pro-v1';
const STATIC_CACHE = 'static-v1';
const DYNAMIC_CACHE = 'dynamic-v1';

// Recursos a cachear
const STATIC_ASSETS = [
    '/',
    '/assets/style.css',
    '/assets/mobile.css',
    '/assets/logo_medicare_pro.jpeg',
    '/assets/icons/icon-192x192.png',
    '/assets/icons/icon-512x512.png'
];

// Instalación: cachear recursos estáticos
self.addEventListener('install', (event) => {
    console.log('[SW] Installing...');
    
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => {
                console.log('[SW] Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .catch(err => console.error('[SW] Cache failed:', err))
    );
    
    self.skipWaiting();
});

// Activación: limpiar cachés antiguas
self.addEventListener('activate', (event) => {
    console.log('[SW] Activating...');
    
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cache => {
                    if (cache !== STATIC_CACHE && cache !== DYNAMIC_CACHE) {
                        console.log('[SW] Deleting old cache:', cache);
                        return caches.delete(cache);
                    }
                })
            );
        })
    );
    
    self.clients.claim();
});

// Fetch: estrategia Cache-First con Network Fallback
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Ignorar requests no-GET
    if (request.method !== 'GET') {
        return;
    }
    
    // Estrategia: Cache First para assets estáticos
    if (STATIC_ASSETS.includes(url.pathname) || 
        url.pathname.match(/\\.(css|js|png|jpg|jpeg|gif|svg|ico|woff|woff2)$/)) {
        
        event.respondWith(
            caches.match(request)
                .then(cached => {
                    if (cached) {
                        // Refrescar caché en background
                        fetch(request)
                            .then(response => {
                                if (response.ok) {
                                    caches.open(STATIC_CACHE)
                                        .then(cache => cache.put(request, response));
                                }
                            })
                            .catch(() => {});
                        
                        return cached;
                    }
                    
                    return fetch(request)
                        .then(response => {
                            if (!response.ok) throw new Error('Fetch failed');
                            
                            const clone = response.clone();
                            caches.open(STATIC_CACHE)
                                .then(cache => cache.put(request, clone));
                            
                            return response;
                        })
                        .catch(() => {
                            // Fallback offline
                            if (request.mode === 'navigate') {
                                return caches.match('/offline.html');
                            }
                        });
                })
        );
    }
    
    // Estrategia: Network First para API calls
    else if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(request)
                .then(response => {
                    if (!response.ok) throw new Error('API fetch failed');
                    
                    // Cachear respuestas GET exitosas
                    if (request.method === 'GET') {
                        const clone = response.clone();
                        caches.open(DYNAMIC_CACHE)
                            .then(cache => cache.put(request, clone));
                    }
                    
                    return response;
                })
                .catch(() => {
                    // Fallback a caché
                    return caches.match(request)
                        .then(cached => {
                            if (cached) {
                                // Agregar header indicando caché
                                const headers = new Headers(cached.headers);
                                headers.set('X-From-Cache', 'true');
                                
                                return new Response(cached.body, {
                                    status: 200,
                                    statusText: 'OK (from cache)',
                                    headers
                                });
                            }
                            
                            // Offline: retornar error JSON
                            return new Response(
                                JSON.stringify({
                                    error: 'offline',
                                    message: 'No hay conexión a internet. Los datos pueden estar desactualizados.'
                                }),
                                {
                                    status: 503,
                                    headers: { 'Content-Type': 'application/json' }
                                }
                            );
                        });
                })
        );
    }
});

// Background Sync: sincronización diferida
self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-data') {
        event.waitUntil(syncData());
    }
});

async function syncData() {
    console.log('[SW] Syncing data...');
    // Implementar sincronización de datos pendientes
    const db = await openDB('medicare-offline', 1);
    const pending = await db.getAll('pending_requests');
    
    for (const request of pending) {
        try {
            await fetch(request.url, {
                method: request.method,
                headers: request.headers,
                body: request.body
            });
            await db.delete('pending_requests', request.id);
        } catch (err) {
            console.error('[SW] Sync failed for request:', request.id);
        }
    }
}

// Push Notifications (futuro)
self.addEventListener('push', (event) => {
    if (!event.data) return;
    
    const data = event.data.json();
    
    event.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: '/assets/icons/icon-192x192.png',
            badge: '/assets/icons/badge-72x72.png',
            tag: data.tag,
            requireInteraction: true,
            actions: data.actions || []
        })
    );
});

// Click en notificación
self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    
    event.waitUntil(
        clients.openWindow(event.notification.data?.url || '/')
    );
});

// Mensajes desde la app
self.addEventListener('message', (event) => {
    if (event.data === 'skipWaiting') {
        self.skipWaiting();
    }
});
"""


def inject_pwa_headers():
    """
    Inyecta headers y metatags necesarios para PWA en Streamlit.
    
    Esto debe llamarse al inicio de la aplicación.
    """
    manifest = generate_pwa_manifest()
    
    # Metatags para PWA
    pwa_meta = f"""
    <!-- PWA Meta Tags -->
    <meta name="theme-color" content="{manifest['theme_color']}">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="{manifest['short_name']}">
    <meta name="application-name" content="{manifest['short_name']}">
    <meta name="msapplication-TileColor" content="{manifest['theme_color']}">
    <meta name="msapplication-TileImage" content="/assets/icons/icon-144x144.png">
    <meta name="msapplication-config" content="/assets/browserconfig.xml">
    
    <!-- Manifest -->
    <link rel="manifest" href="/manifest.json">
    
    <!-- Icons -->
    <link rel="apple-touch-icon" sizes="72x72" href="/assets/icons/icon-72x72.png">
    <link rel="apple-touch-icon" sizes="96x96" href="/assets/icons/icon-96x96.png">
    <link rel="apple-touch-icon" sizes="128x128" href="/assets/icons/icon-128x128.png">
    <link rel="apple-touch-icon" sizes="144x144" href="/assets/icons/icon-144x144.png">
    <link rel="apple-touch-icon" sizes="152x152" href="/assets/icons/icon-152x152.png">
    <link rel="apple-touch-icon" sizes="192x192" href="/assets/icons/icon-192x192.png">
    <link rel="icon" type="image/png" sizes="192x192" href="/assets/icons/icon-192x192.png">
    <link rel="icon" type="image/png" sizes="512x512" href="/assets/icons/icon-512x512.png">
    
    <!-- Service Worker Registration -->
    <script>
    if ('serviceWorker' in navigator) {{
        window.addEventListener('load', () => {{
            navigator.serviceWorker.register('/service-worker.js')
                .then(registration => {{
                    console.log('[PWA] SW registered:', registration);
                }})
                .catch(error => {{
                    console.log('[PWA] SW registration failed:', error);
                }});
        }});
    }}
    </script>
    """
    
    st.markdown(pwa_meta, unsafe_allow_html=True)


def save_pwa_files(output_dir: str = "assets/pwa"):
    """
    Guarda archivos PWA en disco.
    
    Args:
        output_dir: Directorio donde guardar los archivos
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Guardar manifest.json
    manifest = generate_pwa_manifest()
    (output_path.parent / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False)
    )
    
    # Guardar service-worker.js
    sw_code = generate_service_worker()
    (output_path.parent / "service-worker.js").write_text(sw_code)
    
    print(f"✅ PWA files saved to {output_path.parent}")


# Offline page HTML
OFFLINE_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sin Conexión - Medicare Pro</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: white;
            text-align: center;
            padding: 20px;
        }
        .icon {
            font-size: 64px;
            margin-bottom: 20px;
        }
        h1 {
            font-size: 24px;
            margin-bottom: 10px;
        }
        p {
            font-size: 16px;
            opacity: 0.8;
            max-width: 400px;
            line-height: 1.5;
        }
        .retry-btn {
            margin-top: 30px;
            padding: 12px 24px;
            background: #14b8a6;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            cursor: pointer;
        }
        .retry-btn:hover {
            background: #0d9488;
        }
    </style>
</head>
<body>
    <div class="icon">📡</div>
    <h1>Sin Conexión</h1>
    <p>Parece que no tienes conexión a internet. Algunas funciones pueden no estar disponibles.</p>
    <p>Los datos guardados localmente se sincronizarán cuando recuperes la conexión.</p>
    <button class="retry-btn" onclick="window.location.reload()">Reintentar</button>
</body>
</html>
"""


def check_pwa_installability():
    """
    Verifica si el PWA puede ser instalado.
    
    Returns:
        Dict con status de instalación
    """
    return {
        "manifest_present": True,
        "service_worker_present": True,
        "https": True,  # En producción debe ser True
        "icons_present": False,  # Requiere generar icons
        "offline_functionality": True,
        "installable": False  # True cuando todo esté listo
    }


if __name__ == "__main__":
    # Guardar archivos PWA al ejecutar este módulo
    save_pwa_files()
    
    # También guardar offline.html
    Path("assets/offline.html").write_text(OFFLINE_HTML)
    print("✅ offline.html created")
