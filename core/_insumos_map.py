"""Mapa clínico de asociación medicamento/procedimiento → insumos necesarios.

Usado por _recetas_mar.py y _evolucion_panel.py para deducir automáticamente
los insumos consumidos al administrar medicación o realizar procedimientos.

Estructura:
    { "palabra_clave": [{"item": "nombre insumo", "cantidad": N}, ...] }

La búsqueda usa substring matching (case insensitive) contra el nombre del
medicamento o el texto de la evolución.
"""

from __future__ import annotations

from typing import Dict, List

MapType = Dict[str, List[Dict[str, int | str]]]

# ---------------------------------------------------------------------------
# Medicamentos → insumos (por ingrediente activo o nombre comercial común)
# ---------------------------------------------------------------------------
# La clave es una substring del nombre del medicamento (en minúsculas).
# "cantidad" es la cantidad del insumo que se consume por cada dosis.

MEDICAMENTO_A_INSUMOS: MapType = {
    # ---------- Antiespasmódicos ----------
    "hioscina": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja EV", "cantidad": 1},
    ],
    "butilhioscina": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja EV", "cantidad": 1},
    ],
    "hiocina": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja EV", "cantidad": 1},
    ],
    "buscopan": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja EV", "cantidad": 1},
    ],
    # ---------- Antibióticos IV ----------
    "ceftriaxona": [
        {"item": "Jeringa 10ml", "cantidad": 1},
        {"item": "Aguja EV", "cantidad": 1},
        {"item": "Solución fisiológica 500ml", "cantidad": 1},
    ],
    "cefalotina": [
        {"item": "Jeringa 10ml", "cantidad": 1},
        {"item": "Aguja EV", "cantidad": 1},
        {"item": "Solución fisiológica 500ml", "cantidad": 1},
    ],
    "cefalexina": [],
    "amoxicilina": [],
    "ampicilina": [
        {"item": "Jeringa 10ml", "cantidad": 1},
        {"item": "Aguja EV", "cantidad": 1},
        {"item": "Solución fisiológica 500ml", "cantidad": 1},
    ],
    "gentamicina": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja IM", "cantidad": 1},
    ],
    "penicilina": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja IM", "cantidad": 1},
    ],
    "clindamicina": [
        {"item": "Jeringa 10ml", "cantidad": 1},
        {"item": "Aguja EV", "cantidad": 1},
        {"item": "Solución fisiológica 500ml", "cantidad": 1},
    ],
    "metronidazol": [
        {"item": "Equipo de venoclisis", "cantidad": 1},
    ],
    "vancomicina": [
        {"item": "Equipo de venoclisis", "cantidad": 1},
        {"item": "Solución fisiológica 500ml", "cantidad": 1},
    ],
    "ciprofloxacina": [
        {"item": "Equipo de venoclisis", "cantidad": 1},
    ],
    # ---------- AINEs / Analgésicos IM ----------
    "diclofenac": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja IM", "cantidad": 1},
    ],
    "ketorolac": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja IM", "cantidad": 1},
    ],
    "dipirona": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja IM/EV", "cantidad": 1},
    ],
    "metamizol": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja IM/EV", "cantidad": 1},
    ],
    "ibuprofeno": [],
    "paracetamol": [],
    "dexketoprofeno": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja IM", "cantidad": 1},
    ],
    "tramadol": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja IM", "cantidad": 1},
    ],
    "morfina": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja SC", "cantidad": 1},
    ],
    # ---------- Subcutáneos ----------
    "heparina": [
        {"item": "Jeringa 1ml", "cantidad": 1},
        {"item": "Aguja SC", "cantidad": 1},
    ],
    "enoxaparina": [
        {"item": "Jeringa 1ml", "cantidad": 1},
        {"item": "Aguja SC", "cantidad": 1},
    ],
    "clexane": [
        {"item": "Jeringa 1ml", "cantidad": 1},
        {"item": "Aguja SC", "cantidad": 1},
    ],
    "insulina": [
        {"item": "Jeringa 1ml", "cantidad": 1},
        {"item": "Aguja SC", "cantidad": 1},
    ],
    # ---------- Diuréticos / Cardio ----------
    "furosemida": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja EV", "cantidad": 1},
    ],
    "enalapril": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja EV", "cantidad": 1},
    ],
    "amiodarona": [
        {"item": "Jeringa 10ml", "cantidad": 1},
        {"item": "Aguja EV", "cantidad": 1},
        {"item": "Equipo de venoclisis", "cantidad": 1},
    ],
    "lidocaina": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja IM", "cantidad": 1},
    ],
    # ---------- Gastroprotectores ----------
    "omeprazol": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja EV", "cantidad": 1},
    ],
    "omperazol": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja EV", "cantidad": 1},
    ],
    "ranitidina": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja EV", "cantidad": 1},
    ],
    # ---------- Antieméticos ----------
    "metoclopramida": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja IM/EV", "cantidad": 1},
    ],
    "ondansetron": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja EV", "cantidad": 1},
    ],
    # ---------- Benzodiazepinas / Sedantes ----------
    "diazepam": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja IM/EV", "cantidad": 1},
    ],
    "midazolam": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja EV", "cantidad": 1},
    ],
    "haloperidol": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja IM", "cantidad": 1},
    ],
    # ---------- Soluciones / Hidratación ----------
    "solucion fisiologica": [
        {"item": "Equipo de venoclisis", "cantidad": 1},
    ],
    "ringer": [
        {"item": "Equipo de venoclisis", "cantidad": 1},
    ],
    "dextrosa": [
        {"item": "Equipo de venoclisis", "cantidad": 1},
    ],
    "solucion salina": [
        {"item": "Equipo de venoclisis", "cantidad": 1},
    ],
    "cloruro de sodio": [
        {"item": "Equipo de venoclisis", "cantidad": 1},
    ],
    # ---------- Otros ----------
    "vitamina": [],
    "hierro": [],
    "dexametasona": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja IM/EV", "cantidad": 1},
    ],
}

