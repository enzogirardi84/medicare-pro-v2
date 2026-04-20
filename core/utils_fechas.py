"""Funciones de fecha, hora, agenda, horarios de receta e infusión.

Extraído de core/utils.py.
"""
import re
from datetime import datetime
from functools import lru_cache

import pytz

ARG_TZ = pytz.timezone("America/Argentina/Buenos_Aires")


def ahora():
    return datetime.now(ARG_TZ)


def _to_float(value):
    try:
        if value in ("", None):
            return None
        return float(value)
    except Exception:
        return None


@lru_cache(maxsize=8192)
def _parse_fecha_hora_cached(fecha_txt: str):
    formatos = (
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d",
    )
    for formato in formatos:
        try:
            return datetime.strptime(fecha_txt, formato)
        except Exception:
            continue
    return datetime.min


def parse_fecha_hora(fecha_str):
    return _parse_fecha_hora_cached(str(fecha_str or "").strip())


def normalizar_hora_texto(valor, default="08:00"):
    texto = str(valor or "").strip().lower()
    if not texto:
        return default
    texto = (
        texto.replace(" horas", "").replace(" hora", "").replace("hrs", "")
        .replace("hs.", "").replace("hs", "").replace("h", "").strip()
    )
    match = re.search(r"^(\d{1,2})(?::(\d{1,2}))?$", texto)
    if not match:
        return default
    horas = int(match.group(1))
    minutos = int(match.group(2) or 0)
    if horas > 23 or minutos > 59:
        return default
    return f"{horas:02d}:{minutos:02d}"


def parse_agenda_datetime(item):
    fecha_hora_programada = str(item.get("fecha_hora_programada", "")).strip()
    if fecha_hora_programada:
        dt_programado = parse_fecha_hora(fecha_hora_programada)
        if dt_programado != datetime.min:
            return dt_programado
    fecha = str(item.get("fecha_programada", "") or item.get("fecha", "")).strip()
    hora = normalizar_hora_texto(item.get("hora", ""), default="00:00")
    return parse_fecha_hora(f"{fecha} {hora}")


def calcular_estado_agenda(item, now=None):
    now = now or ahora().replace(tzinfo=None)
    estado = str(item.get("estado", "Pendiente")).strip() or "Pendiente"
    if estado in {"Realizada", "Cancelada"}:
        return estado
    dt = parse_agenda_datetime(item)
    if dt == datetime.min:
        return estado
    if dt.date() == now.date() and dt <= now:
        return "En curso"
    if dt < now:
        return "Vencida"
    return "Pendiente"


def parse_horarios_programados(texto):
    if isinstance(texto, list):
        candidatos = texto
    else:
        candidatos = re.split(r"[,\|;/\n]+", str(texto or ""))
    horarios = []
    for valor in candidatos:
        hora = normalizar_hora_texto(valor, default="")
        if hora:
            horarios.append(hora)
    return sorted(set(horarios), key=lambda x: (int(x.split(":")[0]), int(x.split(":")[1])))


def horarios_programados_desde_frecuencia(frecuencia, hora_inicio="08:00"):
    frecuencia = str(frecuencia or "").strip()
    hora_inicio = normalizar_hora_texto(hora_inicio)
    intervalos = {
        "Cada 1 hora": 1, "Cada 2 horas": 2, "Cada 4 horas": 4,
        "Cada 6 horas": 6, "Cada 8 horas": 8, "Cada 12 horas": 12, "Cada 24 horas": 24,
    }
    if frecuencia == "Dosis unica":
        return [hora_inicio]
    if frecuencia == "Infusion continua":
        return [hora_inicio]
    if frecuencia == "Segun necesidad":
        return []
    intervalo = intervalos.get(frecuencia)
    if not intervalo:
        return []
    hora_base = int(hora_inicio.split(":")[0])
    minuto_base = int(hora_inicio.split(":")[1])
    horas = []
    total = 24 if intervalo < 24 else 1
    for paso in range(total):
        horas.append(f"{(hora_base + (paso * intervalo)) % 24:02d}:{minuto_base:02d}")
        if intervalo == 24:
            break
    return sorted(set(horas), key=lambda x: (int(x.split(":")[0]), int(x.split(":")[1])))


def calcular_velocidad_ml_h(volumen_ml, duracion_horas):
    try:
        volumen = float(volumen_ml)
        horas = float(duracion_horas)
        if volumen <= 0 or horas <= 0:
            return None
        return round(volumen / horas, 2)
    except Exception:
        return None


def generar_plan_escalonado_ml_h(inicio_ml_h, maximo_ml_h, incremento_ml_h=7, hora_inicio="08:00", intervalo_horas=1):
    try:
        inicio = float(inicio_ml_h)
        maximo = float(maximo_ml_h)
        incremento = float(incremento_ml_h)
        intervalo = max(1, int(intervalo_horas))
    except Exception:
        return []
    if inicio <= 0 or maximo <= 0 or incremento <= 0:
        return []
    hora_base = normalizar_hora_texto(hora_inicio)
    base_hora = int(hora_base.split(":")[0])
    base_min = int(hora_base.split(":")[1])
    valores = []
    actual = inicio
    while actual < maximo:
        valores.append(round(actual, 2))
        actual += incremento
    if not valores or valores[-1] != round(maximo, 2):
        valores.append(round(maximo, 2))
    plan = []
    for idx, velocidad in enumerate(valores, start=1):
        hora_paso = (base_hora + ((idx - 1) * intervalo)) % 24
        plan.append({"Paso": idx, "Hora sugerida": f"{hora_paso:02d}:{base_min:02d}", "Velocidad (ml/h)": velocidad})
    return plan


def extraer_frecuencia_desde_indicacion(indicacion):
    texto = str(indicacion or "")
    for parte in [p.strip() for p in texto.split("|")]:
        if parte.startswith("Cada ") or parte in ("Dosis unica", "Segun necesidad"):
            return parte
    return ""


def obtener_horarios_receta(registro):
    horarios_guardados = registro.get("horarios_programados", [])
    horarios = parse_horarios_programados(horarios_guardados)
    if horarios:
        return horarios
    frecuencia = registro.get("frecuencia") or extraer_frecuencia_desde_indicacion(registro.get("med", ""))
    hora_inicio = registro.get("hora_inicio", "08:00")
    return horarios_programados_desde_frecuencia(frecuencia, hora_inicio)


def format_horarios_receta(registro):
    horarios = obtener_horarios_receta(registro)
    if not horarios:
        return "A demanda / sin horario fijo"
    return " | ".join(horarios)
