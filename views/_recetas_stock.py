"""Control de stock optimizado.

Registra administración clínica + consumo + descuento de inventario.
Optimización: evita consultas SQL repetidas en cada render y reemplaza guardados
bloqueantes dobles por un guardado silencioso agrupado.
"""

from __future__ import annotations

import time

import streamlit as st

from core.app_logging import log_event
from core.alert_toasts import queue_toast
from core.database import guardar_datos
from core.utils import ahora, registrar_auditoria_legal
from views._recetas_utils import nombre_usuario

_CACHE_TTL_UUIDS = 180.0
_CACHE_TTL_ITEM = 45.0


def _cache_get(key: str, ttl: float):
    item = st.session_state.get(key)
    if not isinstance(item, dict):
        return None
    if (time.monotonic() - float(item.get("ts", 0.0))) > ttl:
        st.session_state.pop(key, None)
        return None
    return item.get("value")


def _cache_set(key: str, value) -> None:
    st.session_state[key] = {"ts": time.monotonic(), "value": value}


def _restaurar_stock_local(mi_empresa, insumo, cantidad):
    for item in st.session_state.get("inventario_db", []):
        if item is None:
            continue
        if item.get("item") == insumo and item.get("empresa") == mi_empresa:
            item["stock"] = int(item.get("stock") or 0) + cantidad
            return


def _descontar_stock_local(mi_empresa, insumo, cantidad):
    for item in st.session_state.get("inventario_db", []):
        if item is None:
            continue
        if item.get("item") == insumo and item.get("empresa") == mi_empresa:
            item["stock"] = max(0, int(item.get("stock") or 0) - int(cantidad))
            return True
    return False


def _append_local_list(clave_db: str, payload: dict, max_items: int = 1000) -> None:
    """Agrega a session_state sin persistir todavía. Persistimos una sola vez al final."""
    if clave_db not in st.session_state or not isinstance(st.session_state[clave_db], list):
        st.session_state[clave_db] = []
    st.session_state[clave_db].append(payload)
    if len(st.session_state[clave_db]) > max_items:
        st.session_state[clave_db] = st.session_state[clave_db][-max_items:]


def _registrar_consumo_en_sql(paciente_sel, mi_empresa, user, med_name, cantidad, empresa_uuid, paciente_uuid, user_uuid):
    """Inserta movimiento SQL. El trigger SQL puede auto-descontar stock."""
    from core.db_sql import get_inventario_item_by_name, insert_inventario_movimiento, update_inventario_stock_sql

    item_key = f"_stock_item_sql_{empresa_uuid}_{med_name}"
    item = _cache_get(item_key, _CACHE_TTL_ITEM)
    if item is None:
        item = get_inventario_item_by_name(empresa_uuid, med_name)
        _cache_set(item_key, item)
    if not item:
        return False

    stock_actual = int(item.get("stock_actual", 0) or 0)
    stock_nuevo = max(0, stock_actual - int(cantidad))
    mov = {
        "inventario_id": item["id"],
        "paciente_id": paciente_uuid,
        "usuario_id": user_uuid,
        "empresa_id": empresa_uuid,
        "tipo_movimiento": "Salida",
        "cantidad": int(cantidad),
        "stock_anterior": stock_actual,
        "stock_nuevo": stock_nuevo,
        "motivo": f"Administración clínica: {med_name} - {paciente_sel}",
        "referencia_documento": "RECETA_AUTOMATICA",
    }
    result = insert_inventario_movimiento(mov)
    if not result:
        update_inventario_stock_sql(item["id"], stock_nuevo, empresa_uuid)

    # Invalida caché para que el próximo render muestre stock fresco.
    st.session_state.pop(item_key, None)
    return True


