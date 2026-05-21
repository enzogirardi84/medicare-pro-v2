"""Context-aware AI help and suggestions for every view."""

from __future__ import annotations

from typing import Dict, List, Optional

_VIEW_HELP: Dict[str, str] = {
    "Visitas y Agenda": (
        "Gestioná visitas y agenda del día. Podés registrar nuevas visitas, "
        "ver el calendario, y hacer seguimiento de pacientes programados. "
        "Usá el botón + para agregar una visita rápida."
    ),
    "Dashboard": (
        "Panel de control con métricas clave: cantidad de pacientes, visitas del día, "
        "ingresos, alertas activas. Personalizá los widgets según tu rol."
    ),
    "Clinicas (panel global)": (
        "Panel global de todas las clínicas. Supervisión centralizada para coordinadores y administradores."
    ),
    "Admision": (
        "Registrá nuevos pacientes, buscá por DNI o nombre, y gestioná la documentación "
        "de ingreso. Datos demográficos, obra social y contacto."
    ),
    "Clinica": (
        "Registro de signos vitales y evaluación clínica rápida. "
        "Cargá TA, FC, FR, temperatura, saturación y HGT en un solo lugar."
    ),
    "Percentilo": (
        "Cálculo de percentilos pediátricos (peso, talla, IMC) según OMS. "
        "Ingresá edad, peso y talla para obtener percentilo y puntaje Z."
    ),
    "Asistente Clinico": (
        "Asistente para la consulta clínica diaria. Incluye guías rápidas, "
        "alertas de seguridad y recordatorios de prácticas recomendadas."
    ),
    "Evolucion": (
        "Redactá evoluciones clínicas en formato SOAP. "
        "Usá el botón 🤖 Sugerir evolución con IA para generar un borrador automático "
        "basado en los signos vitales y la última evolución."
    ),
    "Estudios": (
        "Cargá y consultá estudios complementarios: laboratorio, radiografías, ecografías, "
        "ECG, tomografías y resonancias. Cada estudio puede incluir imagen adjunta. "
        "Usá 🤖 Interpretar con IA para analizar resultados."
    ),
    "Materiales": (
        "Gestión de materiales e insumos descartables. Control de stock mínimo, "
        "registro de consumo y reposición automática."
    ),
    "Recetas": (
        "Prescripción y administración de medicamentos. Incluye vademécum, "
        "control de stock, MAR (registro de administración) y recetas electrónicas. "
        "Usá 🤖 Asistente IA para generar recetas y verificar interacciones."
    ),
    "Balance": (
        "Balance hídrico del paciente: ingresos y egresos de líquidos, "
        "balance neto diario y alertas de desequilibrio."
    ),
    "Inventario": (
        "Control de stock de medicamentos e insumos. Alertas de stock crítico, "
        "vencimientos próximos y trazabilidad de lotes."
    ),
    "Caja": (
        "Registro de cobros, gastos y arqueo de caja. "
        "Conciliación diaria y reportes de movimiento."
    ),
    "Emergencias y Ambulancia": (
        "Gestión de emergencias y servicio de ambulancia. "
        "Registro de llamados, despacho y seguimiento de incidentes."
    ),
    "Alertas app paciente": (
        "Alertas y notificaciones para pacientes a través de la app. "
        "Recordatorios de medicación, turnos y cuidados."
    ),
    "Red de Profesionales": (
        "Directorio de profesionales de la salud. Contacto, especialidad, "
        "disponibilidad y convenios con la clínica."
    ),
    "Escalas Clinicas": (
        "Escalas de evaluación clínica: Glasgow, APACHE, SOFA, NEWS, "
        "escala de dolor, riesgo de úlceras y caídas."
    ),
    "Historial": (
        "Historia clínica completa del paciente: evoluciones, estudios, "
        "recetas, vacunas, alergias y documentos en orden cronológico."
    ),
    "PDF": (
        "Generación y descarga de documentos PDF: historia clínica, "
        "recetas, informes, consentimientos y certificados."
    ),
    "Telemedicina": (
        "Consultas por videollamada con pacientes. "
        "Programación de teleconsultas y registro en historia clínica."
    ),
    "Cierre Diario": (
        "Cierre contable del día: resumen de ingresos, egresos, "
        "cantidad de pacientes atendidos y métricas del día."
    ),
    "Mi Equipo": (
        "Gestión del equipo de trabajo: profesionales, roles, "
        "horarios y coberturas. Altas, bajas y suspensiones."
    ),
    "Asistencia en Vivo": (
        "Asistencia en tiempo real para profesionales en domicilio. "
        "Soporte remoto, guías y comunicación con la base."
    ),
    "RRHH y Fichajes": (
        "Recursos humanos: fichajes, ausentismo, licencias, "
        "y gestión del personal de la clínica."
    ),
    "Proyecto y Roadmap": (
        "Planificación de proyectos y roadmap del equipo. "
        "Tareas, hitos y seguimiento de objetivos."
    ),
    "Auditoria": (
        "Auditoría del sistema: registros de acceso, cambios en datos sensibles, "
        "y trazabilidad de operaciones críticas."
    ),
    "Auditoria Legal": (
        "Auditoría con validez legal: registros inmutables, "
        "firma digital y compliance normativo."
    ),
    "Documentos Legales": (
        "Marco legal: consentimientos informados, reglamentos internos, "
        "contratos y documentación normativa."
    ),
    "Diagnosticos": (
        "Diagnóstico técnico del sistema. Verificación de Supabase, "
        "tablas SQL, datos locales y estado general."
    ),
    "APS / Dispensario": (
        "Atención primaria con enfoque dispensarial. "
        "Seguimiento de pacientes crónicos y programas preventivos."
    ),
    "Vacunacion": (
        "Registro y seguimiento del calendario de vacunación. "
        "Alertas de dosis pendientes y esquemas incompletos."
    ),
    "Estadisticas": (
        "Estadísticas generales: pacientes atendidos, diagnósticos más frecuentes, "
        "medicación más prescripta, y tendencias temporales."
    ),
    "Turnos Online": (
        "Gestión de turnos online. Los pacientes solicitan turnos desde la app/web, "
        "acá los administrás: confirmás, reprogramás o cancelás."
    ),
    "Chatbot IA": (
        "Chatbot inteligente que responde preguntas sobre el paciente actual. "
        "Usa IA para buscar en la historia clínica y dar respuestas precisas."
    ),
    "Calc. Dosis Pediatricas": (
        "Calculadora de dosis pediátricas con validación cruzada. "
        "Evitá errores de dosificación con alertas de seguridad integradas."
    ),
    "Reportes Financieros": (
        "Reportes financieros: facturación, cobros, mora, "
        "y proyecciones económicas de la clínica."
    ),
    "Admin Feature Flags": (
        "Panel de configuración de features. Activá o desactivá "
        "funcionalidades experimentales y módulos del sistema."
    ),
    "Self-Healing IA": (
        "Sistema autónomo de diagnóstico y reparación. "
        "Escaneá el código en busca de errores y aplicá correcciones automáticas."
    ),
    "Asistente IA": (
        "Panel central de funciones de IA. Resumen clínico, "
        "codificación CIE-10, búsqueda inteligente y análisis de población."
    ),
}


