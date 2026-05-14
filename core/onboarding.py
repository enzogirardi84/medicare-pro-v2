"""
Sistema de Onboarding Interactivo para MediCare.
Tour paso a paso, checklist de primeros pasos y tooltips contextuales.
"""

from html import escape
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

import streamlit as st


class TourStepType(Enum):
    """Tipos de pasos del tour."""
    WELCOME = "welcome"
    FEATURE = "feature"
    ACTION = "action"
    COMPLETION = "completion"


@dataclass
class TourStep:
    """Definición de un paso del tour."""
    id: str
    title: str
    content: str
    target: Optional[str] = None  # Selector CSS del elemento objetivo
    type: TourStepType = TourStepType.FEATURE
    position: str = "bottom"  # top, bottom, left, right
    action_button: Optional[str] = None  # Texto del botón de acción


@dataclass
class ChecklistItem:
    """Item de la checklist de primeros pasos."""
    id: str
    title: str
    description: str
    completed: bool = False
    action: Optional[Callable] = None
    icon: str = "✓"


class InteractiveTour:
    """
    Tour interactivo paso a paso para nuevos usuarios.
    """
    
    def __init__(self, tour_id: str = "main"):
        self.tour_id = tour_id
        self.steps: List[TourStep] = []
        self._current_step_key = f"_tour_{tour_id}_step"
        self._completed_key = f"_tour_{tour_id}_completed"
    
    def add_step(
        self,
        id: str,
        title: str,
        content: str,
        target: Optional[str] = None,
        position: str = "bottom",
        action_button: Optional[str] = None,
        type: TourStepType = TourStepType.FEATURE,
    ):
        """Agregar un paso al tour."""
        self.steps.append(TourStep(
            id=id,
            title=title,
            content=content,
            target=target,
            type=type,
            position=position,
            action_button=action_button,
        ))
    
    def start(self):
        """Iniciar el tour."""
        st.session_state[self._current_step_key] = 0
        st.session_state[self._completed_key] = False
    
    def stop(self):
        """Detener el tour."""
        st.session_state[self._current_step_key] = -1
    
    def is_active(self) -> bool:
        """Verificar si el tour está activo."""
        current = st.session_state.get(self._current_step_key, -1)
        return current >= 0 and current < len(self.steps)
    
    def is_completed(self) -> bool:
        """Verificar si el tour fue completado."""
        return st.session_state.get(self._completed_key, False)

    def _on_prev(self):
        """Callback: paso anterior."""
        current_idx = st.session_state.get(self._current_step_key, 0)
        if current_idx > 0:
            st.session_state[self._current_step_key] = current_idx - 1

    def _on_skip(self):
        """Callback: saltar tour."""
        self.stop()

    def _on_next(self):
        """Callback: paso siguiente."""
        current_idx = st.session_state.get(self._current_step_key, 0)
        if current_idx < len(self.steps) - 1:
            st.session_state[self._current_step_key] = current_idx + 1

    def _on_finish(self):
        """Callback: finalizar tour."""
        st.session_state[self._completed_key] = True
        self.stop()

    def _on_action(self):
        """Callback: acción del paso y avanzar."""
        current_idx = st.session_state.get(self._current_step_key, 0)
        st.session_state[self._current_step_key] = current_idx + 1

    def render(self):
        """Renderizar el paso actual del tour."""
        if not self.is_active():
            return
        
        current_idx = st.session_state[self._current_step_key]
        step = self.steps[current_idx]
        total = len(self.steps)
        
        # Overlay
        st.markdown('<div class="mc-tour-overlay"></div>', unsafe_allow_html=True)
        
        # Tooltip del tour
        progress = (current_idx + 1) / total
        progress_percent = int(progress * 100)
        
        col1, col2, col3 = st.columns([1, 3, 1])
        with col2:
            st.markdown(f"""
            <div class="mc-tour-tooltip">
                <div class="mc-tour-header">
                    <span class="mc-tour-badge">{current_idx + 1}/{total}</span>
                    <h4 class="mc-tour-title">{step.title}</h4>
                </div>
                <div class="mc-tour-content">{step.content}</div>
                <div class="mc-tour-progress">
                    <div class="mc-tour-progress-bar" style="width: {progress_percent}%"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Botones de navegación
            cols = st.columns([1, 1, 2])

            with cols[0]:
                if current_idx > 0:
                    st.button("⬅️ Anterior", key=f"tour_{self.tour_id}_prev", on_click=self._on_prev)
                else:
                    st.button("❌ Saltar tour", key=f"tour_{self.tour_id}_skip", on_click=self._on_skip)

            with cols[1]:
                if current_idx < total - 1:
                    st.button("Siguiente ➡️", key=f"tour_{self.tour_id}_next", type="primary", on_click=self._on_next)
                else:
                    st.button("✅ Finalizar", key=f"tour_{self.tour_id}_finish", type="primary", on_click=self._on_finish)

            with cols[2]:
                if step.action_button:
                    st.button(f"⚡ {step.action_button}", key=f"tour_{self.tour_id}_action", on_click=self._on_action)
    
class FirstStepsChecklist:
    """
    Checklist de primeros pasos para nuevos usuarios.
    """
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.items: List[ChecklistItem] = []
        self._key = f"_checklist_{user_id}"
    
    def add_item(
        self,
        id: str,
        title: str,
        description: str,
        icon: str = "✓",
        action: Optional[Callable] = None,
    ):
        """Agregar item a la checklist."""
        completed = self._is_completed(id)
        self.items.append(ChecklistItem(
            id=id,
            title=title,
            description=description,
            completed=completed,
            action=action,
            icon=icon,
        ))
    
    def _is_completed(self, item_id: str) -> bool:
        """Verificar si un item está completado."""
        key = f"{self._key}_{item_id}"
        return st.session_state.get(key, False)
    
    def mark_completed(self, item_id: str):
        """Marcar item como completado."""
        key = f"{self._key}_{item_id}"
        st.session_state[key] = True

    def _on_item_action(self, item_id: str):
        """Callback: ejecutar acción del checklist."""
        self.mark_completed(item_id)
        for item in self.items:
            if item.id == item_id and item.action:
                try:
                    item.action()
                except Exception as e:
                    st.error(f"Error al ejecutar acción: {e}")
                break

    def get_progress(self) -> tuple:
        """Obtener progreso (completados, total)."""
        completed = sum(1 for item in self.items if item.completed)
        return completed, len(self.items)
    
    def render(self, title: str = "✅ Primeros Pasos"):
        """Renderizar la checklist."""
        completed, total = self.get_progress()
        progress_percent = int((completed / total * 100)) if total > 0 else 0
        
        st.markdown(f"""
        <div class="mc-checklist-container">
            <div class="mc-checklist-header">
                <h4>{title}</h4>
                <span class="mc-checklist-counter">{completed}/{total}</span>
            </div>
            <div class="mc-checklist-progress-track">
                <div class="mc-checklist-progress-fill" style="width: {progress_percent}%;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Items
        for item in self.items:
            self._render_item(item)
    
    def _render_item(self, item: ChecklistItem):
        """Renderizar un item individual."""
        is_done = item.completed
        
        opacity = "0.6" if is_done else "1"
        text_decoration = "line-through" if is_done else "none"
        bg = "rgba(34, 197, 94, 0.1)" if is_done else "rgba(30, 41, 59, 0.5)"
        border = "rgba(34, 197, 94, 0.3)" if is_done else "rgba(148, 163, 184, 0.1)"
        
        cols = st.columns([1, 8, 2])
        
        with cols[0]:
            icon_color = "#22c55e" if is_done else "#64748b"
            st.markdown(f"""
            <div class="mc-checklist-icon" style="background: {bg}; border: 2px solid {border}; color: {icon_color};">
                {item.icon if is_done else "○"}
            </div>
            """, unsafe_allow_html=True)
        
        with cols[1]:
            st.markdown(f"""
            <div style="opacity: {opacity};">
                <div style="font-weight: 500; color: #f1f5f9; text-decoration: {text_decoration};">
                    {item.title}
                </div>
                <div style="font-size: 0.8rem; color: #64748b; text-decoration: {text_decoration};">
                    {item.description}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with cols[2]:
            if not is_done and item.action:
                st.button("Ir", key=f"checklist_action_{item.id}", on_click=self._on_item_action, args=(item.id,))


# ============================================================
# ONBOARDING PREDEFINIDO PARA MEDICARE
# ============================================================

def create_medicare_tour(rol: str) -> InteractiveTour:
    """
    Crear tour predefinido para MediCare según el rol.
    
    Args:
        rol: Rol del usuario
    
    Returns:
        InteractiveTour configurado
    """
    tour = InteractiveTour(tour_id=f"medicare_{rol}")
    
    # Paso 1: Bienvenida (todos los roles)
    tour.add_step(
        id="welcome",
        title="👋 ¡Bienvenido a MediCare Pro!",
        content="""
        Tu plataforma integral para gestión de clínicas y historias clínicas.
        
        Este tour te guiará por las funcionalidades principales para que aproveches al máximo el sistema.
        """,
        type=TourStepType.WELCOME,
    )
    
    # Paso 2: Sidebar (todos)
    tour.add_step(
        id="sidebar",
        title="🧭 Navegación Principal",
        content="""
        **La barra lateral** es tu centro de control:
        
        • **Buscador**: Encuentra pacientes por nombre o DNI
        • **Selector**: Elige el paciente activo para trabajar
        • **Card del paciente**: Información rápida del seleccionado
        • **Alertas**: Notificaciones clínicas importantes
        
        💡 *Todo módulo clínico requiere un paciente seleccionado*
        """,
        type=TourStepType.FEATURE,
    )
    
    # Pasos específicos por rol
    r = str(rol or "").strip().lower()
    
    if r in {"medico", "doctor", "enfermera", "enfermero"}:
        # Tour para personal médico
        tour.add_step(
            id="evolucion",
            title="📝 Evolución Clínica",
            content="""
            Documenta el seguimiento diario del paciente:
            
            • Notas de evolución con plantillas
            • Adjunto de fotos clínicas
            • Firma del paciente o familiar
            • Historial cronológico
            """,
            type=TourStepType.ACTION,
            action_button="Ver Evolución",
        )
        
        tour.add_step(
            id="recetas",
            title="💊 Recetas Médicas",
            content="""
            Genera recetas profesionales:
            
            • Medicamentos con posología
            • Diagnósticos codificados (CIE-10)
            • Impresión en formato profesional
            • QR de verificación
            """,
            type=TourStepType.ACTION,
            action_button="Ver Recetas",
        )
        
        tour.add_step(
            id="historial",
            title="📋 Historial Completo",
            content="""
            Visualiza toda la trayectoria del paciente:
            
            • Evoluciones cronológicas
            • Estudios y resultados
            • Signos vitales en gráficos
            • Exportación a PDF
            """,
            type=TourStepType.FEATURE,
        )
    
    elif r in {"admin", "superadmin", "coordinador"}:
        # Tour para administrativos
        tour.add_step(
            id="dashboard",
            title="📊 Dashboard",
            content="""
            Vista general de la clínica en tiempo real:
            
            • Pacientes activos e internados
            • Estadísticas del día
            • Alertas del sistema
            • Rendimiento del equipo
            """,
            type=TourStepType.FEATURE,
        )
        
        tour.add_step(
            id="admision",
            title="📝 Admisión de Pacientes",
            content="""
            Gestiona el alta y seguimiento de pacientes:
            
            • Nuevos ingresos
            • Actualización de datos
            • Historias clínicas nuevas
            • Asignación de médicos
            """,
            type=TourStepType.ACTION,
        )
        
        tour.add_step(
            id="mi_equipo",
            title="👥 Gestión de Equipo",
            content="""
            Administra usuarios y permisos:
            
            • Alta de profesionales
            • Asignación de roles
            • Control de accesos
            • Auditoría de actividad
            """,
            type=TourStepType.FEATURE,
        )
    
    # Paso final: Completado (todos)
    tour.add_step(
        id="completion",
        title="🎉 ¡Listo para comenzar!",
        content="""
        Ya conoces lo esencial de MediCare Pro.
        
        **Próximos pasos sugeridos:**
        • Explora los módulos a tu propio ritmo
        • Selecciona tu primer paciente
        • Completa tu perfil de usuario
        
        💡 *Puedes reiniciar este tour desde Configuración > Ayuda*
        """,
        type=TourStepType.COMPLETION,
    )
    
    return tour


def create_first_steps_checklist(rol: str, user_id: str) -> FirstStepsChecklist:
    """
    Crear checklist de primeros pasos según rol.
    
    Args:
        rol: Rol del usuario
        user_id: ID del usuario
    
    Returns:
        FirstStepsChecklist configurada
    """
    checklist = FirstStepsChecklist(user_id)
    r = str(rol or "").strip().lower()
    
    # Items comunes para todos
    checklist.add_item(
        id="completar_perfil",
        title="Completar perfil",
        description="Agrega tu información profesional y firma",
        icon="👤",
    )
    
    checklist.add_item(
        id="seleccionar_paciente",
        title="Seleccionar primer paciente",
        description="Usa el buscador para encontrar un paciente",
        icon="🔍",
    )
    
    # Items específicos
    if r in {"medico", "doctor", "enfermera", "enfermero"}:
        checklist.add_item(
            id="primera_evolucion",
            title="Registrar primera evolución",
            description="Documenta el estado de un paciente",
            icon="📝",
        )
        
        checklist.add_item(
            id="configurar_plantillas",
            title="Configurar plantillas",
            description="Crea plantillas personalizadas para evoluciones",
            icon="📄",
        )
    
    elif r in {"admin", "superadmin"}:
        checklist.add_item(
            id="revisar_dashboard",
            title="Revisar Dashboard",
            description="Familiarízate con las métricas principales",
            icon="📊",
        )
        
        checklist.add_item(
            id="configurar_alertas",
            title="Configurar alertas",
            description="Personaliza las notificaciones del sistema",
            icon="🔔",
        )
    
    checklist.add_item(
        id="explorar_modulos",
        title="Explorar módulos",
        description="Navega por las diferentes secciones",
        icon="🧭",
    )
    
    return checklist


# ============================================================
# PANEL DE BIENVENIDA ORIGINAL (mantenido para compatibilidad)
# ============================================================


def _tips_por_rol(rol: str) -> list[str]:
    from core.utils import es_control_total

    r = str(rol or "").strip().lower()
    user = st.session_state.get("u_actual")
    if r in {"superadmin", "admin"}:
        return [
            "Revisá el **Dashboard** y el panel **Clínicas** para el estado de la red.",
            "Altas y correcciones de legajos en **Admisión**; permisos del equipo en **Mi Equipo**.",
            "**Auditoría** y **Auditoría Legal** centralizan rastros para soporte y cumplimiento.",
        ]
    if r in {"coordinador", "administrativo"} or (r == "operativo" and es_control_total(rol, user)):
        return [
            "**Visitas y Agenda** + **Asistencia en vivo** para coordinar el día.",
            "**Admisión** para pacientes; **RRHH** para fichajes y reportes.",
            "Con un paciente activo, **Historial** resume la trayectoria clínica.",
        ]
    return [
        "Elegí un **paciente activo** en la barra lateral antes de módulos clínicos.",
        "**Clínica**, **Evolución** y **Recetas** son el núcleo de la atención diaria.",
        "**PDF** y **Telemedicina** dependen de datos cargados en los módulos anteriores.",
    ]


def _clave_onboarding() -> str:
    usuario = st.session_state.get("u_actual") or "anon"
    return f"_mc_onboarding_oculto_{usuario}"


def render_panel_bienvenida(rol: str, menu: list[str], etiquetas_nav: dict[str, str]) -> None:
    from core.ui_liviano import headers_sugieren_equipo_liviano
    clave = _clave_onboarding()
    # Migrar clave vieja si existe
    if st.session_state.get("_mc_onboarding_oculto") and not st.session_state.get(clave):
        st.session_state[clave] = True
    if st.session_state.get(clave):
        return
    # En movil: solo mostrar si es la primera vez en la sesion (no expanded por defecto)
    es_movil = headers_sugieren_equipo_liviano() or st.session_state.get("mc_liviano_modo") == "on"
    if es_movil and not st.session_state.get("_mc_onboarding_visto_movil"):
        st.session_state["_mc_onboarding_visto_movil"] = True
    tips = _tips_por_rol(rol)
    modulos_txt = []
    for m in menu[:8]:
        modulos_txt.append(escape(str(etiquetas_nav.get(m, m))))
    resto = max(0, len(menu) - 8)
    lista_mod = " · ".join(modulos_txt) if modulos_txt else "—"
    if resto:
        lista_mod += f" · (+{resto} más en el menú)"

    with st.expander("Primeros pasos en MediCare", expanded=not es_movil):
        st.markdown(
            f"""
            <div class="mc-onboarding-box">
                <p class="mc-onboarding-lead">Tu menú incluye: {lista_mod}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for t in tips:
            st.markdown(f"- {t}")
        st.caption("Los filtros y fechas suelen conservarse mientras la sesión sigue abierta (hasta Cerrar sesión).")
        c1, c2 = st.columns([1, 2])
        def _on_close_panel():
            st.session_state[clave] = True
            st.session_state["_mc_onboarding_oculto"] = True

        with c1:
            st.button("Entendido, ocultar", width='stretch', key="mc_onboarding_cerrar", on_click=_on_close_panel)
        with c2:
            st.caption("Podés volver a ver ayuda contextual en cada módulo (bloques superiores).")