# ---------------------------------------------------------------------------
# Procedimientos → insumos (por palabra clave en la nota de evolución)
# ---------------------------------------------------------------------------

PROCEDIMIENTO_A_INSUMOS: MapType = {
    "baño en cama": [
        {"item": "Pañal descartable", "cantidad": 2},
        {"item": "Toalla húmeda", "cantidad": 4},
        {"item": "Guantes descartables", "cantidad": 2},
        {"item": "Sábana descartable", "cantidad": 1},
        {"item": "Jabón quirúrgico", "cantidad": 1},
    ],
    "baño": [
        {"item": "Pañal descartable", "cantidad": 2},
        {"item": "Toalla húmeda", "cantidad": 4},
        {"item": "Guantes descartables", "cantidad": 2},
        {"item": "Sábana descartable", "cantidad": 1},
        {"item": "Jabón quirúrgico", "cantidad": 1},
    ],
    "higiene": [
        {"item": "Pañal descartable", "cantidad": 1},
        {"item": "Toalla húmeda", "cantidad": 2},
        {"item": "Guantes descartables", "cantidad": 1},
    ],
    "curación": [
        {"item": "Gasas estériles", "cantidad": 5},
        {"item": "Guantes estériles", "cantidad": 1},
        {"item": "Solución fisiológica 500ml", "cantidad": 1},
        {"item": "Apósito estéril", "cantidad": 1},
    ],
    "curacion": [
        {"item": "Gasas estériles", "cantidad": 5},
        {"item": "Guantes estériles", "cantidad": 1},
        {"item": "Solución fisiológica 500ml", "cantidad": 1},
        {"item": "Apósito estéril", "cantidad": 1},
    ],
    "curacion de herida": [
        {"item": "Gasas estériles", "cantidad": 5},
        {"item": "Guantes estériles", "cantidad": 1},
        {"item": "Solución fisiológica 500ml", "cantidad": 1},
        {"item": "Apósito estéril", "cantidad": 1},
        {"item": "Povidona iodada", "cantidad": 1},
    ],
    "herida": [
        {"item": "Gasas estériles", "cantidad": 5},
        {"item": "Apósito estéril", "cantidad": 1},
    ],
    "sondaje": [
        {"item": "Sonda vesical", "cantidad": 1},
        {"item": "Guantes estériles", "cantidad": 1},
        {"item": "Lubricante urológico", "cantidad": 1},
        {"item": "Bolsa colectora", "cantidad": 1},
    ],
    "sonda vesical": [
        {"item": "Sonda vesical", "cantidad": 1},
        {"item": "Guantes estériles", "cantidad": 1},
        {"item": "Lubricante urológico", "cantidad": 1},
        {"item": "Bolsa colectora", "cantidad": 1},
    ],
    "catéter": [
        {"item": "Catéter EV", "cantidad": 1},
        {"item": "Apósito transparente", "cantidad": 1},
        {"item": "Guantes descartables", "cantidad": 1},
    ],
    "cateter": [
        {"item": "Catéter EV", "cantidad": 1},
        {"item": "Apósito transparente", "cantidad": 1},
        {"item": "Guantes descartables", "cantidad": 1},
    ],
    "venoclisis": [
        {"item": "Equipo de venoclisis", "cantidad": 1},
    ],
    "inyectable im": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja IM", "cantidad": 1},
    ],
    "inyectable ev": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja EV", "cantidad": 1},
    ],
    "inyectable sc": [
        {"item": "Jeringa 1ml", "cantidad": 1},
        {"item": "Aguja SC", "cantidad": 1},
    ],
    "inyección": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja IM/EV", "cantidad": 1},
    ],
    "inyeccion": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja IM/EV", "cantidad": 1},
    ],
    "gasas": [
        {"item": "Gasas estériles", "cantidad": 5},
    ],
    "apósito": [
        {"item": "Apósito estéril", "cantidad": 1},
    ],
    "extraccion de sangre": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja EV", "cantidad": 1},
        {"item": "Tubo de extracción", "cantidad": 1},
    ],
    "extracción de sangre": [
        {"item": "Jeringa 5ml", "cantidad": 1},
        {"item": "Aguja EV", "cantidad": 1},
        {"item": "Tubo de extracción", "cantidad": 1},
    ],
    "glucemia": [
        {"item": "Tira reactiva glucemia", "cantidad": 1},
        {"item": "Lanceta", "cantidad": 1},
    ],
    "control de glucemia": [
        {"item": "Tira reactiva glucemia", "cantidad": 1},
        {"item": "Lanceta", "cantidad": 1},
    ],
    "nebulizacion": [
        {"item": "Equipo de nebulización", "cantidad": 1},
    ],
    "nebulización": [
        {"item": "Equipo de nebulización", "cantidad": 1},
    ],
    "oxigeno": [
        {"item": "Cánula nasal", "cantidad": 1},
    ],
    "oxígeno": [
        {"item": "Cánula nasal", "cantidad": 1},
    ],
}


