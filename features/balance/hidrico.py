"""Cálculos de balance hídrico sin dependencias de Streamlit."""


def totales_balance_hidrico_ml(
    *,
    i_oral: int | float = 0,
    i_par: int | float = 0,
    e_orina: int | float = 0,
    e_dren: int | float = 0,
    e_perd: int | float = 0,
) -> tuple[int, int, int]:
    """Devuelve (ingresos_ml, egresos_ml, balance_ml)."""
    ing = int(i_oral or 0) + int(i_par or 0)
    egr = int(e_orina or 0) + int(e_dren or 0) + int(e_perd or 0)
    return ing, egr, ing - egr


def formato_shift_ml(val: int | float) -> str:
    """Texto corto para tablas y mensajes (+/- ml)."""
    v = int(val)
    if v > 0:
        return f"+{v} ml"
    if v < 0:
        return f"{v} ml"
    return "0 ml"
