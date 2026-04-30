"""Motor de reglas determinista para el Asistente Clinico 360.
Analiza datos de session_state y genera alertas sin IA externa.
"""
from __future__ import annotations
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import streamlit as st

# CONSTANTES DE CONFIGURACION
FORMATOS_FECHA = (
    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
    "%Y-%m-%d", "%d/%m/%Y"
)

MAPEO_BASE_DATOS = {
    "evoluciones_db": "evoluciones", "vitales_db": "vitales",
    "indicaciones_db": "indicaciones", "cuidados_enfermeria_db": "cuidados",
    "consumos_db": "consumos", "balance_db": "balance",
    "estudios_db": "estudios", "administracion_med_db": "administracion_med",
    "diagnosticos_db": "diagnosticos", "escalas_clinicas_db": "escalas",
    "emergencias_db": "emergencias", "checkin_db": "checkin"
}

def _safe_list(key: str) -> list:
    raw = st.session_state.get(key, [])
    if not isinstance(raw, list):
        return []
    return [x for x in raw if isinstance(x, dict)]

def _parse_fecha(valor: Any) -> Optional[datetime]:
    if valor is None:
        return None
    s = str(valor).strip()
    if not s:
        return None
    for fmt in FORMATOS_FECHA:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None

def _ahora() -> datetime:
    return datetime.now()

def _horas_desde(fecha: Optional[datetime]) -> Optional[float]:
    if fecha is None:
        return None
    return (_ahora() - fecha).total_seconds() / 3600.0

def _coincide_paciente(item: dict, paciente_id: str) -> bool:
    if paciente_id is None:
        return False
    pid_norm = str(paciente_id).strip().lower()
    if not pid_norm or pid_norm == "none":
        return False
    # Extraer componentes significativos (nombre, dni, etc.) para match parcial
    pid_partes = [p.strip() for p in pid_norm.replace("(", " ").replace(")", " ").split(" - ") if len(p.strip()) >= 2]
    if not pid_partes:
        pid_partes = [pid_norm]
    for campo in (item.get("paciente"), item.get("paciente_id"), item.get("nombre"), item.get("dni")):
        if campo is None:
            continue
        campo_norm = str(campo).strip().lower()
        # Match exacto o substring en cualquier direccion
        if pid_norm in campo_norm or campo_norm in pid_norm:
            return True
        # Match por parte significativa (nombre o DNI)
        for parte in pid_partes:
            if parte in campo_norm:
                return True
    return False

def _extraer_ta(valor: Any) -> Tuple[Optional[int], Optional[int]]:
    if valor is None:
        return None, None
    m = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", str(valor))
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None

def _to_float(valor: Any) -> Optional[float]:
    if valor is None:
        return None
    try:
        return float(valor)
    except (ValueError, TypeError):
        return None

def _contiene_keyword(texto: Any, keywords: Tuple[str, ...]) -> bool:
    if texto is None:
        return False
    t = str(texto).lower()
    return any(k in t for k in keywords)

def recopilar_datos_paciente(paciente_id: str) -> dict:
    out = {"evoluciones": [], "vitales": [], "indicaciones": [], "cuidados": [],
           "consumos": [], "balance": [], "estudios": [], "administracion_med": [],
           "diagnosticos": [], "escalas": [], "emergencias": [], "checkin": [], "paciente_data": None}
    for key, target in MAPEO_BASE_DATOS.items():
        for item in _safe_list(key):
            if _coincide_paciente(item, paciente_id):
                out[target].append(item)
    for p in _safe_list("pacientes_db"):
        if _coincide_paciente(p, paciente_id):
            out["paciente_data"] = p
            break
    return out

