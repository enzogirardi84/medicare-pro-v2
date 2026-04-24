"""
Floating Action Button (FAB) para MediCare.
Botón flotante con acciones rápidas y menú expandible.
"""
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import html

import streamlit as st


class FABPosition(Enum):
    """Posiciones disponibles para el FAB."""
    BOTTOM_RIGHT = "bottom-right"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM_CENTER = "bottom-center"


@dataclass
class FABAction:
    """Definición de una acción del FAB."""
    id: str
    icon: str
    label: str
    color: str = "#3b82f6"  # Azul por defecto
    on_click: Optional[Callable] = None
    badge: Optional[str] = None  # Número de notificaciones
    disabled: bool = False


class FloatingActionButton:
    """
    Botón flotante de acción principal con menú expandible.
    """
    
    def __init__(
        self,
        main_icon: str = "➕",
        main_label: str = "Acciones",
        position: FABPosition = FABPosition.BOTTOM_RIGHT,
        primary_color: str = "#3b82f6",
    ):
        self.main_icon = main_icon
        self.main_label = main_label
        self.position = position
        self.primary_color = primary_color
        self.actions: List[FABAction] = []
        self._is_open_key = "_fab_open"
    
    def add_action(
        self,
        id: str,
        icon: str,
        label: str,
        on_click: Optional[Callable] = None,
        color: Optional[str] = None,
        badge: Optional[str] = None,
        disabled: bool = False,
    ):
        """Agregar una acción al menú."""
        self.actions.append(FABAction(
            id=id,
            icon=icon,
            label=label,
            color=color or self.primary_color,
            on_click=on_click,
            badge=badge,
            disabled=disabled,
        ))
    
    def render(self, key: str = "fab_main"):
        """Renderizar el FAB completo."""
        # Inyectar CSS
        self._inject_css()
        
        # Verificar estado
        is_open = st.session_state.get(f"{key}_{self._is_open_key}", False)
        
        # Posición CSS
        position_css = {
            FABPosition.BOTTOM_RIGHT: "bottom: 2rem; right: 2rem;",
            FABPosition.BOTTOM_LEFT: "bottom: 2rem; left: 2rem;",
            FABPosition.BOTTOM_CENTER: "bottom: 2rem; left: 50%; transform: translateX(-50%);",
        }.get(self.position, "bottom: 2rem; right: 2rem;")
        
        # Renderizar menú de acciones si está abierto
        if is_open and self.actions:
            self._render_actions_menu(key, position_css)
        
        # Renderizar botón principal
        self._render_main_button(key, position_css, is_open)
    
    def _inject_css(self):
        """Inyectar CSS necesario."""
        css = """
        <style>
        .mc-fab-container {
            position: fixed;
            z-index: 999998;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 0.75rem;
        }
        
        .mc-fab-main {
            width: 56px;
            height: 56px;
            border-radius: 50%;
            border: none;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            position: relative;
            overflow: hidden;
        }
        
        .mc-fab-main:hover {
            transform: scale(1.1);
            box-shadow: 0 6px 30px rgba(0, 0, 0, 0.4);
        }
        
        .mc-fab-main:active {
            transform: scale(0.95);
        }
        
        .mc-fab-main.open {
            transform: rotate(45deg);
        }
        
        .mc-fab-main::before {
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(135deg, rgba(255,255,255,0.2) 0%, transparent 50%);
            border-radius: 50%;
        }
        
        .mc-fab-actions {
            display: flex;
            flex-direction: column-reverse;
            gap: 0.75rem;
            margin-bottom: 0.5rem;
            animation: fab-actions-in 0.3s ease-out;
        }
        
        @keyframes fab-actions-in {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .mc-fab-action {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .mc-fab-action:hover {
            transform: translateX(-5px);
        }
        
        .mc-fab-action-btn {
            width: 48px;
            height: 48px;
            border-radius: 50%;
            border: none;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
            transition: all 0.2s ease;
            position: relative;
        }
        
        .mc-fab-action-btn:hover {
            transform: scale(1.1);
        }
        
        .mc-fab-action-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .mc-fab-action-label {
            background: rgba(15, 23, 42, 0.9);
            color: #f1f5f9;
            padding: 0.5rem 0.75rem;
            border-radius: 6px;
            font-size: 0.875rem;
            white-space: nowrap;
            backdrop-filter: blur(8px);
            border: 1px solid rgba(148, 163, 184, 0.2);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
        }
        
        .mc-fab-badge {
            position: absolute;
            top: -4px;
            right: -4px;
            background: #ef4444;
            color: white;
            font-size: 0.65rem;
            font-weight: 600;
            min-width: 18px;
            height: 18px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 2px solid #0f172a;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        }
        
        /* Overlay para cerrar al hacer click fuera */
        .mc-fab-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(2, 6, 23, 0.5);
            z-index: 999997;
            backdrop-filter: blur(2px);
        }
        
        /* Mobile adjustments */
        @media (max-width: 768px) {
            .mc-fab-container {
                bottom: 1rem !important;
                right: 1rem !important;
                left: auto !important;
                transform: none !important;
            }
            
            .mc-fab-main {
                width: 48px;
                height: 48px;
                font-size: 1.25rem;
            }
            
            .mc-fab-action-btn {
                width: 40px;
                height: 40px;
                font-size: 1rem;
            }
            
            .mc-fab-action-label {
                display: none;
            }
        }
        
        /* Animación de ripple */
        .mc-fab-ripple {
            position: absolute;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.4);
            transform: scale(0);
            animation: ripple 0.6s linear;
            pointer-events: none;
        }
        
        @keyframes ripple {
            to {
                transform: scale(4);
                opacity: 0;
            }
        }
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)
    
    def _render_actions_menu(self, key: str, position_css: str):
        """Renderizar menú de acciones secundarias."""
        # Overlay para cerrar al hacer click fuera
        if st.button("", key=f"{key}_overlay", help="Cerrar menú"):
            st.session_state[f"{key}_{self._is_open_key}"] = False
            st.rerun()
        
        # Contenedor de acciones
        actions_html = ['<div class="mc-fab-actions">']
        
        for i, action in enumerate(reversed(self.actions)):
            badge_html = f'<span class="mc-fab-badge">{action.badge}</span>' if action.badge else ""
            disabled_attr = "disabled" if action.disabled else ""
            
            action_html = f"""
            <div class="mc-fab-action">
                <button class="mc-fab-action-btn" style="background: {action.color};" {disabled_attr}
                        onclick="handleAction('{action.id}')">
                    {action.icon}
                    {badge_html}
                </button>
                <span class="mc-fab-action-label">{html.escape(action.label)}</span>
            </div>
            """
            actions_html.append(action_html)
            
            # Botón invisible de Streamlit para manejar el click
            if st.button(
                f"{action.label}",
                key=f"{key}_action_{action.id}",
                disabled=action.disabled,
            ):
                if action.on_click and not action.disabled:
                    action.on_click()
                st.session_state[f"{key}_{self._is_open_key}"] = False
                st.rerun()
        
        actions_html.append('</div>')
        
        st.markdown(
            f"""
            <div class="mc-fab-container" style="{position_css} bottom: 5rem;">
                {''.join(actions_html)}
            </div>
            """,
            unsafe_allow_html=True
        )
    
    def _render_main_button(self, key: str, position_css: str, is_open: bool):
        """Renderizar botón principal del FAB."""
        open_class = "open" if is_open else ""
        
        # HTML del botón
        st.markdown(
            f"""
            <div class="mc-fab-container" style="{position_css}">
                <button class="mc-fab-main {open_class}" style="background: {self.primary_color};"
                        onclick="toggleFab()">
                    {self.main_icon}
                </button>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Botón invisible de Streamlit
        if st.button(
            self.main_label,
            key=f"{key}_toggle",
            help=self.main_label,
        ):
            st.session_state[f"{key}_{self._is_open_key}"] = not is_open
            st.rerun()