# ---------------------------------------------------------------------------
# Helpers de búsqueda
# ---------------------------------------------------------------------------

def _buscar_en_mapa(texto: str, mapa: MapType) -> List[Dict[str, int | str]]:
    """Busca coincidencias de `texto` en `mapa` (substring, case-insensitive).

    Devuelve la lista de insumos de la primera clave que coincida.
    Si hay múltiples coincidencias, prioriza la clave más larga (más específica).
    """
    t = texto.lower().strip()
    candidatos = []
    for clave, insumos in mapa.items():
        if clave in t:
            candidatos.append((len(clave), clave, insumos))
    if not candidatos:
        return []
    # Prioriza la clave más larga (más específica)
    candidatos.sort(key=lambda x: -x[0])
    return candidatos[0][2]


def insumos_para_medicamento(nombre_med: str) -> List[Dict[str, int | str]]:
    """Retorna los insumos asociados a un medicamento."""
    return _buscar_en_mapa(nombre_med, MEDICAMENTO_A_INSUMOS)


def insumos_para_procedimiento(texto_nota: str) -> List[Dict[str, int | str]]:
    """Retorna los insumos asociados a un procedimiento detectado en la nota."""
    return _buscar_en_mapa(texto_nota, PROCEDIMIENTO_A_INSUMOS)


