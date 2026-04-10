import base64
import json
import re
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
ROL_ADMIN_TOTAL = {"superadmin", "admin", "coordinador"}


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
    rol_normalizado = str(rol_actual or "").strip().lower()
    if rol_normalizado in ROL_ADMIN_TOTAL:
        return True
    if not roles_permitidos:
        return True
    roles_normalizados = {str(rol).strip().lower() for rol in roles_permitidos if rol}
    return rol_normalizado in roles_normalizados


def puede_accion(rol_actual, accion, roles_extra=None):
    roles_base = list(ACTION_ROLE_RULES.get(accion, []))
    if roles_extra:
        roles_base.extend(roles_extra)
    return tiene_permiso(rol_actual, roles_base)


def descripcion_acceso_rol(rol_actual):
    rol_normalizado = str(rol_actual or "").strip().lower()
    if rol_normalizado in {"superadmin", "admin"}:
        return "Acceso de gestion, control y trazabilidad completa."
    if rol_normalizado == "coordinador":
        return "Acceso total a la operacion, horarios, auditoria y control del equipo."
    descripciones = {
        "Medico": "Acceso clinico ampliado: prescripcion, evolucion y decisiones terapeuticas.",
        "Enfermeria": "Acceso asistencial: registro clinico, indicaciones y seguimiento diario del paciente.",
        "Operativo": "Acceso asistencial limitado al registro clinico del paciente.",
        "Administrativo": "Acceso administrativo y operativo sin edicion clinica sensible.",
        "Auditoria": "Acceso de control, revision y trazabilidad legal.",
    }
    return descripciones.get(rol_actual, "Acceso configurado segun el rol asignado.")


def es_control_total(rol_actual):
    return str(rol_actual or "").strip().lower() in ROL_ADMIN_TOTAL


def obtener_modulos_permitidos(rol_actual):
    menu_base = [
        "Visitas y Agenda",
        "Clinica",
        "Pediatria",
        "Evolucion",
        "Estudios",
        "Materiales",
        "Recetas",
        "Balance",
        "Emergencias y Ambulancia",
        "Escalas Clinicas",
        "Historial",
        "PDF",
        "Telemedicina",
    ]
    menu_admin_total = [
        "Visitas y Agenda",
        "Dashboard",
        "Admision",
        "Clinica",
        "Pediatria",
        "Evolucion",
        "Estudios",
        "Materiales",
        "Recetas",
        "Balance",
        "Inventario",
        "Caja",
        "Emergencias y Ambulancia",
        "Red de Profesionales",
        "Escalas Clinicas",
        "Historial",
        "PDF",
        "Telemedicina",
        "Cierre Diario",
        "Mi Equipo",
        "Asistencia en Vivo",
        "RRHH y Fichajes",
        "Auditoria",
        "Auditoria Legal",
    ]
    menu_administrativo = [
        "Dashboard",
        "Admision",
        "Inventario",
        "Caja",
        "Red de Profesionales",
        "Cierre Diario",
        "Mi Equipo",
        "Asistencia en Vivo",
        "RRHH y Fichajes",
        "Auditoria",
        "Auditoria Legal",
    ]
    rol_normalizado = str(rol_actual or "").strip().lower()
    if rol_normalizado in ROL_ADMIN_TOTAL:
        return menu_admin_total
    if rol_normalizado == "administrativo":
        return menu_administrativo
    return menu_base


def filtrar_registros_empresa(items, mi_empresa, rol_actual, empresa_key="empresa"):
    if es_control_total(rol_actual):
        return list(items or [])

    empresa_actual = str(mi_empresa or "").strip().lower()
    filtrados = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        empresa_item = str(item.get(empresa_key, "") or "").strip().lower()
        if empresa_item == empresa_actual:
            filtrados.append(item)
    return filtrados


def compactar_etiqueta_paciente(nombre, estado):
    nombre = str(nombre or "").strip()
    sufijo = " [ALTA]" if estado == "De Alta" else ""
    limite = 34 if sufijo else 40
    if len(nombre) > limite:
        nombre = f"{nombre[:limite - 3].rstrip()}..."
    return f"{nombre}{sufijo}"


