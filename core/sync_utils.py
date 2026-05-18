"""Utilidades de sincronizacion: vencimiento automatico de recetas, sync pendiente."""
from datetime import datetime, timedelta

from core.app_logging import log_event


def auto_vencer_indicaciones(indicaciones: list):
    """Marca como Completada las indicaciones cuyo ciclo de dias ya vencio. Modifica la lista in-place."""
    _hoy = datetime.now().date()
    _modificadas = 0
    for r in indicaciones:
        if r.get("estado_receta", "Activa") != "Activa":
            continue
        try:
            _dur = int(r.get("dias_duracion", 0) or 0)
            if _dur <= 0:
                continue
            _fecha_str = str(r.get("fecha", ""))[:10]
            _inicio = datetime.strptime(_fecha_str, "%d/%m/%Y").date() if "/" in _fecha_str else datetime.fromisoformat(_fecha_str).date()
            if (_inicio + timedelta(days=_dur)) < _hoy:
                r["estado_receta"] = "Completada"
                r["estado_clinico"] = "Completada"
                _sql_id = r.get("_sql_id", "")
                if _sql_id:
                    try:
                        from core._db_sql_clinico import update_estado_indicacion
                        update_estado_indicacion(_sql_id, "Completada")
                    except Exception:
                        pass
                _modificadas += 1
        except Exception:
            pass
    if _modificadas:
        log_event("sync_utils", f"auto_vencer: {_modificadas} indicaciones marcadas como Completadas")
    return _modificadas


def sync_pendientes_agenda_sql(session_state: dict):
    """Intenta sincronizar turnos de agenda_db que no tienen id_sql."""
    pendientes = [
        t for t in session_state.get("agenda_db", [])
        if not t.get("id_sql") and t.get("paciente") and t.get("fecha_hora_programada")
    ]
    if not pendientes:
        return 0
    try:
        from core.db_sql import insert_turno
        from core.nextgen_sync import _obtener_uuid_empresa, _obtener_uuid_paciente
        sinc = 0
        for t in pendientes:
            empresa = t.get("empresa", "")
            pac = str(t.get("paciente", ""))
            partes = pac.split(" - ")
            if len(partes) <= 1:
                continue
            dni = partes[1].strip()
            empresa_uuid = _obtener_uuid_empresa(empresa)
            if not empresa_uuid:
                continue
            pac_uuid = _obtener_uuid_paciente(dni, empresa_uuid)
            if not pac_uuid:
                continue
            datos = {
                "paciente_id": pac_uuid,
                "empresa_id": empresa_uuid,
                "fecha_hora_programada": t.get("fecha_hora_programada", ""),
                "estado": t.get("estado", "Pendiente"),
            }
            prof = str(t.get("profesional", "")).strip()
            if prof:
                from core.database import supabase
                if supabase:
                    res = supabase.table("usuarios").select("id").eq("nombre", prof).eq("empresa_id", empresa_uuid).limit(1).execute()
                    if res and res.data:
                        datos["profesional_id"] = res.data[0]["id"]
            result = insert_turno(datos)
            if result:
                t["id_sql"] = result.get("id")
                sinc += 1
        if sinc:
            log_event("sync_utils", f"sync_agenda: {sinc} turnos sincronizados a SQL")
        return sinc
    except Exception as e:
        log_event("sync_utils", f"sync_agenda_error:{type(e).__name__}:{e}")
        return 0


