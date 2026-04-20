"""Helpers de UI: imagen, firma, archivos, dataframe, assets, geolocalización.

Extraído de core/utils.py.
"""
import base64
import json
from io import BytesIO
from pathlib import Path

import streamlit as st
from PIL import Image, ImageOps

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
MAX_RAW_IMAGE_UPLOAD_MB = 20


def _texto_normalizado(valor):
    import unicodedata
    t = unicodedata.normalize("NFKC", str(valor or "").strip()).lower()
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def modo_celular_viejo_activo(session_state=None):
    SESSION_KEY = "modo_celular_viejo"
    state = session_state if session_state is not None else st.session_state
    try:
        if state is not st.session_state:
            return bool(state.get(SESSION_KEY, False))
        from core.ui_liviano import datos_compactos_por_cliente_sugerido
        return datos_compactos_por_cliente_sugerido()
    except Exception:
        try:
            return bool(state.get(SESSION_KEY, False))
        except Exception:
            return False


def valor_por_modo_liviano(valor_normal, valor_liviano, session_state=None):
    return valor_liviano if modo_celular_viejo_activo(session_state) else valor_normal


@st.cache_data(show_spinner=False)
def cargar_texto_asset(nombre_archivo, _mtime: float = 0.0):
    ruta = ASSETS_DIR / nombre_archivo
    return ruta.read_text(encoding="utf-8")


@st.cache_data(show_spinner=False)
def cargar_json_asset(nombre_archivo):
    ruta = ASSETS_DIR / nombre_archivo
    with ruta.open("r", encoding="utf-8") as archivo:
        return json.load(archivo)


def optimizar_imagen_bytes(image_bytes, max_size=(1280, 1280), quality=75):
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.thumbnail(max_size)
            salida = BytesIO()
            img.save(salida, format="JPEG", optimize=True, quality=quality)
            return salida.getvalue(), "jpg"
    except Exception:
        return image_bytes, None


def _bytes_legibles(cantidad_bytes):
    try:
        cantidad = float(cantidad_bytes or 0)
    except Exception:
        cantidad = 0.0
    if cantidad >= 1024 * 1024:
        return f"{cantidad / (1024 * 1024):.1f} MB"
    if cantidad >= 1024:
        return f"{cantidad / 1024:.0f} KB"
    return f"{int(cantidad)} B"


def limite_archivo_mb(tipo="imagen", session_state=None):
    tipo_normalizado = _texto_normalizado(tipo)
    modo_liviano = modo_celular_viejo_activo(session_state)
    limites = {"imagen": 4 if modo_liviano else 8, "pdf": 6 if modo_liviano else 12, "firma": 2 if modo_liviano else 3}
    return limites.get(tipo_normalizado, 4 if modo_liviano else 8)


def validar_archivo_bytes(file_bytes, tipo="imagen", nombre_archivo="archivo", session_state=None):
    contenido = bytes(file_bytes or b"")
    if not contenido:
        return False, f"No se pudo leer {nombre_archivo}."
    tipo_normalizado = _texto_normalizado(tipo)
    if tipo_normalizado == "imagen":
        max_raw_bytes = MAX_RAW_IMAGE_UPLOAD_MB * 1024 * 1024
        if len(contenido) > max_raw_bytes:
            return (False, f"{nombre_archivo} pesa {_bytes_legibles(len(contenido))}. Para evitar bloqueos, sube una imagen de hasta {MAX_RAW_IMAGE_UPLOAD_MB} MB.")
    limite_mb = limite_archivo_mb(tipo_normalizado, session_state)
    limite_bytes = limite_mb * 1024 * 1024
    if len(contenido) > limite_bytes and tipo_normalizado != "imagen":
        return (False, f"{nombre_archivo} pesa {_bytes_legibles(len(contenido))}. El limite para {tipo_normalizado} es {limite_mb} MB.")
    return True, ""


def preparar_imagen_clinica_bytes(image_bytes, nombre_archivo="imagen.jpg", max_size=(1280, 1280), quality=75, session_state=None):
    ok, error = validar_archivo_bytes(image_bytes, tipo="imagen", nombre_archivo=nombre_archivo, session_state=session_state)
    if not ok:
        return {"ok": False, "error": error}
    modo_liviano = modo_celular_viejo_activo(session_state)
    max_size_final = (960, 960) if modo_liviano else max_size
    calidad_final = min(quality, 62) if modo_liviano else quality
    contenido, extension = optimizar_imagen_bytes(image_bytes, max_size=max_size_final, quality=calidad_final)
    ok, error = validar_archivo_bytes(contenido, tipo="imagen", nombre_archivo=nombre_archivo, session_state=session_state)
    if not ok:
        return {"ok": False, "error": error}
    return {
        "ok": True, "bytes": contenido, "extension": extension or "jpg",
        "mime": "image/jpeg", "name": nombre_archivo,
        "tipo_archivo": "imagen", "size_bytes": len(contenido),
    }


def obtener_config_firma(key_prefix, default_liviano=True):
    modo_liviano = st.checkbox(
        "Modo firma liviana (recomendado en celulares viejos)",
        value=default_liviano,
        key=f"{key_prefix}_firma_liviana",
    )
    if modo_liviano:
        st.caption("Reduce el tamano del lienzo y las herramientas para que firme mas fluido.")
        return {"height": 96, "width": 280, "stroke_width": 1.8, "display_toolbar": False}
    return {"height": 140, "width": 420, "stroke_width": 2.5, "display_toolbar": True}


def firma_a_base64(canvas_image_data=None, uploaded_file=None):
    try:
        if uploaded_file is not None:
            firma_bytes, _ = optimizar_imagen_bytes(uploaded_file.getvalue(), max_size=(700, 220), quality=55)
            return base64.b64encode(firma_bytes).decode("utf-8")
        if canvas_image_data is not None:
            img = Image.fromarray(canvas_image_data.astype("uint8"), "RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            bg.thumbnail((700, 220))
            buf = BytesIO()
            bg.save(buf, format="JPEG", optimize=True, quality=55)
            return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        return ""
    return ""


def seleccionar_limite_registros(label, total, key, default=30, opciones=(10, 20, 30, 50, 100, 200, 500)):
    if total <= 0:
        return 0
    if total <= min(opciones):
        st.caption(f"Mostrando {total} registro(s).")
        return total
    opciones_validas = sorted({valor for valor in opciones if valor < total})
    if total not in opciones_validas:
        opciones_validas.append(total)
    valor_default = min(total, default)
    if valor_default not in opciones_validas:
        opciones_validas.append(valor_default)
        opciones_validas = sorted(set(opciones_validas))
    return st.selectbox(label, opciones_validas, index=opciones_validas.index(valor_default), key=key)


def mostrar_dataframe_con_scroll(df, height=420, border=True, hide_index=True):
    with st.container(height=height, border=border):
        st.dataframe(df, use_container_width=True, hide_index=hide_index, height=height - 24)


def obtener_direccion_real(lat, lon):
    from services.nominatim import reverse_geocode_short_label
    return reverse_geocode_short_label(lat, lon)