def obtener_pacientes_visibles(session_state, mi_empresa, rol_actual, incluir_altas=False, busqueda=""):
    busqueda_norm = str(busqueda or "").strip().lower()
    detalles_db = session_state.get("detalles_pacientes_db", {})
    pacientes_visibles = []

    for paciente in session_state.get("pacientes_db", []):
        detalles = detalles_db.get(paciente, {})
        if not es_control_total(rol_actual):
            empresa_paciente = str(detalles.get("empresa", "") or "").strip().lower()
            empresa_actual = str(mi_empresa or "").strip().lower()
            if empresa_paciente != empresa_actual:
                continue

        estado = detalles.get("estado", "Activo")
        if estado != "Activo" and not incluir_altas:
            continue

        dni = str(detalles.get("dni", "") or "")
        obra_social = str(detalles.get("obra_social", "") or "")
        empresa = str(detalles.get("empresa", "") or "")
        etiqueta = compactar_etiqueta_paciente(paciente, estado)

        searchable = " ".join(
            [
                str(paciente),
                etiqueta,
                dni,
                obra_social,
                empresa,
                str(estado),
            ]
        ).lower()
        if busqueda_norm and busqueda_norm not in searchable:
            continue

        pacientes_visibles.append(
            (paciente, etiqueta, dni, obra_social, estado, empresa)
        )

    pacientes_visibles.sort(key=lambda item: (item[1].lower(), item[0].lower()))
    return pacientes_visibles


def ahora():
    return datetime.now(ARG_TZ)


def registrar_auditoria_legal(tipo_evento, paciente, accion, actor, matricula="", detalle="", referencia="", extra=None, empresa=None):
    extra = extra or {}
    if empresa is None:
        detalles = st.session_state.get("detalles_pacientes_db", {}).get(paciente, {})
        empresa = detalles.get("empresa") or st.session_state.get("user", {}).get("empresa", "")
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
            "empresa": empresa,
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
            return datetime.strptime(str(fecha_str), formato)
        except Exception:
            continue
    return datetime.min


def parse_agenda_datetime(item):
    fecha_hora_programada = str(item.get("fecha_hora_programada", "")).strip()
    if fecha_hora_programada:
        dt_programado = parse_fecha_hora(fecha_hora_programada)
        if dt_programado != datetime.min:
            return dt_programado

    fecha = str(item.get("fecha_programada", "") or item.get("fecha", "")).strip()
    hora = normalizar_hora_texto(item.get("hora", ""), default="00:00")
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


def normalizar_hora_texto(valor, default="08:00"):
    texto = str(valor or "").strip().lower()
    if not texto:
        return default

    texto = (
        texto.replace(" horas", "")
        .replace(" hora", "")
        .replace("hrs", "")
        .replace("hs.", "")
        .replace("hs", "")
        .replace("h", "")
        .strip()
    )

    match = re.search(r"^(\d{1,2})(?::(\d{1,2}))?$", texto)
    if not match:
        return default

    horas = int(match.group(1))
    minutos = int(match.group(2) or 0)
    if horas > 23 or minutos > 59:
        return default
    return f"{horas:02d}:{minutos:02d}"


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

    horarios_unicos = sorted(set(horarios), key=lambda x: (int(x.split(":")[0]), int(x.split(":")[1])))
    return horarios_unicos


def horarios_programados_desde_frecuencia(frecuencia, hora_inicio="08:00"):
    frecuencia = str(frecuencia or "").strip()
    hora_inicio = normalizar_hora_texto(hora_inicio)

    intervalos = {
        "Cada 1 hora": 1,
        "Cada 2 horas": 2,
        "Cada 4 horas": 4,
        "Cada 6 horas": 6,
        "Cada 8 horas": 8,
        "Cada 12 horas": 12,
        "Cada 24 horas": 24,
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
        plan.append(
            {
                "Paso": idx,
                "Hora sugerida": f"{hora_paso:02d}:{base_min:02d}",
                "Velocidad (ml/h)": velocidad,
            }
        )
    return plan


def extraer_frecuencia_desde_indicacion(indicacion):
    texto = str(indicacion or "")
    partes = [parte.strip() for parte in texto.split("|")]
    for parte in partes:
        if parte.startswith("Cada ") or parte == "Dosis unica" or parte == "Segun necesidad":
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


def obtener_profesionales_visibles(session_state, mi_empresa, rol_actual, roles_validos=None):
    empresa_actual = str(mi_empresa or "").strip().lower()
    visibles = []
    for username, data in session_state.get("usuarios_db", {}).items():
        if not isinstance(data, dict):
            continue
        rol_usuario = str(data.get("rol", "") or "").strip()
        if roles_validos and rol_usuario not in roles_validos:
            continue
        if not es_control_total(rol_actual):
            empresa_usuario = str(data.get("empresa", "") or "").strip().lower()
            if empresa_usuario != empresa_actual:
                continue
        visibles.append(
            {
                "username": username,
                **data,
            }
        )

    visibles.sort(key=lambda x: (str(x.get("nombre", "")).lower(), str(x.get("username", "")).lower()))
    return visibles


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
