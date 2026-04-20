"""Helpers de evaluación de signos vitales para el dashboard. Extraído de views/dashboard.py."""

_RANGOS_DASH = {
    "FC":   {"min": 60,   "max": 100,  "crit_min": 40,   "crit_max": 130},
    "FR":   {"min": 12,   "max": 20,   "crit_min": 8,    "crit_max": 30},
    "Sat":  {"min": 94,   "max": 100,  "crit_min": 88,   "crit_max": 100},
    "Temp": {"min": 36.0, "max": 37.5, "crit_min": 35.0, "crit_max": 39.0},
    "HGT":  {"min": 70,   "max": 180,  "crit_min": 50,   "crit_max": 300},
}


def _estado_vital_dash(clave, valor):
    r = _RANGOS_DASH.get(clave)
    if r is None:
        return "normal"
    try:
        v = float(str(valor).replace(",", "."))
    except Exception:
        return "normal"
    if v < r["crit_min"] or v > r["crit_max"]:
        return "critico"
    if v < r["min"] or v > r["max"]:
        return "alerta"
    return "normal"


def _estado_ta_dash(ta_str):
    try:
        partes = str(ta_str or "").replace("/", " ").split()
        if len(partes) < 2:
            return "normal"
        sis, dia = float(partes[0]), float(partes[1])
        if sis < 80 or sis > 180 or dia < 50 or dia > 120:
            return "critico"
        if sis < 90 or sis > 140 or dia < 60 or dia > 90:
            return "alerta"
        return "normal"
    except Exception:
        return "normal"


def _evaluar_ultimo_vital(reg):
    """Devuelve ('critico'|'alerta'|'normal', [str de problemas])"""
    peor = "normal"
    problemas = []
    ta_est = _estado_ta_dash(reg.get("TA", ""))
    if ta_est == "critico":
        peor = "critico"
        problemas.append(f"TA {reg.get('TA')} crítica")
    elif ta_est == "alerta":
        if peor != "critico":
            peor = "alerta"
        problemas.append(f"TA {reg.get('TA')} alterada")
    for clave in ("FC", "FR", "Sat", "Temp", "HGT"):
        val = reg.get(clave)
        if val in (None, "", "-"):
            continue
        est = _estado_vital_dash(clave, val)
        if est == "critico":
            peor = "critico"
            problemas.append(f"{clave}={val} crítico")
        elif est == "alerta" and peor != "critico":
            peor = "alerta"
            problemas.append(f"{clave}={val} alterado")
    return peor, problemas


def _sumar_importe(registros):
    claves = ("monto", "importe", "total", "facturado", "valor")
    total = 0.0
    for item in registros:
        for clave in claves:
            valor = item.get(clave)
            if valor in ("", None):
                continue
            try:
                total += float(str(valor).replace(",", "."))
                break
            except Exception:
                continue
    return round(total, 2)
