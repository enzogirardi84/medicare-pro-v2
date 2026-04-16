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
        except Exception:
            # Scheduler defensivo: nunca tumbar proceso API.
            pass
        finally:
            try:
                if db is not None:
                    db.close()
            except Exception:
                pass
        time.sleep(max(5, int(settings.outbox_auto_flush_interval_seconds)))


def start_outbox_scheduler() -> None:
    if not settings.outbox_auto_flush_enabled:
        return
    t = threading.Thread(target=_run_loop, name="outbox-scheduler", daemon=True)
    t.start()
