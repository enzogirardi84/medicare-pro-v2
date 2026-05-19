"""Control de stock: registra administracion clinica + consumo + descuento de inventario."""

from __future__ import annotations

import streamlit as st

from core.alert_toasts import queue_toast
from core.database import guardar_datos
from core.utils import ahora, registrar_auditoria_legal
from views._recetas_utils import nombre_usuario


def _restaurar_stock_local(mi_empresa, insumo, cantidad):
    for item in st.session_state.get("inventario_db", []):
        if item.get("item") == insumo and item.get("empresa") == mi_empresa:
            item["stock"] = int(item.get("stock") or 0) + cantidad
            return


def _descontar_stock_local(mi_empresa, insumo, cantidad):
    for item in st.session_state.get("inventario_db", []):
        if item.get("item") == insumo and item.get("empresa") == mi_empresa:
            item["stock"] = max(0, int(item.get("stock") or 0) - cantidad)
            return True
    return False


def _registrar_consumo_en_sql(paciente_sel, mi_empresa, user, med_name, cantidad, empresa_uuid, paciente_uuid, user_uuid):
    """Inserta movimiento en inventario_movimientos. El trigger SQL auto-descuenta stock."""
    from core.db_sql import get_inventario_item_by_name, insert_inventario_movimiento, update_inventario_stock_sql
    item = get_inventario_item_by_name(empresa_uuid, med_name)
    if not item:
        return False
    stock_actual = int(item.get("stock_actual", 0))
    stock_nuevo = max(0, stock_actual - cantidad)
    mov = {
        "inventario_id": item["id"],
        "paciente_id": paciente_uuid,
        "usuario_id": user_uuid,
        "empresa_id": empresa_uuid,
        "tipo_movimiento": "Salida",
        "cantidad": cantidad,
        "stock_anterior": stock_actual,
        "stock_nuevo": stock_nuevo,
        "motivo": f"Administracion clinica: {med_name} - {paciente_sel}",
        "referencia_documento": "RECETA_AUTOMATICA",
    }
    result = insert_inventario_movimiento(mov)
    if not result:
        update_inventario_stock_sql(item["id"], stock_nuevo, empresa_uuid)
    return True


def _resolver_uuids(paciente_sel, mi_empresa):
    """Retorna (empresa_uuid, paciente_uuid, user_uuid) o (None, None, None)."""
    from core.nextgen_sync import _obtener_uuid_empresa, _obtener_uuid_paciente
    try:
        partes = paciente_sel.split(" - ")
        if len(partes) <= 1:
            return None, None, None
        dni = partes[1].strip()
        empresa_uuid = _obtener_uuid_empresa(mi_empresa)
        if not empresa_uuid:
            return None, None, None
        paciente_uuid = _obtener_uuid_paciente(dni, empresa_uuid)
        if not paciente_uuid:
            return empresa_uuid, None, None
        user_uuid = None
        usuario_login = st.session_state.get("u_actual", {}).get("usuario_login", "")
        if usuario_login:
            from core.database import supabase
            if supabase:
                res = supabase.table("usuarios").select("id").eq("usuario_login", usuario_login).limit(1).execute()
                if res and res.data:
                    user_uuid = res.data[0]["id"]
        return empresa_uuid, paciente_uuid, user_uuid
    except Exception:
        return None, None, None


def render_control_medicacion_stock(paciente_sel, mi_empresa, user, recs_activas):
    """Seccion: seleccionar medicacion activa, indicar cantidad, y ejecutar triple accion."""
    if not recs_activas:
        return

    st.divider()
    st.markdown("### Control de stock por medicacion administrada")
    st.caption(
        "Selecciona la medicacion, ingresá la cantidad utilizada y ejecutá el registro. "
        "El sistema guarda la administracion clinica, registra el consumo en insumos y descuenta del inventario."
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

    c1, c2 = st.columns([3, 1])
    med_sel = c1.selectbox("Medicacion a registrar", nombres_med, key=sel_key)
    cantidad = c2.number_input("Cantidad utilizada", min_value=1, value=1, step=1, key=qty_key)

    empresa_uuid, paciente_uuid, user_uuid = _resolver_uuids(paciente_sel, mi_empresa)
    if empresa_uuid:
        from core.db_sql import get_inventario_item_by_name
        item_inv = get_inventario_item_by_name(empresa_uuid, med_sel)
        if item_inv:
            st.caption(f"Stock actual en inventario: **{item_inv.get('stock_actual', '?')}**")
        else:
            st.caption("Este medicamento no esta cargado en el inventario. Se registrara solo la administracion clinica y el consumo local.")
    else:
        st.caption("Sin conexion SQL. Solo se registrara en modo local (sesion).")

    if st.button("Registrar y descontar stock", type="primary", width='stretch', key=f"_stock_btn_{paciente_sel}"):
        ts_evento = ahora()
        hora_str = ts_evento.strftime("%H:%M")
        fecha_hoy = ts_evento.strftime("%d/%m/%Y")
        mat_prof = str(user.get("matricula", "") or "").strip()
        login_ref = str(user.get("usuario_login", user.get("usuario", "")) or "").strip()
        prof_name = nombre_usuario(user)

        exito_sql = True

        # -- 1. Registro clinico (administracion_med) --
        from core.database import guardar_json_db
        guardar_json_db("administracion_med_db", {
            "paciente": paciente_sel,
            "med": med_sel,
            "fecha": fecha_hoy,
            "hora": hora_str,
            "horario_programado": "Stock automatico",
            "estado": "Realizada",
            "motivo": "",
            "firma": prof_name,
            "matricula_profesional": mat_prof,
            "usuario_login": login_ref,
            "registro_iso": ts_evento.isoformat(timespec="seconds"),
            "registro_fecha_hora": ts_evento.strftime("%d/%m/%Y %H:%M:%S"),
            "empresa": mi_empresa,
            "cantidad": cantidad,
        }, spinner=True)

        # -- 2. Consumo en insumos (local + SQL) --
        st.session_state.setdefault("consumos_db", [])
        st.session_state["consumos_db"].append({
            "paciente": paciente_sel,
            "insumo": med_sel,
            "cantidad": cantidad,
            "fecha": ts_evento.strftime("%d/%m/%Y %H:%M"),
            "firma": prof_name,
            "empresa": mi_empresa,
        })
        from core.database import _trim_db_list
        _trim_db_list("consumos_db", 1000)

        if empresa_uuid and paciente_uuid:
            if not _registrar_consumo_en_sql(paciente_sel, mi_empresa, user, med_sel, cantidad, empresa_uuid, paciente_uuid, user_uuid):
                exito_sql = False

        # -- 3. Descuento local de stock --
        _descontar_stock_local(mi_empresa, med_sel, cantidad)

        guardar_datos(spinner=True)

        registrar_auditoria_legal(
            "Medicacion", paciente_sel, "Registro clinico + consumo + descuento stock",
            prof_name, mat_prof,
            f"{med_sel} | Cantidad: {cantidad} | Inventario: {'OK' if exito_sql else 'falla SQL, solo local'}",
            referencia=f"STOCK|{fecha_hoy}|{med_sel[:48]}",
            modulo="Recetas / Stock",
            empresa=mi_empresa,
            usuario=user if isinstance(user, dict) else None,
            criticidad="alta",
        )

        if exito_sql:
            queue_toast(f"{cantidad} x {med_sel}: registro clinico + consumo + stock descontado.")
        else:
            queue_toast(f"{cantidad} x {med_sel}: registrado (local). El inventario SQL no se actualizo.")
        st.rerun()
