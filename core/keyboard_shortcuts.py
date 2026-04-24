"""
Sistema de Atajos de Teclado para MediCare.
Permite navegación rápida sin usar el mouse.
"""
import json
from typing import Dict, List, Callable, Optional
from dataclasses import dataclass
from enum import Enum

import streamlit as st


class ShortcutScope(Enum):
    """Ámbito del atajo de teclado."""
    GLOBAL = "global"  # Funciona en toda la app
    MODULE = "module"  # Solo dentro de un módulo específico
    FORM = "form"      # Solo dentro de formularios


@dataclass
class KeyboardShortcut:
    """Definición de un atajo de teclado."""
    key: str                    # Tecla principal (Ctrl+S, Escape, etc.)
    description: str            # Descripción para mostrar
    action: str                 # Identificador de la acción
    scope: ShortcutScope        # Ámbito
    module: Optional[str] = None  # Módulo específico si aplica
    prevent_default: bool = True  # Prevenir comportamiento por defecto del navegador


class ShortcutManager:
    """
    Gestor de atajos de teclado.
    Registra y maneja shortcuts globales y por módulo.
    """
    
    def __init__(self):
        self.shortcuts: Dict[str, KeyboardShortcut] = {}
        self.actions: Dict[str, Callable] = {}
        self._enabled = True
    
    def register(
        self,
        key: str,
        description: str,
        action: Callable,
        scope: ShortcutScope = ShortcutScope.GLOBAL,
        module: Optional[str] = None,
        prevent_default: bool = True,
    ):
        """
        Registrar un atajo de teclado.
        
        Args:
            key: Combinación de teclas (ej: "Ctrl+S", "Escape", "Ctrl+K")
            description: Descripción legible
            action: Función a ejecutar
            scope: Ámbito del atajo
            module: Nombre del módulo si es MODULE
            prevent_default: Evitar comportamiento por defecto
        """
        shortcut = KeyboardShortcut(
            key=key,
            description=description,
            action=key,  # Usamos key como identificador único
            scope=scope,
            module=module,
            prevent_default=prevent_default,
        )
        
        self.shortcuts[key] = shortcut
        self.actions[key] = action
    
    def unregister(self, key: str):
        """Eliminar un atajo registrado."""
        if key in self.shortcuts:
            del self.shortcuts[key]
        if key in self.actions:
            del self.actions[key]
    
    def get_shortcuts_for_scope(
        self,
        scope: ShortcutScope,
        module: Optional[str] = None
    ) -> List[KeyboardShortcut]:
        """Obtener atajos para un ámbito específico."""
        result = []
        
        for shortcut in self.shortcuts.values():
            if shortcut.scope == ShortcutScope.GLOBAL:
                result.append(shortcut)
            elif shortcut.scope == scope:
                if scope != ShortcutScope.MODULE or shortcut.module == module:
                    result.append(shortcut)
        
        return result
    
    def generate_js_handlers(self, scope: ShortcutScope, module: Optional[str] = None) -> str:
        """Generar JavaScript para manejar atajos."""
        shortcuts = self.get_shortcuts_for_scope(scope, module)
        
        handlers = []
        for sc in shortcuts:
            # Parsear combinación
            keys = sc.key.split("+")
            has_ctrl = "Ctrl" in keys
            has_alt = "Alt" in keys
            has_shift = "Shift" in keys
            main_key = keys[-1] if keys else ""
            
            # Generar condición
            conditions = []
            if has_ctrl:
                conditions.append("e.ctrlKey")
            if has_alt:
                conditions.append("e.altKey")
            if has_shift:
                conditions.append("e.shiftKey")
            
            key_check = f"e.key === '{main_key}' || e.key === '{main_key.upper()}'"
            
            all_conditions = " && ".join(conditions + [key_check]) if conditions else key_check
            
            handler = f"""
            if ({all_conditions}) {{
                {'e.preventDefault();' if sc.prevent_default else ''}
                window.parent.postMessage({{
                    type: 'shortcut',
                    action: '{sc.action}'
                }}, '*');
                return;
            }}
            """
            handlers.append(handler)
        
        return f"""
        <script>
        document.addEventListener('keydown', function(e) {{
            {'\n'.join(handlers)}
        }});
        </script>
        """