# ============================================================
# FAB PREDEFINIDO PARA MEDICARE
# ============================================================

def create_medicare_fab(
    paciente_actual: Optional[str] = None,
    on_nueva_evolucion: Optional[Callable] = None,
    on_nueva_receta: Optional[Callable] = None,
    on_buscar_paciente: Optional[Callable] = None,
    on_ver_ultimo: Optional[Callable] = None,
    pending_count: int = 0,
) -> FloatingActionButton:
    """
    Crear FAB preconfigurado para MediCare.
    
    Args:
        paciente_actual: ID del paciente seleccionado
        on_*: Callbacks para cada acción
        pending_count: Número de items pendientes
    
    Returns:
        FloatingActionButton configurado
    """
    fab = FloatingActionButton(
        main_icon="⚡",
        main_label="Acciones rápidas",
        position=FABPosition.BOTTOM_RIGHT,
        primary_color="#3b82f6",
    )
    
    # Nueva evolución (solo si hay paciente)
    if paciente_actual:
        fab.add_action(
            id="nueva_evolucion",
            icon="📝",
            label="Nueva evolución",
            color="#3b82f6",
            on_click=on_nueva_evolucion,
        )
        
        fab.add_action(
            id="nueva_receta",
            icon="💊",
            label="Nueva receta",
            color="#22c55e",
            on_click=on_nueva_receta,
        )
        
        fab.add_action(
            id="ver_ultimo",
            icon="👁️",
            label="Ver último paciente",
            color="#8b5cf6",
            on_click=on_ver_ultimo,
        )
    
    # Siempre disponible
    fab.add_action(
        id="buscar_paciente",
        icon="🔍",
        label="Buscar paciente",
        color="#f59e0b",
        on_click=on_buscar_paciente,
        badge=str(pending_count) if pending_count > 0 else None,
    )
    
    return fab


