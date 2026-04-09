import base64
import json
import urllib.request
from datetime import datetime
from io import BytesIO
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

ROLE_LEVELS = {
    "Operativo": 1,
    "Administrativo": 1,
    "Medico": 1,
    "Enfermeria": 1,
    "Coordinador": 2,
    "Auditoria": 2,
    "SuperAdmin": 3,
}


ACTION_ROLE_RULES = {
    "recetas_prescribir": ["Medico"],
    "recetas_cargar_papel": ["Operativo", "Enfermeria", "Medico"],
    "recetas_registrar_dosis": ["Operativo", "Enfermeria", "Medico"],
    "recetas_cambiar_estado": ["Medico"],
    "pdf_exportar_historia": ["Operativo", "Enfermeria", "Medico", "Administrativo", "Auditoria"],
    "pdf_exportar_excel": ["Administrativo", "Auditoria"],
    "pdf_exportar_respaldo": ["Operativo", "Enfermeria", "Medico", "Administrativo", "Auditoria"],
    "pdf_guardar_consentimiento": ["Operativo", "Enfermeria", "Medico"],
    "pdf_descargar_consentimiento": ["Operativo", "Enfermeria", "Medico", "Administrativo", "Auditoria"],
    "evolucion_registrar": ["Operativo", "Enfermeria", "Medico"],
    "evolucion_borrar": ["Medico"],
    "estudios_registrar": ["Operativo", "Enfermeria", "Medico"],
    "estudios_borrar": ["Medico"],
    "equipo_crear_usuario": ["Coordinador"],
    "equipo_cambiar_estado": ["Coordinador"],
    "equipo_eliminar_usuario": ["SuperAdmin"],
}


def tiene_permiso(rol_actual, roles_permitidos=None):
    if rol_actual in {"SuperAdmin", "Coordinador"}:
        return True
    if not roles_permitidos:
        return True
    if rol_actual in roles_permitidos:
        return True
    nivel_actual = ROLE_LEVELS.get(rol_actual, 0)
    niveles_permitidos = [ROLE_LEVELS.get(rol, 0) for rol in roles_permitidos]
    return bool(niveles_permitidos) and nivel_actual > max(niveles_permitidos)


def puede_accion(rol_actual, accion, roles_extra=None):
    roles_base = list(ACTION_ROLE_RULES.get(accion, []))
    if roles_extra:
        roles_base.extend(roles_extra)
    return tiene_permiso(rol_actual, roles_base)


def descripcion_acceso_rol(rol_actual):
    descripciones = {
        "SuperAdmin": "Acceso de gestion, control y trazabilidad completa.",
        "Coordinador": "Acceso total a la operacion, horarios, auditoria y control del equipo.",
        "Medico": "Acceso clinico ampliado: prescripcion, evolucion y decisiones terapeuticas.",
        "Enfermeria": "Acceso asistencial: registro clinico, indicaciones y seguimiento diario del paciente.",
        "Operativo": "Acceso asistencial limitado al registro clinico del paciente.",
        "Administrativo": "Acceso administrativo y operativo sin edicion clinica sensible.",
        "Auditoria": "Acceso de control, revision y trazabilidad legal.",
    }
    return descripciones.get(rol_actual, "Acceso configurado segun el rol asignado.")


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