# ---------------------------------------------------------------------------
# Deducción en inventario (usado desde MAR y evolución)
# ---------------------------------------------------------------------------

def deducir_insumos(
    insumos: List[Dict[str, int | str]],
    paciente_sel: str,
    mi_empresa: str,
    user: dict,
    *,
    motivo: str = "Automático",
) -> List[str]:
    """Deduce una lista de insumos del inventario (local y SQL).

    Para cada insumo en la lista:
      - Lo registra en ``consumos_db``.
      - Lo busca en ``inventario_db`` (fuzzy match) y descuenta stock.
      - Si no existe, lo auto-crea con stock 0 (flag ``auto_creado``).
      - Sincroniza con SQL (si hay conexión).

    Args:
        insumos: Lista de dicts con ``item`` y ``cantidad``.
        paciente_sel: ``"Nombre - DNI"`` del paciente.
        mi_empresa: Nombre de la empresa actual.
        user: Dict del usuario logueado.
        motivo: Texto descriptivo para el log/auditoría.

    Returns:
        Lista de nombres de insumos que fueron creados automáticamente (stock 0).
    """
    import streamlit as st

    from core.app_logging import log_event
    from core.alert_toasts import queue_toast
    from core.database import _trim_db_list
    from core.utils import ahora

    auto_creados: List[str] = []
    st.session_state.setdefault("consumos_db", [])
    st.session_state.setdefault("_med_inventario_cache", {})

    for ins in insumos:
        nombre = str(ins.get("item", "")).strip()
        cantidad = int(ins.get("cantidad", 1))
        if not nombre:
            continue

        # 1 — Registrar consumo
        st.session_state["consumos_db"].append({
            "paciente": paciente_sel,
            "insumo": nombre,
            "cantidad": cantidad,
            "fecha": ahora().strftime("%d/%m/%Y %H:%M"),
            "firma": user.get("nombre", "Sistema"),
            "empresa": mi_empresa,
            "motivo": motivo,
        })

        # 2 — Buscar en inventario y descontar
        ins_key = nombre.lower().strip()
        inv_db = st.session_state.get("inventario_db", [])
        cache = st.session_state["_med_inventario_cache"]

        # 2a — Cache
        cache_key = (ins_key, mi_empresa)
        cached_key = cache.get(cache_key)
        encontrado = False

        if cached_key:
            for item in inv_db:
                if item.get("item", "").lower().strip() == cached_key and item.get("empresa") == mi_empresa:
                    item["stock"] = max(0, int(item.get("stock") or 0) - cantidad)
                    log_event("insumos", f"deducido_cache:{nombre}:{cantidad}")
                    encontrado = True
                    break
            if not encontrado:
                cache.pop(cache_key, None)

        # 2b — Fuzzy scan
        if not encontrado:
            for item in inv_db:
                item_key = item.get("item", "").lower().strip()
                if item.get("empresa") != mi_empresa:
                    continue
                if item_key == ins_key or ins_key in item_key or item_key in ins_key:
                    item["stock"] = max(0, int(item.get("stock") or 0) - cantidad)
                    log_event("insumos", f"deducido_scan:{nombre}:{cantidad}")
                    cache[cache_key] = item_key
                    encontrado = True
                    break

        # 2c — Auto-crear si no existe
        if not encontrado:
            st.session_state.setdefault("inventario_db", [])
            st.session_state["inventario_db"].append({
                "item": nombre,
                "stock": 0,
                "empresa": mi_empresa,
                "auto_creado_por_mar": True,
            })
            cache[cache_key] = ins_key
            log_event("insumos", f"auto_creado:{nombre}")
            auto_creados.append(nombre)

    _trim_db_list("consumos_db", 1000)
    _trim_db_list("inventario_db", 1000)

    # 3 — Sincronizar con SQL
    try:
        from core.db_sql import get_inventario_item_by_name, insert_inventario_movimiento
        from core.nextgen_sync import _obtener_uuid_empresa, _obtener_uuid_paciente

        partes = paciente_sel.split(" - ")
        if len(partes) > 1:
            dni = partes[1].strip()
            empresa_uuid = _obtener_uuid_empresa(mi_empresa)
            if empresa_uuid:
                pac_uuid = _obtener_uuid_paciente(dni, empresa_uuid)
                for ins in insumos:
                    nombre = str(ins.get("item", "")).strip()
                    cantidad = int(ins.get("cantidad", 1))
                    item = get_inventario_item_by_name(empresa_uuid, nombre)
                    if item:
                        stock_actual = int(item.get("stock_actual", 0))
                        insert_inventario_movimiento({
                            "inventario_id": item["id"],
                            "paciente_id": pac_uuid,
                            "empresa_id": empresa_uuid,
                            "tipo_movimiento": "Salida",
                            "cantidad": cantidad,
                            "stock_anterior": stock_actual,
                            "stock_nuevo": max(0, stock_actual - cantidad),
                            "motivo": f"{motivo}: {nombre} - {paciente_sel}",
                            "referencia_documento": "MAR_AUTO",
                        })
    except Exception as e:
        log_event("insumos", f"error_sql:{type(e).__name__}:{str(e)[:80]}")

    if auto_creados:
        queue_toast(
            f"📦 Insumos auto-creados en inventario: {', '.join(auto_creados)}. "
            "Ajustá el stock desde Inventario."
        )

    return auto_creados