def _resolver_uuids(paciente_sel, mi_empresa):
    """Retorna (empresa_uuid, paciente_uuid, user_uuid). Cacheado para no consultar SQL en cada render."""
    cache_key = f"_stock_uuid_cache_{mi_empresa}_{paciente_sel}_{st.session_state.get('u_actual', {}).get('usuario_login', '')}"
    cached = _cache_get(cache_key, _CACHE_TTL_UUIDS)
    if cached is not None:
        return cached

    from core.nextgen_sync import _obtener_uuid_empresa, _obtener_uuid_paciente
    try:
        partes = str(paciente_sel or "").split(" - ")
        if len(partes) <= 1:
            value = (None, None, None)
            _cache_set(cache_key, value)
            return value

        dni = partes[1].strip()
        empresa_uuid = _obtener_uuid_empresa(mi_empresa)
        if not empresa_uuid:
            value = (None, None, None)
            _cache_set(cache_key, value)
            return value

        paciente_uuid = _obtener_uuid_paciente(dni, empresa_uuid)
        if not paciente_uuid:
            value = (empresa_uuid, None, None)
            _cache_set(cache_key, value)
            return value

        user_uuid = None
        usuario_login = st.session_state.get("u_actual", {}).get("usuario_login", "")
        if usuario_login:
            try:
                from core.database import supabase
                if supabase:
                    res = supabase.table("usuarios").select("id").eq("usuario_login", usuario_login).limit(1).execute()
                    if res and res.data:
                        user_uuid = res.data[0]["id"]
            except Exception:
                user_uuid = None

        value = (empresa_uuid, paciente_uuid, user_uuid)
        _cache_set(cache_key, value)
        return value
    except Exception:
        value = (None, None, None)
        _cache_set(cache_key, value)
        return value


def _obtener_item_inventario_cached(empresa_uuid: str | None, med_sel: str):
    if not empresa_uuid or not med_sel:
        return None
    key = f"_stock_item_sql_{empresa_uuid}_{med_sel}"
    cached = _cache_get(key, _CACHE_TTL_ITEM)
    if cached is not None:
        return cached
    try:
        from core.db_sql import get_inventario_item_by_name
        item = get_inventario_item_by_name(empresa_uuid, med_sel)
        _cache_set(key, item)
        return item
    except Exception:
        _cache_set(key, None)
        return None


