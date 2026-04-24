"""Lógica de construcción de texto de indicaciones y resumen de medicación activa.

Extraído de views/recetas.py para mantenerlo bajo las 300 líneas.
"""
from datetime import datetime as _dt, timedelta as _td

import streamlit as st

from views._recetas_utils import resumen_plan_hidratacion


def construir_texto_indicacion(
    tipo_indicacion,
    med_final="",
    via="",
    frecuencia="",
    dias=None,
    solucion="",
    volumen_ml=None,
    velocidad_ml_h=None,
    alternar_con="",
    detalle_infusion="",
    plan_hidratacion=None,
):
    if tipo_indicacion == "Infusion / hidratacion":
        partes = []
        titulo = solucion.strip() or "Infusion endovenosa"
        if volumen_ml:
            titulo = f"{titulo} {int(volumen_ml)} ml"
        partes.append(titulo)
        if via:
            partes.append(f"Via: {via}")
        if velocidad_ml_h not in ("", None):
            partes.append(f"Velocidad: {velocidad_ml_h} ml/h")
        if alternar_con:
            partes.append(f"Alternar con: {alternar_con}")
        if dias:
            partes.append(f"Durante {dias} dias")
        if plan_hidratacion:
            resumen = resumen_plan_hidratacion(plan_hidratacion)
            if resumen:
                partes.append(f"Plan: {resumen}")
        if detalle_infusion:
            partes.append(f"Indicacion: {detalle_infusion.strip()}")
        return " | ".join([p for p in partes if str(p).strip()])

    texto_base = med_final.strip().title()
    partes = [texto_base]
    if via:
        partes.append(f"Via: {via}")
    if frecuencia:
        partes.append(frecuencia)
    if dias:
        partes.append(f"Durante {dias} dias")
    return " | ".join([p for p in partes if str(p).strip()])


def resumen_medicacion_activa(paciente_sel, mi_empresa):
    """Bloque compacto de medicación activa con indicador de próximas a vencer."""
    todas = [
        r for r in st.session_state.get("indicaciones_db", [])
        if r.get("paciente") == paciente_sel
        and r.get("empresa", mi_empresa) == mi_empresa
    ]
    activas = [
        r for r in todas
        if str(r.get("estado_receta", "Activa")).strip().lower() not in ("suspendida", "cancelada")
    ]
    if not activas:
        return

    hoy = _dt.now().date()
    por_vencer = []
    vencidas = []
    for r in activas:
        try:
            fecha_inicio = _dt.strptime(str(r.get("fecha", ""))[:10], "%d/%m/%Y").date()
            dias_dur = int(r.get("dias_duracion", 0) or 0)
            if dias_dur > 0:
                fecha_fin = fecha_inicio + _td(days=dias_dur)
                dias_restantes = (fecha_fin - hoy).days
                if dias_restantes < 0:
                    vencidas.append((r, abs(dias_restantes)))
                elif dias_restantes <= 2:
                    por_vencer.append((r, dias_restantes))
        except Exception as _exc:
            from core.app_logging import log_event
            log_event("recetas_indicaciones", f"parse_fecha_vencimiento_error:{type(_exc).__name__}:{r.get('fecha','')}")

    with st.expander(f"📊 Medicación activa ({len(activas)} indicación/es)", expanded=bool(vencidas or por_vencer)):
        if vencidas:
            for r, dias in vencidas[:3]:
                nom = (r.get("med") or "")[:60]
                st.error(f"🔴 VENCIDA hace {dias}d: **{nom}**")
        if por_vencer:
            for r, dias in por_vencer:
                nom = (r.get("med") or "")[:60]
                label = "hoy" if dias == 0 else f"en {dias}d"
                st.warning(f"🟡 Vence {label}: **{nom}**")

        cols = st.columns([3, 2, 2, 1])
        cols[0].caption("**Medicación**")
        cols[1].caption("**Frecuencia**")
        cols[2].caption("**Médico**")
        cols[3].caption("**Días**")
        for r in activas[:12]:
            cols = st.columns([3, 2, 2, 1])
            cols[0].write((r.get("med") or "")[:55])
            cols[1].write(r.get("frecuencia") or r.get("via") or "—")
            cols[2].write((r.get("medico_nombre") or r.get("profesional_estado") or "—")[:24])
            cols[3].write(str(r.get("dias_duracion") or "—"))
        if len(activas) > 12:
            st.caption(f"... y {len(activas) - 12} más.")
