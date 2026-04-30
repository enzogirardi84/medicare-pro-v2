"""Motor de reglas determinista para el Asistente Clinico 360.
Analiza datos de session_state y genera alertas sin IA externa.
"""
from __future__ import annotations
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import streamlit as st

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
    for fmt in ("%Y-%m-%dT%H:%M:%S","%Y-%m-%d %H:%M:%S","%Y-%m-%dT%H:%M","%Y-%m-%d %H:%M","%d/%m/%Y %H:%M:%S","%d/%m/%Y %H:%M","%Y-%m-%d","%d/%m/%Y"):
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
    for campo in (item.get("paciente"), item.get("paciente_id"), item.get("nombre"), item.get("dni")):
        if campo is not None and pid_norm in str(campo).strip().lower():
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
    for key, target in (("evoluciones_db","evoluciones"),("vitales_db","vitales"),
                        ("indicaciones_db","indicaciones"),("cuidados_enfermeria_db","cuidados"),
                        ("consumos_db","consumos"),("balance_db","balance"),
                        ("estudios_db","estudios"),("administracion_med_db","administracion_med"),
                        ("diagnosticos_db","diagnosticos"),("escalas_clinicas_db","escalas"),
                        ("emergencias_db","emergencias"),("checkin_db","checkin")):
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
        sys_ta, dia_ta = _extraer_ta(v.get("presion_arterial") or v.get("ta") or v.get("tension"))
        if sys_ta and sys_ta > 150:
            alertas.append({"titulo":"Riesgo Cardiovascular — TA elevada","detalle":f"Ultima TA: {sys_ta}/{dia_ta or '-'} mmHg. Supera umbral de 150/90.","nivel":"danger","categoria":"vitales"})
            break
    # Glucemia extrema
    for v in vitales:
        glu = _to_float(v.get("glucemia") or v.get("glucosa"))
        if glu is not None and (glu < 70 or glu > 250):
            tipo = "hipoglucemia" if glu < 70 else "hiperglucemia"
            alertas.append({"titulo":f"Riesgo Metabolico — {tipo}","detalle":f"Glucemia: {glu} mg/dL. Requiere revision.","nivel":"danger","categoria":"vitales"})
            break
    # Fiebre
    for v in vitales:
        temp = _to_float(v.get("temperatura") or v.get("temp"))
        if temp is not None and temp >= 38.5:
            alertas.append({"titulo":"Fiebre significativa","detalle":f"Temperatura: {temp}C. Evaluar origen infeccioso.","nivel":"warning","categoria":"vitales"})
            break
    # FC extrema
    for v in vitales:
        fc = _to_float(v.get("frecuencia_cardiaca") or v.get("fc") or v.get("pulso"))
        if fc is not None:
            if fc < 50:
                alertas.append({"titulo":"Bradicardia","detalle":f"FC: {fc} lat/min. < 50 requiere evaluacion.","nivel":"warning","categoria":"vitales"})
                break
            elif fc > 120:
                alertas.append({"titulo":"Taquicardia","detalle":f"FC: {fc} lat/min. > 120 requiere evaluacion.","nivel":"warning","categoria":"vitales"})
                break
    # Hipoxemia
    for v in vitales:
        sat = _to_float(v.get("saturacion_o2") or v.get("saturacion") or v.get("spo2"))
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
                    alertas.append({"titulo":"Riesgo Farmacologico — HTA no controlada","detalle":"Paciente con medicacion antihipertensiva activa y TA > 150/90. Evaluar ajuste.","nivel":"danger","categoria":"farmacologia"})
                break
    # Indicaciones sin administracion
    for ind in indicaciones:
        if "activa" not in str(ind.get("estado_receta",ind.get("estado_clinico",""))).lower():
            continue
        med_texto = ind.get("med","")
        ya_admin = any(str(med_texto).lower() in str(adm.get("med","")).lower() for adm in administracion)
        if not ya_admin:
            alertas.append({"titulo":"Administracion Pendiente","detalle":f"Indicacion activa: {str(med_texto)[:60]}... sin registro de administracion.","nivel":"warning","categoria":"farmacologia"})
    # Curacion sin insumos
    for c in cuidados:
        if _contiene_keyword(c.get("cuidado_tipo",c.get("tipo_cuidado","")),("curacion","curacion")):
            tiene_insumo = any(_contiene_keyword(co.get("insumo",co.get("material","")),("gasa","antisep","aposito","venda")) for co in datos.get("consumos",[]))
            if not tiene_insumo:
                alertas.append({"titulo":"Auditoria de Insumos — Curacion sin consumo","detalle":"Se registro una curacion pero no hay gasto de gasa/antiseptico en consumos.","nivel":"warning","categoria":"insumos"})
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
            alertas.append({"titulo":"Estudio pendiente de resultado","detalle":f"{es.get('tipo','Estudio')}: {es.get('nombre',es.get('detalle','-'))} — Estado: {es.get('estado','Pendiente')}","nivel":"info","categoria":"consistencia"})
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
            alertas.append({"titulo":"Auditoria de Insumos — Consumo elevado","detalle":f"Consumo de {insumo}: {cantidad} unidades. Revisar justificacion clinica.","nivel":"warning","categoria":"insumos"})
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
        s, d = _extraer_ta(ultimo_vital.get("presion_arterial") or ultimo_vital.get("ta"))
        if s:
            ultima_ta = f"{s}/{d or '-'}"
        ultima_fc = str(ultimo_vital.get("frecuencia_cardiaca") or ultimo_vital.get("fc") or "-")
        t = _to_float(ultimo_vital.get("temperatura") or ultimo_vital.get("temp"))
        if t is not None:
            ultima_temp = f"{t:.1f}"
        g = _to_float(ultimo_vital.get("glucemia") or ultimo_vital.get("glucosa"))
        if g is not None:
            ultima_glu = f"{g:.0f}"
        s2 = _to_float(ultimo_vital.get("saturacion_o2") or ultimo_vital.get("saturacion") or ultimo_vital.get("spo2"))
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
        s, d = _extraer_ta(v.get("presion_arterial") or v.get("ta"))
        g = _to_float(v.get("glucemia") or v.get("glucosa"))
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