# Instancia global
_shortcut_manager: Optional[ShortcutManager] = None

def get_shortcut_manager() -> ShortcutManager:
    """Obtener instancia del gestor."""
    global _shortcut_manager
    if _shortcut_manager is None:
        _shortcut_manager = ShortcutManager()
    return _shortcut_manager


# ============================================================
# ATAJOS PREDEFINIDOS
# ============================================================

def register_default_shortcuts():
    """Registrar atajos por defecto de MediCare."""
    manager = get_shortcut_manager()
    
    # Atajos globales
    manager.register(
        key="Ctrl+S",
        description="Guardar formulario actual",
        action=lambda: st.toast("💾 Guardando..."),
        scope=ShortcutScope.GLOBAL,
    )
    
    manager.register(
        key="Ctrl+F",
        description="Buscar paciente",
        action=lambda: st.session_state.update({"_search_focus": True}),
        scope=ShortcutScope.GLOBAL,
    )
    
    manager.register(
        key="Ctrl+K",
        description="Abrir menú de comandos",
        action=lambda: st.session_state.update({"_command_palette_open": True}),
        scope=ShortcutScope.GLOBAL,
    )
    
    manager.register(
        key="Escape",
        description="Cerrar modal/volver atrás",
        action=lambda: st.session_state.update({"_escape_pressed": True}),
        scope=ShortcutScope.GLOBAL,
    )
    
    manager.register(
        key="Ctrl+N",
        description="Nuevo registro",
        action=lambda: st.session_state.update({"_new_record": True}),
        scope=ShortcutScope.GLOBAL,
    )
    
    manager.register(
        key="Ctrl+P",
        description="Imprimir/PDF",
        action=lambda: st.session_state.update({"_print_requested": True}),
        scope=ShortcutScope.GLOBAL,
    )
    
    # Atajos de navegación
    manager.register(
        key="Ctrl+1",
        description="Ir a Dashboard",
        action=lambda: st.session_state.update({"current_view": "dashboard"}),
        scope=ShortcutScope.GLOBAL,
    )
    
    manager.register(
        key="Ctrl+2",
        description="Ir a Evolución",
        action=lambda: st.session_state.update({"current_view": "evolucion"}),
        scope=ShortcutScope.GLOBAL,
    )
    
    manager.register(
        key="Ctrl+3",
        description="Ir a Historial",
        action=lambda: st.session_state.update({"current_view": "historial"}),
        scope=ShortcutScope.GLOBAL,
    )
    
    manager.register(
        key="Ctrl+4",
        description="Ir a Recetas",
        action=lambda: st.session_state.update({"current_view": "recetas"}),
        scope=ShortcutScope.GLOBAL,
    )
    
    manager.register(
        key="Ctrl+0",
        description="Ir a Configuración",
        action=lambda: st.session_state.update({"current_view": "configuracion"}),
        scope=ShortcutScope.GLOBAL,
    )


# ============================================================
# COMPONENTES UI
# ============================================================

def render_shortcuts_help(key: str = "shortcuts_help"):
    """
    Renderizar panel de ayuda con todos los atajos disponibles.
    """
    manager = get_shortcut_manager()
    shortcuts = manager.shortcuts.values()
    
    st.markdown("## ⌨️ Atajos de Teclado")
    st.caption("Navega más rápido sin usar el mouse")
    
    # Agrupar por scope
    global_shortcuts = [s for s in shortcuts if s.scope == ShortcutScope.GLOBAL]
    module_shortcuts = [s for s in shortcuts if s.scope == ShortcutScope.MODULE]
    form_shortcuts = [s for s in shortcuts if s.scope == ShortcutScope.FORM]
    
    if global_shortcuts:
        st.markdown("### 🌍 Globales")
        for sc in sorted(global_shortcuts, key=lambda x: x.key):
            cols = st.columns([2, 3])
            with cols[0]:
                st.markdown(f"<kbd>{sc.key}</kbd>", unsafe_allow_html=True)
            with cols[1]:
                st.caption(sc.description)
    
    if module_shortcuts:
        st.markdown("### 📦 Por Módulo")
        for sc in sorted(module_shortcuts, key=lambda x: (x.module or "", x.key)):
            cols = st.columns([2, 2, 3])
            with cols[0]:
                st.markdown(f"<kbd>{sc.key}</kbd>", unsafe_allow_html=True)
            with cols[1]:
                st.caption(f"📁 {sc.module}")
            with cols[2]:
                st.caption(sc.description)
    
    st.markdown("---")
    st.info("💡 **Tip:** Presiona `Ctrl+K` en cualquier momento para abrir el menú de comandos")