def render_control_medicacion_stock(paciente_sel, mi_empresa, user, recs_activas):
    """Sección: seleccionar medicación activa, indicar cantidad y registrar rápido."""
    if not recs_activas:
        return

    st.divider()
    st.markdown("### Control de stock por medicación administrada")
    st.caption(
        "Seleccioná la medicación, ingresá la cantidad utilizada y ejecutá el registro. "
        "El sistema guarda la administración clínica, registra el consumo en insumos y descuenta del inventario."
    )

    nombres_med = sorted(set(
        r.get("med", "").strip()
        for r in recs_activas
        if r.get("med", "").strip()
    ))
    if not nombres_med:
        st.caption("No hay medicaciones activas con nombre registrado.")
        return

    sel_key = f"_stock_med_sel_{paciente_sel}"
    qty_key = f"_stock_med_qty_{paciente_sel}"
    btn_key = f"_stock_btn_{paciente_sel}"
    saving_key = f"_stock_saving_{paciente_sel}"

    c1, c2 = st.columns([3, 1])
    med_sel = c1.selectbox("Medicación a registrar", nombres_med, key=sel_key)
    cantidad = int(c2.number_input("Cantidad utilizada", min_value=1, value=1, step=1, key=qty_key))

    # Caché: evita pegarle a SQL en cada rerun. En celular esto baja mucho la espera.
    empresa_uuid, paciente_uuid, user_uuid = _resolver_uuids(paciente_sel, mi_empresa)
    item_inv = _obtener_item_inventario_cached(empresa_uuid, med_sel) if empresa_uuid else None
    if empresa_uuid and item_inv:
        st.caption(f"Stock actual en inventario: **{item_inv.get('stock_actual', '?')}**")
    elif empresa_uuid:
        st.caption("Este medicamento no está cargado en el inventario. Se registrará solo la administración clínica y el consumo local.")
    else:
        st.caption("Sin conexión SQL. Solo se registrará en modo local (sesión).")

    if st.session_state.get(saving_key):
        st.info("Guardando registro...")

    if st.button(
        "Registrar y descontar stock",
        type="primary",
        width='stretch',
        key=btn_key,
        disabled=bool(st.session_state.get(saving_key)),
    ):
        st.session_state[saving_key] = True
        t0 = time.monotonic()
        ts_evento = ahora()
        hora_str = ts_evento.strftime("%H:%M")
        fecha_hoy = ts_evento.strftime("%d/%m/%Y")
        mat_prof = str(user.get("matricula", "") or "").strip() if isinstance(user, dict) else ""
        login_ref = str(user.get("usuario_login", user.get("usuario", "")) or "").strip() if isinstance(user, dict) else ""
        prof_name = nombre_usuario(user)

        exito_sql = True
        try:
            # 1) Registro clínico: solo session_state, sin guardar todavía.
            _append_local_list("administracion_med_db", {
                "paciente": paciente_sel,
                "med": med_sel,
                "fecha": fecha_hoy,
                "hora": hora_str,
                "horario_programado": "Stock automático",
                "estado": "Realizada",
                "motivo": "",
                "firma": prof_name,
                "matricula_profesional": mat_prof,
                "usuario_login": login_ref,
                "registro_iso": ts_evento.isoformat(timespec="seconds"),
                "registro_fecha_hora": ts_evento.strftime("%d/%m/%Y %H:%M:%S"),
                "empresa": mi_empresa,
                "cantidad": cantidad,
            }, max_items=1000)

            # 2) Consumo local.
            _append_local_list("consumos_db", {
                "paciente": paciente_sel,
                "insumo": med_sel,
                "cantidad": cantidad,
                "fecha": ts_evento.strftime("%d/%m/%Y %H:%M"),
                "firma": prof_name,
                "empresa": mi_empresa,
            }, max_items=1000)

            # 3) Descuento local inmediato para que la UI responda rápido.
            _descontar_stock_local(mi_empresa, med_sel, cantidad)

            # 4) SQL si hay UUIDs resueltos. Si falla, no bloquea el uso local.
            if empresa_uuid and paciente_uuid:
                try:
                    if not _registrar_consumo_en_sql(paciente_sel, mi_empresa, user, med_sel, cantidad, empresa_uuid, paciente_uuid, user_uuid):
                        exito_sql = False
                except Exception as exc:
                    exito_sql = False
                    log_event("stock", f"sql_stock_fallo:{type(exc).__name__}:{exc}")
            else:
                exito_sql = False

            # 5) Auditoría en memoria antes del único guardado.
            try:
                registrar_auditoria_legal(
                    "Medicación", paciente_sel, "Registro clínico + consumo + descuento stock",
                    prof_name, mat_prof,
                    f"{med_sel} | Cantidad: {cantidad} | Inventario: {'OK' if exito_sql else 'falla SQL, solo local'}",
                    referencia=f"STOCK|{fecha_hoy}|{med_sel[:48]}",
                    modulo="Recetas / Stock",
                    empresa=mi_empresa,
                    usuario=user if isinstance(user, dict) else None,
                    criticidad="alta",
                )
            except Exception as exc:
                log_event("stock", f"auditoria_stock_fallo:{type(exc).__name__}:{exc}")

            # 6) Un solo guardado, silencioso y agrupable.
            # Esto evita el doble guardado bloqueante que hacía lenta la experiencia móvil.
            guardar_datos(spinner=False)

            dt_ms = int((time.monotonic() - t0) * 1000)
            log_event("stock", f"registro_stock_ok:{dt_ms}ms:sql={exito_sql}")
            if exito_sql:
                queue_toast(f"{cantidad} x {med_sel}: registrado y stock descontado.")
            else:
                queue_toast(f"{cantidad} x {med_sel}: registrado localmente. Sin descuento SQL confirmado.")
        finally:
            st.session_state[saving_key] = False

        st.rerun()
