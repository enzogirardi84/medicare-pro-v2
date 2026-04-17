"""
Batch Processor para operaciones masivas eficientes.

- Procesamiento por chunks para no saturar memoria
- Paralelización controlada
- Checkpointing para reanudación
- Dead letter queue para items fallidos
"""

from __future__ import annotations

import concurrent.futures
import threading
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Generic, Iterator, List, Optional, TypeVar, Tuple

import streamlit as st

from core.app_logging import log_event

# Import perf_metrics with fallback to prevent KeyError crashes
try:
    from core.perf_metrics import record_perf
except Exception:
    # Fallback: dummy function if perf_metrics fails to import
    def record_perf(event: str, duration_ms: float, ok: bool = True) -> None:
        pass

T = TypeVar('T')
R = TypeVar('R')


class BatchStatus(Enum):
    """Estados de un job batch."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProcessingStrategy(Enum):
    """Estrategias de procesamiento."""
    SEQUENTIAL = "sequential"      # Uno por uno, más seguro
    PARALLEL_THREADS = "threads"  # Paralelización con threads
    CHUNKED = "chunked"          # Procesamiento por chunks


@dataclass
class BatchJob:
    """Definición de un job batch."""
    job_id: str
    name: str
    items: List[Any]
    processor: Callable[[Any], Any]
    strategy: ProcessingStrategy = ProcessingStrategy.CHUNKED
    chunk_size: int = 100
    max_workers: int = 4
    retry_attempts: int = 3
    checkpoint_interval: int = 500
    continue_on_error: bool = True


@dataclass
class BatchResult:
    """Resultado de procesamiento batch."""
    job_id: str
    status: BatchStatus
    processed_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    dead_letter_items: List[Tuple[Any, str]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    checkpoints: List[int] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0

    @property
    def success_rate(self) -> float:
        total = self.processed_count
        return self.success_count / total if total > 0 else 0.0


@dataclass
class Checkpoint:
    """Punto de control para reanudación."""
    job_id: str
    last_processed_index: int
    timestamp: float
    partial_results: Dict[str, Any]


class BatchProcessor:
    """
    Procesador de operaciones batch optimizado para millones de items.
    """

    def __init__(
        self,
        default_chunk_size: int = 100,
        default_max_workers: int = 4,
        enable_checkpoints: bool = True,
    ):
        self.default_chunk_size = default_chunk_size
        self.default_max_workers = default_max_workers
        self.enable_checkpoints = enable_checkpoints

        self._active_jobs: Dict[str, BatchJob] = {}
        self._job_results: Dict[str, BatchResult] = {}
        self._checkpoints: Dict[str, Checkpoint] = {}
        self._lock = threading.RLock()
        self._stop_flags: Dict[str, threading.Event] = {}

    def _get_checkpoint_key(self, job_id: str, tenant: str) -> str:
        return f"batch_checkpoint:{tenant}:{job_id}"

    def _load_checkpoint(self, job_id: str, tenant: str) -> Optional[Checkpoint]:
        """Carga checkpoint desde session_state."""
        if not self.enable_checkpoints:
            return None

        key = self._get_checkpoint_key(job_id, tenant)
        checkpoint_data = st.session_state.get(key)
        if checkpoint_data and isinstance(checkpoint_data, dict):
            return Checkpoint(
                job_id=checkpoint_data.get("job_id", job_id),
                last_processed_index=checkpoint_data.get("last_processed_index", 0),
                timestamp=checkpoint_data.get("timestamp", 0),
                partial_results=checkpoint_data.get("partial_results", {}),
            )
        return None

    def _save_checkpoint(
        self,
        job_id: str,
        tenant: str,
        last_index: int,
        partial_results: Dict[str, Any],
    ):
        """Guarda checkpoint en session_state."""
        if not self.enable_checkpoints:
            return

        key = self._get_checkpoint_key(job_id, tenant)
        st.session_state[key] = {
            "job_id": job_id,
            "last_processed_index": last_index,
            "timestamp": time.time(),
            "partial_results": partial_results,
        }

    def _clear_checkpoint(self, job_id: str, tenant: str):
        """Limpia checkpoint después de completar."""
        key = self._get_checkpoint_key(job_id, tenant)
        if key in st.session_state:
            del st.session_state[key]

    def submit_job(
        self,
        job: BatchJob,
        tenant: str = "default",
    ) -> str:
        """
        Sube un job para procesamiento.

        Returns:
            job_id para seguimiento
        """
        with self._lock:
            self._active_jobs[job.job_id] = job
            self._job_results[job.job_id] = BatchResult(
                job_id=job.job_id,
                status=BatchStatus.PENDING,
            )
            self._stop_flags[job.job_id] = threading.Event()

        log_event("batch", f"job_submitted:{job.job_id}:{len(job.items)}_items")
        return job.job_id

    def run_job(
        self,
        job_id: str,
        tenant: str = "default",
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> BatchResult:
        """
        Ejecuta un job batch de forma síncrona.

        Args:
            job_id: ID del job
            tenant: Tenant para checkpointing
            progress_callback: Callback(procesados, total) -> None

        Returns:
            BatchResult con resultados
        """
        with self._lock:
            job = self._active_jobs.get(job_id)
            if not job:
                raise ValueError(f"Job {job_id} no encontrado")

            result = self._job_results[job_id]
            result.status = BatchStatus.RUNNING
            result.start_time = time.time()
            stop_flag = self._stop_flags[job_id]

        # Cargar checkpoint si existe
        checkpoint = self._load_checkpoint(job_id, tenant)
        start_index = checkpoint.last_processed_index if checkpoint else 0

        try:
            if job.strategy == ProcessingStrategy.SEQUENTIAL:
                self._run_sequential(
                    job, result, start_index, stop_flag, progress_callback
                )
            elif job.strategy == ProcessingStrategy.PARALLEL_THREADS:
                self._run_parallel(
                    job, result, start_index, stop_flag, progress_callback
                )
            else:  # CHUNKED
                self._run_chunked(
                    job, result, start_index, stop_flag, tenant, progress_callback
                )

            if not stop_flag.is_set():
                result.status = BatchStatus.COMPLETED
                result.end_time = time.time()
                self._clear_checkpoint(job_id, tenant)
            else:
                result.status = BatchStatus.CANCELLED

        except Exception as e:
            result.status = BatchStatus.FAILED
            result.end_time = time.time()
            result.errors.append(f"Error fatal: {str(e)}")
            log_event("batch", f"job_failed:{job_id}:{type(e).__name__}")

        with self._lock:
            self._job_results[job_id] = result

        return result

    def _run_sequential(
        self,
        job: BatchJob,
        result: BatchResult,
        start_index: int,
        stop_flag: threading.Event,
        progress_callback: Optional[Callable],
    ):
        """Ejecución secuencial."""
        for idx, item in enumerate(job.items[start_index:], start=start_index):
            if stop_flag.is_set():
                break

            success, error = self._process_item_with_retry(
                item, job.processor, job.retry_attempts
            )

            result.processed_count += 1
            if success:
                result.success_count += 1
            else:
                result.failed_count += 1
                result.dead_letter_items.append((item, error))
                if not job.continue_on_error:
                    raise RuntimeError(f"Job detenido por error: {error}")

            if progress_callback and idx % 10 == 0:
                progress_callback(result.processed_count, len(job.items))

    def _run_parallel(
        self,
        job: BatchJob,
        result: BatchResult,
        start_index: int,
        stop_flag: threading.Event,
        progress_callback: Optional[Callable],
    ):
        """Ejecución paralela con ThreadPoolExecutor."""
        items_to_process = job.items[start_index:]
        total = len(items_to_process)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=job.max_workers
        ) as executor:
            future_to_item = {
                executor.submit(
                    self._process_item_with_retry,
                    item,
                    job.processor,
                    job.retry_attempts,
                ): item
                for item in items_to_process[:job.max_workers * 2]
            }

            processed = 0
            while future_to_item and not stop_flag.is_set():
                done, _ = concurrent.futures.wait(
                    future_to_item,
                    timeout=1,
                    return_when=concurrent.futures.FIRST_COMPLETED
                )

                for future in done:
                    item = future_to_item.pop(future)
                    processed += 1

                    try:
                        success, error = future.result()
                        result.processed_count += 1
                        if success:
                            result.success_count += 1
                        else:
                            result.failed_count += 1
                            result.dead_letter_items.append((item, error))
                    except Exception as e:
                        result.failed_count += 1
                        result.dead_letter_items.append((item, str(e)))

                    if progress_callback and processed % 10 == 0:
                        progress_callback(
                            result.processed_count + start_index,
                            len(job.items)
                        )

    def _run_chunked(
        self,
        job: BatchJob,
        result: BatchResult,
        start_index: int,
        stop_flag: threading.Event,
        tenant: str,
        progress_callback: Optional[Callable],
    ):
        """Ejecución por chunks con checkpointing."""
        items_to_process = job.items[start_index:]
        chunks = self._chunk_list(items_to_process, job.chunk_size)

        chunk_idx = 0
        for chunk in chunks:
            if stop_flag.is_set():
                break

            chunk_start = time.time()

            for item in chunk:
                if stop_flag.is_set():
                    break

                success, error = self._process_item_with_retry(
                    item, job.processor, job.retry_attempts
                )

                result.processed_count += 1
                if success:
                    result.success_count += 1
                else:
                    result.failed_count += 1
                    result.dead_letter_items.append((item, error))
                    if not job.continue_on_error:
                        raise RuntimeError(f"Job detenido: {error}")

            chunk_idx += 1
            current_index = start_index + (chunk_idx * job.chunk_size)

            # Guardar checkpoint
            if chunk_idx % max(1, job.checkpoint_interval // job.chunk_size) == 0:
                self._save_checkpoint(
                    job.job_id,
                    tenant,
                    current_index,
                    {"success_count": result.success_count},
                )
                result.checkpoints.append(current_index)

            # Métricas de performance
            chunk_duration = (time.time() - chunk_start) * 1000
            record_perf("batch_chunk", chunk_duration, ok=True)

            if progress_callback:
                progress_callback(
                    result.processed_count + start_index,
                    len(job.items)
                )

    def _process_item_with_retry(
        self,
        item: Any,
        processor: Callable[[Any], Any],
        max_attempts: int,
    ) -> Tuple[bool, str]:
        """Procesa un item con reintentos."""
        last_error = ""

        for attempt in range(max_attempts):
            try:
                start = time.time()
                processor(item)
                duration = (time.time() - start) * 1000
                record_perf("batch_item", duration, ok=True)
                return True, ""
            except Exception as e:
                last_error = str(e)
                if attempt < max_attempts - 1:
                    time.sleep(0.1 * (attempt + 1))  # Backoff incremental

        return False, last_error

    def _chunk_list(self, items: List[T], chunk_size: int) -> Iterator[List[T]]:
        """Divide lista en chunks."""
        for i in range(0, len(items), chunk_size):
            yield items[i:i + chunk_size]

    def cancel_job(self, job_id: str) -> bool:
        """Cancela un job en ejecución."""
        with self._lock:
            stop_flag = self._stop_flags.get(job_id)
            if stop_flag:
                stop_flag.set()
                log_event("batch", f"job_cancelled:{job_id}")
                return True
            return False

    def get_job_status(self, job_id: str) -> Optional[BatchResult]:
        """Obtiene estado de un job."""
        with self._lock:
            return self._job_results.get(job_id)

    def list_active_jobs(self) -> List[str]:
        """Lista jobs activos."""
        with self._lock:
            return [
                job_id for job_id, result in self._job_results.items()
                if result.status in (BatchStatus.PENDING, BatchStatus.RUNNING)
            ]


class BulkDataImporter:
    """
    Importador masivo de datos con validación y transformación.
    """

    def __init__(
        self,
        validator: Optional[Callable[[Any], Tuple[bool, str]]] = None,
        transformer: Optional[Callable[[Any], Any]] = None,
        batch_size: int = 500,
    ):
        self.validator = validator
        self.transformer = transformer
        self.batch_size = batch_size
        self._import_stats: Dict[str, Any] = {}

    def import_data(
        self,
        data: List[Dict[str, Any]],
        inserter: Callable[[List[Any]], None],
        tenant: str = "default",
    ) -> Dict[str, Any]:
        """
        Importa datos en bulk con validación.

        Returns:
            Estadísticas de importación
        """
        stats = {
            "total": len(data),
            "valid": 0,
            "invalid": 0,
            "imported": 0,
            "errors": [],
        }

        valid_items = []

        # Validación
        for item in data:
            if self.validator:
                is_valid, error = self.validator(item)
                if is_valid:
                    stats["valid"] += 1
                    if self.transformer:
                        item = self.transformer(item)
                    valid_items.append(item)
                else:
                    stats["invalid"] += 1
                    stats["errors"].append(f"Validación fallida: {error}")
            else:
                valid_items.append(item)
                stats["valid"] += 1

        # Importación por batches
        for i in range(0, len(valid_items), self.batch_size):
            batch = valid_items[i:i + self.batch_size]
            try:
                inserter(batch)
                stats["imported"] += len(batch)
            except Exception as e:
                stats["errors"].append(f"Error en batch {i//self.batch_size}: {str(e)}")
                log_event("bulk_import", f"batch_error:{tenant}:{e}")

        self._import_stats[tenant] = stats
        return stats


# Singleton global
_processor_instance: Optional[BatchProcessor] = None
_processor_lock = threading.Lock()


def get_batch_processor() -> BatchProcessor:
    """Obtiene instancia global del batch processor."""
    global _processor_instance
    if _processor_instance is None:
        with _processor_lock:
            if _processor_instance is None:
                _processor_instance = BatchProcessor()
    return _processor_instance


def create_batch_job(
    name: str,
    items: List[Any],
    processor: Callable[[Any], Any],
    strategy: ProcessingStrategy = ProcessingStrategy.CHUNKED,
    **kwargs
) -> BatchJob:
    """Crea un job batch con configuración por defecto."""
    import uuid

    return BatchJob(
        job_id=str(uuid.uuid4())[:8],
        name=name,
        items=items,
        processor=processor,
        strategy=strategy,
        **kwargs
    )
