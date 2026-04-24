import threading
import time

from sqlalchemy import select

from app.core.config import settings
from app.infrastructure.db import SessionLocal
from app.infrastructure.models import Tenant
from app.services.outbox_service import flush_outbox_for_tenant


def _run_loop() -> None:
    while True:
        db = None
        try:
            db = SessionLocal()
            tenants = db.scalars(select(Tenant.id)).all()
            for tenant_id in tenants:
                flush_outbox_for_tenant(db, tenant_id=tenant_id, limit=settings.outbox_flush_batch_size)
        except Exception as _exc:
            # Scheduler defensivo: nunca tumbar proceso API.
            import logging
            logging.getLogger("outbox_scheduler").warning(f"fallo_flush_cycle:{type(_exc).__name__}")
        finally:
            try:
                if db is not None:
                    db.close()
            except Exception as _exc:
                import logging
                logging.getLogger("outbox_scheduler").debug(f"fallo_db_close:{type(_exc).__name__}")
        time.sleep(max(5, int(settings.outbox_auto_flush_interval_seconds)))


def start_outbox_scheduler() -> None:
    if not settings.outbox_auto_flush_enabled:
        return
    t = threading.Thread(target=_run_loop, name="outbox-scheduler", daemon=True)
    t.start()