def generar_texto_pase_guardia(paciente_id: str, datos: dict, dashboard: dict) -> str:
    paciente_data = datos.get("paciente_data") or {}
    nombre = paciente_data.get("nombre", paciente_id)
    dni = paciente_data.get("dni", "-")
    lines = [
        f"=== INFORME DE PASE DE GUARDIA / AUDITORIA ===",
        f"Paciente: {nombre} | DNI: {dni}",
        f"Generado: {_ahora().strftime('%d/%m/%Y %H:%M')}",
        f"Semaforo de estado: {dashboard.get('semaforo', 'desconocido').upper()}",
        "",
        f"Alertas criticas: {dashboard['alertas_criticas']}",
        f"Alertas warning: {dashboard['alertas_warning']}",
        f"Alertas info: {dashboard['alertas_info']}",
        "",
        "--- Signos vitales mas recientes ---",
        f"TA: {dashboard['ultima_ta']} | FC: {dashboard['ultima_fc']} | Temp: {dashboard['ultima_temp']}C",
        f"Glucemia: {dashboard['ultima_glu']} | SatO2: {dashboard['ultima_spo2']}",
        "",
        "--- Resumen de actividad ---",
        f"Evoluciones (24h): {dashboard['evoluciones_24h']} | Total: {dashboard['total_evoluciones']}",
        f"Cuidados (24h): {dashboard['cuidados_24h']} | Total: {dashboard['total_cuidados']}",
        f"Indicaciones activas: {dashboard['indicaciones_activas']}",
        f"Administraciones pendientes: {dashboard['administraciones_pendientes']}",
        f"Estudios pendientes: {dashboard['estudios_pendientes']}",
        "",
        "--- Alertas activas ---",
    ]
    for a in dashboard.get("alertas", []):
        lines.append(f"[{a['nivel'].upper()}] {a['titulo']}: {a['detalle']}")
    lines.append("")
    lines.append("=== FIN DEL INFORME ===")
    return "\n".join(lines)