def evaluar_riesgo_clinico(datos: dict) -> List[dict]:
    alertas = []
    vitales = datos.get("vitales", [])
    cuidados = datos.get("cuidados", [])
    indicaciones = datos.get("indicaciones", [])
    administracion = datos.get("administracion_med", [])
    diagnosticos = datos.get("diagnosticos", [])
    evoluciones = datos.get("evoluciones", [])
    emergencias = datos.get("emergencias", [])
    # TA elevada
    for v in vitales:
        sys_ta, dia_ta = _extraer_ta(v.get("presion_arterial") or v.get("ta") or v.get("TA") or v.get("tension"))
        if sys_ta and sys_ta > 150:
            alertas.append({"titulo":"Riesgo Cardiovascular - TA elevada","detalle":f"Ultima TA: {sys_ta}/{dia_ta or '-'} mmHg. Supera umbral de 150/90.","nivel":"danger","categoria":"vitales"})
            break
    # Glucemia extrema
    for v in vitales:
        glu = _to_float(v.get("glucemia") or v.get("glucosa") or v.get("HGT"))
        if glu is not None and (glu < 70 or glu > 250):
            tipo = "hipoglucemia" if glu < 70 else "hiperglucemia"
            alertas.append({"titulo":f"Riesgo Metabolico - {tipo}","detalle":f"Glucemia: {glu} mg/dL. Requiere revision.","nivel":"danger","categoria":"vitales"})
            break
    # Fiebre
    for v in vitales:
        temp = _to_float(v.get("temperatura") or v.get("temp") or v.get("Temp"))
        if temp is not None and temp >= 38.5:
            alertas.append({"titulo":"Fiebre significativa","detalle":f"Temperatura: {temp}C. Evaluar origen infeccioso.","nivel":"warning","categoria":"vitales"})
            break
    # FC extrema
    for v in vitales:
        fc = _to_float(v.get("frecuencia_cardiaca") or v.get("fc") or v.get("FC") or v.get("pulso"))
        if fc is not None:
            if fc < 50:
                alertas.append({"titulo":"Bradicardia","detalle":f"FC: {fc} lat/min. < 50 requiere evaluacion.","nivel":"warning","categoria":"vitales"})
                break
            elif fc > 120:
                alertas.append({"titulo":"Taquicardia","detalle":f"FC: {fc} lat/min. > 120 requiere evaluacion.","nivel":"warning","categoria":"vitales"})
                break
    # Hipoxemia
    for v in vitales:
        sat = _to_float(v.get("saturacion_o2") or v.get("saturacion") or v.get("spo2") or v.get("Sat"))
        if sat is not None and sat < 90:
            alertas.append({"titulo":"Hipoxemia","detalle":f"SatO2: {sat}%. < 90% requiere oxigenoterapia.","nivel":"danger","categoria":"vitales"})
            break
    # Escaras
    tiene_escaras = any(_contiene_keyword(c.get("cuidado_tipo",c.get("tipo_cuidado","")),("escara","decubito","ulceras por presion")) for c in cuidados)
    mov_red = any(_contiene_keyword(c.get("observaciones",c.get("detalle","")),("movilidad reducida","inmovil","encamado")) for c in cuidados)
    cambio_post = any(_contiene_keyword(c.get("cuidado_tipo",c.get("tipo_cuidado","")),("cambio postural","cambio de posicion","posicion")) for c in cuidados)
    if (tiene_escaras or mov_red) and not cambio_post:
        alertas.append({"titulo":"Riesgo de Escaras","detalle":"Paciente con riesgo/movilidad reducida sin registro de cambio postural reciente.","nivel":"warning","categoria":"cuidados"})
    # HTA sin control + medicacion
    tiene_hta = any(_contiene_keyword(d.get("diagnostico",d.get("nombre","")),("hta","hipertension","hipertension arterial")) for d in diagnosticos)
    if not tiene_hta:
        tiene_hta = any(_contiene_keyword(ev.get("texto",ev.get("evolucion","")),("hta","hipertension","hipertension arterial")) for ev in evoluciones)
    if tiene_hta:
        for ind in indicaciones:
            med_texto = str(ind.get("med","")).lower()
            if any(m in med_texto for m in ("enalapril","losartan","amlodipina","atenolol","metoprolol")):
                ta_alta = False
                for v in vitales:
                    s, _ = _extraer_ta(v.get("presion_arterial") or v.get("ta"))
                    if s and s > 150:
                        ta_alta = True
                        break
                if ta_alta:
                    alertas.append({"titulo":"Riesgo Farmacologico - HTA no controlada","detalle":"Paciente con medicacion antihipertensiva activa y TA > 150/90. Evaluar ajuste.","nivel":"danger","categoria":"farmacologia"})
                break
    # Indicaciones sin administracion
    for ind in indicaciones:
        if "activa" not in str(ind.get("estado_receta",ind.get("estado_clinico",""))).lower():
            continue
        med_texto = ind.get("med","")
        ya_admin = any(str(med_texto).lower() in str(adm.get("med","")).lower() for adm in administracion)
        if not ya_admin:
            alertas.append({"titulo":"Administracion Pendiente","detalle":f"Indicacion activa: {str(med_texto)} sin registro de administracion.","nivel":"warning","categoria":"farmacologia"})
    # Curacion sin insumos
    for c in cuidados:
        if _contiene_keyword(c.get("cuidado_tipo",c.get("tipo_cuidado","")),("curacion","curacion")):
            tiene_insumo = any(_contiene_keyword(co.get("insumo",co.get("material","")),("gasa","antisep","aposito","venda")) for co in datos.get("consumos",[]))
            if not tiene_insumo:
                alertas.append({"titulo":"Auditoria de Insumos - Curacion sin consumo","detalle":"Se registro una curacion pero no hay gasto de gasa/antiseptico en consumos.","nivel":"warning","categoria":"insumos"})
                break
    # Peso
    pesos = []
    for v in vitales:
        p = _to_float(v.get("peso") or v.get("weight"))
        f = _parse_fecha(v.get("fecha") or v.get("timestamp"))
        if p is not None and f is not None:
            pesos.append((f, p))
    if len(pesos) >= 2:
        pesos.sort(key=lambda x: x[0])
        primero, ultimo = pesos[0], pesos[-1]
        dias_diff = (ultimo[0] - primero[0]).days
        if dias_diff >= 7 and primero[1] > 0:
            variacion = ((ultimo[1] - primero[1]) / primero[1]) * 100
            if variacion <= -5:
                alertas.append({"titulo":"Perdida de peso significativa","detalle":f"Peso bajo {abs(variacion):.1f}% en {dias_diff} dias. Evaluar nutricion.","nivel":"warning","categoria":"nutricion"})
    # Emergencias activas
    for em in emergencias:
        if str(em.get("estado","")).lower() in ("activa","pendiente","en curso"):
            alertas.append({"titulo":"Emergencia activa","detalle":f"Emergencia: {em.get('motivo',em.get('tipo','Sin detalle'))}. Estado: {em.get('estado','-')}","nivel":"danger","categoria":"emergencias"})
    return alertas