def auto_facturar_servicio(
    paciente_sel: str,
    mi_empresa: str,
    user: dict,
    nombre_servicio: str,
    *,
    monto: float = 0,
) -> bool:
    """Crea automáticamente un item de facturación por un servicio prestado.

    Args:
        nombre_servicio: Descripción del servicio ("Hiocina 20mg EV",
                         "Curación de herida", etc.).
        monto: Importe sugerido (0 si el usuario lo fija después).

    Returns:
        True si se creó el item, False si ya existía uno similar en el mismo día.
    """
    import streamlit as st

    from core.database import _trim_db_list
    from core.utils import ahora

    hoy = ahora().strftime("%d/%m/%Y")

    # Evitar duplicados: mismo paciente + mismo servicio + misma fecha
    for item in st.session_state.get("facturacion_db", []):
        if (
            item.get("paciente") == paciente_sel
            and item.get("serv", "").strip().lower() == nombre_servicio.strip().lower()
            and item.get("fecha", "").startswith(hoy)
        ):
            return False

    st.session_state.setdefault("facturacion_db", [])
    st.session_state["facturacion_db"].append({
        "paciente": paciente_sel,
        "serv": nombre_servicio.strip(),
        "monto": monto,
        "metodo": "Pendiente",
        "estado": "Pendiente / A Facturar",
        "fecha": ahora().strftime("%d/%m/%Y %H:%M"),
        "empresa": mi_empresa,
        "operador": user.get("nombre", "Sistema"),
        "operador_dni": user.get("dni", "S/D"),
    })
    _trim_db_list("facturacion_db", 500)
    return True


def sugerencias_reposicion(mi_empresa: str) -> List[Dict[str, int | str]]:
    """Retorna lista de items de inventario cuyo stock está por debajo del mínimo.

    Cada item incluye ``item``, ``stock``, ``stock_minimo`` y ``sugerido``
    (cantidad recomendada a reponer).

    Si un item no tiene ``stock_minimo`` definido, se usa 10 como valor por
    defecto para el umbral de alerta.

    Útil para mostrar en Dashboard o generar órdenes de compra.
    """
    import streamlit as st

    UMBRAL_DEFECTO = 10
    sugerencias: List[Dict[str, int | str]] = []
    for item in st.session_state.get("inventario_db", []):
        if item.get("empresa") != mi_empresa:
            continue
        stock = int(item.get("stock") or 0)
        sm = int(item.get("stock_minimo") or 0)
        umbral = sm if sm > 0 else UMBRAL_DEFECTO
        if stock <= umbral:
            sugerencias.append({
                "item": item.get("item", ""),
                "stock": stock,
                "stock_minimo": sm,
                "sugerido": max(1, (umbral * 2) - stock),
            })
    return sugerencias