def sync_pendientes_consumos_sql(session_state: dict):
    """Intenta sincronizar consumos_db a inventario_movimientos SQL."""
    pendientes = [
        c for c in session_state.get("consumos_db", [])
        if not c.get("id_sql") and c.get("insumo") and c.get("paciente")
    ]
    if not pendientes:
        return 0
    try:
        from core.db_sql import get_inventario_item_by_name, insert_inventario_movimiento
        from core.nextgen_sync import _obtener_uuid_empresa, _obtener_uuid_paciente
        sinc = 0
        for c in pendientes:
            empresa = c.get("empresa", "")
            pac = str(c.get("paciente", ""))
            partes = pac.split(" - ")
            if len(partes) <= 1:
                continue
            dni = partes[1].strip()
            empresa_uuid = _obtener_uuid_empresa(empresa)
            if not empresa_uuid:
                continue
            pac_uuid = _obtener_uuid_paciente(dni, empresa_uuid)
            item = get_inventario_item_by_name(empresa_uuid, c.get("insumo", ""))
            if not item:
                continue
            stock_actual = int(item.get("stock_actual", 0))
            cant = int(c.get("cantidad", 0) or 0)
            mov = {
                "inventario_id": item["id"],
                "paciente_id": pac_uuid,
                "empresa_id": empresa_uuid,
                "tipo_movimiento": "Salida",
                "cantidad": cant,
                "stock_anterior": stock_actual,
                "stock_nuevo": max(0, stock_actual - cant),
                "motivo": f"Sync automatico: {c.get('insumo', '')} - {c.get('paciente', '')}",
                "referencia_documento": "SYNC_AUTO",
            }
            result = insert_inventario_movimiento(mov)
            if result:
                c["id_sql"] = result.get("id")
                sinc += 1
        if sinc:
            log_event("sync_utils", f"sync_consumos: {sinc} consumos sincronizados a SQL")
        return sinc
    except Exception as e:
        log_event("sync_utils", f"sync_consumos_error:{type(e).__name__}:{e}")
        return 0


def sync_pendientes_facturacion_sql(session_state: dict):
    """Sincroniza facturacion_db pendiente a SQL."""
    pendientes = [
        f for f in session_state.get("facturacion_db", [])
        if not f.get("id_sql") and f.get("paciente") and f.get("importe")
    ]
    if not pendientes:
        return 0
    try:
        from core.db_sql import insert_facturacion
        from core.nextgen_sync import _obtener_uuid_empresa, _obtener_uuid_paciente
        sinc = 0
        for f in pendientes:
            empresa = f.get("empresa", "")
            pac = str(f.get("paciente", ""))
            partes = pac.split(" - ")
            if len(partes) <= 1:
                continue
            dni = partes[1].strip()
            empresa_uuid = _obtener_uuid_empresa(empresa)
            if not empresa_uuid:
                continue
            pac_uuid = _obtener_uuid_paciente(dni, empresa_uuid)
            if not pac_uuid:
                continue
            datos = {
                "paciente_id": pac_uuid,
                "empresa_id": empresa_uuid,
                "fecha_emision": f.get("fecha_emision", ""),
                "concepto": f"Insumo: {f.get('insumo', '')}",
                "importe": float(f.get("importe", 0)),
                "estado": "Pendiente",
            }
            result = insert_facturacion(datos)
            if result:
                f["id_sql"] = result.get("id")
                sinc += 1
        if sinc:
            log_event("sync_utils", f"sync_facturacion: {sinc} registros sincronizados a SQL")
        return sinc
    except Exception as e:
        log_event("sync_utils", f"sync_facturacion_error:{type(e).__name__}:{e}")
        return 0


def backup_diario_sql(session_state: dict):
    """Exporta las claves _db del session_state a la tabla backup_diario en SQL."""
    _db_keys = [k for k in session_state.keys() if k.endswith("_db") and isinstance(session_state[k], list)]
    if not _db_keys:
        return 0
    try:
        import json
        from datetime import date
        from core.database import supabase
        if supabase is None:
            return 0
        payload = {
            "fecha": str(date.today()),
            "datos": {k: session_state[k] for k in _db_keys},
            "tipo": "backup_diario_auto",
        }
        response = supabase.table("backup_diario").insert(payload).execute()
        if response and response.data:
            log_event("sync_utils", f"backup_diario: {len(_db_keys)} claves respaldadas")
            return 1
        return 0
    except Exception as e:
        log_event("sync_utils", f"backup_diario_error:{type(e).__name__}:{e}")
        return 0


def sync_todo(session_state: dict):
    """Ejecuta todas las sincronizaciones pendientes."""
    total = 0
    total += auto_vencer_indicaciones(session_state.get("indicaciones_db", []))
    total += sync_pendientes_agenda_sql(session_state)
    total += sync_pendientes_consumos_sql(session_state)
    total += sync_pendientes_facturacion_sql(session_state)
    total += backup_diario_sql(session_state)
    if total:
        log_event("sync_utils", f"sync_todo: {total} operaciones realizadas")
    return total
