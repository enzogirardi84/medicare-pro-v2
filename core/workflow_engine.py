"""
Motor de Flujos de Trabajo (Workflow Engine) para Medicare Pro.

Automatiza procesos clínicos y administrativos:
- Protocolos de atención (clinical pathways)
- Aprobaciones escalonadas
- Notificaciones automáticas
- Tareas asignadas
- Checklists quirúrgicos
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Callable, Set
from collections import defaultdict
import json

import pandas as pd
import streamlit as st

from core.app_logging import log_event
from core.audit_trail import audit_log, AuditEventType
from core.clinical_reminders import get_reminder_manager, ReminderType, ReminderPriority


class WorkflowStatus(Enum):
    """Estados de un workflow."""
    PENDING = "pending"      # Pendiente de iniciar
    ACTIVE = "active"          # En progreso
    COMPLETED = "completed"    # Completado exitosamente
    CANCELLED = "cancelled"    # Cancelado
    ON_HOLD = "on_hold"        # Pausado
    OVERDUE = "overdue"        # Vencido


class TaskStatus(Enum):
    """Estados de una tarea."""
    PENDING = "pending"        # Pendiente
    IN_PROGRESS = "in_progress" # En progreso
    COMPLETED = "completed"    # Completada
    SKIPPED = "skipped"        # Omitida
    FAILED = "failed"          # Falló


@dataclass
class WorkflowTask:
    """Tarea dentro de un workflow."""
    id: str
    name: str
    description: str
    assignee_role: str  # médico, enfermera, recepción, admin
    assignee_id: Optional[str] = None
    
    # Timing
    estimated_duration_minutes: int = 15
    due_after_minutes: Optional[int] = None  # Tiempo límite desde inicio workflow
    due_at: Optional[datetime] = None  # Fecha límite absoluta
    
    # Estado
    status: TaskStatus = TaskStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None
    
    # Dependencias
    depends_on: List[str] = field(default_factory=list)  # IDs de tareas que deben completarse primero
    
    # Acciones automáticas
    auto_actions: List[Dict[str, Any]] = field(default_factory=list)
    
    # Condiciones para completar
    required_fields: List[str] = field(default_factory=list)
    validation_rules: List[Dict[str, Any]] = field(default_factory=list)
    
    # Notas
    notes: Optional[str] = None
    
    def can_start(self, completed_tasks: Set[str]) -> bool:
        """Verifica si la tarea puede iniciarse."""
        return all(dep in completed_tasks for dep in self.depends_on)
    
    def is_overdue(self) -> bool:
        """Verifica si la tarea está vencida."""
        if self.due_at and self.status != TaskStatus.COMPLETED:
            return datetime.now() > self.due_at
        return False


@dataclass
class WorkflowInstance:
    """Instancia ejecutándose de un workflow."""
    id: str
    template_id: str
    name: str
    description: str
    
    # Contexto
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    context_data: Dict[str, Any] = field(default_factory=dict)
    
    # Estado
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_task_index: int = 0
    
    # Tareas
    tasks: List[WorkflowTask] = field(default_factory=list)
    completed_tasks: Set[str] = field(default_factory=set)
    
    # Timeline
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Metadata
    created_by: str = ""
    priority: str = "normal"  # low, normal, high, urgent
    
    def get_current_task(self) -> Optional[WorkflowTask]:
        """Obtiene la tarea actual."""
        for task in self.tasks:
            if task.status not in [TaskStatus.COMPLETED, TaskStatus.SKIPPED]:
                if task.can_start(self.completed_tasks):
                    return task
        return None
    
    def get_progress_percentage(self) -> float:
        """Calcula porcentaje de progreso."""
        if not self.tasks:
            return 100.0
        completed = len([t for t in self.tasks if t.status == TaskStatus.COMPLETED])
        return (completed / len(self.tasks)) * 100
    
    def to_dict(self) -> dict:
        """Convierte a diccionario."""
        return {
            **asdict(self),
            "status": self.status.value,
            "tasks": [asdict(t) for t in self.tasks],
            "completed_tasks": list(self.completed_tasks)
        }


class WorkflowTemplate:
    """Template predefinido de workflow."""
    
    TEMPLATES = {
        "pre_surgery_checklist": {
            "name": "Checklist Pre-Operatorio",
            "description": "Verificaciones obligatorias antes de cirugía",
            "tasks": [
                {
                    "name": "Verificar consentimiento firmado",
                    "description": "Confirmar que el paciente firmó el consentimiento informado",
                    "assignee_role": "médico",
                    "estimated_duration_minutes": 5,
                    "required_fields": ["consent_id"]
                },
                {
                    "name": "Verificar ayuno",
                    "description": "Confirmar ayuno de 8 horas (sólidos) y 2 horas (líquidos claros)",
                    "assignee_role": "enfermera",
                    "estimated_duration_minutes": 5,
                    "depends_on": []
                },
                {
                    "name": "Marcar sitio quirúrgico",
                    "description": "Marcar el sitio de la cirugía con el paciente despierto",
                    "assignee_role": "médico",
                    "estimated_duration_minutes": 5,
                    "depends_on": []
                },
                {
                    "name": "Administrar pre-medicación",
                    "description": "Dar medicación pre-operatoria según protocolo",
                    "assignee_role": "enfermera",
                    "estimated_duration_minutes": 10,
                    "depends_on": ["Verificar ayuno"],
                    "required_fields": ["medication_given"]
                },
                {
                    "name": "Checklist de seguridad WHO",
                    "description": "Completar checklist de seguridad quirúrgica",
                    "assignee_role": "médico",
                    "estimated_duration_minutes": 5,
                    "depends_on": ["Marcar sitio quirúrgico", "Administrar pre-medicación"]
                }
            ]
        },
        
        "new_patient_admission": {
            "name": "Admisión de Nuevo Paciente",
            "description": "Proceso de admisión de paciente nuevo",
            "tasks": [
                {
                    "name": "Verificar identidad",
                    "description": "Confirmar identidad con documento válido",
                    "assignee_role": "recepción",
                    "estimated_duration_minutes": 5
                },
                {
                    "name": "Completar ficha médica",
                    "description": "Registrar datos básicos y antecedentes",
                    "assignee_role": "recepción",
                    "estimated_duration_minutes": 15,
                    "depends_on": ["Verificar identidad"]
                },
                {
                    "name": "Verificar cobertura médica",
                    "description": "Validar obra social/seguro",
                    "assignee_role": "recepción",
                    "estimated_duration_minutes": 10,
                    "depends_on": ["Verificar identidad"]
                },
                {
                    "name": "Consulta inicial",
                    "description": "Primera consulta médica",
                    "assignee_role": "médico",
                    "estimated_duration_minutes": 30,
                    "depends_on": ["Completar ficha médica"]
                }
            ]
        },
        
        "lab_results_review": {
            "name": "Revisión de Resultados de Laboratorio",
            "description": "Proceso de revisión y notificación de resultados",
            "tasks": [
                {
                    "name": "Verificar resultados",
                    "description": "Revisar que todos los estudios solicitados tengan resultado",
                    "assignee_role": "médico",
                    "estimated_duration_minutes": 10
                },
                {
                    "name": "Marcar valores críticos",
                    "description": "Identificar y marcar valores que requieren atención inmediata",
                    "assignee_role": "médico",
                    "estimated_duration_minutes": 5,
                    "depends_on": ["Verificar resultados"]
                },
                {
                    "name": "Notificar paciente",
                    "description": "Contactar al paciente para informar resultados",
                    "assignee_role": "recepción",
                    "estimated_duration_minutes": 10,
                    "depends_on": ["Verificar resultados"]
                }
            ]
        },
        
        "discharge_process": {
            "name": "Proceso de Alta",
            "description": "Pasos para dar de alta a un paciente",
            "tasks": [
                {
                    "name": "Orden médica de alta",
                    "description": "El médico debe firmar la orden de alta",
                    "assignee_role": "médico",
                    "estimated_duration_minutes": 5
                },
                {
                    "name": "Indicaciones de alta",
                    "description": "Preparar documento con indicaciones para el paciente",
                    "assignee_role": "médico",
                    "estimated_duration_minutes": 15,
                    "depends_on": ["Orden médica de alta"]
                },
                {
                    "name": "Facturación",
                    "description": "Generar factura y cobrar si aplica",
                    "assignee_role": "recepción",
                    "estimated_duration_minutes": 10,
                    "depends_on": ["Orden médica de alta"]
                },
                {
                    "name": "Entrega de documentación",
                    "description": "Entregar al paciente: indicaciones, recetas, certificados",
                    "assignee_role": "recepción",
                    "estimated_duration_minutes": 5,
                    "depends_on": ["Indicaciones de alta", "Facturación"]
                }
            ]
        }
    }
    
    @classmethod
    def get_template(cls, template_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene template por ID."""
        return cls.TEMPLATES.get(template_id)
    
    @classmethod
    def list_templates(cls) -> List[Dict[str, str]]:
        """Lista templates disponibles."""
        return [
            {"id": k, "name": v["name"], "description": v["description"]}
            for k, v in cls.TEMPLATES.items()
        ]


