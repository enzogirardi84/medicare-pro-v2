"""Cola de tareas asincronas para procesamiento intensivo (PDF, GPS).
Desacopla la generacion de PDFs y el geoprocesamiento del hilo
principal de Streamlit usando Redis + workers multiproceso.

Arquitectura:
- Streamlit UI encola tareas y recibe un task_id
- Workers procesan en segundo plano
- Resultados subidos a S3/R2
- UI consulta estado via session_state
"""
from __future__ import annotations

import json
import os
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE TAREA
# ═══════════════════════════════════════════════════════════════════

class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    """Una tarea asincrona."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tipo: str = ""  # "generar_pdf" | "geoprocesar" | "exportar_lote"
    params: dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    resultado: Optional[str] = None  # URL del resultado en S3
    error: str = ""
    creado_en: float = field(default_factory=time.time)
    procesado_en: float = 0.0
    tenant_id: str = "default"
    usuario: str = ""


# ═══════════════════════════════════════════════════════════════════
# 2. COLA DE TAREAS (Redis / in-process)
# ═══════════════════════════════════════════════════════════════════

class TaskQueue(ABC):
    """Cola de tareas abstracta. Implementar con Redis o in-process."""

    @abstractmethod
    def encolar(self, tarea: Task) -> str:
        """Encola una tarea y retorna su ID."""
        ...

    @abstractmethod
    def obtener_resultado(self, task_id: str) -> Optional[Task]:
        """Obtiene el resultado de una tarea por ID."""
        ...

    @abstractmethod
    def procesar_siguiente(self) -> Optional[Task]:
        """Procesa la siguiente tarea de la cola (worker)."""
        ...

    @abstractmethod
    def pending_count(self) -> int:
        ...


class RedisTaskQueue(TaskQueue):
    """Cola de tareas con Redis (produccion).

    Usa Redis Lists para la cola y Redis Hashes para resultados.
    """

    REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
    REDIS_DB = int(os.environ.get("REDIS_DB", "0"))

    def __init__(self):
        self._redis = None
        self._init_redis()

    def _init_redis(self) -> None:
        try:
            import redis as r
            self._redis = r.Redis(
                host=self.REDIS_HOST,
                port=self.REDIS_PORT,
                db=self.REDIS_DB,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=3,
            )
            self._redis.ping()
            log_event("task_queue", "redis_conectado")
        except Exception as exc:
            log_event("task_queue", f"redis_error:{type(exc).__name__}. Usando fallback in-process.")
            self._redis = None

    def _get_redis(self):
        if self._redis is None:
            return None
        try:
            self._redis.ping()
            return self._redis
        except Exception:
            return None

    def encolar(self, tarea: Task) -> str:
        r = self._get_redis()
        if r:
            r.lpush("medicare:tasks:queue", tarea.task_id)
            r.hset(f"medicare:tasks:{tarea.task_id}", mapping={
                "task_id": tarea.task_id,
                "tipo": tarea.tipo,
                "params": json.dumps(tarea.params),
                "status": tarea.status.value,
                "creado_en": str(tarea.creado_en),
                "tenant_id": tarea.tenant_id,
                "usuario": tarea.usuario,
            })
            log_event("task_queue", f"encolada_redis:{tarea.task_id}:{tarea.tipo}")
        return tarea.task_id

    def obtener_resultado(self, task_id: str) -> Optional[Task]:
        r = self._get_redis()
        if r:
            data = r.hgetall(f"medicare:tasks:{task_id}")
            if data:
                return Task(
                    task_id=data.get("task_id", task_id),
                    tipo=data.get("tipo", ""),
                    params=json.loads(data.get("params", "{}")),
                    status=TaskStatus(data.get("status", "pending")),
                    resultado=data.get("resultado"),
                    error=data.get("error", ""),
                    creado_en=float(data.get("creado_en", "0")),
                    procesado_en=float(data.get("procesado_en", "0")),
                    tenant_id=data.get("tenant_id", "default"),
                    usuario=data.get("usuario", ""),
                )
        return None

    def procesar_siguiente(self) -> Optional[Task]:
        r = self._get_redis()
        if r:
            task_id = r.brpoplpush(
                "medicare:tasks:queue",
                "medicare:tasks:processing",
                timeout=5,
            )
            if task_id:
                t = self.obtener_resultado(task_id)
                if t:
                    t.status = TaskStatus.PROCESSING
                    self._actualizar_estado(t)
                    return t
        return None

    def _actualizar_estado(self, tarea: Task) -> None:
        r = self._get_redis()
        if r:
            r.hset(f"medicare:tasks:{tarea.task_id}", "status", tarea.status.value)
            if tarea.resultado:
                r.hset(f"medicare:tasks:{tarea.task_id}", "resultado", tarea.resultado)
            if tarea.error:
                r.hset(f"medicare:tasks:{tarea.task_id}", "error", tarea.error)
            if tarea.procesado_en:
                r.hset(f"medicare:tasks:{tarea.task_id}", "procesado_en", str(tarea.procesado_en))

    def pending_count(self) -> int:
        r = self._get_redis()
        if r:
            return r.llen("medicare:tasks:queue")
        return 0


class InProcessTaskQueue(TaskQueue):
    """Cola in-process (fallback / dev). Usa dict + threading.

    No persiste entre reinicios. Solo para desarrollo.
    """

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._queue: list[str] = []

    def encolar(self, tarea: Task) -> str:
        self._tasks[tarea.task_id] = tarea
        self._queue.append(tarea.task_id)
        return tarea.task_id

    def obtener_resultado(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def procesar_siguiente(self) -> Optional[Task]:
        if not self._queue:
            return None
        task_id = self._queue.pop(0)
        t = self._tasks.get(task_id)
        if t:
            t.status = TaskStatus.PROCESSING
        return t

    def pending_count(self) -> int:
        return len(self._queue)


# ═══════════════════════════════════════════════════════════════════
# 3. WORKER DE PROCESAMIENTO
# ═══════════════════════════════════════════════════════════════════

class TaskWorker:
    """Worker que procesa tareas de la cola en segundo plano.

    Ejecutar como proceso separado:
        python -c "from core.task_queue import TaskWorker; TaskWorker().run()"
    """

    def __init__(self, queue: Optional[TaskQueue] = None):
        self.queue = queue or RedisTaskQueue()
        self._handlers: dict[str, Callable] = {}

    def registrar_handler(self, tipo: str, handler: Callable) -> None:
        """Registra un handler para un tipo de tarea."""
        self._handlers[tipo] = handler

    def procesar_tarea(self, tarea: Task) -> None:
        """Procesa una tarea y actualiza su estado."""
        handler = self._handlers.get(tarea.tipo)
        if handler is None:
            tarea.status = TaskStatus.FAILED
            tarea.error = f"No hay handler registrado para tipo: {tarea.tipo}"
            return

        try:
            t0 = time.time()
            resultado = handler(tarea.params)
            tarea.status = TaskStatus.COMPLETED
            tarea.resultado = resultado
            tarea.procesado_en = time.time()
            log_event("task_queue", f"completada:{tarea.task_id}:{tarea.tipo}:{(time.time()-t0)*1000:.0f}ms")
        except Exception as exc:
            tarea.status = TaskStatus.FAILED
            tarea.error = f"{type(exc).__name__}: {exc}"
            tarea.procesado_en = time.time()
            log_event("task_queue", f"fallo:{tarea.task_id}:{tarea.tipo}:{exc}")

    def run(self, intervalo: float = 0.5) -> None:
        """Loop principal del worker."""
        log_event("task_queue", "worker_iniciado")
        while True:
            tarea = self.queue.procesar_siguiente()
            if tarea:
                self.procesar_tarea(tarea)
                self.queue._actualizar_estado(tarea) if hasattr(self.queue, '_actualizar_estado') else None
            else:
                time.sleep(intervalo)


# ═══════════════════════════════════════════════════════════════════
# 4. HANDLER PREDEFINIDO: GENERAR PDF
# ═══════════════════════════════════════════════════════════════════

def handler_generar_pdf(params: dict[str, Any]) -> str:
    """Genera un PDF clinico y lo sube a S3. Retorna URL."""
    from core.clinical_pdf import ClinicalPDFGenerator, DatosEvolucion
    from core.cloud_storage import CloudStorage

    datos = DatosEvolucion(**params.get("datos", {}))
    gen = ClinicalPDFGenerator()
    pdf_bytes = gen.generar(datos)

    tenant = params.get("tenant_id", "default")
    storage = CloudStorage(tenant_id=tenant)
    result = storage.subir_archivo(
        pdf_bytes,
        f"evolucion_{datos.paciente}_{int(time.time())}.pdf",
        "application/pdf",
        metadata={"tenant": tenant, "paciente": datos.paciente},
    )
    if result:
        return result.get("url", "")
    raise RuntimeError("No se pudo subir el PDF a S3")


# ═══════════════════════════════════════════════════════════════════
# 5. INTEGRACION CON STREAMLIT UI
# ═══════════════════════════════════════════════════════════════════

def encolar_generar_pdf_async(
    datos_evolucion: Any,
    tenant_id: str = "default",
    usuario: str = "",
) -> str:
    """Encola la generacion de un PDF y retorna el task_id.

    La UI debe llamar a esta funcion y luego consultar el estado
    mediante task_queue.obtener_resultado(task_id).
    """
    queue = RedisTaskQueue()
    tarea = Task(
        tipo="generar_pdf",
        params={
            "datos": datos_evolucion.__dict__ if hasattr(datos_evolucion, '__dict__') else datos_evolucion,
            "tenant_id": tenant_id,
        },
        tenant_id=tenant_id,
        usuario=usuario,
    )
    queue.encolar(tarea)
    return tarea.task_id


def render_task_status(task_id: str) -> Optional[str]:
    """Renderiza el estado de una tarea en Streamlit.

    Returns:
        URL del resultado si la tarea se completo, None si no.
    """
    import streamlit as st
    queue = RedisTaskQueue()
    tarea = queue.obtener_resultado(task_id)
    if tarea is None:
        st.caption("Tarea no encontrada.")
        return None
    if tarea.status == TaskStatus.PENDING:
        st.info("Tarea en cola...")
        return None
    if tarea.status == TaskStatus.PROCESSING:
        with st.spinner("Procesando..."):
            pass
        return None
    if tarea.status == TaskStatus.COMPLETED:
        st.success("Documento generado.")
        return tarea.resultado
    if tarea.status == TaskStatus.FAILED:
        st.error(f"Error: {tarea.error}")
        return None
    return None