# ============================================================
# QUICK ACTIONS BAR (alternativa para desktop)
# ============================================================

def render_quick_actions_bar(
    actions: List[Dict[str, Any]],
    key: str = "quick_actions",
):
    """
    Barra de acciones rápidas fija (alternativa al FAB para desktop).
    
    Args:
        actions: Lista de dicts con keys: icon, label, on_click, color
    """
    st.markdown("""
    <style>
    .mc-quick-actions-bar {
        display: flex;
        gap: 0.5rem;
        padding: 0.75rem;
        background: rgba(30, 41, 59, 0.8);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 12px;
        backdrop-filter: blur(8px);
        position: sticky;
        bottom: 1rem;
        z-index: 99999;
        margin-top: 2rem;
        justify-content: center;
        flex-wrap: wrap;
    }
    
    .mc-quick-action-btn {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.625rem 1rem;
        border-radius: 8px;
        border: 1px solid transparent;
        cursor: pointer;
        transition: all 0.2s ease;
        font-size: 0.9rem;
        font-weight: 500;
    }
    
    .mc-quick-action-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }
    
    @media (max-width: 768px) {
        .mc-quick-actions-bar {
            gap: 0.375rem;
            padding: 0.5rem;
        }
        
        .mc-quick-action-btn {
            padding: 0.5rem 0.75rem;
            font-size: 0.8rem;
        }
        
        .mc-quick-action-btn span {
            display: none;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Renderizar barra
    cols = st.columns(len(actions))
    
    for i, (col, action) in enumerate(zip(cols, actions)):
        with col:
            icon = action.get("icon", "")
            label = action.get("label", "")
            color = action.get("color", "#3b82f6")
            on_click = action.get("on_click")
            disabled = action.get("disabled", False)
            
            if st.button(
                f"{icon} {label}",
                key=f"{key}_action_{i}",
                use_container_width=True,
                disabled=disabled,
                type="secondary",
            ):
                if on_click:
                    on_click()


# ============================================================
# DEMO
# ============================================================

def demo_floating_action_button():
    """Demo interactiva del FAB."""
    st.markdown("## ⚡ Floating Action Button")
    st.caption("Acciones rápidas desde cualquier parte de la aplicación")
    
    # Tabs para diferentes demos
    tab1, tab2 = st.tabs(["FAB Móvil", "Barra Desktop"])
    
    with tab1:
        st.markdown("### Botón Flotante (Mobile)")
        
        # Crear FAB con acciones de ejemplo
        fab = FloatingActionButton(
            main_icon="➕",
            main_label="Acciones",
            primary_color="#3b82f6",
        )
        
        fab.add_action(
            id="evolucion",
            icon="📝",
            label="Nueva evolución",
            color="#3b82f6",
            on_click=lambda: st.toast("📝 Nueva evolución"),
        )
        
        fab.add_action(
            id="receta",
            icon="💊",
            label="Nueva receta",
            color="#22c55e",
            on_click=lambda: st.toast("💊 Nueva receta"),
            badge="3",
        )
        
        fab.add_action(
            id="buscar",
            icon="🔍",
            label="Buscar paciente",
            color="#f59e0b",
            on_click=lambda: st.toast("🔍 Buscando..."),
        )
        
        fab.add_action(
            id="imprimir",
            icon="🖨️",
            label="Imprimir",
            color="#64748b",
            on_click=lambda: st.toast("🖨️ Imprimiendo..."),
        )
        
        # Renderizar
        fab.render(key="demo_fab")
        
        st.info("💡 En móvil, el FAB aparece en la esquina inferior derecha")
    
    with tab2:
        st.markdown("### Barra de Acciones (Desktop)")
        
        actions = [
            {
                "icon": "📝",
                "label": "Evolución",
                "color": "#3b82f6",
                "on_click": lambda: st.toast("📝 Nueva evolución"),
            },
            {
                "icon": "💊",
                "label": "Receta",
                "color": "#22c55e",
                "on_click": lambda: st.toast("💊 Nueva receta"),
            },
            {
                "icon": "🔍",
                "label": "Buscar",
                "color": "#f59e0b",
                "on_click": lambda: st.toast("🔍 Buscando..."),
            },
            {
                "icon": "💾",
                "label": "Guardar",
                "color": "#64748b",
                "on_click": lambda: st.toast("💾 Guardado"),
            },
            {
                "icon": "🖨️",
                "label": "Imprimir",
                "color": "#8b5cf6",
                "on_click": lambda: st.toast("🖨️ Imprimiendo..."),
            },
        ]
        
        render_quick_actions_bar(actions, key="demo_bar")
        
        st.info("💡 En desktop, se muestra una barra de acciones sticky al final de la página")
    
    st.markdown("---")
    
    # FAB predefinido de MediCare
    st.markdown("### FAB Predefinido de MediCare")
    
    paciente_sel = st.checkbox("Simular paciente seleccionado", value=True)
    
    medicare_fab = create_medicare_fab(
        paciente_actual="paciente_123" if paciente_sel else None,
        on_nueva_evolucion=lambda: st.toast("📝 Nueva evolución"),
        on_nueva_receta=lambda: st.toast("💊 Nueva receta"),
        on_buscar_paciente=lambda: st.toast("🔍 Buscando paciente..."),
        on_ver_ultimo=lambda: st.toast("👁️ Ver último paciente"),
        pending_count=2 if paciente_sel else 0,
    )
    
    medicare_fab.render(key="medicare_fab")
    
    st.markdown("---")
    st.caption("ℹ️ El FAB se adapta automáticamente: si hay paciente seleccionado, muestra acciones relevantes")