def render_keyboard_hint(key: str, hint: str, inline: bool = False):
    """
    Renderizar hint visual de atajo de teclado junto a un elemento.
    
    Args:
        key: Combinación de teclas
        hint: Descripción corta
        inline: Si es True, muestra en línea
    """
    style = "" if inline else "margin-left: auto;"
    
    html = f"""
    <span style="
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.75rem;
        color: #64748b;
        background: rgba(30, 41, 59, 0.5);
        padding: 0.25rem 0.5rem;
        border-radius: 6px;
        {style}
    ">
        <kbd style="
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid rgba(148, 163, 184, 0.3);
            border-radius: 4px;
            padding: 0.125rem 0.375rem;
            font-family: monospace;
            font-size: 0.7rem;
            color: #94a3b8;
        ">{key}</kbd>
        <span>{hint}</span>
    </span>
    """
    
    st.markdown(html, unsafe_allow_html=True)


def render_command_palette(
    is_open: bool = False,
    on_close: Optional[Callable] = None,
    key: str = "command_palette",
):
    """
    Paleta de comandos estilo VS Code (Ctrl+K).
    Permite búsqueda rápida de acciones.
    """
    if not is_open:
        return
    
    manager = get_shortcut_manager()
    shortcuts = list(manager.shortcuts.values())
    
    st.markdown("""
    <style>
    .cmd-palette-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(2, 6, 23, 0.8);
        backdrop-filter: blur(4px);
        z-index: 999999;
        display: flex;
        align-items: flex-start;
        justify-content: center;
        padding-top: 15vh;
    }
    
    .cmd-palette-container {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 12px;
        width: 100%;
        max-width: 600px;
        max-height: 60vh;
        overflow: hidden;
        box-shadow: 0 25px 50px rgba(2, 6, 23, 0.5);
    }
    
    .cmd-palette-input {
        width: 100%;
        padding: 1rem 1.25rem;
        background: transparent;
        border: none;
        border-bottom: 1px solid rgba(148, 163, 184, 0.2);
        color: #f1f5f9;
        font-size: 1.1rem;
        outline: none;
    }
    
    .cmd-palette-input::placeholder {
        color: #64748b;
    }
    
    .cmd-palette-list {
        max-height: calc(60vh - 80px);
        overflow-y: auto;
    }
    
    .cmd-palette-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.75rem 1.25rem;
        cursor: pointer;
        transition: all 0.15s ease;
        border-left: 3px solid transparent;
    }
    
    .cmd-palette-item:hover,
    .cmd-palette-item.selected {
        background: rgba(59, 130, 246, 0.1);
        border-left-color: #3b82f6;
    }
    
    .cmd-palette-item-title {
        color: #f1f5f9;
        font-size: 0.95rem;
    }
    
    .cmd-palette-item-desc {
        color: #64748b;
        font-size: 0.8rem;
        margin-top: 0.125rem;
    }
    
    .cmd-palette-shortcut {
        display: flex;
        align-items: center;
        gap: 0.375rem;
    }
    
    .cmd-palette-kbd {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(148, 163, 184, 0.3);
        border-radius: 4px;
        padding: 0.25rem 0.5rem;
        font-family: monospace;
        font-size: 0.75rem;
        color: #94a3b8;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Input de búsqueda
    search = st.text_input(
        "Buscar comando...",
        key=f"{key}_search",
        placeholder="Escribe para buscar comandos...",
        label_visibility="collapsed",
    )
    
    # Filtrar shortcuts
    filtered = shortcuts
    if search:
        search_lower = search.lower()
        filtered = [
            s for s in shortcuts
            if search_lower in s.description.lower() 
            or search_lower in s.key.lower()
        ]
    
    # Mostrar resultados
    for i, sc in enumerate(filtered[:10]):  # Máximo 10 resultados
        cols = st.columns([4, 2])
        
        with cols[0]:
            st.markdown(f"""
            <div style="padding: 0.5rem 0;">
                <div style="font-weight: 500;">{sc.description}</div>
                <div style="font-size: 0.8rem; color: #64748b;">
                    {sc.module or 'Global'}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with cols[1]:
            render_keyboard_hint(sc.key, "")
        
        # Click handler simulado con button invisible
        if st.button(f"Ejecutar: {sc.description}", key=f"{key}_cmd_{i}", type="secondary"):
            action = manager.actions.get(sc.action)
            if action:
                action()
            if on_close:
                on_close()
            st.rerun()
    
    # Botón cerrar
    if st.button("Cerrar (Escape)", key=f"{key}_close"):
        if on_close:
            on_close()
        st.rerun()


# ============================================================
# INYECCIÓN DE JS GLOBAL
# ============================================================

def inject_shortcuts_js(scope: ShortcutScope = ShortcutScope.GLOBAL, module: Optional[str] = None):
    """
    Inyectar JavaScript para manejar atajos de teclado.
    Llama a esto al inicio de cada view para habilitar shortcuts.
    """
    manager = get_shortcut_manager()
    js_code = manager.generate_js_handlers(scope, module)
    
    st.markdown(js_code, unsafe_allow_html=True)


# ============================================================
# HOOKS DE INTEGRACIÓN
# ============================================================

def init_keyboard_shortcuts():
    """Inicializar sistema de atajos en la aplicación."""
    # Registrar atajos por defecto
    register_default_shortcuts()
    
    # Guardar en session state
    if "_shortcuts_initialized" not in st.session_state:
        st.session_state._shortcuts_initialized = True
        st.session_state._command_palette_open = False
    
    # Inyectar JS global
    inject_shortcuts_js(ShortcutScope.GLOBAL)


def check_shortcut_triggered(action: str) -> bool:
    """
    Verificar si un atajo fue activado.
    Usar en views para responder a shortcuts.
    
    Returns:
        True si el atajo fue presionado
    """
    key = f"_shortcut_{action}"
    if st.session_state.get(key):
        # Resetear
        st.session_state[key] = False
        return True
    return False


# ============================================================
# DEMO
# ============================================================

def demo_keyboard_shortcuts():
    """Demo interactiva de atajos de teclado."""
    st.markdown("## ⌨️ Demo de Atajos de Teclado")
    
    # Inicializar
    init_keyboard_shortcuts()
    
    # Mostrar ayuda
    with st.expander("Ver todos los atajos (Ctrl+H)", expanded=True):
        render_shortcuts_help()
    
    # Simular triggers
    st.markdown("---")
    st.markdown("### 🧪 Simulación de Atajos")
    
    cols = st.columns(3)
    
    with cols[0]:
        if st.button("💾 Simular Ctrl+S"):
            st.toast("💾 Guardando...")
    
    with cols[1]:
        if st.button("🔍 Simular Ctrl+F"):
            st.toast("🔍 Abriendo búsqueda...")
    
    with cols[2]:
        if st.button("⌨️ Simular Ctrl+K"):
            st.session_state._command_palette_open = True
            st.rerun()
    
    # Mostrar paleta de comandos
    if st.session_state.get("_command_palette_open"):
        st.markdown("---")
        render_command_palette(
            is_open=True,
            on_close=lambda: st.session_state.update({"_command_palette_open": False})
        )
    
    st.markdown("---")
    st.info("💡 **En una implementación real**, estos atajos funcionarían con el teclado físico")
