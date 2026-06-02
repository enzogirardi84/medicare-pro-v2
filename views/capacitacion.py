"""Módulo de capacitación interactiva con guías, quizzes, certificado y progreso persistente."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import streamlit as st

from datetime import date

from core.app_logging import log_event

# ─── Ruta de progreso persistente ───────────────────────────────────────
RUTA_PROGRESO = Path(__file__).resolve().parent.parent / ".cache" / "progreso_capacitacion"


def _cargar_progreso() -> dict:
    if RUTA_PROGRESO.exists():
        try:
            return json.loads(RUTA_PROGRESO.read_text())
        except Exception:
            return {}
    return {}


def _guardar_progreso(data: dict) -> None:
    RUTA_PROGRESO.parent.mkdir(parents=True, exist_ok=True)
    RUTA_PROGRESO.write_text(json.dumps(data, indent=2, ensure_ascii=False))


# ─── Datos de capacitación ──────────────────────────────────────────────

CAPACITACION: dict[str, dict[str, Any]] = {
    "Dashboard": {
        "emoji": "📊", "categoria": "Primeros pasos",
        "desc": "Visión ejecutiva con KPIs, gráficos semanales, calendario heatmap y mapa de visitas GPS.",
        "tiempo": "5 min", "roles": ["todos"],
        "pasos": [
            "Al iniciar sesión, el Dashboard es tu pantalla principal.",
            "Los KPIs superiores muestran: pacientes activos, visitas del día, urgencias e ingresos del mes.",
            "El heatmap de actividad visualiza los últimos 30 días con picos de demanda.",
            "El mapa geográfico ubica cada visita del día con la posición del profesional.",
            "Usá el selector de fechas para filtrar el período a analizar.",
            "Los gráficos semanales evolucionan automáticamente con cada nueva carga de datos.",
        ],
        "tips": ["Los KPIs se actualizan en tiempo real.", "Podés hacer clic en cualquier gráfico para ver detalle."],
        "quiz": [
            {"p": "¿Qué muestra el heatmap del Dashboard?", "r": "La actividad de los últimos 30 días",
             "o": ["Los KPIs del mes", "La actividad de los últimos 30 días", "El mapa de visitas", "Los ingresos del día"]},
        ],
    },
    "Visitas y Agenda": {
        "emoji": "📅", "categoria": "Operaciones",
        "desc": "Planificación, asignación y fichado GPS de visitas domiciliarias.",
        "tiempo": "8 min", "roles": ["todos"],
        "pasos": [
            "Andá a Visitas y Agenda desde el menú lateral.",
            "Usá el calendario para seleccionar el día. Las visitas asignadas aparecen ordenadas.",
            "Creá una visita: seleccioná paciente, profesional, fecha, hora y tipo de prestación.",
            "El profesional recibe la visita en su móvil con dirección, datos del paciente y croquis.",
            "Al llegar, el profesional ficha con GPS: queda registrada ubicación y hora exacta.",
            "Al retirarse, ficha nuevamente. La duración total queda registrada.",
            "Completada la visita, puede cargar evolución, fotos, formularios y firmas.",
        ],
        "tips": ["Las visitas pendientes aparecen en azul, atrasadas en rojo, completadas en verde.",
                 "Podés reasignar una visita desde el menú de opciones de cada evento.",
                 "El reporte mensual de cumplimiento descargable muestra métricas por profesional."],
        "quiz": [
            {"p": "¿Qué datos registra automáticamente la fichada GPS?", "r": "Ubicación y hora exacta",
             "o": ["Solo la hora", "Ubicación y hora exacta", "Solo la ubicación", "El nombre del paciente"]},
        ],
    },
    "Historia Clínica": {
        "emoji": "📋", "categoria": "Gestión clínica",
        "desc": "Registro clínico digital completo: admisión, vitales, evolución, estudios y escalas.",
        "tiempo": "10 min", "roles": ["clinica"],
        "pasos": [
            "Seleccioná un paciente desde el selector superior y andá a Historia Clínica.",
            "La solapa 'Admisión' contiene datos filiatorios, contacto y obra social.",
            "En 'Evolución' se carga el registro diario con texto libre y signos vitales.",
            "Las 'Escalas Clínicas' permiten evaluar riesgo de úlceras, dolor, caídas y más.",
            "Los 'Estudios' agrupan resultados de laboratorio e imágenes.",
            "El 'Balance' hídrico y 'Percentilo' pediátrico están disponibles según el paciente.",
            "Cada cambio queda registrado en la auditoría con fecha, usuario y detalle.",
        ],
        "tips": ["Todos los cambios tienen trazabilidad legal.",
                 "Podés generar un PDF ejecutivo desde el botón 'Exportar'.",
                 "Buscá pacientes por nombre, DNI o número de afiliado."],
        "quiz": [
            {"p": "¿Dónde se cargan los signos vitales del paciente?", "r": "En la solapa Evolución",
             "o": ["En la solapa Admisión", "En la solapa Evolución", "En Estudios", "En Dashboard"]},
        ],
    },
    "Recetas": {
        "emoji": "💊", "categoria": "Gestión clínica",
        "desc": "Prescripción, administración y control de medicamentos con alertas de interacciones.",
        "tiempo": "7 min", "roles": ["clinica", "todos"],
        "pasos": [
            "Andá a Recetas con un paciente seleccionado.",
            "La solapa 'Prescribir' permite crear una nueva receta médica.",
            "Buscá el medicamento en el vademécum integrado de más de 50 fármacos.",
            "Especificá dosis, frecuencia, duración y vía de administración.",
            "La receta queda firmada digitalmente. Podés imprimirla o enviarla.",
            "La solapa 'MAR' muestra el plan de administración por turno.",
            "La solapa 'Stock' controla existencias con alertas de vencimiento.",
        ],
        "tips": ["El sistema alerta automáticamente sobre interacciones medicamentosas.",
                 "Usá la calculadora de dosis pediátricas para ajustar por peso.",
                 "Las recetas se almacenan con validez legal para presentar donde sea necesario."],
        "quiz": [
            {"p": "¿Qué alerta incorpora el sistema al prescribir?", "r": "Interacciones medicamentosas",
             "o": ["Vencimiento del paciente", "Interacciones medicamentosas", "Stock disponible", "Costo del medicamento"]},
        ],
    },
    "Emergencias": {
        "emoji": "🚨", "categoria": "Emergencias",
        "desc": "Gestión de llamados de emergencia con triage, alertas y respuesta coordinada.",
        "tiempo": "5 min", "roles": ["todos"],
        "pasos": [
            "Andá a Emergencias desde el menú lateral.",
            "Registrá un nuevo evento: seleccioná paciente y nivel de prioridad (baja, media, alta).",
            "El sistema notifica automáticamente a los profesionales disponibles.",
            "Podés hacer seguimiento del tiempo de respuesta y resolución.",
            "Cada emergencia se documenta con fecha, hora y actuación profesional.",
            "El módulo se integra con la app del paciente para alertas en tiempo real.",
        ],
        "tips": ["Emergencias con prioridad alta se muestran en rojo en el dashboard.",
                 "El tiempo de respuesta se mide automáticamente desde la alerta hasta la asignación."],
        "quiz": [
            {"p": "¿Qué nivel de prioridad se puede asignar a una emergencia?", "r": "Baja, media o alta",
             "o": ["Solo alta", "Baja, media o alta", "Crítica o normal", "Urgente o programada"]},
        ],
    },
    "Telemedicina": {
        "emoji": "📹", "categoria": "Operaciones",
        "desc": "Sala de teleconsulta remota con acceso a la historia clínica del paciente.",
        "tiempo": "4 min", "roles": ["clinica"],
        "pasos": [
            "Seleccioná un paciente y andá a Telemedicina.",
            "Iniciá una nueva sesión. El paciente recibe un enlace para unirse.",
            "Durante la consulta tenés acceso a los datos clínicos del paciente.",
            "Podés cargar indicaciones y recetas durante o después de la consulta.",
        ],
        "tips": ["La sala queda grabada si es necesario para auditoría (requiere configuración).",
                 "Compartí tu pantalla para mostrar resultados de estudios durante la llamada."],
    },
    "Admisión": {
        "emoji": "👤", "categoria": "Gestión clínica",
        "desc": "Registro y gestión de pacientes: datos personales, obra social, historia previa.",
        "tiempo": "6 min", "roles": ["todos"],
        "pasos": [
            "Andá a Admisión desde el menú lateral.",
            "Usá el buscador para encontrar pacientes existentes por nombre o DNI.",
            "Creá un nuevo paciente completando los datos obligatorios.",
            "Agregá obra social, número de afiliado y datos de contacto.",
            "Cargá antecedentes, alergias y medicación habitual.",
            "El paciente queda disponible en todos los módulos clínicos.",
        ],
        "tips": ["La búsqueda funciona con coincidencias parciales.",
                 "Los datos de contacto se usan para la app del paciente y recordatorios.",
                 "Podés adjuntar documentos como DNI o certificados."],
    },
    "Estudios": {
        "emoji": "🔬", "categoria": "Gestión clínica",
        "desc": "Carga y consulta de estudios complementarios: laboratorio, imágenes, informes.",
        "tiempo": "5 min", "roles": ["clinica"],
        "pasos": [
            "Seleccioná un paciente y andá a Estudios.",
            "Cargá un nuevo estudio: seleccioná tipo (laboratorio, imagen, etc.), fecha y resultados.",
            "Podés adjuntar archivos PDF o imágenes del estudio original.",
            "Los resultados quedan visibles en el historial del paciente.",
            "Estudios anteriores se pueden consultar y comparar.",
        ],
        "tips": ["Los estudios se ordenan por fecha automáticamente.",
                 "Los valores de laboratorio se pueden cargar como texto libre o datos estructurados."],
    },
    "Escalas Clínicas": {
        "emoji": "📏", "categoria": "Gestión clínica",
        "desc": "Evaluación estandarizada con escalas de dolor, úlceras, riesgo de caídas y más.",
        "tiempo": "6 min", "roles": ["clinica"],
        "pasos": [
            "Seleccioná un paciente y andá a Escalas Clínicas.",
            "Elegí la escala a aplicar: EVA (dolor), Norton (úlceras), Downton (caídas), entre otras.",
            "Completá los parámetros de la escala. El sistema calcula el puntaje automáticamente.",
            "Cada evaluación queda registrada con fecha para seguimiento evolutivo.",
            "Podés ver el histórico de evaluaciones y la evolución del puntaje.",
        ],
        "tips": ["Las escalas son herramientas de screening, no reemplazan el juicio clínico.",
                 "La tendencia del puntaje ayuda a detectar mejora o deterioro."],
    },
    "Balance": {
        "emoji": "💧", "categoria": "Gestión clínica",
        "desc": "Control de ingesta y eliminación de líquidos con cálculo automático de balance hídrico.",
        "tiempo": "4 min", "roles": ["clinica"],
        "pasos": [
            "Seleccioná un paciente y andá a Balance.",
            "Registrá ingresos: vía oral, sonda, intravenosa, etc.",
            "Registrá egresos: diuresis, vómitos, drenajes, etc.",
            "El sistema calcula automáticamente el balance del turno y acumulado del día.",
            "Podés ver el histórico de balances diarios en formato tabla y gráfico.",
        ],
        "tips": ["El balance se expresa en ml. Valores negativos indican balance negativo.",
                 "Especialmente importante en pacientes críticos, post-quirúrgicos y pediátricos."],
    },
    "Percentilo": {
        "emoji": "📈", "categoria": "Gestión clínica",
        "desc": "Seguimiento de crecimiento pediátrico con gráficos de percentilos OMS.",
        "tiempo": "4 min", "roles": ["clinica"],
        "pasos": [
            "Seleccioná un paciente pediátrico y andá a Percentilo.",
            "Cargá peso, talla y perímetro cefálico con fecha de medición.",
            "El sistema ubica automáticamente los valores en las curvas de percentilo OMS.",
            "Podés ver la evolución del paciente a lo largo del tiempo.",
        ],
        "tips": ["Las curvas siguen los estándares de la OMS para cada edad y sexo.",
                 "Percentilos entre 3 y 97 se consideran dentro del rango normal."],
    },
    "RRHH y Fichajes": {
        "emoji": "👥", "categoria": "Administración",
        "desc": "Gestión de profesionales, fichajes, presentismo, guardias y reportes.",
        "tiempo": "6 min", "roles": ["gestion"],
        "pasos": [
            "Andá a RRHH y Fichajes desde el menú.",
            "La solapa 'Equipo' lista todos los profesionales con su rol y estado.",
            "Agregá, editá o desactivá profesionales según rotación del equipo.",
            "La solapa 'Fichajes' registra entradas y salidas del personal.",
            "Los reportes de presentismo se exportan a PDF o Excel.",
            "Las guardias se asignan desde el calendario de turnos.",
        ],
        "tips": ["Cada profesional tiene un rol que determina acceso a módulos.",
                 "Los fichajes se integran con la geolocalización de visitas."],
    },
    "Caja": {
        "emoji": "💰", "categoria": "Administración",
        "desc": "Registro de cobros, comprobantes, libro diario y cierre de caja.",
        "tiempo": "5 min", "roles": ["gestion"],
        "pasos": [
            "Andá a Caja desde el menú lateral.",
            "Registrá un nuevo comprobante: factura, recibo o nota de crédito.",
            "Seleccioná paciente, concepto, monto y forma de pago.",
            "El libro diario se actualiza automáticamente con cada movimiento.",
            "Al final del día ejecutá el cierre de caja para verificar el balance.",
            "Podés reimprimir comprobantes desde el histórico.",
        ],
        "tips": ["La caja se integra con facturación electrónica vía API.",
                 "Los comprobantes anulados quedan registrados en auditoría."],
    },
    "Inventario": {
        "emoji": "📦", "categoria": "Administración",
        "desc": "Control de stock de insumos, materiales y medicamentos con alertas de reposición.",
        "tiempo": "5 min", "roles": ["gestion"],
        "pasos": [
            "Andá a Inventario desde el menú lateral.",
            "Agregá productos con nombre, categoría, cantidad y precio.",
            "Configurá el umbral mínimo para recibir alertas de reposición.",
            "Registrá ingresos y egresos con fecha y responsable.",
            "El sistema marca en rojo los productos por debajo del mínimo.",
            "Podés exportar el listado de stock para inventario físico.",
        ],
        "tips": ["Configurá alertas de reposición para insumos críticos.",
                 "El inventario se integra con el módulo de Recetas para descontar automático."],
    },
    "Auditoría": {
        "emoji": "🔍", "categoria": "Legal",
        "desc": "Trazabilidad legal completa de cada acción realizada en el sistema.",
        "tiempo": "4 min", "roles": ["todos"],
        "pasos": [
            "Andá a Auditoría desde el menú lateral.",
            "Filtrá eventos por fecha, usuario, paciente o tipo de acción.",
            "Cada entrada muestra: quién, qué, cuándo y desde qué dispositivo.",
            "La información es inviolable: no se puede modificar ni eliminar.",
            "Podés exportar reportes de auditoría firmados digitalmente.",
        ],
        "tips": ["Ideal para presentar ante inspecciones o requerimientos legales.",
                 "Auditoría retiene datos incluso después de eliminar pacientes."],
    },
    "Chatbot IA": {
        "emoji": "🤖", "categoria": "Legal",
        "desc": "Asistente clínico inteligente. Consultá en lenguaje natural sobre fármacos, dosis y más.",
        "tiempo": "3 min", "roles": ["todos"],
        "pasos": [
            "Andá a Chatbot IA desde el menú.",
            "Escribí tu consulta en lenguaje natural, ej: 'dosis de ibuprofeno para niño de 20kg'.",
            "El chatbot busca en la farmacopea, datos del paciente y en web.",
            "Siempre verificá la información con fuentes oficiales antes de actuar.",
        ],
        "tips": ["El chatbot NO reemplaza el criterio médico. Siempre verificá las respuestas."],
    },
    "App Paciente": {
        "emoji": "📱", "categoria": "Operaciones",
        "desc": "Aplicación para que pacientes accedan a su información, turnos y comunicación.",
        "tiempo": "4 min", "roles": ["todos"],
        "pasos": [
            "Configurá el acceso del paciente desde el panel de Alertas.",
            "El paciente puede ver su historia clínica, turnos, recetas y enviar mensajes.",
            "Las alertas se envían automáticamente: recordatorios, cambios de turno, resultados.",
        ],
        "tips": ["La app del paciente es una PWA, no requiere instalación.",
                 "El paciente puede reportar su estado de salud diariamente."],
    },
    "APS / Dispensario": {
        "emoji": "🏥", "categoria": "Gestión clínica",
        "desc": "Atención Primaria de Salud con dispensario de medicamentos por paciente.",
        "tiempo": "6 min", "roles": ["clinica"],
        "pasos": [
            "Andá a APS / Dispensario desde el menú con un paciente seleccionado.",
            "Registrá la entrega de medicamentos del vademécum del programa.",
            "Cada entrega se descuenta automáticamente del stock del dispensario.",
            "El historial de entregas queda registrado por paciente.",
        ],
        "tips": ["El dispensario sigue las guías de APS del ministerio de salud.",
                 "Las entregas se registran con firma del profesional y del paciente."],
    },
    "Vacunación": {
        "emoji": "💉", "categoria": "Gestión clínica",
        "desc": "Registro y seguimiento del calendario de vacunación de cada paciente.",
        "tiempo": "5 min", "roles": ["clinica"],
        "pasos": [
            "Seleccioná un paciente y andá a Vacunación.",
            "Registrá cada vacuna aplicada con lote, laboratorio y fecha.",
            "El sistema muestra el calendario de vacunas pendientes según edad.",
            "Podés generar el certificado de vacunación en PDF.",
        ],
        "tips": ["El calendario sigue el esquema nacional de vacunación vigente.",
                 "Las alertas recuerdan vacunas próximas a vencer o atrasadas."],
    },
    "Documentos Legales": {
        "emoji": "📄", "categoria": "Legal",
        "desc": "Gestión de consentimientos informados, poderes y documentación legal.",
        "tiempo": "5 min", "roles": ["gestion"],
        "pasos": [
            "Andá a Documentos Legales desde el menú.",
            "Seleccioná el tipo de documento: consentimiento, poder, instructivo.",
            "Completá los datos requeridos. El sistema genera el PDF profesional.",
            "El documento queda firmado digitalmente y almacenado con respaldo legal.",
            "Podés reimprimir o reenviar en cualquier momento.",
        ],
        "tips": ["Los documentos tienen validez legal con firma digital.",
                 "Cada documento queda vinculado al paciente en la auditoría."],
    },
    "Red de Profesionales": {
        "emoji": "🤝", "categoria": "Emergencias",
        "desc": "Directorio de profesionales con disponibilidad, especialidad y zona de cobertura.",
        "tiempo": "4 min", "roles": ["todos"],
        "pasos": [
            "Andá a Red de Profesionales desde el menú lateral.",
            "Buscá profesionales por nombre, especialidad o zona.",
            "Cada perfil muestra disponibilidad, contactos y módulos a su cargo.",
            "Podés contactar directamente por WhatsApp o email.",
        ],
        "tips": ["Mantené actualizado tu perfil para aparecer en búsquedas.",
                 "La red permite coordinar coberturas entre profesionales."],
    },
}

CATEGORIAS_CAPACITACION: dict[str, list[str]] = {
    "🚀 Primeros pasos": ["Dashboard"],
    "🩺 Gestión clínica": ["Historia Clínica", "Recetas", "Admisión", "Estudios",
                          "Escalas Clínicas", "Balance", "Percentilo", "APS / Dispensario", "Vacunación"],
    "📋 Operaciones": ["Visitas y Agenda", "Telemedicina", "App Paciente"],
    "🚨 Emergencias": ["Emergencias", "Red de Profesionales"],
    "💰 Administración": ["Caja", "RRHH y Fichajes", "Inventario"],
    "🔒 Legal": ["Auditoría", "Documentos Legales", "Chatbot IA"],
}

ROLES_A_CATEGORIA: dict[str, list[str]] = {
    "médico": ["🚀 Primeros pasos", "🩺 Gestión clínica", "📋 Operaciones", "🚨 Emergencias", "🔒 Legal"],
    "enfermería": ["🚀 Primeros pasos", "🩺 Gestión clínica", "📋 Operaciones", "🚨 Emergencias"],
    "coordinador": ["🚀 Primeros pasos", "💰 Administración", "📋 Operaciones", "🚨 Emergencias", "🔒 Legal"],
    "operativo": ["🚀 Primeros pasos", "📋 Operaciones", "💰 Administración", "🚨 Emergencias"],
    "auditoría": ["🚀 Primeros pasos", "🔒 Legal", "💰 Administración"],
}


def _modulos_recomendados_para_rol(rol: str) -> list[str]:
    """Devuelve los módulos recomendados según el rol del usuario."""
    rol_key = rol.strip().lower()
    cats = ROLES_A_CATEGORIA.get(rol_key, list(CATEGORIAS_CAPACITACION.keys()))
    recomendados = []
    for cat in cats:
        for mod in CATEGORIAS_CAPACITACION.get(cat, []):
            datos = CAPACITACION.get(mod, {})
            roles_mod = datos.get("roles", [])
            if "todos" in roles_mod or rol_key in roles_mod:
                recomendados.append(mod)
    return recomendados


# ─── Helpers ────────────────────────────────────────────────────────────

def _render_busqueda(filtro: str, modulos: dict) -> list[str]:
    if not filtro:
        return list(modulos.keys())
    f = filtro.lower()
    return [n for n, d in modulos.items()
            if f in n.lower() or f in d.get("emoji", "") or f in d.get("desc", "").lower()]


def _render_modulo(nombre: str, datos: dict) -> None:
    completados = set(st.session_state.get("capacitacion_completados", []))
    st.markdown(f"### {datos['emoji']} {nombre}")
    st.caption(f"⏱️ {datos['tiempo']} · {'✅ Completado' if nombre in completados else '📖 Pendiente'}")

    st.markdown("**Descripción:** " + datos["desc"])

    st.markdown("#### 📖 Guía paso a paso")
    for i, paso in enumerate(datos["pasos"], 1):
        st.markdown(f"**{i}.** {paso}")

    if datos.get("tips"):
        st.markdown("#### 💡 Tips")
        for tip in datos["tips"]:
            st.info(tip)

    # Quiz
    preguntas = datos.get("quiz", [])
    if preguntas:
        st.markdown("#### 🧠 Verificá lo aprendido")
        for j, q in enumerate(preguntas):
            key = f"quiz_{nombre}_{j}"
            resp = st.radio(q["p"], q["o"], key=key, index=None)
            if resp:
                if resp == q["r"]:
                    st.success("✅ Correcto!")
                else:
                    st.error(f"❌ Incorrecto. La respuesta correcta es: {q['r']}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button(f"✅ Marcar como leído", key=f"completar_{nombre}",
                     use_container_width=True, type="primary"):
            comp = set(st.session_state.get("capacitacion_completados", []))
            comp.add(nombre)
            st.session_state.capacitacion_completados = list(comp)
            prog = _cargar_progreso()
            prog[nombre] = {"completado": True}
            _guardar_progreso(prog)
            log_event("capacitacion", f"Modulo completado: {nombre}")
            st.rerun()
    with col2:
        if st.button("← Volver", key=f"volver_{nombre}", use_container_width=True):
            st.session_state.capacitacion_modulo_actual = None
            st.rerun()


# ─── Certificado PDF ────────────────────────────────────────────────────

def _generar_certificado_html(nombre_usuario: str, completados: int, total: int) -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
* {{margin:0;padding:0;box-sizing:border-box}}
body {{font-family:Georgia,serif;background:#fff;padding:40px;color:#1e293b}}
.cert {{max-width:700px;margin:auto;border:4px double #14b8a6;padding:50px;text-align:center}}
h1 {{font-size:32px;color:#0f172a;margin-bottom:8px}}
.sub {{color:#14b8a6;font-size:18px;margin-bottom:30px}}
.med {{font-size:48px;margin:20px 0}}
.info {{font-size:14px;color:#64748b;margin-top:30px;line-height:1.6}}
.footer {{margin-top:40px;font-size:12px;color:#94a3b8}}
</style></head><body><div class="cert">
<div class="med">🎓</div>
<h1>Certificado de Capacitación</h1>
<p class="sub">MediCare Enterprise PRO</p>
<p style="font-size:16px;margin:20px 0">
Otorgado a<br><strong style="font-size:22px">{nombre_usuario}</strong>
</p>
<p style="font-size:14px;color:#334155">
Por haber completado <strong>{completados} de {total}</strong> módulos
de capacitación de la plataforma.
</p>
<p class="info">Fecha: {date.today().strftime('%d/%m/%Y')}</p>
<div class="footer">MediCare Enterprise PRO · Plataforma integral de gestión sanitaria</div>
</div></body></html>"""


