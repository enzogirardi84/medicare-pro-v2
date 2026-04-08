import json
import urllib.request
from io import BytesIO
from datetime import datetime
from pathlib import Path

import pytz
import streamlit as st
from PIL import Image

# Zona horaria fija para Argentina
ARG_TZ = pytz.timezone("America/Argentina/Buenos_Aires")
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


DEFAULT_ADMIN_USER = {
    "pass": "37108100",
    "rol": "SuperAdmin",
    "nombre": "Enzo Girardi",
    "empresa": "SISTEMAS E.G.",
    "matricula": "M.P 21947",
    "dni": "37108100",
    "titulo": "Director de Sistemas",
    "estado": "Activo",
    "pin": "1234",
}


def ahora():
    return datetime.now(ARG_TZ)


def registrar_auditoria_legal(tipo_evento, paciente, accion, actor, matricula="", detalle="", referencia="", extra=None):
    extra = extra or {}
    st.session_state.setdefault("auditoria_legal_db", [])
    st.session_state["auditoria_legal_db"].append(
        {
            "fecha": ahora().strftime("%d/%m/%Y %H:%M:%S"),
            "tipo_evento": tipo_evento,
            "paciente": paciente,
            "accion": accion,
            "actor": actor,
            "matricula": matricula,
            "detalle": detalle,
            "referencia": referencia,
            **extra,
        }
    )


def asegurar_usuarios_base():
    st.session_state.setdefault("usuarios_db", {})
    if "admin" not in st.session_state["usuarios_db"]:
        st.session_state["usuarios_db"]["admin"] = DEFAULT_ADMIN_USER.copy()
    else:
        combinado = DEFAULT_ADMIN_USER.copy()
        combinado.update(st.session_state["usuarios_db"]["admin"])
        st.session_state["usuarios_db"]["admin"] = combinado


@st.cache_data(show_spinner=False)
def cargar_texto_asset(nombre_archivo):
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
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.thumbnail(max_size)
            salida = BytesIO()
            img.save(salida, format="JPEG", optimize=True, quality=quality)
            return salida.getvalue(), "jpg"
    except Exception:
        return image_bytes, None


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
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=hide_index,
            height=height - 24,
        )


def obtener_direccion_real(lat, lon):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
        req = urllib.request.Request(url, headers={"User-Agent": "MediCareProApp/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            display_name = data.get("display_name", "Direccion no encontrada")
            partes = display_name.split(", ")
            if len(partes) > 3:
                return ", ".join(partes[:3])
            return display_name
    except Exception:
        return "Direccion exacta no disponible (solo coordenadas)"


def inicializar_db_state(db):
    if "db_inicializada" not in st.session_state:
        claves_base = {
            "usuarios_db": {
                "admin": DEFAULT_ADMIN_USER.copy()
            },
            "pacientes_db": [],
            "detalles_pacientes_db": {},
            "vitales_db": [],
            "indicaciones_db": [],
            "turnos_db": [],
            "evoluciones_db": [],
            "facturacion_db": [],
            "logs_db": [],
            "balance_db": [],
            "pediatria_db": [],
            "fotos_heridas_db": [],
            "agenda_db": [],
            "checkin_db": [],
            "inventario_db": [],
            "consumos_db": [],
            "nomenclador_db": [],
            "firmas_tactiles_db": [],
            "reportes_diarios_db": [],
            "estudios_db": [],
            "administracion_med_db": [],
            "consentimientos_db": [],
            "emergencias_db": [],
            "cuidados_enfermeria_db": [],
            "escalas_clinicas_db": [],
            "auditoria_legal_db": [],
        }
        if db:
            for k, v in db.items():
                st.session_state[k] = v
            for k, v in claves_base.items():
                if k not in st.session_state:
                    st.session_state[k] = v
        else:
            for k, v in claves_base.items():
                st.session_state[k] = v
        asegurar_usuarios_base()
        st.session_state["db_inicializada"] = True
