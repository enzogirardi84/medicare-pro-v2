"""Skeleton loaders de marca con shimmer effect acelerado por GPU.
Muestra un armazon estatico traslucido mientras el modulo lazy carga.
Elimina la pantalla gris vacia de Streamlit.
"""
from __future__ import annotations

import streamlit as st


def inyectar_skeleton_loader() -> None:
    """Inyecta CSS para skeleton loaders animados con shimmer effect.

    El skeleton se activa con la clase CSS .mc-skeleton-active.
    Se compone de:
    - Barra lateral simulada (bloque estrecho)
    - 3 cards de metricas rectangulares
    - Animacion shimmer (barrido de brillo)
    """
    st.markdown("""<style>
    /* ════════════════════════════════════════════════════════
       SKELETON LOADER: contenedor base
       ════════════════════════════════════════════════════════ */
    @keyframes mc-shimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }

    .mc-skeleton {
        display: none;
        position: relative;
        min-height: 100vh;
        background: rgba(8,16,30,0.95);
        overflow: hidden;
    }

    .mc-skeleton-active .mc-skeleton {
        display: block !important;
    }

    /* ─── Shimmer universal ────────────────────────────── */
    .mc-skeleton-shimmer {
        background: linear-gradient(
            90deg,
            rgba(15,23,42,0.4) 25%,
            rgba(30,41,59,0.6) 50%,
            rgba(15,23,42,0.4) 75%
        ) !important;
        background-size: 200% 100% !important;
        animation: mc-shimmer 1.8s ease-in-out infinite !important;
        will-change: background-position !important;
        border-radius: 12px !important;
    }

    /* ─── Sidebar skeleton ─────────────────────────────── */
    .mc-skeleton-sidebar {
        position: fixed;
        left: 0;
        top: 0;
        width: 240px;
        height: 100vh;
        padding: 16px;
        background: rgba(12,25,41,0.9);
        border-right: 1px solid rgba(100,180,255,0.06);
    }
    .mc-skeleton-sidebar-item {
        height: 20px;
        margin-bottom: 12px;
        width: 80%;
    }
    .mc-skeleton-sidebar-item:nth-child(2) { width: 60%; }
    .mc-skeleton-sidebar-item:nth-child(3) { width: 70%; }
    .mc-skeleton-sidebar-item:nth-child(4) { width: 55%; }
    .mc-skeleton-sidebar-item:nth-child(5) { width: 65%; }

    /* ─── Main content skeleton ────────────────────────── */
    .mc-skeleton-main {
        margin-left: 260px;
        padding: 24px;
    }
    .mc-skeleton-header {
        height: 32px;
        width: 40%;
        margin-bottom: 24px;
    }
    .mc-skeleton-cards {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 16px;
        margin-bottom: 24px;
    }
    .mc-skeleton-card {
        height: 100px;
        border-radius: 14px;
    }
    .mc-skeleton-table {
        height: 200px;
        border-radius: 14px;
    }
    .mc-skeleton-table-row {
        height: 28px;
        margin-bottom: 8px;
        width: 100%;
    }
    .mc-skeleton-table-row:last-child { width: 70%; }

    /* ─── Ocultar contenido real mientras skeleton activo ── */
    .mc-skeleton-active section[data-testid="stAppViewContainer"] > div:not(.mc-skeleton) {
        opacity: 0 !important;
        pointer-events: none !important;
    }

    /* ════════════════════════════════════════════════════════
       REDUCED MOTION
       ════════════════════════════════════════════════════════ */
    @media (prefers-reduced-motion: reduce) {
        .mc-skeleton-shimmer {
            animation: none !important;
            background: rgba(15,23,42,0.3) !important;
        }
    }
    </style>

    <!-- HTML del skeleton (oculto por defecto) -->
    <div class="mc-skeleton">
        <div class="mc-skeleton-sidebar">
            <div class="mc-skeleton-shimmer mc-skeleton-sidebar-item"></div>
            <div class="mc-skeleton-shimmer mc-skeleton-sidebar-item"></div>
            <div class="mc-skeleton-shimmer mc-skeleton-sidebar-item"></div>
            <div class="mc-skeleton-shimmer mc-skeleton-sidebar-item"></div>
            <div class="mc-skeleton-shimmer mc-skeleton-sidebar-item"></div>
            <div style="height:40px;"></div>
            <div class="mc-skeleton-shimmer mc-skeleton-sidebar-item"></div>
            <div class="mc-skeleton-shimmer mc-skeleton-sidebar-item"></div>
            <div class="mc-skeleton-shimmer mc-skeleton-sidebar-item"></div>
        </div>
        <div class="mc-skeleton-main">
            <div class="mc-skeleton-shimmer mc-skeleton-header"></div>
            <div class="mc-skeleton-cards">
                <div class="mc-skeleton-shimmer mc-skeleton-card"></div>
                <div class="mc-skeleton-shimmer mc-skeleton-card"></div>
                <div class="mc-skeleton-shimmer mc-skeleton-card"></div>
            </div>
            <div class="mc-skeleton-shimmer mc-skeleton-table"></div>
            <div style="height:16px;"></div>
            <div class="mc-skeleton-shimmer mc-skeleton-table-row"></div>
            <div class="mc-skeleton-shimmer mc-skeleton-table-row"></div>
            <div class="mc-skeleton-shimmer mc-skeleton-table-row"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Activar skeleton via JS (se desactiva cuando el modulo termina de cargar)
    st.markdown("""<script>
    // Activar skeleton al inicio de cada navegacion
    document.body.classList.add('mc-skeleton-active');
    // Streamlit desactivara automaticamente al re-renderizar
    </script>""", unsafe_allow_html=True)


def desactivar_skeleton() -> None:
    """Desactiva el skeleton loader.

    Llamar DESPUES de que el modulo haya terminado de renderizar.
    """
    st.markdown("""<script>
    document.body.classList.remove('mc-skeleton-active');
    </script>""", unsafe_allow_html=True)