def render_capacitacion(paciente_sel: Any, mi_empresa: Any, user: Any, rol: str) -> None:
    st.title("🎓 Capacitación Interactiva")

    # Estado
    completados = set(st.session_state.get("capacitacion_completados", []))
    progreso_persistente = _cargar_progreso()
    for k, v in progreso_persistente.items():
        if v.get("completado") and k not in completados:
            completados.add(k)
    st.session_state.capacitacion_completados = list(completados)

    nombre_user = (user or {}).get("nombre", "Usuario") if isinstance(user, dict) else str(user or "Usuario")

    tab_intro, tab_guias, tab_progreso, tab_certificado = st.tabs([
        "📖 Inicio", "📚 Guías", "📊 Progreso", "🎓 Certificado"
    ])

    with tab_intro:
        st.markdown(f"""
### Bienvenido a la capacitación de MediCare PRO

Completá los módulos a tu ritmo. Cada guía incluye pasos detallados, tips
y una pregunta para verificar lo aprendido.

**🎯 Recomendado para vos ({rol}):"""
        )
        recomendados = _modulos_recomendados_para_rol(rol)
        cols = st.columns(3)
        for i, nombre in enumerate(recomendados[:9]):
            d = CAPACITACION.get(nombre)
            if not d:
                continue
            with cols[i % 3]:
                if st.button(f"{d['emoji']} {nombre}", key=f"rec_{nombre}",
                             use_container_width=True):
                    st.session_state.capacitacion_modulo_actual = nombre
                    st.rerun()

        st.markdown("### 🔍 Todos los módulos")
        cols = st.columns(3)
        todos = list(CAPACITACION.keys())
        for i, nombre in enumerate(todos[:15]):
            d = CAPACITACION.get(nombre)
            if not d:
                continue
            with cols[i % 3]:
                leido = "✅ " if nombre in completados else ""
                if st.button(f"{leido}{d['emoji']} {nombre}", key=f"all_{nombre}",
                             use_container_width=True):
                    st.session_state.capacitacion_modulo_actual = nombre
                    st.rerun()

    with tab_guias:
        busqueda = st.text_input("🔎 Buscar módulo...", placeholder="Ej: recetas, emergencias...",
                                 key="capacitacion_busqueda")
        filtrados = _render_busqueda(busqueda, CAPACITACION)

        modulo_actual = st.session_state.get("capacitacion_modulo_actual")
        if modulo_actual and modulo_actual in filtrados:
            datos = CAPACITACION.get(modulo_actual)
            if datos:
                _render_modulo(modulo_actual, datos)
                return

        if not filtrados:
            st.warning("No se encontraron módulos.")
            return

        for cat, mods in CATEGORIAS_CAPACITACION.items():
            visibles = [m for m in mods if m in filtrados]
            if not visibles:
                continue
            st.markdown(f"#### {cat}")
            cols = st.columns(2)
            for i, nombre in enumerate(visibles):
                d = CAPACITACION.get(nombre)
                if not d:
                    continue
                leido = "✅ " if nombre in completados else ""
                with cols[i % 2]:
                    st.button(
                        f"{leido}{d['emoji']} **{nombre}**\n{d['desc'][:70]}...\n⏱️ {d['tiempo']}",
                        key=f"cat_{nombre}", use_container_width=True,
                        on_click=lambda n=nombre: st.session_state.update(
                            {"capacitacion_modulo_actual": n}))

    with tab_progreso:
        total = len(CAPACITACION)
        leidos = len(completados)
        pct = round(leidos / total * 100) if total else 0

        st.markdown("### 📊 Progreso general")
        st.progress(pct / 100, text=f"{pct}% completado ({leidos}/{total})")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", total)
        c2.metric("Completados", leidos)
        c3.metric("Pendientes", total - leidos)
        c4.metric("Avance", f"{pct}%")

        if leidos == total:
            st.balloons()
            st.success("¡Felicitaciones! Completaste todos los módulos de capacitación.")

        st.markdown("#### ✅ Completados")
        for nombre in sorted(completados):
            d = CAPACITACION.get(nombre, {})
            st.success(f"{d.get('emoji', '📘')} {nombre}")

        st.markdown("#### 📌 Pendientes")
        cols = st.columns(3)
        i = 0
        for nombre, d in CAPACITACION.items():
            if nombre in completados:
                continue
            with cols[i % 3]:
                if st.button(f"{d.get('emoji', '📘')} {nombre}",
                             key=f"pend_{nombre}", use_container_width=True):
                    st.session_state.capacitacion_modulo_actual = nombre
                    st.rerun()
            i += 1

        if completados:
            st.markdown("---")
            if st.button("🔄 Reiniciar progreso", use_container_width=True, type="secondary"):
                st.session_state.capacitacion_completados = []
                _guardar_progreso({})
                st.rerun()

    with tab_certificado:
        st.markdown("### 🎓 Certificado de capacitación")

        if leidos == total:
            st.success("¡Completaste todos los módulos! Descargá tu certificado.")
            html = _generar_certificado_html(nombre_user, leidos, total)
            st.download_button("📄 Descargar certificado PDF", html,
                               file_name="certificado_medicare.html",
                               mime="text/html", use_container_width=True, type="primary")
            st.markdown("> Abrí el archivo HTML en el navegador y usá _Imprimir → Guardar como PDF_")
            with st.expander("👀 Vista previa del certificado"):
                st.components.v1.html(html, height=500, scrolling=True)
        else:
            pendientes = total - leidos
            st.warning(f"Te faltan **{pendientes} módulo(s)** para obtener el certificado.")
            st.progress(pct / 100, text=f"{pct}% completado")
            st.markdown("Seguí completando guías en la sección **📚 Guías** para desbloquear tu certificado.")