def analizar_consistencia_datos(datos: dict) -> List[dict]:
    alertas = []
    evoluciones = datos.get("evoluciones", [])
    vitales = datos.get("vitales", [])
    indicaciones = datos.get("indicaciones", [])
    cuidados = datos.get("cuidados", [])
    estudios = datos.get("estudios", [])
    balance = datos.get("balance", [])
    consumos = datos.get("consumos", [])
    diagnosticos = datos.get("diagnosticos", [])
    # Indicaciones sin vitales recientes
    if indicaciones:
        vitales_rec = any((_horas_desde(_parse_fecha(v.get("fecha") or v.get("timestamp"))) or 999) < 12 for v in vitales)
        if not vitales_rec:
            alertas.append({"titulo":"Atencion: Indicaciones activas sin signos vitales recientes","detalle":"El paciente tiene medicacion/terapia indicada pero no se registran signos vitales desde hace mas de 12 horas.","nivel":"warning","categoria":"consistencia"})
    # Evolucion sin diagnostico
    if evoluciones and not diagnosticos:
        alertas.append({"titulo":"Evolucion sin diagnostico formal","detalle":"Hay evoluciones clinicas pero no hay diagnosticos cargados.","nivel":"info","categoria":"consistencia"})
    # Estudios sin resultado
    for es in estudios:
        if str(es.get("estado","")).lower() in ("solicitado","pendiente"):
            alertas.append({"titulo":"Estudio pendiente de resultado","detalle":f"{es.get('tipo','Estudio')}: {es.get('nombre',es.get('detalle','-'))} - Estado: {es.get('estado','Pendiente')}","nivel":"info","categoria":"consistencia"})
    # Balance desactualizado
    if balance:
        ultimo = None
        for bl in balance:
            f = _parse_fecha(bl.get("fecha") or bl.get("timestamp"))
            if f and (ultimo is None or f > ultimo):
                ultimo = f
        if ultimo and _horas_desde(ultimo) and _horas_desde(ultimo) > 24:
            alertas.append({"titulo":"Balance desactualizado","detalle":"Ultimo registro de balance hidrico hace mas de 24 horas.","nivel":"info","categoria":"consistencia"})
    # Consumo elevado de canulas
    for co in consumos:
        insumo = str(co.get("insumo",co.get("material",""))).lower()
        cantidad = co.get("cantidad", 0)
        if "canula" in insumo and int(cantidad or 0) > 4:
            alertas.append({"titulo":"Auditoria de Insumos - Consumo elevado","detalle":f"Consumo de {insumo}: {cantidad} unidades. Revisar justificacion clinica.","nivel":"warning","categoria":"insumos"})
    return alertas

def compilar_dashboard_ejecutivo(datos: dict) -> dict:
    vitales = datos.get("vitales", [])
    indicaciones = datos.get("indicaciones", [])
    evoluciones = datos.get("evoluciones", [])
    cuidados = datos.get("cuidados", [])
    estudios = datos.get("estudios", [])
    consumos = datos.get("consumos", [])
    balance = datos.get("balance", [])
    administracion = datos.get("administracion_med", [])
    diagnosticos = datos.get("diagnosticos", [])
    escalas = datos.get("escalas", [])
    emergencias = datos.get("emergencias", [])
    # Ultimos vitales
    ultimo_vital = None
    for v in sorted(vitales, key=lambda x: (_parse_fecha(x.get("fecha") or x.get("timestamp")) or datetime.min, vitales.index(x) if x in vitales else 0), reverse=True):
        ultimo_vital = v
        break
    ultima_ta = "-"
    ultima_fc = "-"
    ultima_temp = "-"
    ultima_glu = "-"
    ultima_spo2 = "-"
    if ultimo_vital:
        s, d = _extraer_ta(ultimo_vital.get("presion_arterial") or ultimo_vital.get("ta") or ultimo_vital.get("TA"))
        if s:
            ultima_ta = f"{s}/{d or '-'}"
        ultima_fc = str(ultimo_vital.get("frecuencia_cardiaca") or ultimo_vital.get("fc") or ultimo_vital.get("FC") or "-")
        t = _to_float(ultimo_vital.get("temperatura") or ultimo_vital.get("temp") or ultimo_vital.get("Temp"))
        if t is not None:
            ultima_temp = f"{t:.1f}"
        g = _to_float(ultimo_vital.get("glucemia") or ultimo_vital.get("glucosa") or ultimo_vital.get("HGT"))
        if g is not None:
            ultima_glu = f"{g:.0f}"
        s2 = _to_float(ultimo_vital.get("saturacion_o2") or ultimo_vital.get("saturacion") or ultimo_vital.get("spo2") or ultimo_vital.get("Sat"))
        if s2 is not None:
            ultima_spo2 = f"{s2:.0f}"
    # Alertas
    alertas_riesgo = evaluar_riesgo_clinico(datos)
    alertas_consistencia = analizar_consistencia_datos(datos)
    todas = alertas_riesgo + alertas_consistencia
    criticas = sum(1 for a in todas if a["nivel"] == "danger")
    warnings = sum(1 for a in todas if a["nivel"] == "warning")
    infos = sum(1 for a in todas if a["nivel"] == "info")
    semaforo = "rojo" if criticas > 0 else ("amarillo" if warnings > 0 else "verde")
    # Conteos
    ind_activas = sum(1 for i in indicaciones if "activa" in str(i.get("estado_receta",i.get("estado_clinico",""))).lower())
    adm_pend = sum(1 for i in indicaciones if "activa" in str(i.get("estado_receta",i.get("estado_clinico",""))).lower() and not any(str(i.get("med","")).lower() in str(a.get("med","")).lower() for a in administracion))
    estudios_pend = sum(1 for e in estudios if str(e.get("estado","")).lower() in ("solicitado","pendiente"))
    cuidados_hoy = sum(1 for c in cuidados if (_horas_desde(_parse_fecha(c.get("fecha") or c.get("timestamp"))) or 999) < 24)
    evo_recientes = sum(1 for e in evoluciones if (_horas_desde(_parse_fecha(e.get("fecha") or e.get("timestamp"))) or 999) < 24)
    # Tendencias TA / Glucemia
    ta_tendencia = []
    glu_tendencia = []
    for v in sorted(vitales, key=lambda x: _parse_fecha(x.get("fecha") or x.get("timestamp")) or datetime.min):
        f = _parse_fecha(v.get("fecha") or v.get("timestamp"))
        s, d = _extraer_ta(v.get("presion_arterial") or v.get("ta") or v.get("TA"))
        g = _to_float(v.get("glucemia") or v.get("glucosa") or v.get("HGT"))
        if f and s:
            ta_tendencia.append({"fecha": f.strftime("%Y-%m-%d %H:%M"), "sistolica": s, "diastolica": d or 0})
        if f and g is not None:
            glu_tendencia.append({"fecha": f.strftime("%Y-%m-%d %H:%M"), "glucemia": g})
    return {
        "ultima_ta": ultima_ta, "ultima_fc": ultima_fc, "ultima_temp": ultima_temp,
        "ultima_glu": ultima_glu, "ultima_spo2": ultima_spo2,
        "alertas": todas, "alertas_criticas": criticas, "alertas_warning": warnings, "alertas_info": infos,
        "semaforo": semaforo,
        "indicaciones_activas": ind_activas, "administraciones_pendientes": adm_pend,
        "estudios_pendientes": estudios_pend, "cuidados_24h": cuidados_hoy, "evoluciones_24h": evo_recientes,
        "ta_tendencia": ta_tendencia, "glu_tendencia": glu_tendencia,
        "total_evoluciones": len(evoluciones), "total_vitales": len(vitales),
        "total_indicaciones": len(indicaciones), "total_cuidados": len(cuidados),
        "total_estudios": len(estudios), "total_balance": len(balance),
        "total_consumos": len(consumos), "total_administracion": len(administracion),
        "total_diagnosticos": len(diagnosticos), "total_escalas": len(escalas),
        "total_emergencias": len(emergencias),
    }