class WorkflowEngine:
    """
    Motor de ejecución de workflows.
    """
    
    def __init__(self):
        self._workflows: Dict[str, WorkflowInstance] = {}
        self._load_workflows()
    
    def _load_workflows(self):
        """Carga workflows activos."""
        if "active_workflows" in st.session_state:
            try:
                data = st.session_state["active_workflows"]
                if isinstance(data, dict):
                    for k, v in data.items():
                        # Reconstruir workflow
                        if isinstance(v, dict):
                            self._workflows[k] = self._dict_to_workflow(v)
            except Exception as e:
                log_event("workflow", f"Error loading workflows: {e}")
    
    def _save_workflows(self):
        """Guarda workflows."""
        data = {k: v.to_dict() for k, v in self._workflows.items()}
        st.session_state["active_workflows"] = data
    
    def _dict_to_workflow(self, data: dict) -> WorkflowInstance:
        """Convierte dict a WorkflowInstance."""
        tasks = []
        for t_data in data.get("tasks", []):
            tasks.append(WorkflowTask(
                id=t_data["id"],
                name=t_data["name"],
                description=t_data["description"],
                assignee_role=t_data["assignee_role"],
                assignee_id=t_data.get("assignee_id"),
                estimated_duration_minutes=t_data.get("estimated_duration_minutes", 15),
                due_after_minutes=t_data.get("due_after_minutes"),
                due_at=datetime.fromisoformat(t_data["due_at"]) if t_data.get("due_at") else None,
                status=TaskStatus(t_data["status"]),
                started_at=datetime.fromisoformat(t_data["started_at"]) if t_data.get("started_at") else None,
                completed_at=datetime.fromisoformat(t_data["completed_at"]) if t_data.get("completed_at") else None,
                completed_by=t_data.get("completed_by"),
                depends_on=t_data.get("depends_on", []),
                auto_actions=t_data.get("auto_actions", []),
                required_fields=t_data.get("required_fields", []),
                validation_rules=t_data.get("validation_rules", []),
                notes=t_data.get("notes")
            ))
        
        return WorkflowInstance(
            id=data["id"],
            template_id=data["template_id"],
            name=data["name"],
            description=data["description"],
            patient_id=data.get("patient_id"),
            patient_name=data.get("patient_name"),
            context_data=data.get("context_data", {}),
            status=WorkflowStatus(data["status"]),
            current_task_index=data.get("current_task_index", 0),
            tasks=tasks,
            completed_tasks=set(data.get("completed_tasks", [])),
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            created_by=data.get("created_by", ""),
            priority=data.get("priority", "normal")
        )
    
    def create_workflow(
        self,
        template_id: str,
        patient_id: Optional[str] = None,
        patient_name: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None,
        priority: str = "normal",
        created_by: str = ""
    ) -> Optional[WorkflowInstance]:
        """
        Crea una nueva instancia de workflow desde template.
        """
        import uuid
        
        template = WorkflowTemplate.get_template(template_id)
        if not template:
            st.error(f"❌ Template no encontrado: {template_id}")
            return None
        
        # Crear tareas desde template
        tasks = []
        for i, task_template in enumerate(template["tasks"]):
            task = WorkflowTask(
                id=f"task_{i}_{uuid.uuid4().hex[:8]}",
                name=task_template["name"],
                description=task_template.get("description", ""),
                assignee_role=task_template["assignee_role"],
                estimated_duration_minutes=task_template.get("estimated_duration_minutes", 15),
                depends_on=task_template.get("depends_on", [])
            )
            tasks.append(task)
        
        # Crear instancia
        workflow = WorkflowInstance(
            id=str(uuid.uuid4()),
            template_id=template_id,
            name=template["name"],
            description=template["description"],
            patient_id=patient_id,
            patient_name=patient_name,
            context_data=context_data or {},
            tasks=tasks,
            priority=priority,
            created_by=created_by
        )
        
        self._workflows[workflow.id] = workflow
        self._save_workflows()
        
        # Crear recordatorio
        if patient_id:
            reminder_mgr = get_reminder_manager()
            reminder_mgr.create_reminder(
                reminder_type=ReminderType.CUSTOM,
                patient_id=patient_id,
                patient_name=patient_name or "Paciente",
                title=f"Workflow iniciado: {template['name']}",
                description=f"Se ha iniciado el proceso: {template['description']}",
                priority=ReminderPriority.HIGH if priority == "urgent" else ReminderPriority.MEDIUM
            )
        
        log_event("workflow", f"Workflow created: {workflow.id} ({template['name']})")
        
        return workflow
    
    def start_workflow(self, workflow_id: str) -> bool:
        """Inicia un workflow."""
        if workflow_id not in self._workflows:
            return False
        
        workflow = self._workflows[workflow_id]
        workflow.status = WorkflowStatus.ACTIVE
        workflow.started_at = datetime.now()
        
        # Iniciar primera tarea
        first_task = workflow.get_current_task()
        if first_task:
            first_task.status = TaskStatus.IN_PROGRESS
            first_task.started_at = datetime.now()
        
        self._save_workflows()
        
        log_event("workflow", f"Workflow started: {workflow_id}")
        return True
    
    def complete_task(
        self,
        workflow_id: str,
        task_id: str,
        completed_by: str,
        notes: Optional[str] = None
    ) -> bool:
        """Completa una tarea del workflow."""
        if workflow_id not in self._workflows:
            return False
        
        workflow = self._workflows[workflow_id]
        
        # Buscar tarea
        task = None
        for t in workflow.tasks:
            if t.id == task_id:
                task = t
                break
        
        if not task:
            return False
        
        # Verificar que puede completarse
        if not task.can_start(workflow.completed_tasks):
            st.error("❌ No se puede completar esta tarea aún. Hay dependencias pendientes.")
            return False
        
        # Completar
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()
        task.completed_by = completed_by
        if notes:
            task.notes = notes
        
        workflow.completed_tasks.add(task_id)
        
        # Avanzar a siguiente tarea
        next_task = workflow.get_current_task()
        if next_task:
            next_task.status = TaskStatus.IN_PROGRESS
            next_task.started_at = datetime.now()
        else:
            # Workflow completado
            workflow.status = WorkflowStatus.COMPLETED
            workflow.completed_at = datetime.now()
            
            st.success(f"✅ Workflow '{workflow.name}' completado exitosamente")
        
        self._save_workflows()
        
        log_event("workflow", f"Task completed: {task_id} in workflow {workflow_id}")
        
        return True
    
    def get_workflow(self, workflow_id: str) -> Optional[WorkflowInstance]:
        """Obtiene workflow por ID."""
        return self._workflows.get(workflow_id)
    
    def get_workflows(
        self,
        patient_id: Optional[str] = None,
        status: Optional[WorkflowStatus] = None,
        assignee: Optional[str] = None
    ) -> List[WorkflowInstance]:
        """Obtiene workflows con filtros."""
        results = []
        
        for workflow in self._workflows.values():
            if patient_id and workflow.patient_id != patient_id:
                continue
            if status and workflow.status != status:
                continue
            if assignee:
                # Verificar si tiene tareas asignadas a esta persona
                has_task = any(
                    t.assignee_id == assignee or t.assignee_role == assignee
                    for t in workflow.tasks
                    if t.status not in [TaskStatus.COMPLETED, TaskStatus.SKIPPED]
                )
                if not has_task:
                    continue
            
            results.append(workflow)
        
        return sorted(results, key=lambda x: x.created_at, reverse=True)
    
    def render_workflow_dashboard(self):
        """Renderiza dashboard de workflows."""
        st.title("⚙️ Gestión de Workflows y Procesos")
        
        # Tabs
        tabs = st.tabs(["📋 Activos", "➕ Nuevo Workflow", "📊 Estadísticas"])
        
        with tabs[0]:
            self._render_active_workflows()
        
        with tabs[1]:
            self._render_create_workflow()
        
        with tabs[2]:
            self._render_workflow_stats()
    
    def _render_active_workflows(self):
        """Renderiza workflows activos."""
        st.header("📋 Workflows Activos")
        
        workflows = self.get_workflows()
        
        if not workflows:
            st.info("📭 No hay workflows activos")
            return
        
        for workflow in workflows:
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    status_colors = {
                        WorkflowStatus.PENDING: "⚪",
                        WorkflowStatus.ACTIVE: "🟢",
                        WorkflowStatus.COMPLETED: "✅",
                        WorkflowStatus.CANCELLED: "❌",
                        WorkflowStatus.ON_HOLD: "⏸️",
                        WorkflowStatus.OVERDUE: "🔴"
                    }
                    icon = status_colors.get(workflow.status, "⚪")
                    
                    st.markdown(f"**{icon} {workflow.name}**")
                    if workflow.patient_name:
                        st.caption(f"Paciente: {workflow.patient_name}")
                    st.caption(f"Creado: {workflow.created_at.strftime('%d/%m/%Y %H:%M')}")
                
                with col2:
                    progress = workflow.get_progress_percentage()
                    st.progress(progress / 100)
                    st.caption(f"Progreso: {progress:.0f}%")
                    
                    # Tarea actual
                    current = workflow.get_current_task()
                    if current:
                        st.caption(f"Actual: {current.name}")
                
                with col3:
                    if st.button("👁️ Ver", key=f"view_wf_{workflow.id}"):
                        self._render_workflow_detail(workflow.id)
                
                st.divider()
    
    def _render_workflow_detail(self, workflow_id: str):
        """Renderiza detalle de un workflow."""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            st.error("Workflow no encontrado")
            return
        
        st.subheader(f"📋 {workflow.name}")
        st.caption(workflow.description)
        
        # Timeline de tareas
        st.subheader("Tareas")
        
        for task in workflow.tasks:
            with st.container():
                col1, col2, col3 = st.columns([1, 4, 2])
                
                with col1:
                    status_icons = {
                        TaskStatus.PENDING: "⏳",
                        TaskStatus.IN_PROGRESS: "▶️",
                        TaskStatus.COMPLETED: "✅",
                        TaskStatus.SKIPPED: "⏭️",
                        TaskStatus.FAILED: "❌"
                    }
                    st.markdown(f"### {status_icons.get(task.status, '⚪')}")
                
                with col2:
                    st.markdown(f"**{task.name}**")
                    st.caption(task.description)
                    st.caption(f"Asignado a: {task.assignee_role}")
                    
                    if task.notes:
                        st.caption(f"Notas: {task.notes}")
                
                with col3:
                    user = st.session_state.get("u_actual", {})
                    user_role = user.get("rol", "")
                    
                    # Verificar si el usuario puede completar esta tarea
                    can_complete = (
                        task.status == TaskStatus.IN_PROGRESS and
                        (user_role == task.assignee_role or user_role in ["admin", "superadmin"])
                    )
                    
                    def _on_complete_task(workflow_id: str, task_id: str, notes_key: str, user_name: str):
                        notes = st.session_state.get(notes_key, "")
                        try:
                            self.complete_task(workflow_id, task_id, user_name, notes)
                        except Exception as e:
                            log_event("workflow_engine", f"Error al completar tarea {task_id}: {e}")
                            st.error("No se pudo completar la tarea.")

                    if can_complete:
                        notes = st.text_input("Notas", key=f"notes_{task.id}")
                        st.button("✅ Completar", key=f"complete_{task.id}", on_click=_on_complete_task, args=(workflow_id, task.id, f"notes_{task.id}", user.get("nombre", "Sistema")))
                    
                    if task.completed_at:
                        st.caption(f"Completado: {task.completed_at.strftime('%H:%M')}")
                        if task.completed_by:
                            st.caption(f"Por: {task.completed_by}")
                
                st.divider()
    
    def _render_create_workflow(self):
        """Formulario para crear workflow."""
        st.header("➕ Iniciar Nuevo Workflow")
        
        # Templates
        templates = WorkflowTemplate.list_templates()
        
        if not templates:
            st.error("No hay templates disponibles")
            return
        
        template_options = {f"{t['name']} - {t['description']}": t['id'] for t in templates}
        
        selected = st.selectbox(
            "Seleccionar tipo de workflow",
            options=list(template_options.keys())
        )
        
        template_id = template_options[selected]
        
        # Paciente (opcional)
        pacientes = st.session_state.get("pacientes_db", {})
        paciente_options = {"Sin paciente específico": None}
        paciente_options.update({f"{p['apellido']}, {p['nombre']}": dni for dni, p in pacientes.items()})
        
        paciente_selected = st.selectbox(
            "Paciente (opcional)",
            options=list(paciente_options.keys())
        )
        
        paciente_dni = paciente_options[paciente_selected]
        paciente = pacientes.get(paciente_dni) if paciente_dni else None
        
        # Prioridad
        priority = st.selectbox(
            "Prioridad",
            options=[("Baja", "low"), ("Normal", "normal"), ("Alta", "high"), ("Urgente", "urgent")],
            format_func=lambda x: x[0]
        )
        
        def _on_start_workflow(template_id: str, patient_id: Optional[str], patient_name: Optional[str], priority: str, created_by: str):
            try:
                workflow = self.create_workflow(
                    template_id=template_id,
                    patient_id=patient_id,
                    patient_name=patient_name,
                    priority=priority,
                    created_by=created_by
                )
                if workflow:
                    self.start_workflow(workflow.id)
                    st.success(f"✅ Workflow '{workflow.name}' iniciado")
            except Exception as e:
                log_event("workflow_engine", f"Error al iniciar workflow: {e}")
                st.error("No se pudo iniciar el workflow.")

        if st.button("🚀 Iniciar Workflow", use_container_width=True, type="primary"):
            user = st.session_state.get("u_actual", {})
            _patient_id = paciente.get("id", paciente_dni) if paciente else None
            _patient_name = f"{paciente['nombre']} {paciente['apellido']}" if paciente else None
            _on_start_workflow(
                template_id=template_id,
                patient_id=_patient_id,
                patient_name=_patient_name,
                priority=priority[1],
                created_by=user.get("nombre", "Sistema")
            )
    
    def _render_workflow_stats(self):
        """Estadísticas de workflows."""
        st.header("📊 Estadísticas de Workflows")
        
        workflows = list(self._workflows.values())
        
        if not workflows:
            st.info("No hay datos suficientes")
            return
        
        # KPIs
        total = len(workflows)
        active = len([w for w in workflows if w.status == WorkflowStatus.ACTIVE])
        completed = len([w for w in workflows if w.status == WorkflowStatus.COMPLETED])
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total", total)
        with col2:
            st.metric("Activos", active)
        with col3:
            st.metric("Completados", completed)
        with col4:
            completion_rate = (completed / total * 100) if total > 0 else 0
            st.metric("Tasa de Éxito", f"{completion_rate:.1f}%")
        
        # Por template
        by_template = {}
        for w in workflows:
            by_template[w.name] = by_template.get(w.name, 0) + 1
        
        if by_template:
            st.subheader("Por Tipo")
            data = [{"Workflow": k, "Cantidad": v} for k, v in sorted(by_template.items(), key=lambda x: x[1], reverse=True)]
            df = pd.DataFrame(data)
            st.bar_chart(df.set_index("Workflow"))


# Singleton
_workflow_engine: Optional[WorkflowEngine] = None


def get_workflow_engine() -> WorkflowEngine:
    """Obtiene instancia del motor."""
    global _workflow_engine
    if _workflow_engine is None:
        _workflow_engine = WorkflowEngine()
    return _workflow_engine
