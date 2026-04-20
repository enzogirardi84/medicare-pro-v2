"""BulkDataImporter. Extraído de core/batch_processor.py."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from core.app_logging import log_event


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