def obtener_alertas_clinicas(session_state, paciente_sel):
    if not paciente_sel:
        return []

    detalles = session_state.get("detalles_pacientes_db", {}).get(paciente_sel, {})
    alertas = []

    alergias = str(detalles.get("alergias", "") or "").strip()
    if alergias:
        alertas.append(
            {
                "nivel": "critica",
                "titulo": "Alergias registradas",
                "detalle": alergias,
            }
        )

    patologias = str(detalles.get("patologias", "") or "").strip()
    if patologias:
        alertas.append(
            {
                "nivel": "media",
                "titulo": "Patologias y riesgos",
                "detalle": patologias,
            }
        )

    consentimientos = [x for x in session_state.get("consentimientos_db", []) if x.get("paciente") == paciente_sel]
    if not consentimientos:
        alertas.append(
            {
                "nivel": "alta",
                "titulo": "Consentimiento legal pendiente",
                "detalle": "Todavia no hay un consentimiento domiciliario firmado para este paciente.",
            }
        )

    vitales = [x for x in session_state.get("vitales_db", []) if x.get("paciente") == paciente_sel]
    if vitales:
        ultimo_vital = sorted(vitales, key=lambda x: parse_fecha_hora(x.get("fecha", "")))[-1]
        sat = _to_float(ultimo_vital.get("Sat"))
        temp = _to_float(ultimo_vital.get("Temp"))
        fc = _to_float(ultimo_vital.get("FC"))
        if sat is not None and sat < 92:
            alertas.append(
                {
                    "nivel": "critica",
                    "titulo": "Desaturacion reciente",
                    "detalle": f"Ultimo SatO2 registrado: {sat:.0f}% | {ultimo_vital.get('fecha', 'S/D')}",
                }
            )
        if temp is not None and temp >= 38:
            alertas.append(
                {
                    "nivel": "alta",
                    "titulo": "Fiebre registrada",
                    "detalle": f"Ultima temperatura: {temp:.1f} C | {ultimo_vital.get('fecha', 'S/D')}",
                }
            )
        if fc is not None and (fc > 110 or fc < 50):
            alertas.append(
                {
                    "nivel": "alta",
                    "titulo": "Frecuencia cardiaca fuera de rango",
                    "detalle": f"Ultima FC: {fc:.0f} lpm | {ultimo_vital.get('fecha', 'S/D')}",
                }
            )

    for indicacion in reversed(session_state.get("indicaciones_db", [])):
        if indicacion.get("paciente") != paciente_sel:
            continue
        estado = str(indicacion.get("estado_receta") or indicacion.get("estado_clinico") or "Activa").strip()
        if estado in {"Suspendida", "Modificada"}:
            fecha_estado = indicacion.get("fecha_estado") or indicacion.get("fecha_suspension") or indicacion.get("fecha", "")
            alertas.append(
                {
                    "nivel": "alta" if estado == "Suspendida" else "media",
                    "titulo": f"Medicacion {estado.lower()}",
                    "detalle": (
                        f"{indicacion.get('med', 'Sin detalle')} | {fecha_estado} | "
                        f"{indicacion.get('profesional_estado', indicacion.get('medico_nombre', 'Sin profesional'))}"
                    ),
                }
            )

    return alertas[:5]


def _to_float(value):
    try:
        if value in ("", None):
            return None
        return float(value)
    except Exception:
        return None


def parse_fecha_hora(fecha_str):
    formatos = ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y")
    for formato in formatos:
        try:
            return datetime.strptime(str(fecha_str), formato)
        except Exception:
            continue
    return datetime.min


def parse_agenda_datetime(item):
    fecha = str(item.get("fecha", "")).strip()
    hora = str(item.get("hora", "")).strip() or "00:00"
    combinado = f"{fecha} {hora}"
    return parse_fecha_hora(combinado)


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


def obtener_config_firma(key_prefix, default_liviano=True):
    modo_liviano = st.checkbox(
        "Modo firma liviana (recomendado en celulares viejos)",
        value=default_liviano,
        key=f"{key_prefix}_firma_liviana",
    )
    if modo_liviano:
        st.caption("Reduce el tamano del lienzo y las herramientas para que firme mas fluido.")
        return {
            "height": 96,
            "width": 280,
            "stroke_width": 1.8,
            "display_toolbar": False,
        }
    return {
        "height": 140,
        "width": 420,
        "stroke_width": 2.5,
        "display_toolbar": True,
    }


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
            "usuarios_db": {"admin": DEFAULT_ADMIN_USER.copy()},
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
            "profesionales_red_db": [],
            "solicitudes_servicios_db": [],
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
