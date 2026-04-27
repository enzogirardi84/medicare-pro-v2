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
    
    def _on_close_overlay(self, key: str):
        """Callback: cerrar menú FAB."""
        st.session_state[f"{key}_{self._is_open_key}"] = False

    def _on_toggle(self, key: str):
        """Callback: toggle FAB."""
        is_open = st.session_state.get(f"{key}_{self._is_open_key}", False)
        st.session_state[f"{key}_{self._is_open_key}"] = not is_open

    def _on_action_click(self, key: str, action_id: str):
        """Callback: ejecutar acción del FAB."""
        st.session_state[f"{key}_{self._is_open_key}"] = False
        for action in self.actions:
            if action.id == action_id and action.on_click and not action.disabled:
                try:
                    action.on_click()
                except Exception as e:
                    st.error(f"Error en acción: {e}")
                break

    def _render_actions_menu(self, key: str, position_css: str):
        """Renderizar menú de acciones secundarias."""
        # Overlay para cerrar al hacer click fuera
        st.button("", key=f"{key}_overlay", help="Cerrar menú", on_click=self._on_close_overlay, args=(key,))

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
            st.button(
                f"{action.label}",
                key=f"{key}_action_{action.id}",
                disabled=action.disabled,
                on_click=self._on_action_click,
                args=(key, action.id),
            )

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
        st.button(
            self.main_label,
            key=f"{key}_toggle",
            help=self.main_label,
            on_click=self._on_toggle,
            args=(key,),
        )


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