def get_view_help(view_name: str) -> str:
    return _VIEW_HELP.get(view_name, "Consultá al asistente IA para ayuda contextual.")


def get_view_tips(view_name: str) -> List[str]:
    """Sugerencias proactivas para cada vista."""
    _tips: Dict[str, List[str]] = {
        "Visitas y Agenda": [
            "Programá visitas recurrentes con un solo clic.",
            "Usá el filtro por estado para ver solo pendientes.",
        ],
        "Clinica": [
            "Registrá los signos vitales al inicio de cada consulta.",
        ],
        "Evolucion": [
            "Probá el botón 🤖 Sugerir evolución con IA para ahorrar tiempo.",
        ],
        "Recetas": [
            "Usá 🤖 Asistente IA para verificar interacciones medicamentosas.",
            "El control de stock evita recetar medicamentos sin inventario.",
        ],
        "Estudios": [
            "Adjuntá imágenes a los estudios para mejor trazabilidad.",
            "Usá 🤖 Interpretar con IA para entender resultados complejos.",
        ],
    }
    return _tips.get(view_name, [])


def get_quick_actions(view_name: str) -> List[Dict]:
    """Acciones rápidas contextuales."""
    _actions: Dict[str, List[Dict]] = {
        "Visitas y Agenda": [
            {"label": "📅 Nueva visita", "action": "nueva_visita"},
            {"label": "📋 Ver agenda hoy", "action": "agenda_hoy"},
        ],
        "Evolucion": [
            {"label": "🤖 Sugerir evolución", "action": "sugerir_evolucion"},
        ],
        "Recetas": [
            {"label": "✍️ Nueva receta", "action": "nueva_receta"},
            {"label": "🔍 Verificar interacciones", "action": "interacciones"},
        ],
        "Clinica": [
            {"label": "📊 Registrar vitales", "action": "registrar_vitales"},
        ],
    }
    return _actions.get(view_name, [])