def _esc_html(valor: Any) -> str:
    """Escape seguro para contenido HTML."""
    from html import escape
    return escape(str(valor) if valor is not None else "-")


def generar_html_informe_profesional(paciente_id: str, datos: dict, dashboard: dict) -> str:
    """Genera un informe clinico profesional en HTML con CSS embebido."""
    paciente_data = datos.get("paciente_data") or {}
    nombre = _esc_html(paciente_data.get("nombre", paciente_id))
    dni = _esc_html(paciente_data.get("dni", "-"))
    obra_social = _esc_html(paciente_data.get("obra_social", "S/D"))
    fnac = _esc_html(paciente_data.get("fnac", "S/D"))
    diag_principal = _esc_html(paciente_data.get("diagnostico", paciente_data.get("patologias", "Sin diagnostico principal registrado")))
    fecha_generacion = _esc_html(_ahora().strftime("%d/%m/%Y %H:%M"))

    semaforo = dashboard.get("semaforo", "desconocido")
    estado_general = "Atencion Requerida" if semaforo in ("rojo", "amarillo") else "Estable"
    color_semaforo = "#E74C3C" if semaforo == "rojo" else ("#F39C12" if semaforo == "amarillo" else "#27AE60")

    # Signos vitales
    ta = _esc_html(dashboard.get("ultima_ta", "-"))
    fc = _esc_html(dashboard.get("ultima_fc", "-"))
    temp = _esc_html(dashboard.get("ultima_temp", "-"))
    spo2 = _esc_html(dashboard.get("ultima_spo2", "-"))
    glu = _esc_html(dashboard.get("ultima_glu", "-"))

    # Ultima evolucion
    evoluciones = datos.get("evoluciones", [])
    if evoluciones:
        ultima_evo = max(evoluciones, key=lambda x: _parse_fecha(x.get("fecha", "")) or datetime.min)
        evo_fecha = _esc_html(ultima_evo.get("fecha", "S/D"))
        evo_prof = _esc_html(ultima_evo.get("firma", ultima_evo.get("profesional", "S/D")))
        evo_texto = _esc_html(ultima_evo.get("nota", ultima_evo.get("evolucion", ultima_evo.get("texto", "Sin detalle de texto"))))
        bloque_evolucion = f"""
        <section class="section">
            <div class="section-title">2. Ultima Evolucion Clinica</div>
            <div class="evo-box">
                <p><strong>Fecha:</strong> {evo_fecha} <span class="sep">|</span> <strong>Profesional:</strong> {evo_prof}</p>
                <blockquote>{evo_texto}</blockquote>
            </div>
        </section>
        """
    else:
        bloque_evolucion = """
        <section class="section">
            <div class="section-title">2. Ultima Evolucion Clinica</div>
            <p class="empty-state">Sin evoluciones registradas.</p>
        </section>
        """

    # Medicacion activa
    indicaciones = datos.get("indicaciones", [])
    indicaciones_activas = [
        ind for ind in indicaciones
        if "activa" in str(ind.get("estado_receta", ind.get("estado_clinico", ""))).lower()
    ]
    bloque_medicacion = ""
    if indicaciones_activas:
        for ind in indicaciones_activas:
            med = _esc_html(ind.get("med", "Medicacion"))
            dosis = _esc_html(ind.get("dosis", "S/D"))
            via = _esc_html(ind.get("via", "S/D"))
            frec = _esc_html(ind.get("frecuencia", "S/D"))
            estado_ind = _esc_html(ind.get("estado_receta", ind.get("estado_clinico", "Activa")))
            fecha_ind = _esc_html(ind.get("fecha", "S/D"))
            bloque_medicacion += f"""
            <article class="med-card">
                <div class="med-card__title">{med}</div>
                <dl class="med-card__meta">
                    <div><dt>Dosis</dt><dd>{dosis}</dd></div>
                    <div><dt>Via</dt><dd>{via}</dd></div>
                    <div><dt>Frecuencia</dt><dd>{frec}</dd></div>
                    <div><dt>Estado</dt><dd>{estado_ind}</dd></div>
                    <div><dt>Fecha</dt><dd>{fecha_ind}</dd></div>
                </dl>
            </article>
            """
    else:
        bloque_medicacion = '<p class="empty-state">Sin indicaciones activas registradas.</p>'

    # Alertas / Pendientes - lenguaje clinico profesional
    alertas = dashboard.get("alertas", [])
    criticas = [a for a in alertas if a.get("nivel") == "danger"]
    warnings = [a for a in alertas if a.get("nivel") == "warning"]
    infos = [a for a in alertas if a.get("nivel") == "info"]

    bloque_alertas = ""
    if criticas:
        bloque_alertas += '<div class="alerta critica"><strong>Alertas Criticas - Requiere Intervencion Inmediata</strong></div>\n'
        for a in criticas:
            titulo = _esc_html(a.get("titulo", ""))
            detalle = _esc_html(a.get("detalle", ""))
            bloque_alertas += f'<div class="observacion critica"><strong>{titulo}:</strong> {detalle}</div>\n'
    if warnings:
        bloque_alertas += '<div class="alerta advertencia"><strong>Advertencias Clinicas - Monitoreo Necesario</strong></div>\n'
        for a in warnings:
            titulo = _esc_html(a.get("titulo", ""))
            detalle = _esc_html(a.get("detalle", ""))
            bloque_alertas += f'<div class="observacion advertencia"><strong>{titulo}:</strong> {detalle}</div>\n'
    if infos:
        bloque_alertas += '<div class="alerta info"><strong>Observaciones de Auditoria</strong></div>\n'
        for a in infos:
            titulo = _esc_html(a.get("titulo", ""))
            detalle = _esc_html(a.get("detalle", ""))
            bloque_alertas += f'<div class="observacion info"><strong>{titulo}:</strong> {detalle}</div>\n'
    if not alertas:
        bloque_alertas = '<p>No se registran alertas ni pendientes de auditoria.</p>'

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Reporte de Auditoria y Pase de Sala - {nombre}</title>
<style>
    @page {{ size: A4; margin: 14mm; }}
    @media print {{
        body {{ margin: 0; padding: 0; background: #fff; }}
        .no-print {{ display: none; }}
        .report-shell {{ box-shadow: none; margin: 0; max-width: none; padding: 0; }}
        .section, .med-card {{ break-inside: avoid; page-break-inside: avoid; }}
    }}
    body {{
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        color: #172033; line-height: 1.5; margin: 0; padding: 0;
        background: #F3F6FA;
    }}
    .report-shell {{
        max-width: 1040px; margin: 0 auto; padding: 28px 28px 24px;
        background: #fff; box-sizing: border-box; color: #172033;
    }}
    .report-shell * {{
        color: inherit;
    }}
    .header {{
        border-bottom: 3px solid #1F4E79; padding-bottom: 14px; margin-bottom: 22px;
    }}
    .header h1 {{
        margin: 0; color: #12324D; font-size: 24px; letter-spacing: 0;
    }}
    .header p {{ margin: 4px 0; color: #617084; font-size: 13px; }}
    .estado-badge {{
        display: inline-block; padding: 5px 11px; border-radius: 999px; color: #fff;
        font-size: 12px; font-weight: 700; background-color: {color_semaforo};
    }}
    .patient-grid, .vitals-grid {{
        display: grid; gap: 10px; margin: 12px 0 22px;
    }}
    .patient-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .vitals-grid {{ grid-template-columns: repeat(5, minmax(0, 1fr)); }}
    .field, .vital {{
        border: 1px solid #D8E0E8; border-radius: 8px; padding: 10px 12px;
        background: #FBFCFE; min-width: 0;
    }}
    .field__label, .vital__label, .med-card dt {{
        display: block; color: #66758A; font-size: 11px; font-weight: 700;
        text-transform: uppercase; letter-spacing: .03em; margin-bottom: 3px;
    }}
    .field__value, .vital__value, .med-card dd {{
        margin: 0; color: #10243A; font-size: 14px; overflow-wrap: anywhere;
    }}
    .vital__value {{ font-size: 18px; font-weight: 700; }}
    .section {{ margin-top: 22px; }}
    .sep {{ color: #95A3B3; padding: 0 6px; }}
    .empty-state {{
        border: 1px dashed #C7D2DE; border-radius: 8px; padding: 14px;
        color: #617084; background: #FBFCFE;
    }}
    .section-title {{
        background-color: #EEF4F8; color: #12324D; padding: 10px 12px;
        font-size: 16px; font-weight: 700; margin: 0 0 12px;
        border-left: 5px solid #2D9CDB; border-radius: 4px;
    }}
    .evo-box {{
        background: #FBFCFE; border: 1px solid #D8E0E8; padding: 14px; border-radius: 8px;
    }}
    .evo-box blockquote {{
        margin: 8px 0 0; padding-left: 14px; border-left: 3px solid #2D9CDB;
        color: #27384A; overflow-wrap: anywhere;
    }}
    .treatment-list {{ display: grid; gap: 10px; }}
    .med-card {{
        border: 1px solid #D8E0E8; border-radius: 8px; padding: 12px;
        background: #fff;
    }}
    .med-card__title {{
        color: #10243A; font-weight: 700; margin-bottom: 9px; overflow-wrap: anywhere;
    }}
    .med-card__meta {{
        display: grid; grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 8px; margin: 0;
    }}
    .observacion {{
        margin-bottom: 10px; padding: 10px 12px; border-radius: 7px;
        font-size: 13px; overflow-wrap: anywhere; color: #172033;
    }}
    .observacion strong {{
        color: #10243A;
    }}
    .observacion.critica {{
        background: #FDEDEC; border-left: 4px solid #E74C3C; color: #4A1F1A;
    }}
    .observacion.critica strong {{
        color: #8A1F15;
    }}
    .observacion.advertencia {{
        background: #FEF5E7; border-left: 4px solid #F39C12; color: #4D3410;
    }}
    .observacion.advertencia strong {{
        color: #7A4A00;
    }}
    .observacion.info {{
        background: #EBF5FB; border-left: 4px solid #3498DB; color: #173A56;
    }}
    .observacion.info strong {{
        color: #1F5E8A;
    }}
    .alerta {{
        font-size: 13px; font-weight: 600; margin-top: 14px; margin-bottom: 6px;
        padding: 6px 10px; border-radius: 3px; display: inline-block;
    }}
    .alerta.critica {{ background: #E74C3C; color: #fff; }}
    .alerta.advertencia {{ background: #F39C12; color: #fff; }}
    .alerta.info {{ background: #3498DB; color: #fff; }}
    .footer {{
        margin-top: 30px; padding-top: 10px; border-top: 1px solid #BDC3C7;
        font-size: 11px; color: #95A5A6; text-align: center;
    }}
    @media (max-width: 720px) {{
        .report-shell {{ padding: 18px 14px; }}
        .header h1 {{ font-size: 21px; }}
        .patient-grid, .vitals-grid, .med-card__meta {{ grid-template-columns: 1fr; }}
        .vital__value {{ font-size: 16px; }}
    }}
</style>
</head>
<body>
<main class="report-shell">
    <div class="header">
        <h1>Reporte de Auditoria y Pase de Sala</h1>
        <p><strong>Generado:</strong> {fecha_generacion}</p>
        <p><strong>Institucion:</strong> MediCare Enterprise PRO</p>
    </div>

    <section class="patient-grid" aria-label="Datos del paciente">
        <div class="field"><span class="field__label">Paciente</span><div class="field__value">{nombre}</div></div>
        <div class="field"><span class="field__label">DNI</span><div class="field__value">{dni}</div></div>
        <div class="field"><span class="field__label">Obra Social</span><div class="field__value">{obra_social}</div></div>
        <div class="field"><span class="field__label">Estado General</span><div class="field__value"><span class="estado-badge">{estado_general}</span></div></div>
        <div class="field"><span class="field__label">Fecha de Nacimiento</span><div class="field__value">{fnac}</div></div>
        <div class="field"><span class="field__label">Diagnostico Principal</span><div class="field__value">{diag_principal}</div></div>
    </section>

    <section class="section">
        <div class="section-title">1. Signos Vitales Mas Recientes</div>
        <div class="vitals-grid">
            <div class="vital"><span class="vital__label">Tension Arterial</span><div class="vital__value">{ta} <small>mmHg</small></div></div>
            <div class="vital"><span class="vital__label">Frec. Cardiaca</span><div class="vital__value">{fc} <small>lpm</small></div></div>
            <div class="vital"><span class="vital__label">Temperatura</span><div class="vital__value">{temp} <small>C</small></div></div>
            <div class="vital"><span class="vital__label">Saturacion O2</span><div class="vital__value">{spo2} <small>%</small></div></div>
            <div class="vital"><span class="vital__label">Glucemia</span><div class="vital__value">{glu} <small>mg/dL</small></div></div>
        </div>
    </section>

    {bloque_evolucion}

    <section class="section">
        <div class="section-title">3. Tratamiento y Cuidados Activos</div>
        <div class="treatment-list">
            {bloque_medicacion}
        </div>
    </section>

    <section class="section">
        <div class="section-title">4. Pendientes y Observaciones de Auditoria</div>
        {bloque_alertas}
    </section>

    <div class="footer">
        Documento generado por MediCare Enterprise PRO - No sustituye la historia clinica original.
    </div>
</main>
</body>
</html>"""
    return html


def generar_pdf_informe_profesional(paciente_id: str, datos: dict, dashboard: dict) -> bytes:
    """Genera un PDF profesional del informe de pase de sala/auditoria usando FPDF.

    Devuelve los bytes listos para descargar.
    """
    from io import BytesIO
    from fpdf import FPDF
    from core.export_utils import safe_text

    paciente_data = datos.get("paciente_data") or {}
    nombre = safe_text(paciente_data.get("nombre", paciente_id))
    dni = safe_text(paciente_data.get("dni", "-"))
    obra_social = safe_text(paciente_data.get("obra_social", "S/D"))
    fnac = safe_text(paciente_data.get("fnac", "S/D"))
    diag_principal = safe_text(paciente_data.get("diagnostico", paciente_data.get("patologias", "Sin diagnostico principal registrado")))
    fecha_generacion = safe_text(_ahora().strftime("%d/%m/%Y %H:%M"))

    semaforo = dashboard.get("semaforo", "desconocido")
    estado_general = "ATENCION REQUERIDA" if semaforo in ("rojo", "amarillo") else "ESTABLE"

    pdf = FPDF()
    pdf.set_margins(14, 14, 14)
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    page_w = pdf.w - pdf.l_margin - pdf.r_margin

    def reset_text():
        pdf.set_text_color(23, 32, 51)

    def ensure_space(mm: float):
        if pdf.get_y() + mm > pdf.page_break_trigger:
            pdf.add_page()

    def section_title(title: str):
        ensure_space(14)
        pdf.set_x(pdf.l_margin)
        pdf.set_fill_color(238, 244, 248)
        pdf.set_draw_color(45, 156, 219)
        pdf.set_text_color(18, 50, 77)
        pdf.set_font("Helvetica", "B", 11)
        y = pdf.get_y()
        pdf.rect(pdf.l_margin, y, page_w, 8, style="F")
        pdf.rect(pdf.l_margin, y, 2.2, 8, style="F")
        pdf.set_xy(pdf.l_margin + 4, y)
        pdf.cell(page_w - 4, 8, title, ln=True)
        pdf.ln(3)
        reset_text()

    def wrapped(text: str, font_size: int = 9, line_h: float = 5, indent: float = 0):
        pdf.set_x(pdf.l_margin + indent)
        pdf.set_font("Helvetica", "", font_size)
        reset_text()
        pdf.multi_cell(page_w - indent, line_h, safe_text(text))

    def label_value(label: str, value: str, x: float, y: float, w: float, h: float = 15):
        pdf.set_xy(x, y)
        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(216, 224, 232)
        pdf.rect(x, y, w, h, style="DF")
        pdf.set_xy(x + 2.5, y + 2)
        pdf.set_text_color(102, 117, 138)
        pdf.set_font("Helvetica", "B", 7)
        pdf.cell(w - 5, 4, label.upper(), ln=True)
        pdf.set_x(x + 2.5)
        reset_text()
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(w - 5, 4.2, safe_text(value))

    def text_box(text: str, fill, border, text_color=(23, 32, 51), title: str | None = None):
        ensure_space(18)
        start_y = pdf.get_y()
        x = pdf.l_margin
        pdf.set_font("Helvetica", "B", 9)
        lines = []
        if title:
            lines.append(("title", safe_text(title)))
        pdf.set_font("Helvetica", "", 9)
        body = safe_text(text)
        body_lines = pdf.multi_cell(page_w - 8, 4.8, body, split_only=True)
        height = 7 + (4.8 * max(1, len(body_lines))) + (4 if title else 0)
        ensure_space(height + 2)
        start_y = pdf.get_y()
        pdf.set_fill_color(*fill)
        pdf.set_draw_color(*border)
        pdf.rect(x, start_y, page_w, height, style="DF")
        pdf.set_xy(x + 4, start_y + 3)
        pdf.set_text_color(*text_color)
        if title:
            pdf.set_font("Helvetica", "B", 9)
            pdf.multi_cell(page_w - 8, 4.8, safe_text(title))
            pdf.set_x(x + 4)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_x(x + 4)
        pdf.multi_cell(page_w - 8, 4.8, body)
        pdf.set_y(start_y + height + 3)
        reset_text()

    def alert_group(title: str, items: list, fill, border, title_color):
        if not items:
            return
        ensure_space(12)
        pdf.set_x(pdf.l_margin)
        pdf.set_fill_color(*fill)
        pdf.set_text_color(*title_color)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(page_w, 8, title, ln=True, fill=True)
        reset_text()
        pdf.ln(1.5)
        for item in items:
            titulo = safe_text(item.get("titulo", ""))
            detalle = safe_text(item.get("detalle", ""))
            text_box(detalle, fill, border, text_color=(23, 32, 51), title=titulo)

    # Encabezado corporativo
    pdf.set_fill_color(18, 50, 77)
    pdf.rect(pdf.l_margin, pdf.get_y(), page_w, 22, style="F")
    pdf.set_xy(pdf.l_margin + 5, pdf.get_y() + 4)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(page_w - 10, 7, "Reporte de Auditoria y Pase de Sala", ln=True)
    pdf.set_x(pdf.l_margin + 5)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(page_w - 10, 5, f"Generado: {fecha_generacion} | MediCare Enterprise PRO", ln=True)
    pdf.ln(8)
    reset_text()

    # Datos del paciente
    section_title("Datos del paciente")
    gap = 4
    col = (page_w - gap) / 2
    y = pdf.get_y()
    label_value("Paciente", nombre, pdf.l_margin, y, col)
    label_value("DNI", dni, pdf.l_margin + col + gap, y, col)
    y += 18
    label_value("Obra Social", obra_social, pdf.l_margin, y, col)
    label_value("F. Nacimiento", fnac, pdf.l_margin + col + gap, y, col)
    y += 18
    label_value("Diagnostico", diag_principal, pdf.l_margin, y, page_w)
    pdf.set_y(y + 18)
    badge_fill = (231, 76, 60) if semaforo == "rojo" else ((243, 156, 18) if semaforo == "amarillo" else (39, 174, 96))
    pdf.set_fill_color(*badge_fill)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(60, 7, f"Estado: {estado_general}", ln=True, align="C", fill=True)
    reset_text()
    pdf.ln(4)

    # Signos vitales
    section_title("1. Signos vitales mas recientes")
    vitals = [
        ("TA", safe_text(dashboard.get("ultima_ta", "-")), "mmHg"),
        ("FC", safe_text(dashboard.get("ultima_fc", "-")), "lpm"),
        ("Temp", safe_text(dashboard.get("ultima_temp", "-")), "C"),
        ("SatO2", safe_text(dashboard.get("ultima_spo2", "-")), "%"),
        ("Glucemia", safe_text(dashboard.get("ultima_glu", "-")), "mg/dL"),
    ]
    card_gap = 3
    card_w = (page_w - (card_gap * 4)) / 5
    y = pdf.get_y()
    for idx, (label, value, unit) in enumerate(vitals):
        x = pdf.l_margin + idx * (card_w + card_gap)
        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(216, 224, 232)
        pdf.rect(x, y, card_w, 18, style="DF")
        pdf.set_xy(x + 2, y + 2)
        pdf.set_text_color(102, 117, 138)
        pdf.set_font("Helvetica", "B", 7)
        pdf.cell(card_w - 4, 4, label.upper(), ln=True)
        pdf.set_xy(x + 2, y + 7)
        reset_text()
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(card_w - 4, 5, value, ln=True)
        pdf.set_x(x + 2)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(102, 117, 138)
        pdf.cell(card_w - 4, 4, unit)
    pdf.set_y(y + 22)
    reset_text()

    # Ultima evolucion
    section_title("2. Ultima evolucion clinica")
    evoluciones = datos.get("evoluciones", [])
    if evoluciones:
        ultima_evo = max(evoluciones, key=lambda x: _parse_fecha(x.get("fecha", "")) or datetime.min)
        evo_fecha = safe_text(ultima_evo.get("fecha", "S/D"))
        evo_prof = safe_text(ultima_evo.get("firma", ultima_evo.get("profesional", "S/D")))
        evo_texto = safe_text(ultima_evo.get("nota", ultima_evo.get("evolucion", ultima_evo.get("texto", "Sin detalle de texto"))))
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 5, f"Fecha: {evo_fecha} | Profesional: {evo_prof}", ln=True)
        pdf.ln(1)
        text_box(evo_texto, (248, 250, 252), (216, 224, 232))
    else:
        wrapped("Sin evoluciones registradas.")
    pdf.ln(1)

    # Tratamiento y cuidados activos
    section_title("3. Tratamiento y cuidados activos")
    indicaciones = datos.get("indicaciones", [])
    indicaciones_activas = [
        ind for ind in indicaciones
        if "activa" in str(ind.get("estado_receta", ind.get("estado_clinico", ""))).lower()
    ]
    if indicaciones_activas:
        for ind in indicaciones_activas:
            med = safe_text(ind.get("med", "Medicacion"))
            dosis = safe_text(ind.get("dosis", "S/D"))
            via = safe_text(ind.get("via", "S/D"))
            frec = safe_text(ind.get("frecuencia", "S/D"))
            estado_ind = safe_text(ind.get("estado_receta", ind.get("estado_clinico", "Activa")))
            fecha_ind = safe_text(ind.get("fecha", "S/D"))
            detalle = f"Dosis: {dosis} | Via: {via} | Frecuencia: {frec} | Estado: {estado_ind} | Fecha: {fecha_ind}"
            text_box(detalle, (255, 255, 255), (216, 224, 232), title=med)
    else:
        wrapped("Sin indicaciones activas registradas.")
    pdf.ln(1)

    # Pendientes y observaciones
    section_title("4. Pendientes y observaciones de auditoria")
    alertas = dashboard.get("alertas", [])
    criticas = [a for a in alertas if a.get("nivel") == "danger"]
    warnings = [a for a in alertas if a.get("nivel") == "warning"]
    infos = [a for a in alertas if a.get("nivel") == "info"]

    alert_group(
        "Alertas criticas - requiere intervencion inmediata",
        criticas,
        (253, 237, 236),
        (231, 76, 60),
        (138, 31, 21),
    )
    alert_group(
        "Advertencias clinicas - monitoreo necesario",
        warnings,
        (254, 245, 231),
        (243, 156, 18),
        (122, 74, 0),
    )
    alert_group(
        "Observaciones de auditoria",
        infos,
        (235, 245, 251),
        (52, 152, 219),
        (31, 94, 138),
    )
    if not alertas:
        wrapped("No se registran alertas ni pendientes de auditoria.")

    ensure_space(12)
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(127, 140, 141)
    pdf.cell(page_w, 5, "Documento generado por MediCare Enterprise PRO - No sustituye la historia clinica original.", ln=True, align="C")

    return bytes(pdf.output(dest="S"))


def generar_texto_pase_guardia(paciente_id: str, datos: dict, dashboard: dict) -> str:
    paciente_data = datos.get("paciente_data") or {}
    nombre = paciente_data.get("nombre", paciente_id)
    dni = paciente_data.get("dni", "-")
    obra_social = paciente_data.get("obra_social", "S/D")
    edad = paciente_data.get("fnac", "S/D")
    diag_principal = paciente_data.get("diagnostico", paciente_data.get("patologias", "Sin diagnostico principal registrado"))

    lines = [
        "=== INFORME DE PASE DE GUARDIA / AUDITORIA ===",
        f"Generado: {_ahora().strftime('%d/%m/%Y %H:%M')}",
        f"Paciente: {nombre}",
        f"DNI: {dni}  |  Obra Social: {obra_social}  |  F.Nac: {edad}",
        f"Diagnostico principal: {diag_principal}",
        f"Estado del Sistema: {dashboard.get('semaforo', 'desconocido').upper()} {'(REQUIERE ATENCION)' if dashboard.get('semaforo') in ('rojo', 'amarillo') else '(ESTABLE)'}",
        "",
        "--- 1. ESTADO ACTUAL (Ultimos Signos Vitales) ---",
        f"TA: {dashboard['ultima_ta']} mmHg  |  FC: {dashboard['ultima_fc']} lpm  |  Temp: {dashboard['ultima_temp']} C",
        f"SatO2: {dashboard['ultima_spo2']} %  |  Glucemia: {dashboard['ultima_glu']} mg/dL",
        "",
    ]

    # 2. ULTIMA EVOLUCION CLINICA
    evoluciones = datos.get("evoluciones", [])
    if evoluciones:
        ultima_evo = max(evoluciones, key=lambda x: _parse_fecha(x.get("fecha", "")) or datetime.min)
        evo_fecha = ultima_evo.get("fecha", "S/D")
        evo_prof = ultima_evo.get("firma", ultima_evo.get("profesional", "S/D"))
        evo_texto = ultima_evo.get("nota", ultima_evo.get("evolucion", ultima_evo.get("texto", "Sin detalle de texto")))
        lines.append("--- 2. ULTIMA EVOLUCION CLINICA ---")
        lines.append(f"[{evo_fecha}] - {evo_prof}:")
        lines.append(f'"{evo_texto}"')
        lines.append("")
    else:
        lines.append("--- 2. ULTIMA EVOLUCION CLINICA ---")
        lines.append("Sin evoluciones registradas.")
        lines.append("")

    # 3. TRATAMIENTO Y CUIDADOS ACTIVOS
    indicaciones = datos.get("indicaciones", [])
    indicaciones_activas = [
        ind for ind in indicaciones
        if "activa" in str(ind.get("estado_receta", ind.get("estado_clinico", ""))).lower()
    ]
    if indicaciones_activas:
        lines.append("--- 3. TRATAMIENTO Y CUIDADOS ACTIVOS ---")
        for ind in indicaciones_activas:
            med = str(ind.get("med", "Medicacion"))
            dosis = str(ind.get("dosis", "S/D"))
            via = str(ind.get("via", "S/D"))
            frecuencia = str(ind.get("frecuencia", "S/D"))
            estado_ind = ind.get("estado_receta", ind.get("estado_clinico", "Activa"))
            fecha_ind = str(ind.get("fecha", "S/D"))
            lines.append(f"- {med} | Dosis: {dosis} | Via: {via} | Frecuencia: {frecuencia} | Estado: {estado_ind} | Fecha: {fecha_ind}")
        lines.append("")
    else:
        lines.append("--- 3. TRATAMIENTO Y CUIDADOS ACTIVOS ---")
        lines.append("Sin indicaciones activas registradas.")
        lines.append("")

    # 4. ALERTAS Y PENDIENTES
    lines.append("--- 4. ALERTAS Y PENDIENTES (ATENCION) ---")

    alertas = dashboard.get("alertas", [])
    criticas = [a for a in alertas if a.get("nivel") == "danger"]
    warnings = [a for a in alertas if a.get("nivel") == "warning"]
    infos = [a for a in alertas if a.get("nivel") == "info"]

    if criticas:
        lines.append("[CRITICAS]")
        for a in criticas:
            lines.append(f"[!] {a['titulo']}: {a['detalle']}")
    if warnings:
        lines.append("[ADVERTENCIAS]")
        for a in warnings:
            lines.append(f"[!!] {a['titulo']}: {a['detalle']}")
    if infos:
        lines.append("[OBSERVACIONES / AUDITORIA]")
        for a in infos:
            lines.append(f"[i] {a['titulo']}: {a['detalle']}")

    if not alertas:
        lines.append("Sin alertas ni pendientes detectados.")

    lines.append("")
    lines.append("=" * 46)
    return "\n".join(lines)
