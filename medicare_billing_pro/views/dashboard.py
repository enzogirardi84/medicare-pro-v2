"""Dashboard ejecutivo de Medicare Billing Pro."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import streamlit as st

from core.db_sql import get_clientes, get_cobros, get_prefacturas, get_presupuestos
from core.billing_logic import enriquecer_prefacturas_con_saldo, prefacturas_con_saldo, total_saldo_prefacturas
from core.utils import bloque_estado_vacio, fmt_fecha, fmt_moneda


MESES_ES = {
    "01": "enero",
    "02": "febrero",
    "03": "marzo",
    "04": "abril",
    "05": "mayo",
    "06": "junio",
    "07": "julio",
    "08": "agosto",
    "09": "septiembre",
    "10": "octubre",
    "11": "noviembre",
    "12": "diciembre",
}


def _money(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _month_label(month_key: str) -> str:
    if len(str(month_key)) < 7 or "-" not in str(month_key):
        return str(month_key or "-")
    year, month = month_key.split("-")
    return f"{MESES_ES.get(month, month).capitalize()} {year}"


def _set_module(label: str) -> None:
    st.session_state["billing_modulo_activo"] = label
    st.rerun()


def _total_prefacturas(prefacturas: List[Dict[str, Any]]) -> float:
    return sum(_money(p.get("total")) for p in prefacturas)


def _estado(value: Any) -> str:
    return str(value or "").strip().lower()


def _recent_activity(
    presupuestos: List[Dict[str, Any]],
    prefacturas: List[Dict[str, Any]],
    cobros: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in presupuestos:
        rows.append(
            {
                "fecha": str(item.get("fecha") or item.get("created_at") or "")[:10],
                "tipo": "Presupuesto",
                "cliente": item.get("cliente_nombre", ""),
                "detalle": item.get("numero", ""),
                "importe": _money(item.get("total")),
            }
        )
    for item in prefacturas:
        rows.append(
            {
                "fecha": str(item.get("fecha") or item.get("created_at") or "")[:10],
                "tipo": "Pre-factura",
                "cliente": item.get("cliente_nombre", ""),
                "detalle": item.get("numero", ""),
                "importe": _money(item.get("total")),
            }
        )
    for item in cobros:
        rows.append(
            {
                "fecha": str(item.get("fecha") or item.get("created_at") or "")[:10],
                "tipo": "Cobro",
                "cliente": item.get("cliente_nombre", ""),
                "detalle": item.get("medio_pago", ""),
                "importe": _money(item.get("monto")),
            }
        )
    return sorted(rows, key=lambda r: r.get("fecha") or "", reverse=True)[:30]


def render_dashboard() -> None:
    empresa_id = st.session_state.get("billing_empresa_id", "")
    clientes = get_clientes(empresa_id)
    presupuestos = get_presupuestos(empresa_id)
    prefacturas_raw = get_prefacturas(empresa_id)
    cobros = get_cobros(empresa_id)
    prefacturas = enriquecer_prefacturas_con_saldo(prefacturas_raw, cobros)

    current_month = date.today().strftime("%Y-%m")
    cobros_mes = [c for c in cobros if str(c.get("fecha", ""))[:7] == current_month]
    prefacturas_mes = [p for p in prefacturas if str(p.get("fecha", ""))[:7] == current_month]
    prefacturas_pendientes = prefacturas_con_saldo(prefacturas_raw, cobros)
    presupuestos_abiertos = [
        p for p in presupuestos if _estado(p.get("estado")) in {"borrador", "enviado", "pendiente"}
    ]
    presupuestos_aceptados = [
        p for p in presupuestos if _estado(p.get("estado")) in {"aceptado", "convertido"}
    ]

    total_cobrado_mes = sum(_money(c.get("monto")) for c in cobros_mes)
    total_prefacturado_mes = _total_prefacturas(prefacturas_mes)
    total_pendiente = total_saldo_prefacturas(prefacturas_raw, cobros)
    conversion = (len(presupuestos_aceptados) / len(presupuestos) * 100) if presupuestos else 0
    cumplimiento = min(total_cobrado_mes / total_prefacturado_mes, 1.0) if total_prefacturado_mes else 0
    prefacturas_vencidas = [
        p
        for p in prefacturas_pendientes
        if str(p.get("vencimiento", ""))[:10] and str(p.get("vencimiento", ""))[:10] < date.today().isoformat()
    ]
    presupuestos_por_vencer = [
        p
        for p in presupuestos_abiertos
        if str(p.get("valido_hasta", ""))[:10] and str(p.get("valido_hasta", ""))[:10] >= date.today().isoformat()
    ]

    st.markdown("## Resumen")
    st.caption(f"Vista de control para {_month_label(current_month)}.")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Cobrado este mes", fmt_moneda(total_cobrado_mes))
    k2.metric("Pendiente de cobro", fmt_moneda(total_pendiente))
    k3.metric("Presupuestos abiertos", len(presupuestos_abiertos))
    k4.metric("Conversion presupuestos", f"{conversion:.0f}%")

    st.progress(cumplimiento, text=f"Cobrado sobre pre-facturado del mes: {cumplimiento * 100:.0f}%")
    if prefacturas_vencidas:
        st.warning(
            f"Hay {len(prefacturas_vencidas)} pre-factura(s) vencida(s) con saldo por "
            f"{fmt_moneda(sum(_money(p.get('saldo')) for p in prefacturas_vencidas))}."
        )
    elif total_pendiente > 0:
        st.info(f"Hay saldo pendiente por {fmt_moneda(total_pendiente)}, sin vencimientos atrasados.")
    else:
        st.success("Cartera al dia: no hay saldos pendientes.")
    if presupuestos_por_vencer:
        st.caption(f"Presupuestos abiertos vigentes: {len(presupuestos_por_vencer)}.")

    st.markdown("### Accesos rapidos")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("Nuevo cliente", width='stretch'):
            _set_module("Clientes fiscales")
    with c2:
        if st.button("Nuevo presupuesto", width='stretch'):
            _set_module("Presupuestos")
    with c3:
        if st.button("Nueva pre-factura", width='stretch'):
            _set_module("Pre-facturas")
    with c4:
        if st.button("Registrar cobro", width='stretch'):
            _set_module("Cobros")

    st.divider()
    left, right = st.columns([1.05, 0.95], gap="large")

    with left:
        st.markdown("### Pendientes de cobro")
        with st.container(height=250, border=True):
            if not prefacturas_pendientes:
                bloque_estado_vacio(
                    "Sin pendientes",
                    "No hay pre-facturas pendientes o parciales para cobrar.",
                )
            else:
                rows = []
                for item in sorted(
                    prefacturas_pendientes,
                    key=lambda p: str(p.get("vencimiento") or p.get("fecha") or ""),
                ):
                    rows.append(
                        {
                            "Numero": item.get("numero", ""),
                            "Cliente": item.get("cliente_nombre", ""),
                            "Vence": fmt_fecha(item.get("vencimiento", "")),
                            "Estado": item.get("estado_calculado", item.get("estado", "")),
                            "Total": fmt_moneda(item.get("total", 0)),
                            "Saldo": fmt_moneda(item.get("saldo", 0)),
                        }
                    )
                st.dataframe(rows, width='stretch', hide_index=True, height=185)

        st.markdown("### Meses con cobros")
        with st.container(height=220, border=True):
            if not cobros:
                bloque_estado_vacio("Sin cobros", "Todavia no hay cobros registrados.")
            else:
                meses: Dict[str, float] = {}
                for cobro in cobros:
                    key = str(cobro.get("fecha", ""))[:7]
                    if key:
                        meses[key] = meses.get(key, 0.0) + _money(cobro.get("monto"))
                month_rows = [
                    {"Mes": _month_label(key), "Cobrado": fmt_moneda(value)}
                    for key, value in sorted(meses.items(), reverse=True)
                ]
                st.dataframe(month_rows, width='stretch', hide_index=True, height=155)
                chart_rows = [
                    {"Mes": _month_label(key), "Cobrado": value}
                    for key, value in sorted(meses.items())[-6:]
                ]
                if chart_rows:
                    st.bar_chart(chart_rows, x="Mes", y="Cobrado", height=180)

    with right:
        st.markdown("### Actividad reciente")
        with st.container(height=520, border=True):
            recent = _recent_activity(presupuestos, prefacturas, cobros)
            if not recent:
                bloque_estado_vacio(
                    "Sin actividad",
                    "Cuando cargues clientes, presupuestos, pre-facturas o cobros, van a aparecer aca.",
                )
            else:
                for row in recent:
                    with st.container(border=True):
                        st.caption(f"{fmt_fecha(row.get('fecha', ''))} | {row.get('tipo', '')}")
                        st.markdown(f"**{row.get('cliente') or 'Sin cliente'}**")
                        detail = str(row.get("detalle") or "").strip()
                        if detail:
                            st.caption(detail)
                        st.markdown(f"**{fmt_moneda(row.get('importe', 0))}**")

        st.markdown("### Calidad de datos")
        checks = [
            ("Clientes cargados", len(clientes) > 0),
            ("Hay presupuestos", len(presupuestos) > 0),
            ("Hay pre-facturas", len(prefacturas) > 0),
            ("Hay cobros", len(cobros) > 0),
        ]
        for label, ok in checks:
            st.caption(f"{'OK' if ok else 'Pendiente'} - {label}")
