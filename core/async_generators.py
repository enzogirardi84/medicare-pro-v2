"""
Procesos asíncronos para tareas pesadas (Fase 4).
Generación de PDFs y exportaciones en background para no congelar la UI.
"""
import threading
import queue
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

import streamlit as st


class TaskStatus(Enum):
    """Estados de una tarea asíncrona."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AsyncTask:
    """Representa una tarea asíncrona."""
    id: str
    name: str
    status: TaskStatus
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Any = None
    error: Optional[str] = None
    progress: int = 0  # 0-100
    metadata: Dict[str, Any] = field(default_factory=dict)


class BackgroundTaskManager:
    """
    Manager para ejecutar tareas pesadas en background threads.
    No bloquea la interfaz de Streamlit.
    """
    
    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self.tasks: Dict[str, AsyncTask] = {}
        self._lock = threading.Lock()
        self._task_queue: queue.Queue = queue.Queue()
        self._workers: List[threading.Thread] = []
        self._running = False
    
    def start(self):
        """Iniciar workers."""
        if self._running:
            return
        
        self._running = True
        for i in range(self.max_workers):
            worker = threading.Thread(target=self._worker_loop, daemon=True)
            worker.start()
            self._workers.append(worker)
    
    def stop(self):
        """Detener workers."""
        self._running = False
        for worker in self._workers:
            worker.join(timeout=1)
    
    def _worker_loop(self):
        """Loop principal de worker thread."""
        while self._running:
            try:
                task_id, func, args, kwargs = self._task_queue.get(timeout=1)
                
                with self._lock:
                    if task_id in self.tasks:
                        self.tasks[task_id].status = TaskStatus.RUNNING
                        self.tasks[task_id].started_at = datetime.now().isoformat()
                
                try:
                    result = func(*args, **kwargs)
                    
                    with self._lock:
                        self.tasks[task_id].status = TaskStatus.COMPLETED
                        self.tasks[task_id].completed_at = datetime.now().isoformat()
                        self.tasks[task_id].result = result
                        self.tasks[task_id].progress = 100
                        
                except Exception as e:
                    with self._lock:
                        self.tasks[task_id].status = TaskStatus.FAILED
                        self.tasks[task_id].completed_at = datetime.now().isoformat()
                        self.tasks[task_id].error = str(e)
                
                self._task_queue.task_done()
                
            except queue.Empty:
                continue
    
    def submit(
        self,
        name: str,
        func: Callable,
        *args,
        metadata: Optional[Dict] = None,
        **kwargs
    ) -> str:
        """
        Enviar tarea para ejecución en background.
        
        Returns:
            Task ID para seguimiento
        """
        self.start()
        
        task_id = str(uuid.uuid4())[:8]
        
        task = AsyncTask(
            id=task_id,
            name=name,
            status=TaskStatus.PENDING,
            created_at=datetime.now().isoformat(),
            metadata=metadata or {},
        )
        
        with self._lock:
            self.tasks[task_id] = task
        
        self._task_queue.put((task_id, func, args, kwargs))
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[AsyncTask]:
        """Obtener estado de una tarea."""
        with self._lock:
            return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[AsyncTask]:
        """Obtener todas las tareas."""
        with self._lock:
            return list(self.tasks.values())
    
    def clear_completed(self):
        """Limpiar tareas completadas o fallidas."""
        with self._lock:
            to_remove = [
                tid for tid, t in self.tasks.items()
                if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
            ]
            for tid in to_remove:
                del self.tasks[tid]
    
    def render_task_status(self, task_id: str):
        """Renderizar status de tarea en Streamlit."""
        task = self.get_task(task_id)
        if not task:
            st.error(f"Tarea {task_id} no encontrada")
            return
        
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            st.write(f"**{task.name}**")
        
        with col2:
            if task.status == TaskStatus.PENDING:
                st.info("⏳ Pendiente")
            elif task.status == TaskStatus.RUNNING:
                st.info(f"🔄 Ejecutando ({task.progress}%)")
            elif task.status == TaskStatus.COMPLETED:
                st.success("✅ Completado")
            elif task.status == TaskStatus.FAILED:
                st.error("❌ Error")
        
        with col3:
            if task.status == TaskStatus.COMPLETED and task.result:
                if isinstance(task.result, dict) and "download" in task.result:
                    st.download_button(
                        "⬇️ Descargar",
                        task.result["data"],
                        file_name=task.result.get("filename", "archivo.bin"),
                        key=f"dl_task_{task_id}"
                    )


# Instancia global del task manager
_task_manager: Optional[BackgroundTaskManager] = None

def get_task_manager() -> BackgroundTaskManager:
    """Obtener instancia del task manager."""
    global _task_manager
    if _task_manager is None:
        _task_manager = BackgroundTaskManager(max_workers=2)
    return _task_manager


# ============================================================
# GENERACIÓN DE PDFS EN BACKGROUND
# ============================================================

def generate_pdf_background(
    generator_fn: Callable,
    *args,
    filename: str = "documento.pdf",
    **kwargs
) -> str:
    """
    Generar PDF en background thread.
    
    Args:
        generator_fn: Función que genera el PDF (debe retornar bytes)
        filename: Nombre del archivo para descarga
        *args, **kwargs: Argumentos para generator_fn
    
    Returns:
        Task ID para seguimiento
    """
    def wrapper():
        pdf_bytes = generator_fn(*args, **kwargs)
        return {
            "download": True,
            "data": pdf_bytes,
            "filename": filename,
            "mime": "application/pdf",
        }
    
    return get_task_manager().submit(
        name=f"Generar PDF: {filename}",
        func=wrapper,
        metadata={"type": "pdf_generation", "filename": filename}
    )


def generate_backup_background(
    paciente_id: str,
    paciente_nombre: str,
) -> str:
    """
    Generar backup integral del paciente en background.
    
    Returns:
        Task ID para seguimiento
    """
    def wrapper():
        from core.clinical_exports import build_backup_pdf_bytes
        from core.utils import ahora
        
        # Este puede tardar varios segundos
        pdf_bytes = build_backup_pdf_bytes(
            paciente_seleccionado=paciente_nombre,
            session_state=st.session_state,
        )
        
        fecha = ahora().strftime("%Y%m%d_%H%M")
        filename = f"backup_{paciente_id}_{fecha}.pdf"
        
        return {
            "download": True,
            "data": pdf_bytes,
            "filename": filename,
            "mime": "application/pdf",
        }
    
    return get_task_manager().submit(
        name=f"Backup integral: {paciente_nombre}",
        func=wrapper,
        metadata={"type": "backup", "paciente_id": paciente_id}
    )


def generate_historia_clinica_pdf_background(
    paciente_id: str,
    paciente_nombre: str,
    secciones: List[str],
) -> str:
    """
    Generar historia clínica en PDF en background.
    
    Returns:
        Task ID para seguimiento
    """
    def wrapper():
        from core.clinical_exports import build_history_pdf_bytes
        from core.utils import ahora
        
        pdf_bytes = build_history_pdf_bytes(
            paciente_seleccionado=paciente_nombre,
            session_state=st.session_state,
            secciones=secciones,
        )
        
        fecha = ahora().strftime("%Y%m%d")
        filename = f"historia_{paciente_id}_{fecha}.pdf"
        
        return {
            "download": True,
            "data": pdf_bytes,
            "filename": filename,
            "mime": "application/pdf",
        }
    
    return get_task_manager().submit(
        name=f"Historia clínica PDF: {paciente_nombre}",
        func=wrapper,
        metadata={"type": "historia_pdf", "paciente_id": paciente_id}
    )


def export_excel_background(
    paciente_id: str,
    paciente_nombre: str,
) -> str:
    """
    Exportar datos del paciente a Excel en background.
    
    Returns:
        Task ID para seguimiento
    """
    def wrapper():
        from core.clinical_exports import build_patient_excel_bytes
        from core.utils import ahora
        
        excel_bytes = build_patient_excel_bytes(
            paciente_seleccionado=paciente_nombre,
            session_state=st.session_state,
        )
        
        fecha = ahora().strftime("%Y%m%d")
        filename = f"datos_{paciente_id}_{fecha}.xlsx"
        
        return {
            "download": True,
            "data": excel_bytes,
            "filename": filename,
            "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
    
    return get_task_manager().submit(
        name=f"Exportar Excel: {paciente_nombre}",
        func=wrapper,
        metadata={"type": "excel_export", "paciente_id": paciente_id}
    )


# ============================================================
# UI PARA STREAMLIT
# ============================================================

def render_pending_tasks_dashboard():
    """Renderizar dashboard de tareas pendientes en Streamlit."""
    st.subheader("📋 Tareas en Proceso")
    
    manager = get_task_manager()
    tasks = manager.get_all_tasks()
    
    if not tasks:
        st.info("No hay tareas en proceso")
        return
    
    # Filtrar tareas activas
    active_tasks = [t for t in tasks if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING)]
    completed_tasks = [t for t in tasks if t.status == TaskStatus.COMPLETED]
    failed_tasks = [t for t in tasks if t.status == TaskStatus.FAILED]
    
    # Mostrar tareas activas
    if active_tasks:
        st.write("**🔄 En progreso:**")
        for task in active_tasks:
            manager.render_task_status(task.id)
    
    # Mostrar tareas completadas con descarga
    if completed_tasks:
        st.write("**✅ Completadas:**")
        for task in completed_tasks[:3]:  # Solo últimas 3
            manager.render_task_status(task.id)
    
    # Mostrar errores
    if failed_tasks:
        st.write("**❌ Con errores:**")
        for task in failed_tasks:
            with st.expander(f"Error en: {task.name}"):
                st.error(task.error or "Error desconocido")
    
    # Botón para limpiar
    if st.button("🧹 Limpiar completadas", key="clear_completed_tasks"):
        manager.clear_completed()


def render_async_pdf_button(
    label: str,
    task_type: str,
    paciente_id: str,
    paciente_nombre: str,
    **kwargs
):
    """
    Renderizar botón que ejecuta generación de PDF en background.
    
    Args:
        label: Texto del botón
        task_type: Tipo de tarea ('backup', 'historia', 'excel')
        paciente_id: ID del paciente
        paciente_nombre: Nombre del paciente
    """
    button_key = f"async_btn_{task_type}_{paciente_id}"
    
    if st.button(label, key=button_key):
        if task_type == "backup":
            task_id = generate_backup_background(paciente_id, paciente_nombre)
        elif task_type == "historia":
            secciones = kwargs.get("secciones", [])
            task_id = generate_historia_clinica_pdf_background(
                paciente_id, paciente_nombre, secciones
            )
        elif task_type == "excel":
            task_id = export_excel_background(paciente_id, paciente_nombre)
        else:
            st.error(f"Tipo de tarea desconocido: {task_type}")
            return
        
        st.session_state[f"_last_task_{task_type}"] = task_id
        st.success(f"✅ {label} iniciado en background")
        st.info("La descarga aparecerá cuando esté listo. Podés seguir usando el sistema.")
    
    # Mostrar estado de tarea anterior
    task_id = st.session_state.get(f"_last_task_{task_type}")
    if task_id:
        manager = get_task_manager()
        task = manager.get_task(task_id)
        if task:
            manager.render_task_status(task_id)
